/* Registrazione: OV9281 1280×800 (risoluzione piena, come #001; sensore a 50 fps) → ISP YUV420 → H.264 hardware → SD, a pezzi da 60 s.
 * Si codifica 1 fotogramma ogni REC_DIV (50/3 ≈ 16,7 fps, come il logger001 a 15).
 * Per ogni pezzo: clip_<sessione>_<A|B>_<NNNNN>.h264 + clip_..._frames.csv
 *   frame,t_us,t_a_us,bytes     (t_us = orologio della scheda, t_a_us = orologio della A: confrontabile fra A e B)
 * Lo streaming prende lo stesso fotogramma e lo comprime in JPEG solo se qualcuno guarda. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
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
#include "esp_video_ioctl.h"
#include "ov9281_1280x800.h"
#include "driver/jpeg_encode.h"
#include "driver/i2c_master.h"
#include "logger02.h"

static const char *TAG = "rec";

#define W           1280
#if CONFIG_L02_REC_1280X800
#define H           800          /* 23/11: risoluzione piena OV9281, stessi pixel di #001 (multiplo di 16: H.264 senza ritagli) */
#else
#define H           720
#endif
#define NBUF        4
#if CONFIG_L02_REC_1280X800
#define REC_DIV     1           /* 1280×800: il sensore va già a 16,67 fps (VTS ×3), si registra ogni fotogramma */
#else
#define REC_DIV     3
#endif
#define SEG_S       60
#define H264_BITRATE 2000000     /* 23/11: provati 6 Mbps → la A perdeva il wifi e andava in crash durante gli scarichi (file da 25 MB, proxy della B): tornati a 2 */
#define N_ULTIMI    32

static int s_cap = -1, s_enc = -1;
static uint8_t s_hdr[128];                 /* SPS+PPS H.264: in testa a ogni pezzo, così ogni file si apre da solo */
static size_t s_hdr_len;

/* tipi di NAL presenti nel fotogramma codificato: bit 1<<tipo (5 = IDR, 7 = SPS, 8 = PPS) */
static uint32_t nal_tipi(const uint8_t *b, size_t n)
{
    uint32_t m = 0;
    for (size_t i = 0; i + 4 < n; i++) {
        if (b[i] == 0 && b[i + 1] == 0 && b[i + 2] == 1) {
            m |= 1u << (b[i + 3] & 0x1f);
            i += 3;
        }
    }
    return m;
}

static void salva_header(const uint8_t *b, size_t n)
{
    size_t start = SIZE_MAX, end = n;
    for (size_t i = 0; i + 4 < n; i++) {
        if (b[i] == 0 && b[i + 1] == 0 && b[i + 2] == 1) {
            int t = b[i + 3] & 0x1f;
            size_t p = (i > 0 && b[i - 1] == 0) ? i - 1 : i;
            if ((t == 7 || t == 8) && start == SIZE_MAX) start = p;
            if (t != 7 && t != 8 && start != SIZE_MAX) { end = p; break; }
            i += 3;
        }
    }
    if (start != SIZE_MAX && end - start <= sizeof(s_hdr)) {
        memcpy(s_hdr, b + start, end - start);
        s_hdr_len = end - start;
    }
}
static uint8_t *s_buf[NBUF];
static uint8_t *s_enc_out;
static volatile bool s_rec, s_stop;
static volatile bool s_pausa, s_attendi_idr;   /* 23/11: bici ferma col wifi → niente pezzi nuovi, si scaricano quelli fatti */
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

/* istanti di fine fotogramma presi nell'ISR della CSI (patch in components/esp_video) */
extern volatile int64_t l02_frame_t[32];
extern volatile uint32_t l02_frame_n;
static uint32_t s_deq;
static volatile int64_t s_ultimo_t;           /* ultimo fotogramma, orologio locale */
static double s_periodo_us = 20000;           /* periodo misurato */
static volatile int64_t s_t_rif = -1;         /* B: ultimo fotogramma noto della A (tempo A) ... */
static volatile uint32_t s_f_rif;             /* ... e il suo numero */
static volatile double s_p_rif = 0;

