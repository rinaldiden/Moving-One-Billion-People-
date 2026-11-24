/* Server HTTP (porta 80). La A è l'unica faccia verso l'esterno: /b/<percorso> viene girato alla B.
 *   GET  /                  pagina con streaming A + B
 *   GET  :81/stream         MJPEG (solo banco: nei logger nessuno lo apre e non costa niente). Server a parte:
 *                           uno streaming occupa il suo server finché resta aperto. Su A, :82/b/stream = quello della B.
 *   GET  /api/stato         JSON: ruolo, uptime, registrazione, sync, IMU, batteria
 *   GET  /api/frames        ultimi tempi dei fotogrammi in tempo A (per misurare lo sfasamento A↔B)
 *   GET  /api/files         elenco file in /sd/rec
 *   GET  /dl?f=<nome>       scarica un file; supporta Range: bytes=N[-M] (206) per riprendere. Un solo trasferimento
 *                           alla volta (altri: 503 Retry-After), buffer preallocati all'avvio (24/11)
 *   POST /del?f=<nome>      cancella (il Mac cancella solo dopo aver controllato la dimensione)
 *   POST /ota               nuovo firmware (corpo = .bin), poi riavvio
 *   POST /dormi             deep sleep subito (prova) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>
#include <sys/stat.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_http_server.h"
#include "esp_http_client.h"
#include "esp_ota_ops.h"
#include "esp_app_desc.h"
#include "nvs.h"
#include <time.h>
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "logger02.h"

static const char *TAG = "web";
/* IP della B: quello che lei manda sulla UART ("I <ip>"), perché su una rete diversa da casa non è .124 */
char g_ip_b[16] = "192.168.1.124";

static const char PAGINA[] =        /* stessa pagina dello streaming di asmile #001 (pi/camera/stream_server.py) */
    "<!DOCTYPE html><html><head><meta charset=utf-8><title>Asmile Cameras</title><style>"
    "body{background:#111;margin:0;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh}"
    "h1{color:#888;font-family:monospace}.cams{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}"
    "img{border:2px solid #333;width:640px;max-width:48vw;background:#222}"
    "pre{color:#777;font:11px monospace;max-width:1300px;white-space:pre-wrap}</style></head><body>"
    "<h1>ASMILE STEREO — logger02</h1><div class=cams><img id=a><img id=b></div><pre id=s></pre>"
    "<script>let h=location.hostname;a.src='http://'+h+':81/stream';b.src='http://'+h+':82/b/stream';"
    "async function t(){try{let A=await(await fetch('/api/stato')).json(),B=await(await fetch('/b/api/stato')).json();"
    "document.querySelector('h1').textContent='ASMILE STEREO — '+A.scheda.slice(0,-1);"
    "s.textContent='A luce '+A.rec.luma+' esp '+A.rec.esposizione_us+'us g '+A.rec.guadagno+' | B luce '+B.rec.luma+"
    "' | sync camere '+(B.sync.fase_camere_us||'-')+' us | batteria '+(A.imu?A.imu.batteria_v:'-')+' V'}catch(e){}}"
    "setInterval(t,2000);t()</script></body></html>";

static esp_err_t h_root(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, PAGINA, sizeof(PAGINA) - 1);
}

static esp_err_t h_stream(httpd_req_t *req)
{
    static const char *B = "123456789000000000000987654321";
    char hdr[96];
    size_t max = 1280 * 800 / 2;          /* come il buffer JPEG di logger02_rec.c (W*H/2) */
    uint8_t *jpg = heap_caps_malloc(max, MALLOC_CAP_SPIRAM);
    if (!jpg) return ESP_FAIL;
    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=123456789000000000000987654321");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    esp_err_t r = ESP_OK;
    while (r == ESP_OK) {
        size_t n = logger02_rec_jpeg(jpg, max);
        if (!n) {
            vTaskDelay(pdMS_TO_TICKS(30));
            continue;
        }
        int k = snprintf(hdr, sizeof(hdr), "\r\n--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", B,
                         (unsigned)n);
        r = httpd_resp_send_chunk(req, hdr, k);
        if (r == ESP_OK) r = httpd_resp_send_chunk(req, (const char *)jpg, n);
    }
    free(jpg);
    return ESP_OK;
}

