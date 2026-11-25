/* Salute della scheda (A e B), come asmile_health.csv del logger001 (Daniele 20/11: "errori, temperatura interna,
 * correnti... come sul raspi"). Una riga al secondo in /sd/rec/salute_<sessione>_NNNNN.csv (un file al minuto, come
 * i sensori: chiuderlo è l'unico modo sicuro di salvarlo) e gli avvisi/errori del log in errori_<sessione>_NNNNN.log.
 * Corrente: la scheda Waveshare non ha un sensore di corrente → non si misura (serve un INA219 sul 5 V).
 * Motivo dell'ultimo riavvio + contatori nella NVS "salute": un calo di tensione si vede come "brownout". */
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <unistd.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/temperature_sensor.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "nvs.h"
#include "logger02.h"

static const char *TAG = "salute";

/* --- avvisi/errori del log: copia in un anello in RAM, il task li scrive su SD --- */
#define RIGHE       24
#define LUNGA       160
static char s_anello[RIGHE][LUNGA];
static volatile uint32_t s_testa, s_coda, s_persi;
static volatile uint32_t s_n_err, s_n_avv;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static vprintf_like_t s_vprintf_orig;

/* Il livello è già nella stringa di formato (log v1, senza colori: "W (%lu) %s: ..."): formatto SOLO avvisi ed
 * errori, direttamente nella riga dell'anello, niente buffer sullo stack (gira nei task di chiunque scriva un log,
 * anche quelli con lo stack piccolo). */
static volatile uint32_t s_pronta[RIGHE];               /* = indice+1 quando la riga è scritta */

static int log_copia(const char *fmt, va_list ap)
{
    const char *f = fmt;
    if (*f == '\033') {                                 /* colori accesi: salta ESC[0;31m */
        while (*f && *f != 'm') f++;
        if (*f) f++;
    }
    if (*f == 'E' || *f == 'W') {
        uint32_t i;
        bool posto;
        taskENTER_CRITICAL(&s_mux);
        if (*f == 'E') s_n_err++; else s_n_avv++;
        posto = s_testa - s_coda < RIGHE;
        i = s_testa;
        if (posto) s_testa++; else s_persi++;
        taskEXIT_CRITICAL(&s_mux);
        if (posto) {
            char *d = s_anello[i % RIGHE];
            va_list ap2;
            va_copy(ap2, ap);
            vsnprintf(d, LUNGA, fmt, ap2);
            va_end(ap2);
            for (char *c = d; *c; c++) if (*c == '\n' || *c == '\033') { *c = 0; break; }
            s_pronta[i % RIGHE] = i + 1;
        }
    }
    return s_vprintf_orig(fmt, ap);
}

/* --- riavvii --- */
static const char *motivo_riavvio(esp_reset_reason_t r)
{
    switch (r) {
    case ESP_RST_POWERON:   return "accensione";
    case ESP_RST_SW:        return "software";
    case ESP_RST_PANIC:     return "crash";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT:       return "watchdog";
    case ESP_RST_DEEPSLEEP: return "deep_sleep";
    case ESP_RST_BROWNOUT:  return "brownout";
    case ESP_RST_EXT:       return "pin_reset";
    default:                return "altro";
    }
}

static const char *s_motivo;
static uint32_t s_avvii, s_brownout, s_crash;

static void conta_riavvio(void)
{
    esp_reset_reason_t r = esp_reset_reason();
    s_motivo = motivo_riavvio(r);
    nvs_handle_t h;
    if (nvs_open("salute", NVS_READWRITE, &h) != ESP_OK) return;
    nvs_get_u32(h, "avvii", &s_avvii);
    nvs_get_u32(h, "brownout", &s_brownout);
    nvs_get_u32(h, "crash", &s_crash);
    if (r != ESP_RST_DEEPSLEEP) s_avvii++;
    if (r == ESP_RST_BROWNOUT) s_brownout++;
    if (r == ESP_RST_PANIC || r == ESP_RST_INT_WDT || r == ESP_RST_TASK_WDT || r == ESP_RST_WDT) s_crash++;
    nvs_set_u32(h, "avvii", s_avvii);
    nvs_set_u32(h, "brownout", s_brownout);
    nvs_set_u32(h, "crash", s_crash);
    nvs_commit(h);
    nvs_close(h);
}