/* sensore OV9281 (SCCB 0x60, registri a 16 bit): VTS per spostare la fase della B */
static i2c_master_dev_handle_t s_sens;
static uint16_t s_vts0;
static volatile int s_sposta_righe;
static int s_sposta_stato;
static uint32_t s_correzioni;

static void sens_w(uint16_t reg, uint8_t v)
{
    uint8_t b[3] = {reg >> 8, reg & 0xff, v};
    i2c_master_transmit(s_sens, b, 3, 20);
}

static uint8_t sens_r(uint16_t reg)
{
    uint8_t a[2] = {reg >> 8, reg & 0xff}, v = 0;
    i2c_master_transmit_receive(s_sens, a, 2, &v, 1, 20);
    return v;
}

/* --- esposizione automatica (il driver OV9281 non ne ha: esposizione fissa ~0,5 ms = immagine scura) ---
 * La A misura la luminosità e decide; manda gli stessi valori alla B (stereo: due camere identiche). */
#define AE_TARGET       105          /* luminosità media voluta (0-255), come rpicam su #001 */
#define AE_EXP_MAX_US   16500        /* come #001 ma lasciando ~3 ms: la B deve poter accorciare il fotogramma per agganciarsi */
#define AE_GAIN_MAX     0xF0         /* 15× (0x10 = 1×) */
static volatile uint32_t s_exp16 = 0x2a9;    /* esposizione in 1/16 di riga */
static volatile uint32_t s_gain = 0x18;
static volatile int s_ae_luma = -1;

static void sens_w(uint16_t reg, uint8_t v);
static void applica_esposizione(uint32_t exp16, uint32_t gain)
{
    /* 18/11: fotogrammi bianchi isolati (A ~1 su 10, B ~1 su 150, al buio con esposizione al massimo): l'AE riscriveva
     * i registri ogni 10 fotogrammi anche senza cambiare nulla, sul bus I2C condiviso con IMU e codec.
     * Ora: si scrive solo se cambia, e in "group hold" (0x3208) così il sensore prende i 4 valori insieme al fotogramma dopo. */
    static uint32_t ultimo_exp = UINT32_MAX, ultimo_gain = UINT32_MAX;
    if (!s_sens || (exp16 == ultimo_exp && gain == ultimo_gain)) return;
    ultimo_exp = exp16;
    ultimo_gain = gain;
    sens_w(0x3208, 0x00);                   /* inizio gruppo 0 */
    sens_w(0x3500, (exp16 >> 16) & 0x0f);
    sens_w(0x3501, (exp16 >> 8) & 0xff);
    sens_w(0x3502, exp16 & 0xff);
    sens_w(0x3509, gain & 0xff);
    sens_w(0x3208, 0x10);                   /* fine gruppo 0 */
    sens_w(0x3208, 0xA0);                   /* lancio: applicato al prossimo fotogramma */
}

static int luma_media(const uint8_t *yuv, uint32_t len)
{
    /* YUV420 Espressif (righe "U Y Y" / "V Y Y"): la camera è mono, U/V ≈ 128 → Y = (3*media - 128) / 2 */
    uint64_t somma = 0;
    uint32_t n = 0;
    for (uint32_t i = 0; i < len; i += 61) { somma += yuv[i]; n++; }
    int m = n ? (int)(somma / n) : 0;
    int y = (3 * m - 128) / 2;
    return y < 0 ? 0 : y > 255 ? 255 : y;
}

static void ae_invia_b(void)
{
    char m[40];
    snprintf(m, sizeof(m), "E %lu %lu", (unsigned long)s_exp16, (unsigned long)s_gain);
    logger02_link_invia(m);                            /* la B usa gli stessi valori (e non riscrive se uguali) */
}