static esp_err_t h_stato(httpd_req_t *req)
{
    char rec[320], sync[480], imu[320], ts[96], sal[200], out[1900];
    logger02_rec_stato(rec, sizeof(rec));
    logger02_sync_stato(sync, sizeof(sync));
    if (logger02_ruolo()->is_a) logger02_imu_stato(imu, sizeof(imu));
    else snprintf(imu, sizeof(imu), "null");
    logger02_tailscale_stato(ts, sizeof(ts));
    logger02_salute_stato(sal, sizeof(sal));
    const esp_app_desc_t *app = esp_app_get_description();
    snprintf(out, sizeof(out), "{\"scheda\":\"%s\",\"riavvio\":%d,\"versione\":\"%s %s %s\",\"partizione\":\"%s\",\"ram_interna_libera\":%u,\"ram_interna_min\":%u,\"uptime_s\":%lld,\"t_us\":%lld,\"t_a_us\":%lld,\"rec\":%s,\"sync\":%s,\"imu\":%s,\"tailscale\":%s,\"salute\":%s}",
             logger02_ruolo()->nome, (int)esp_reset_reason(), app->version, app->date, app->time, esp_ota_get_running_partition()->label,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL), esp_timer_get_time() / 1000000, esp_timer_get_time(),
             logger02_t_a(esp_timer_get_time()), rec, sync, imu, ts, sal);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, out);
}

static esp_err_t h_frames(httpd_req_t *req)
{
    char out[1400];
    logger02_rec_ultimi(out, sizeof(out));
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, out);
}

static esp_err_t h_files(httpd_req_t *req)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr_chunk(req, "[");
    DIR *d = opendir(L02_REC_DIR);
    bool primo = true;
    struct dirent *e;
    char riga[320], p[300];
    while (d && (e = readdir(d))) {
        struct stat st;
        snprintf(p, sizeof(p), L02_REC_DIR "/%s", e->d_name);
        if (stat(p, &st) != 0 || S_ISDIR(st.st_mode)) continue;
        snprintf(riga, sizeof(riga), "%s{\"nome\":\"%s\",\"byte\":%ld}", primo ? "" : ",", e->d_name, (long)st.st_size);
        httpd_resp_sendstr_chunk(req, riga);
        primo = false;
    }
    if (d) closedir(d);
    httpd_resp_sendstr_chunk(req, "]");
    return httpd_resp_sendstr_chunk(req, NULL);
}

static bool nome_ok(httpd_req_t *req, char *path, size_t n)
{
    char q[128], f[96];
    if (httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK || httpd_query_key_value(q, "f", f, sizeof(f)) != ESP_OK
        || strchr(f, '/') || strstr(f, "..")) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "f mancante o non valido");
        return false;
    }
    snprintf(path, n, L02_REC_DIR "/%s", f);
    return true;
}

/* 24/11 scarico affidabile (crash 18/11: esp_hosted SDIO non trova 23 KB di RAM interna contigua mentre si trasferisce).
 *  - buffer preallocati UNA volta all'avvio (PSRAM): niente malloc/free per richiesta, niente frammentazione
 *  - blocchi da 8 KB (prima 32 KB file / 16 KB proxy) e una pausa di 1 tick fra blocchi
 *  - un solo trasferimento di FILE alla volta (A: proprio o della B): il secondo riceve 503 e il Mac riprova
 *  - contropressione: se la RAM interna libera scende sotto SOGLIA_RAM si aspetta (fino a 1 s) invece di spingere */
#define BLK 8192
#define SOGLIA_RAM 70000
static uint8_t *s_buf_dl;                     /* trasferimenti di file */
static uint8_t *s_buf_api;                    /* risposte piccole/POST via proxy */
static SemaphoreHandle_t s_lock_dl, s_lock_api;
static char s_cr[96];                         /* Content-Range della risposta in corso (protetto da s_lock_dl) */