/* --- file --- */
static temperature_sensor_handle_t s_tsens;
/* Sospetto 21/11: sulla A (unica con l'ADC della batteria) il firmware con la temperatura moriva dopo 20 s - 2 min,
 * sulla B (senza ADC) girava. Sensore di temperatura e ADC usano la stessa parte analogica: mai insieme. */
SemaphoreHandle_t logger02_analogico;
static float s_temp = -99;
static char s_sess[24];
static uint32_t s_pezzo;
static int64_t s_pezzo_t0;
static FILE *s_csv, *s_err;
static SemaphoreHandle_t s_lock;                     /* file aperti/chiusi da task diversi (deep sleep) */
static bool s_fermo;

static void apri_file(void)
{
    char p[112];
    if (!s_sess[0]) logger02_nome_sessione(s_sess, sizeof(s_sess));
    snprintf(p, sizeof(p), L02_REC_DIR "/salute_%s_%05lu.csv", s_sess, (unsigned long)s_pezzo);
    s_csv = fopen(p, "w");
    if (s_csv) {
        fprintf(s_csv, "ora,t_us,t_a_us,uptime_s,ultimo_riavvio,avvii,brownout,crash,temp_c,batt_v,"
                       "ram_int_libera,ram_int_min,psram_libera,sd_libero_mb,fotogrammi,scritti,errori,avvisi,log_persi,rssi\n");
    }
    s_err = NULL;                                     /* il .log si apre solo se arriva un avviso */
    s_pezzo++;
    s_pezzo_t0 = esp_timer_get_time();
}

static void chiudi_file(void)
{
    if (s_csv) { fclose(s_csv); s_csv = NULL; }
    if (s_err) { fclose(s_err); s_err = NULL; }
}

static void ora_iso(char *out, size_t n)
{
    if (!logger02_ora_valida()) { out[0] = 0; return; }
    struct timeval tv;
    gettimeofday(&tv, NULL);
    struct tm tm;
    localtime_r(&tv.tv_sec, &tm);
    size_t k = strftime(out, n, "%Y-%m-%dT%H:%M:%S", &tm);
    snprintf(out + k, n - k, ".%03ld", (long)(tv.tv_usec / 1000));
}

static void scrivi_errori(const char *ora)
{
    while (s_coda != s_testa && s_pronta[s_coda % RIGHE] == s_coda + 1) {
        char riga[LUNGA];
        memcpy(riga, s_anello[s_coda % RIGHE], LUNGA);
        taskENTER_CRITICAL(&s_mux);
        s_coda++;
        taskEXIT_CRITICAL(&s_mux);
        if (!s_err) {
            char p[112];
            snprintf(p, sizeof(p), L02_REC_DIR "/errori_%s_%05lu.log", s_sess, (unsigned long)(s_pezzo - 1));
            s_err = fopen(p, "w");
            if (!s_err) return;
        }
        fprintf(s_err, "%s,%lld,%s\n", ora, (long long)esp_timer_get_time(), riga);
    }
}