static void ae_passo(const uint8_t *yuv, uint32_t len)
{
    static uint32_t n;
    /* ogni 2 s ripeto i valori alla B anche se non cambiano: una B riavviata (OTA, crash) li riprende subito.
     * È solo UART: la B scrive il sensore solo se i valori sono diversi dai suoi (applica_esposizione). */
    if (++n % 10 == 0) ae_invia_b();
    int y = luma_media(yuv, len);
    s_ae_luma = y;
    if (y < 1) y = 1;
    double f = (double)AE_TARGET / y;
    if (f > 0.93 && f < 1.07) return;                  /* già a posto: niente sfarfallio */
    if (f > 2.0) f = 2.0;
    if (f < 0.5) f = 0.5;
    double riga = s_vts0 ? s_periodo_us / s_vts0 : 11.0;
    double exp_max16 = AE_EXP_MAX_US / riga * 16;
    double prodotto = (double)s_exp16 * s_gain * f;     /* luce totale = esposizione × guadagno */
    double e = prodotto / 0x10, g = 0x10;               /* prima allunga l'esposizione col guadagno a 1× */
    if (e > exp_max16) { e = exp_max16; g = prodotto / e; }
    if (e < 16) e = 16;
    if (g > AE_GAIN_MAX) g = AE_GAIN_MAX;
    /* già al limite (buio pieno o luce piena): niente scritture né messaggi alla B */
    if (abs((int)e - (int)s_exp16) <= 16 && (uint32_t)g == s_gain) return;
    s_exp16 = (uint32_t)e;
    s_gain = (uint32_t)g;
    applica_esposizione(s_exp16, s_gain);
    ae_invia_b();
}

void logger02_rec_esposizione(uint32_t exp16, uint32_t gain)
{
    s_exp16 = exp16;
    s_gain = gain;
    applica_esposizione(exp16, gain);
}

static void vts(uint16_t v)
{
    sens_w(0x380E, v >> 8);
    sens_w(0x380F, v & 0xff);
}

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