static void contropressione(void)
{
    for (int i = 0; i < 50 && heap_caps_get_free_size(MALLOC_CAP_INTERNAL) < SOGLIA_RAM; i++) vTaskDelay(pdMS_TO_TICKS(20));
    vTaskDelay(1);
}

static bool occupato(httpd_req_t *req)
{
    httpd_resp_set_status(req, "503 Service Unavailable");
    httpd_resp_set_hdr(req, "Retry-After", "5");
    httpd_resp_sendstr(req, "trasferimento in corso");
    return true;
}

/* "Range: bytes=N-" o "bytes=N-M" -> da, a (incluso). false se assente. Solo un intervallo, niente suffissi */
static bool leggi_range(httpd_req_t *req, long *da, long *a)
{
    char v[64];
    if (httpd_req_get_hdr_value_str(req, "Range", v, sizeof(v)) != ESP_OK || strncmp(v, "bytes=", 6)) return false;
    char *fine;
    long n = strtol(v + 6, &fine, 10);
    if (*fine != '-' || fine == v + 6) return false;
    *da = n;
    *a = fine[1] ? strtol(fine + 1, NULL, 10) : -1;
    return true;
}

static esp_err_t h_dl(httpd_req_t *req)
{
    char p[160];
    if (!nome_ok(req, p, sizeof(p))) return ESP_OK;
    struct stat st;
    if (stat(p, &st) != 0) return httpd_resp_send_404(req);
    if (!s_buf_dl || xSemaphoreTake(s_lock_dl, 0) != pdTRUE) { occupato(req); return ESP_OK; }
    long size = st.st_size, da = 0, a = size - 1;
    bool parz = false;
    long rd, ra;
    if (leggi_range(req, &rd, &ra)) {
        if (rd < 0 || rd >= size) {
            snprintf(s_cr, sizeof(s_cr), "bytes */%ld", size);
            httpd_resp_set_status(req, "416 Range Not Satisfiable");
            httpd_resp_set_hdr(req, "Content-Range", s_cr);
            httpd_resp_sendstr(req, "range fuori file");
            xSemaphoreGive(s_lock_dl);
            return ESP_OK;
        }
        da = rd;
        if (ra >= 0 && ra < size - 1) a = ra;
        parz = true;
    }
    FILE *f = fopen(p, "rb");
    if (!f || (da && fseek(f, da, SEEK_SET) != 0)) {
        if (f) fclose(f);
        xSemaphoreGive(s_lock_dl);
        return httpd_resp_send_404(req);
    }
    httpd_resp_set_type(req, "application/octet-stream");
    httpd_resp_set_hdr(req, "Accept-Ranges", "bytes");
    if (parz) {
        snprintf(s_cr, sizeof(s_cr), "bytes %ld-%ld/%ld", da, a, size);
        httpd_resp_set_status(req, "206 Partial Content");
        httpd_resp_set_hdr(req, "Content-Range", s_cr);
    }
    long resto = a - da + 1;
    esp_err_t r = ESP_OK;
    logger02_scarico_inizio();                      /* 24/11: scarico in corso = mai dormire */
    while (r == ESP_OK && resto > 0) {
        size_t n = fread(s_buf_dl, 1, resto < BLK ? (size_t)resto : BLK, f);
        if (n == 0) { r = ESP_FAIL; break; }        /* file accorciato: chunk finale mancante = il Mac vede il troncamento */
        contropressione();
        r = httpd_resp_send_chunk(req, (const char *)s_buf_dl, n);
        resto -= n;
        logger02_scarico_visto();                   /* 23/11: un pezzo da 25 MB dura più di un minuto: sveglia a ogni blocco */
    }
    fclose(f);
    logger02_scarico_fine();
    xSemaphoreGive(s_lock_dl);
    if (r != ESP_OK) return r;
    return httpd_resp_send_chunk(req, NULL, 0);
}

