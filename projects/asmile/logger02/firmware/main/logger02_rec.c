/* Registrazione: OV9281 1280×720 (sensore a 50 fps) → ISP YUV420 → H.264 hardware → SD, a pezzi da 60 s.
 * Si codifica 1 fotogramma ogni REC_DIV (50/3 ≈ 16,7 fps, come il logger001 a 15).
 * Per ogni pezzo: clip_<sessione>_<A|B>_<NNNNN>.h264 + clip_..._frames.csv
 *   frame,t_us,t_a_us,bytes     (t_us = orologio della scheda, t_a_us = orologio della A: confrontabile fra A e B)
 * Lo streaming prende lo stesso fotogramma e lo comprime in JPEG solo se qualcuno guarda. */
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "linux/videodev2.h"
#include "esp_video_device.h"
#include "driver/jpeg_encode.h"
#include "logger02.h"

static const char *TAG = "rec";

#define W           1280
#define H           720
#define NBUF        4
#define REC_DIV     3
#define SEG_S       60
#define H264_BITRATE 2000000
#define N_ULTIMI    32

static int s_cap = -1, s_enc = -1;
static uint8_t *s_buf[NBUF];
static uint8_t *s_enc_out;
static volatile bool s_rec, s_stop;
static volatile uint32_t s_frame, s_scritti, s_seg;
static FILE *s_vid, *s_csv;
static char s_sess[24], s_file[64];
static int64_t s_seg_t0;
static uint64_t s_bytes;

static SemaphoreHandle_t s_jmux;
static jpeg_encoder_handle_t s_jpeg;
static uint8_t *s_jpg;
static size_t s_jpg_len, s_jpg_cap;
static volatile int64_t s_jpg_chiesto;    /* ultimo istante in cui qualcuno ha chiesto un JPEG */

static int64_t s_ultimi[N_ULTIMI];
static uint32_t s_ultimi_f[N_ULTIMI];
static int s_ui;

static esp_err_t ctrl(int fd, uint32_t id, int32_t v)
{
    struct v4l2_ext_control c = {.id = id, .value = v};
    struct v4l2_ext_controls cs = {.ctrl_class = V4L2_CID_CODEC_CLASS, .count = 1, .controls = &c};
    return ioctl(fd, VIDIOC_S_EXT_CTRLS, &cs) == 0 ? ESP_OK : ESP_FAIL;
}

static void apri_segmento(void)
{
    char base[96];
    snprintf(base, sizeof(base), L02_REC_DIR "/clip_%s_%c_%05lu", s_sess, logger02_ruolo()->is_a ? 'A' : 'B',
             (unsigned long)s_seg);
    char p[112];
    snprintf(p, sizeof(p), "%s.h264", base);
    s_vid = fopen(p, "wb");
    snprintf(s_file, sizeof(s_file), "%s", strrchr(p, '/') + 1);
    snprintf(p, sizeof(p), "%s_frames.csv", base);
    s_csv = fopen(p, "w");
    if (s_vid) setvbuf(s_vid, NULL, _IOFBF, 64 * 1024);
    if (s_csv) {
        setvbuf(s_csv, NULL, _IOFBF, 16 * 1024);
        fprintf(s_csv, "frame,t_us,t_a_us,bytes\n");
    }
    s_seg_t0 = esp_timer_get_time();
    ESP_LOGI(TAG, "nuovo pezzo %s", s_file);
}

static void chiudi_segmento(void)
{
    if (s_vid) { fclose(s_vid); s_vid = NULL; }
    if (s_csv) { fclose(s_csv); s_csv = NULL; }
    s_seg++;
}

static void jpeg_dal_frame(const uint8_t *yuv, uint32_t len)
{
    if (!s_jpeg || esp_timer_get_time() - s_jpg_chiesto > 2000000) {
        return;                                     /* nessuno guarda lo streaming */
    }
    static int64_t ultimo;
    if (esp_timer_get_time() - ultimo < 150000) {
        return;                                     /* ~6 fps per lo streaming bastano */
    }
    ultimo = esp_timer_get_time();
    jpeg_encode_cfg_t cfg = {.height = H, .width = W, .src_type = JPEG_ENCODE_IN_FORMAT_YUV420,
                             .sub_sample = JPEG_DOWN_SAMPLING_YUV420, .image_quality = 70};
    uint32_t out = 0;
    xSemaphoreTake(s_jmux, portMAX_DELAY);
    if (jpeg_encoder_process(s_jpeg, &cfg, yuv, len, s_jpg, s_jpg_cap, &out) == ESP_OK) {
        s_jpg_len = out;
    }
    xSemaphoreGive(s_jmux);
}