static volatile int s_da_scaricare = -1;
static void conta_pezzi_sd(void);
static void chiudi_segmento(void)
{
    if (s_vid) { fclose(s_vid); s_vid = NULL; if (s_da_scaricare >= 0) s_da_scaricare++; }
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
        int64_t t;
        if (l02_frame_n - s_deq <= 30) {
            t = l02_frame_t[s_deq % 32];
        } else {                                     /* troppo indietro: riallineo */
            s_deq = l02_frame_n - 1;
            t = l02_frame_t[s_deq % 32];
        }
        s_deq++;
        if (s_ultimo_t > 0) {
            double d = (double)(t - s_ultimo_t);
            if (d > 0.5 * s_periodo_us && d < 1.5 * s_periodo_us) s_periodo_us += (d - s_periodo_us) * 0.02;
        }
        s_ultimo_t = t;
        /* numerazione COMUNE ad A e B: indice del fotogramma nel tempo della A (stesso numero = stesso istante) */
        int64_t ta = logger02_t_a(t);
        uint32_t f = (s_t_rif >= 0 && s_p_rif > 0 && ta > 0)
                         ? s_f_rif + (uint32_t)llround((double)(ta - s_t_rif) / s_p_rif)   /* B: numero della A */
                         : s_deq;                                                           /* A: il suo contatore */
        s_frame = f;
        /* B: fase rispetto alla griglia dei fotogrammi della A (predetta fra un sync e l'altro), corretta ogni 5 */
        static uint32_t ultima_corr;
        if (s_t_rif >= 0 && s_p_rif > 0 && ta > 0 && s_vts0 && f - ultima_corr >= 5) {
            double ph = fmod((double)(ta - s_t_rif), s_p_rif);
            if (ph < 0) ph += s_p_rif;
            if (ph > s_p_rif / 2) ph -= s_p_rif;
            double riga = s_periodo_us / s_vts0;
            if (fabs(ph) > riga * 0.75 && fabs(ph) < riga * 40 && !s_sposta_righe && !s_sposta_stato) {
                s_sposta_righe = -(int)llround(ph / riga);       /* in ritardo → accorcia, in anticipo → allunga */
                ultima_corr = f;
            }
        }
        /* B: allunga UN fotogramma di N righe per agganciare la fase alla A */
        if (s_sens && s_vts0) {
            if (s_sposta_stato == 0 && s_sposta_righe) {
                vts(s_vts0 + s_sposta_righe);
                s_sposta_stato = 1;
            } else if (s_sposta_stato == 1) {
                vts(s_vts0);
                s_sposta_stato = 0;
                s_sposta_righe = 0;
                s_correzioni++;
            }
        }
        s_ultimi[s_ui] = ta;
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
                uint32_t tipi = nal_tipi(s_enc_out, ec.bytesused);
                if (tipi & (1u << 7)) salva_header(s_enc_out, ec.bytesused);
                /* nuovo pezzo solo su un fotogramma IDR, con SPS/PPS in testa: ogni file si decodifica da solo */
                if (s_pausa) {
                    if (s_vid) chiudi_segmento();               /* pezzo chiuso = scaricabile subito */
                    s_attendi_idr = true;
                } else if (s_attendi_idr && !(tipi & (1u << 5))) {
                    /* dopo la pausa si riparte solo da un IDR: ogni file si decodifica da solo */
                } else if (!s_vid || (esp_timer_get_time() - s_seg_t0 > SEG_S * 1000000LL && (tipi & (1u << 5)))) {
                    s_attendi_idr = false;
                    if (s_vid) chiudi_segmento();
                    apri_segmento();
                    if (s_vid && s_hdr_len && !(tipi & (1u << 7))) fwrite(s_hdr, 1, s_hdr_len, s_vid);
                }
                if (s_vid && !s_pausa) fwrite(s_enc_out, 1, ec.bytesused, s_vid);
                if (s_csv && !s_pausa) fprintf(s_csv, "%lu,%lld,%lld,%lu\n", (unsigned long)f, (long long)t,
                                   (long long)logger02_t_a(t), (unsigned long)ec.bytesused);
                s_bytes += ec.bytesused;
                s_scritti++;
                if (0 && s_scritti % 50 == 0) {   /* PROVA: fsync spento */           /* ogni ~3 s su SD: un taglio di corrente perde al massimo questo */
                    if (s_vid) { fflush(s_vid); fsync(fileno(s_vid)); }
                    if (s_csv) { fflush(s_csv); fsync(fileno(s_csv)); }
                }
                ioctl(s_enc, VIDIOC_QBUF, &ec);
                ioctl(s_enc, VIDIOC_DQBUF, &eo);
            }
        }
        if (logger02_ruolo()->is_a && f % 10 == 0) ae_passo(s_buf[b.index], b.bytesused);
        else if (!logger02_ruolo()->is_a && f % 10 == 0) s_ae_luma = luma_media(s_buf[b.index], b.bytesused);
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
    conta_pezzi_sd();                               /* pezzi rimasti dalle sessioni prima (dal task principale, stack grande) */
    struct v4l2_format fmt = {0};
    struct v4l2_requestbuffers req = {0};
    struct v4l2_buffer b;

    s_cap = open(ESP_VIDEO_MIPI_CSI_DEVICE_NAME, O_RDONLY);
    s_enc = open(ESP_VIDEO_H264_DEVICE_NAME, O_RDONLY);
    if (s_cap < 0 || s_enc < 0) {
        ESP_LOGE(TAG, "camera o encoder non disponibili");
        return ESP_FAIL;
    }
#if CONFIG_L02_REC_1280X800
    /* il driver Espressif ha solo 640x400 e 1280x720: il modo 1280x800 è in main/ov9281_1280x800.h (va dato PRIMA dei buffer) */
    if (ioctl(s_cap, VIDIOC_S_SENSOR_FMT, &l02_ov9281_1280x800) != 0) {
        ESP_LOGE(TAG, "OV9281: formato 1280x800 rifiutato");
        return ESP_FAIL;
    }