static esp_err_t h_del(httpd_req_t *req)
{
    char p[160];
    if (!nome_ok(req, p, sizeof(p))) return ESP_OK;
    bool ok = remove(p) == 0;
    size_t l = strlen(p);
    if (ok && l > 5 && !strcmp(p + l - 5, ".h264")) logger02_rec_pezzo_tolto();
    return httpd_resp_sendstr(req, ok ? "ok" : "errore");
}

/* storico aggiornamenti nella NVS della scheda: ultime 8 righe "data ora | da versione → partizione" */
static void storia_aggiungi(const char *riga)
{
    nvs_handle_t h;
    if (nvs_open("storia", NVS_READWRITE, &h) != ESP_OK) return;
    uint8_t i = 0;
    nvs_get_u8(h, "i", &i);
    char k[4];
    snprintf(k, sizeof(k), "r%u", i % 8);
    nvs_set_str(h, k, riga);
    nvs_set_u8(h, "i", (uint8_t)(i + 1));
    nvs_commit(h);
    nvs_close(h);
}

static esp_err_t h_storia(httpd_req_t *req)
{
    nvs_handle_t h;
    httpd_resp_set_type(req, "text/plain");
    if (nvs_open("storia", NVS_READONLY, &h) != ESP_OK) return httpd_resp_sendstr(req, "(vuota)\n");
    uint8_t i = 0;
    nvs_get_u8(h, "i", &i);
    char k[4], v[128];
    for (int n = 0; n < 8; n++) {
        size_t len = sizeof(v);
        snprintf(k, sizeof(k), "r%u", (unsigned)((i + n) % 8));
        if (nvs_get_str(h, k, v, &len) == ESP_OK) { httpd_resp_sendstr_chunk(req, v); httpd_resp_sendstr_chunk(req, "\n"); }
    }
    nvs_close(h);
    return httpd_resp_sendstr_chunk(req, NULL);
}

static void riga_storia(char *out, size_t n, const char *cosa, const char *verso)
{
    time_t t = time(NULL);
    struct tm tm;
    localtime_r(&t, &tm);
    char d[20];
    strftime(d, sizeof(d), "%Y-%m-%d %H:%M", &tm);
    snprintf(out, n, "%s | %s | da %s (%s) -> %s", d, cosa, esp_app_get_description()->version,
             esp_ota_get_running_partition()->label, verso);
}

/* torna alla versione precedente (è sempre nell'altra partizione OTA) */
static esp_err_t h_rollback(httpd_req_t *req)
{
    const esp_partition_t *altra = esp_ota_get_next_update_partition(NULL);
    esp_app_desc_t d;
    if (!altra || esp_ota_get_partition_description(altra, &d) != ESP_OK) {
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "nessuna versione precedente");
    }
    char r[128];
    riga_storia(r, sizeof(r), "ROLLBACK", d.version);
    storia_aggiungi(r);
    esp_ota_set_boot_partition(altra);
    httpd_resp_sendstr(req, r);
    logger02_rec_stop();
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
    return ESP_OK;
}

static esp_err_t h_ota(httpd_req_t *req)
{
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t h;
    /* prima ferma la registrazione: cancellare la flash blocca la cache e con camera+SD attive la scheda va in
     * crash (17/11). Poi cancella solo quanto serve (dimensione del file), non tutti i 4 MB. */
    logger02_rec_stop();
    if (!part || esp_ota_begin(part, req->content_len > 0 ? req->content_len : OTA_SIZE_UNKNOWN, &h) != ESP_OK) {
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota begin");
    }
    char *buf = heap_caps_malloc(8192, MALLOC_CAP_SPIRAM);   /* RAM interna: serve al wifi (crash 17/11) */
    int resto = req->content_len, n;
    while (resto > 0) {
        n = httpd_req_recv(req, buf, resto < 8192 ? resto : 8192);
        if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
        if (n <= 0 || esp_ota_write(h, buf, n) != ESP_OK) {
            free(buf);
            esp_ota_abort(h);
            return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota scrittura");
        }
        resto -= n;
    }
    free(buf);
    if (esp_ota_end(h) != ESP_OK || esp_ota_set_boot_partition(part) != ESP_OK) {
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota fine");
    }
    esp_app_desc_t nuovo;
    char r[128];
    riga_storia(r, sizeof(r), "OTA", esp_ota_get_partition_description(part, &nuovo) == ESP_OK ? nuovo.version : "?");
    storia_aggiungi(r);
    httpd_resp_sendstr(req, "ok, riavvio");
    ESP_LOGW(TAG, "nuovo firmware in %s: riavvio", part->label);
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
    return ESP_OK;
}