static void salute_task(void *arg)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    apri_file();
    xSemaphoreGive(s_lock);
    TickType_t t0 = xTaskGetTickCount();
    while (1) {
        vTaskDelayUntil(&t0, pdMS_TO_TICKS(1000));
        if (s_tsens) {                                /* acceso solo per la lettura, mai insieme all'ADC della batteria */
            xSemaphoreTake(logger02_analogico, portMAX_DELAY);
            if (temperature_sensor_enable(s_tsens) == ESP_OK) {
                temperature_sensor_get_celsius(s_tsens, &s_temp);
                temperature_sensor_disable(s_tsens);
            }
            xSemaphoreGive(logger02_analogico);
        }
        xSemaphoreTake(s_lock, portMAX_DELAY);
        if (s_fermo) { xSemaphoreGive(s_lock); continue; }
        int64_t t = esp_timer_get_time();
        char ora[32];
        ora_iso(ora, sizeof(ora));
        if (s_csv) {
            float bv = logger02_ruolo()->is_a ? logger02_batteria_v() : -1;
            fprintf(s_csv, "%s,%lld,%lld,%lld,%s,%lu,%lu,%lu,%.1f,", ora, (long long)t, (long long)logger02_t_a(t),
                    (long long)(t / 1000000), s_motivo, (unsigned long)s_avvii, (unsigned long)s_brownout,
                    (unsigned long)s_crash, s_temp);
            if (bv > 0) fprintf(s_csv, "%.2f", bv);
            fprintf(s_csv, ",%u,%u,%u,%llu,%lu,%lu,%lu,%lu,%lu,",
                    (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                    (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL),
                    (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
                    (unsigned long long)logger02_sd_libero_mb(), (unsigned long)logger02_rec_frame(),
                    (unsigned long)logger02_rec_scritti(), (unsigned long)s_n_err, (unsigned long)s_n_avv,
                    (unsigned long)s_persi);
            int rssi = logger02_rete_rssi();         /* 25/11: segnale wifi (vuoto = non collegato / non noto) */
            if (rssi) fprintf(s_csv, "%d", rssi);
            fputc('\n', s_csv);
        }
        scrivi_errori(ora);
        if (t - s_pezzo_t0 > 60000000LL) { chiudi_file(); apri_file(); }
        else if ((t / 1000000) % 10 == 0) {           /* se la scheda muore restano i dati fino a 10 s prima */
            if (s_csv) { fflush(s_csv); fsync(fileno(s_csv)); }
            if (s_err) { fflush(s_err); fsync(fileno(s_err)); }
        }
        xSemaphoreGive(s_lock);
    }
}

/* subito all'avvio (prima di camera e wifi): così il log tiene anche gli errori dell'accensione */
void logger02_salute_presto(void)
{
    s_vprintf_orig = esp_log_set_vprintf(log_copia);
    conta_riavvio();
    temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    logger02_analogico = xSemaphoreCreateMutex();
    if (temperature_sensor_install(&tc, &s_tsens) != ESP_OK) {
        s_tsens = NULL;
    }
}

/* dopo la SD montata */
esp_err_t logger02_salute_start(void)
{
    s_lock = xSemaphoreCreateMutex();
    xTaskCreatePinnedToCore(salute_task, "salute", 4096, NULL, 3, NULL, 0);
    ESP_LOGI(TAG, "ultimo riavvio: %s (avvii %lu, brownout %lu, crash %lu)", s_motivo,
             (unsigned long)s_avvii, (unsigned long)s_brownout, (unsigned long)s_crash);
    return ESP_OK;
}

void logger02_salute_chiudi(void)
{
    if (!s_lock) return;                              /* SD mai montata: niente file */
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_fermo = true;
    char ora[32];
    ora_iso(ora, sizeof(ora));
    scrivi_errori(ora);                               /* prima di chiudere: c'è dentro il motivo del deep sleep */
    chiudi_file();
    xSemaphoreGive(s_lock);
}

void logger02_salute_stato(char *json, size_t n)
{
    snprintf(json, n, "{\"ultimo_riavvio\":\"%s\",\"avvii\":%lu,\"brownout\":%lu,\"crash\":%lu,\"temp_c\":%.1f,"
             "\"errori\":%lu,\"avvisi\":%lu}", s_motivo ? s_motivo : "?", (unsigned long)s_avvii,
             (unsigned long)s_brownout, (unsigned long)s_crash, s_temp, (unsigned long)s_n_err, (unsigned long)s_n_avv);
}