#endif
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

    i2c_master_bus_handle_t bus;
    if (i2c_master_get_bus_handle(0, &bus) == ESP_OK) {
        i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = 0x60, .scl_speed_hz = 100000};
        if (i2c_master_bus_add_device(bus, &dc, &s_sens) == ESP_OK) {
            s_vts0 = (sens_r(0x380E) << 8) | sens_r(0x380F);
            ESP_LOGI(TAG, "OV9281 VTS=%u righe, HTS=%u", s_vts0, (sens_r(0x380C) << 8) | sens_r(0x380D));
        }
    }
    logger02_nome_sessione(s_sess, sizeof(s_sess));
    s_rec = true;
    xTaskCreatePinnedToCore(rec_task, "rec", 6144, NULL, 8, NULL, 1);
    ESP_LOGI(TAG, "registro sessione %s (%dx%d, 1 fotogramma su %d, H.264 %d kbps)", s_sess, W, H, REC_DIV,
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

void logger02_rec_pausa(bool p)
{
    if (p && !s_pausa) ESP_LOGI(TAG, "pausa: bici ferma, chiudo il pezzo per lo scarico");
    if (!p && s_pausa) ESP_LOGI(TAG, "riprendo a registrare");
    s_pausa = p;
}

/* Pezzi chiusi ancora sulla SD: contati UNA volta all'avvio, poi +1 a ogni pezzo chiuso e -1 a ogni pezzo cancellato
 * dallo scarico (web /del). 23/11: contarli con opendir/readdir 50 volte al secondo dal task IMU mandava in crash la A. */

static void conta_pezzi_sd(void)
{
    int n = 0;
    DIR *d = opendir(L02_REC_DIR);
    struct dirent *e;
    while (d && (e = readdir(d))) {
        size_t l = strlen(e->d_name);
        if (l > 5 && !strcmp(e->d_name + l - 5, ".h264")) n++;
    }
    if (d) closedir(d);
    s_da_scaricare = n;
}

int logger02_rec_da_scaricare(void)
{
    return s_da_scaricare < 0 ? 0 : s_da_scaricare;
}

void logger02_rec_pezzo_tolto(void)
{
    if (s_da_scaricare > 0) s_da_scaricare--;
}

uint32_t logger02_rec_scritti(void)
{
    return s_scritti;
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
    snprintf(json, n, "{\"w\":%d,\"h\":%d,\"luma\":%d,\"esposizione_us\":%.0f,\"guadagno\":%.2f,\"registra\":%s,\"sessione\":\"%s\",\"file\":\"%s\",\"fotogrammi\":%lu,\"scritti\":%lu,"
             "\"pezzi\":%lu,\"mb\":%.1f,\"sd_libero_mb\":%llu}",
             W, H, s_ae_luma, s_vts0 ? s_exp16 / 16.0 * s_periodo_us / s_vts0 : 0, s_gain / 16.0,
             s_rec && !s_pausa ? "true" : "false", s_sess, s_vid ? s_file : "", (unsigned long)s_frame, (unsigned long)s_scritti,
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

/* --- fase delle camere --- */
void logger02_rec_fase(int64_t *t_ultimo_locale, uint32_t *frame, double *periodo_us)
{
    *t_ultimo_locale = s_ultimo_t;
    *frame = s_frame;
    *periodo_us = s_periodo_us;
}

void logger02_rec_riferimento(int64_t t_rif_a, uint32_t f_rif, double p_us)
{
    s_t_rif = t_rif_a;
    s_f_rif = f_rif;
    s_p_rif = p_us;
}

/* B: sposta la propria fase di 'us' microsecondi: >0 allunga un fotogramma (ritarda), <0 lo accorcia (anticipa,
 * solo di poche righe per non toccare l'esposizione) */
void logger02_rec_ritarda(int64_t us)
{
    if (!s_vts0 || s_sposta_righe || s_sposta_stato) return;
    double riga_us = s_periodo_us / s_vts0;
    int n = (int)llround((double)us / riga_us);
    if (n != 0 && n < 4 * s_vts0 && n > -(int)(s_vts0 / 8)) s_sposta_righe = n;
}

double logger02_rec_riga_us(void)
{
    return s_vts0 ? s_periodo_us / s_vts0 : 0;
}

uint32_t logger02_rec_correzioni(void)
{
    return s_correzioni;
}

void logger02_rec_standby(void)
{
    if (s_sens) sens_w(0x0100, 0x00);       /* OV9281: streaming off = standby */
}