/* chiave Tailscale nella NVS (solo scrittura: non si rilegge mai via web). La manda logger02/chiave_tailscale.sh */
static esp_err_t h_tskey(httpd_req_t *req)
{
    char k[128] = {0};
    if (req->content_len <= 0 || req->content_len >= (int)sizeof(k) || httpd_req_recv(req, k, req->content_len) != req->content_len) {
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "chiave mancante");
    }
    k[strcspn(k, "\r\n ")] = 0;
    esp_err_t r = logger02_tailscale_salva_chiave(k);
    memset(k, 0, sizeof(k));
    if (r != ESP_OK) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "chiave non valida (tskey-auth-...)");
    return httpd_resp_sendstr(req, "chiave salvata nella NVS: vale dal prossimo avvio\n");
}

static esp_err_t h_formatta(httpd_req_t *req)
{
    char q[48], v[16];
    if (httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK || httpd_query_key_value(q, "si", v, sizeof(v)) != ESP_OK
        || strcmp(v, "cancella")) {
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "serve ?si=cancella");
    }
    esp_err_t r = logger02_sd_formatta();
    httpd_resp_sendstr(req, r == ESP_OK ? "riavvio e formatto la SD in FAT32" : esp_err_to_name(r));
    if (r == ESP_OK) {
        vTaskDelay(pdMS_TO_TICKS(500));
        esp_restart();
    }
    return ESP_OK;
}

static esp_err_t h_dormi(httpd_req_t *req)
{
    extern uint32_t g_dormi_prova_s;
    char q[32], v[8];
    if (httpd_req_get_url_query_str(req, q, sizeof(q)) == ESP_OK && httpd_query_key_value(q, "s", v, sizeof(v)) == ESP_OK) {
        g_dormi_prova_s = atoi(v);                  /* prova: si risveglia da sola dopo s secondi */
    }
    httpd_resp_sendstr(req, "vado in deep sleep");
    vTaskDelay(pdMS_TO_TICKS(300));
    logger02_dormi("comando web");
    return ESP_OK;
}

/* A: /b/<x> → http://B/<x>, in streaming (anche POST /b/ota) */
/* se la B non risponde, per 30 s rispondo subito "B giù" invece di aspettare: il server della A è uno solo
 * e ogni attesa lo blocca per tutti (17/11: la pagina che chiedeva /b ogni 2 s rendeva la A "irraggiungibile") */
static volatile int64_t s_b_giu_fino;

static const char *stato_str(int c)
{
    switch (c) {
    case 206: return "206 Partial Content";
    case 404: return "404 Not Found";
    case 416: return "416 Range Not Satisfiable";
    case 503: return "503 Service Unavailable";
    default:  return NULL;                         /* 200 e il resto: stato di default */
    }
}

/* IDF 5.5: esp_http_client_get_header() legge gli header della RICHIESTA, non della risposta (guardian 24/11):
 * il Content-Range della B si cattura qui, nell'evento ON_HEADER, e finisce in s_cr_b (protetto da s_lock_dl) */
static char s_cr_b[96];
static esp_err_t ev_b(esp_http_client_event_t *e)
{
    if (e->event_id == HTTP_EVENT_ON_HEADER && e->header_key && e->header_value && !strcasecmp(e->header_key, "Content-Range")) {
        snprintf(s_cr_b, sizeof(s_cr_b), "%s", e->header_value);
    }
    return ESP_OK;
}