static void rec_task(void *arg)
{
    struct v4l2_buffer b, eo, ec;
    while (!s_stop) {
        memset(&b, 0, sizeof(b));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        b.memory = V4L2_MEMORY_MMAP;
        if (ioctl(s_cap, VIDIOC_DQBUF, &b) != 0) {
            vTaskDelay(1);
            continue;
        }
        int64_t t = (b.timestamp.tv_sec || b.timestamp.tv_usec)
                        ? (int64_t)b.timestamp.tv_sec * 1000000 + b.timestamp.tv_usec : esp_timer_get_time();
        uint32_t f = ++s_frame;
        s_ultimi[s_ui] = logger02_t_a(t);
        s_ultimi_f[s_ui] = f;
        s_ui = (s_ui + 1) % N_ULTIMI;

        if (s_rec && f % REC_DIV == 0) {
            memset(&eo, 0, sizeof(eo));
            eo.type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
            eo.memory = V4L2_MEMORY_USERPTR;
            eo.m.userptr = (unsigned long)s_buf[b.index];
            eo.length = b.bytesused;
            memset(&ec, 0, sizeof(ec));
            ec.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            ec.memory = V4L2_MEMORY_MMAP;
            if (ioctl(s_enc, VIDIOC_QBUF, &eo) == 0 && ioctl(s_enc, VIDIOC_DQBUF, &ec) == 0) {
                if (!s_vid || esp_timer_get_time() - s_seg_t0 > SEG_S * 1000000LL) {
                    if (s_vid) chiudi_segmento();
                    apri_segmento();
                }
                if (s_vid) fwrite(s_enc_out, 1, ec.bytesused, s_vid);
                if (s_csv) fprintf(s_csv, "%lu,%lld,%lld,%lu\n", (unsigned long)f, (long long)t,
                                   (long long)logger02_t_a(t), (unsigned long)ec.bytesused);
                s_bytes += ec.bytesused;
                s_scritti++;
                ioctl(s_enc, VIDIOC_QBUF, &ec);
                ioctl(s_enc, VIDIOC_DQBUF, &eo);
            }
        }
        jpeg_dal_frame(s_buf[b.index], b.bytesused);
        ioctl(s_cap, VIDIOC_QBUF, &b);
    }
    chiudi_segmento();
    s_rec = false;
    ESP_LOGI(TAG, "registrazione chiusa");
    vTaskDelete(NULL);
}