static esp_err_t proxy_b_corpo(httpd_req_t *req, const char *porta)
{
    if (esp_timer_get_time() < s_b_giu_fino) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "{\"errore\":\"B non raggiungibile\"}");
    }
    bool file = porta[0] == 0 && strstr(req->uri, "/dl");     /* download di un file della B: buffer e lock dei file */
    bool stream = porta[0] != 0;                              /* :82 streaming: buffer proprio (policy: niente streaming lungo) */
    SemaphoreHandle_t lock = file ? s_lock_dl : s_lock_api;
    uint8_t *buf = file ? s_buf_dl : s_buf_api;
    int blk = file ? BLK : 8192;
    if (stream) { buf = heap_caps_malloc(16384, MALLOC_CAP_SPIRAM); blk = 16384; lock = NULL; }
    if (!buf || (lock && xSemaphoreTake(lock, file ? 0 : pdMS_TO_TICKS(5000)) != pdTRUE)) {
        if (stream) free(buf);
        occupato(req);
        return ESP_OK;
    }
    char url[192];
    snprintf(url, sizeof(url), "http://%s%s%s", g_ip_b, porta, req->uri + 2);
    esp_http_client_config_t cc = {.url = url, .timeout_ms = req->method == HTTP_POST ? 15000 : (file ? 8000 : 2500), .buffer_size = 4096, .event_handler = ev_b,
                                   .method = req->method == HTTP_POST ? HTTP_METHOD_POST : HTTP_METHOD_GET};
    if (file) s_cr_b[0] = 0;
    esp_http_client_handle_t c = esp_http_client_init(&cc);
    char rng[64];
    if (file && httpd_req_get_hdr_value_str(req, "Range", rng, sizeof(rng)) == ESP_OK) esp_http_client_set_header(c, "Range", rng);
    esp_err_t r = esp_http_client_open(c, req->method == HTTP_POST ? req->content_len : 0);
    if (r == ESP_OK && req->method == HTTP_POST) {
        int resto = req->content_len, n;
        while (resto > 0 && (n = httpd_req_recv(req, (char *)buf, resto < blk ? resto : blk)) > 0) {
            esp_http_client_write(c, (char *)buf, n);
            resto -= n;
        }
    }
    if (r != ESP_OK || esp_http_client_fetch_headers(c) < 0) {
        esp_http_client_cleanup(c);
        if (stream) free(buf);
        if (lock) xSemaphoreGive(lock);
        s_b_giu_fino = esp_timer_get_time() + 8000000;
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "{\"errore\":\"B non raggiungibile\"}");
    }
    char *ct = NULL;
    if (esp_http_client_get_header(c, "Content-Type", &ct) == ESP_OK && ct) httpd_resp_set_type(req, ct);
    if (file) {
        const char *ss = stato_str(esp_http_client_get_status_code(c));
        if (ss) httpd_resp_set_status(req, ss);
        if (s_cr_b[0]) httpd_resp_set_hdr(req, "Content-Range", s_cr_b);     /* catturato in ev_b */
        httpd_resp_set_hdr(req, "Accept-Ranges", "bytes");
    }
    int n;
    esp_err_t e = ESP_OK;
    while ((n = esp_http_client_read(c, (char *)buf, blk)) > 0) {
        if (file) contropressione();
        if ((e = httpd_resp_send_chunk(req, (const char *)buf, n)) != ESP_OK) break;
        if (file) logger02_scarico_visto();                /* solo blocchi di FILE della B (non gli elenchi /b/api/files) */
    }
    /* se la B si e' interrotta (n < 0) NON chiudo con il chunk finale: il Mac vede la risposta troncata e riprende con Range */
    bool ok_fine = (n == 0) && e == ESP_OK;
    esp_http_client_close(c);
    esp_http_client_cleanup(c);
    if (stream) free(buf);
    if (lock) xSemaphoreGive(lock);
    if (!ok_fine) return ESP_FAIL;
    return httpd_resp_send_chunk(req, NULL, 0);
}

/* ogni /b (file della B via A) conta come trasferimento aperto, qualunque sia l'uscita; lo stream :81 no */
static esp_err_t proxy_b(httpd_req_t *req, const char *porta)
{
    bool conta = porta[0] == 0 && strstr(req->uri, "/dl");     /* solo download di file della B */
    if (conta) logger02_scarico_inizio();
    esp_err_t e = proxy_b_corpo(req, porta);
    if (conta) logger02_scarico_fine();
    return e;
}

static httpd_handle_t server(uint16_t porta, uint16_t ctrl, int handlers)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = porta;
    cfg.ctrl_port = ctrl;
    cfg.max_uri_handlers = handlers;
    cfg.stack_size = 8192;
    cfg.max_open_sockets = 3;
    cfg.lru_purge_enable = true;
    cfg.uri_match_fn = httpd_uri_match_wildcard;
    httpd_handle_t s = NULL;
    ESP_ERROR_CHECK(httpd_start(&s, &cfg));
    return s;
}

static esp_err_t h_b(httpd_req_t *req)
{
    return proxy_b(req, "");
}

static esp_err_t h_b_stream(httpd_req_t *req)
{
    return proxy_b(req, ":81");
}

esp_err_t logger02_web_start(void)
{
    /* buffer e lock una volta sola (24/11): PSRAM, mai piu' allocati per richiesta */
    s_buf_dl = heap_caps_malloc(BLK, MALLOC_CAP_SPIRAM);
    s_buf_api = heap_caps_malloc(8192, MALLOC_CAP_SPIRAM);
    s_lock_dl = xSemaphoreCreateBinary(); xSemaphoreGive(s_lock_dl);
    s_lock_api = xSemaphoreCreateBinary(); xSemaphoreGive(s_lock_api);
    httpd_handle_t s81 = server(81, 32769, 2);
    httpd_uri_t st = {"/stream", HTTP_GET, h_stream};
    httpd_register_uri_handler(s81, &st);
    if (logger02_ruolo()->is_a) {
        httpd_handle_t s82 = server(82, 32770, 2);
        httpd_uri_t bs = {"/b/*", HTTP_GET, h_b_stream};
        httpd_register_uri_handler(s82, &bs);
    }
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.max_uri_handlers = 20;
    cfg.stack_size = 8192;
    cfg.max_open_sockets = 7;
    cfg.lru_purge_enable = true;
    cfg.uri_match_fn = httpd_uri_match_wildcard;
    cfg.recv_wait_timeout = 30;
    cfg.send_wait_timeout = 30;
    httpd_handle_t s;
    ESP_ERROR_CHECK(httpd_start(&s, &cfg));
    const httpd_uri_t u[] = {
        {"/", HTTP_GET, h_root}, {"/api/stato", HTTP_GET, h_stato},
        {"/api/frames", HTTP_GET, h_frames}, {"/api/files", HTTP_GET, h_files}, {"/dl", HTTP_GET, h_dl},
        {"/del", HTTP_POST, h_del}, {"/ota", HTTP_POST, h_ota}, {"/dormi", HTTP_POST, h_dormi}, {"/formatta", HTTP_POST, h_formatta},
        {"/api/storia", HTTP_GET, h_storia}, {"/rollback", HTTP_POST, h_rollback}, {"/tskey", HTTP_POST, h_tskey},
    };
    for (size_t i = 0; i < sizeof(u) / sizeof(u[0]); i++) httpd_register_uri_handler(s, &u[i]);
    if (logger02_ruolo()->is_a) {
        httpd_uri_t bg = {"/b/*", HTTP_GET, h_b}, bp = {"/b/*", HTTP_POST, h_b};
        httpd_register_uri_handler(s, &bg);
        httpd_register_uri_handler(s, &bp);
    }
    ESP_LOGI(TAG, "server web su http://%s/", logger02_ruolo()->ip);
    return ESP_OK;
}