esp_err_t logger02_rec_start(void)
{
    struct v4l2_format fmt = {0};
    struct v4l2_requestbuffers req = {0};
    struct v4l2_buffer b;

    s_cap = open(ESP_VIDEO_MIPI_CSI_DEVICE_NAME, O_RDONLY);
    s_enc = open(ESP_VIDEO_H264_DEVICE_NAME, O_RDONLY);
    if (s_cap < 0 || s_enc < 0) {
        ESP_LOGE(TAG, "camera o encoder non disponibili");
        return ESP_FAIL;
    }
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = W;
    fmt.fmt.pix.height = H;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420;
    ESP_ERROR_CHECK(ioctl(s_cap, VIDIOC_S_FMT, &fmt));
    req.count = NBUF;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    ESP_ERROR_CHECK(ioctl(s_cap, VIDIOC_REQBUFS, &req));
    for (int i = 0; i < NBUF; i++) {
        memset(&b, 0, sizeof(b));
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        ESP_ERROR_CHECK(ioctl(s_cap, VIDIOC_QUERYBUF, &b));
        s_buf[i] = mmap(NULL, b.length, PROT_READ | PROT_WRITE, MAP_SHARED, s_cap, b.m.offset);
        ESP_ERROR_CHECK(ioctl(s_cap, VIDIOC_QBUF, &b));
    }

    ctrl(s_enc, V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, 17);     /* un I-frame al secondo circa */
    ctrl(s_enc, V4L2_CID_MPEG_VIDEO_BITRATE, H264_BITRATE);
    ctrl(s_enc, V4L2_CID_MPEG_VIDEO_H264_MIN_QP, 22);
    ctrl(s_enc, V4L2_CID_MPEG_VIDEO_H264_MAX_QP, 38);
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
    fmt.fmt.pix.width = W;
    fmt.fmt.pix.height = H;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_S_FMT, &fmt));
    memset(&req, 0, sizeof(req));
    req.count = 1;
    req.type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
    req.memory = V4L2_MEMORY_USERPTR;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_REQBUFS, &req));
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = W;
    fmt.fmt.pix.height = H;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_H264;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_S_FMT, &fmt));
    memset(&req, 0, sizeof(req));
    req.count = 1;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_REQBUFS, &req));
    memset(&b, 0, sizeof(b));
    b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    b.memory = V4L2_MEMORY_MMAP;
    b.index = 0;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_QUERYBUF, &b));
    s_enc_out = mmap(NULL, b.length, PROT_READ | PROT_WRITE, MAP_SHARED, s_enc, b.m.offset);
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_QBUF, &b));
    int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_STREAMON, &type));
    type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
    ESP_ERROR_CHECK(ioctl(s_enc, VIDIOC_STREAMON, &type));
    type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    ESP_ERROR_CHECK(ioctl(s_cap, VIDIOC_STREAMON, &type));

    /* JPEG per lo streaming */
    s_jmux = xSemaphoreCreateMutex();
    jpeg_encode_engine_cfg_t ec = {.timeout_ms = 200};
    if (jpeg_new_encoder_engine(&ec, &s_jpeg) == ESP_OK) {
        jpeg_encode_memory_alloc_cfg_t mc = {.buffer_direction = JPEG_ENC_ALLOC_OUTPUT_BUFFER};
        s_jpg = jpeg_alloc_encoder_mem(W * H / 2, &mc, &s_jpg_cap);
    }

    logger02_nome_sessione(s_sess, sizeof(s_sess));
    s_rec = true;
    xTaskCreatePinnedToCore(rec_task, "rec", 6144, NULL, 8, NULL, 1);
    ESP_LOGI(TAG, "registro sessione %s (1280x720, 1 fotogramma su %d, H.264 %d kbps)", s_sess, REC_DIV,
             H264_BITRATE / 1000);
    return ESP_OK;
}

void logger02_rec_stop(void)
{
    if (!s_rec) return;
    s_stop = true;
    for (int i = 0; i < 40 && s_rec; i++) vTaskDelay(pdMS_TO_TICKS(50));
}

uint32_t logger02_rec_frame(void)
{
    return s_frame;
}

size_t logger02_rec_jpeg(uint8_t *out, size_t max)
{
    s_jpg_chiesto = esp_timer_get_time();
    if (!s_jmux) return 0;
    size_t n = 0;
    xSemaphoreTake(s_jmux, portMAX_DELAY);
    if (s_jpg_len && s_jpg_len <= max) {
        memcpy(out, s_jpg, s_jpg_len);
        n = s_jpg_len;
        s_jpg_len = 0;                              /* lo stesso fotogramma non si manda due volte */
    }
    xSemaphoreGive(s_jmux);
    return n;
}

void logger02_rec_stato(char *json, size_t n)
{
    snprintf(json, n, "{\"registra\":%s,\"sessione\":\"%s\",\"file\":\"%s\",\"fotogrammi\":%lu,\"scritti\":%lu,"
             "\"pezzi\":%lu,\"mb\":%.1f,\"sd_libero_mb\":%llu}",
             s_rec ? "true" : "false", s_sess, s_file, (unsigned long)s_frame, (unsigned long)s_scritti,
             (unsigned long)s_seg, s_bytes / 1e6, logger02_sd_libero_mb());
}

void logger02_rec_ultimi(char *json, size_t n)
{
    size_t k = snprintf(json, n, "{\"f\":[");
    for (int i = 0; i < N_ULTIMI && k < n - 40; i++) {
        int j = (s_ui + i) % N_ULTIMI;
        k += snprintf(json + k, n - k, "%s[%lu,%lld]", i ? "," : "", (unsigned long)s_ultimi_f[j], (long long)s_ultimi[j]);
    }
    snprintf(json + k, n - k, "]}");
}
