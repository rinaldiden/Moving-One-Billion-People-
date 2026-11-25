/* Collegamento A↔B: filo SYNC (A GPIO3 → B GPIO21) + UART1 (TX22/RX23, incrociata).
 * Ogni secondo A alza SYNC e manda "S <seq> <t_A_us>". B prende l'istante del fronte con il SUO orologio (ISR),
 * poi abbina il messaggio: offset = t_A - t_B. Con gli ultimi N campioni fa una retta (offset + deriva) e
 * misura lo scarto residuo = quanto bene i due orologi sono allineati (la "latenza fra i sync"). */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "logger02.h"

static const char *TAG = "link";

#define UARTN       UART_NUM_1
#define N_FIT       30

static volatile int64_t s_fronte_b;       /* B: istante dell'ultimo fronte SYNC (orologio B) */
static volatile uint32_t s_fronti;

static int64_t s_tb[N_FIT], s_off[N_FIT];
static int s_n, s_i;
static double s_a = 0, s_b = 0;           /* offset(tB) = a + b*(tB - tB0) */
static int64_t s_tb0;
static double s_resid_us = -1, s_resid_max_us = -1;
static uint32_t s_campioni;
static double s_fase_us = 1e9, s_fase_max_us;     /* B: sfasamento fotogrammi B - A (µs) all'ultimo sync */
static double s_fase_hist[N_FIT];
static int s_fh;
static bool s_valido;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

static void IRAM_ATTR sync_isr(void *arg)
{
    s_fronte_b = esp_timer_get_time();
    s_fronti++;
}

static void fit(void)
{
    /* minimi quadrati offset = a + b*(tb - tb0) */
    int n = s_n;
    int64_t tb0 = s_tb[(s_i - n + N_FIT) % N_FIT];
    double sx = 0, sy = 0, sxx = 0, sxy = 0;
    for (int k = 0; k < n; k++) {
        int j = (s_i - n + k + N_FIT) % N_FIT;
        double x = (double)(s_tb[j] - tb0) / 1e6, y = (double)s_off[j];
        sx += x; sy += y; sxx += x * x; sxy += x * y;
    }
    double den = n * sxx - sx * sx;
    double b = n > 1 && den != 0 ? (n * sxy - sx * sy) / den : 0;
    double a = (sy - b * sx) / n;
    double ss = 0, mx = 0;
    for (int k = 0; k < n; k++) {
        int j = (s_i - n + k + N_FIT) % N_FIT;
        double x = (double)(s_tb[j] - tb0) / 1e6;
        double r = (double)s_off[j] - (a + b * x);
        ss += r * r;
        if (fabs(r) > mx) mx = fabs(r);
    }
    portENTER_CRITICAL(&s_mux);
    s_a = a; s_b = b; s_tb0 = tb0;
    s_resid_us = n > 2 ? sqrt(ss / (n - 2)) : -1;
    s_resid_max_us = mx;
    s_valido = n >= 3;
    portEXIT_CRITICAL(&s_mux);
}

int64_t logger02_t_a(int64_t t)
{
    if (logger02_ruolo()->is_a) {
        return t;
    }
    if (!s_valido) {
        return -1;
    }
    portENTER_CRITICAL(&s_mux);
    double off = s_a + s_b * ((double)(t - s_tb0) / 1e6);
    portEXIT_CRITICAL(&s_mux);
    return t + (int64_t)llround(off);
}

void logger02_link_invia(const char *riga)
{
    char b[100];                                     /* 25/11: riga e \n in UNA scrittura: due task (sync e imu) non si mescolano */
    int n = snprintf(b, sizeof(b), "%s\n", riga);
    uart_write_bytes(UARTN, b, n < (int)sizeof(b) ? n : (int)sizeof(b) - 1);
    uart_wait_tx_done(UARTN, pdMS_TO_TICKS(100));    /* esce davvero dal filo (prima del deep sleep) */
}

/* B: se la A abbassa WAKE (si è addormentata) anche senza il comando "Z", dopo 3 s si addormenta pure la B */
static void wake_task(void *arg)
{
    int basso = 0;
    vTaskDelay(pdMS_TO_TICKS(20000));                /* all'avvio la A deve avere il tempo di alzarlo */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(500));
        basso = gpio_get_level(L02_PIN_WAKE) ? 0 : basso + 1;
        if (basso >= 6) logger02_dormi("la A ha abbassato WAKE");
    }
}

static volatile int s_b_pend = -1;
static volatile int64_t s_b_pend_t;

int logger02_b_da_scaricare(void)
{
    return esp_timer_get_time() - s_b_pend_t < 30000000LL ? s_b_pend : -1;
}

static void comando(const char *riga)
{
    if (riga[0] == 'S' && !logger02_ruolo()->is_a) {
        unsigned seq, fa = 0;
        long long ta, tfa = -1;
        double pa = 0;
        int k = sscanf(riga, "S %u %lld %u %lld %lf", &seq, &ta, &fa, &tfa, &pa);
        if (k >= 2) {
            int64_t tb = s_fronte_b;
            if (tb == 0 || esp_timer_get_time() - tb > 500000) {
                return;                         /* fronte vecchio o perso: scarto */
            }
            s_tb[s_i] = tb;
            s_off[s_i] = ta - tb;
            s_i = (s_i + 1) % N_FIT;
            if (s_n < N_FIT) s_n++;
            s_campioni++;
            fit();
            if (k == 5 && s_valido && pa > 1000 && tfa > 0) {
                /* aggancio di fase delle camere (come rpicam --sync su #001) */
                int64_t tb;
                uint32_t fb;
                double pb;
                logger02_rec_fase(&tb, &fb, &pb);
                logger02_rec_riferimento(tfa, fa, pa);
                double ph = fmod((double)(logger02_t_a(tb) - tfa), pa);
                if (ph < 0) ph += pa;
                if (ph > pa / 2) ph -= pa;                      /* >0: la B scatta dopo la A */
                s_fase_us = ph;
                s_fase_hist[s_fh++ % N_FIT] = fabs(ph);
                double riga = logger02_rec_riga_us();
                if (riga > 0 && fabs(ph) > riga * 0.75) {
                    if (ph > 0 && ph < riga * 40) logger02_rec_ritarda((int64_t)-ph);     /* anticipa di poco */
                    else logger02_rec_ritarda((int64_t)(ph > 0 ? pa - ph : -ph));       /* ritarda */
                }
            }
        }
    } else if (riga[0] == 'I' && logger02_ruolo()->is_a) {
        extern char g_ip_b[16];
        char ip[16];
        if (sscanf(riga, "I %15s", ip) == 1 && strcmp(ip, g_ip_b)) {
            strcpy(g_ip_b, ip);
            ESP_LOGI(TAG, "la B è su %s", g_ip_b);
        }
    } else if (riga[0] == 'E' && !logger02_ruolo()->is_a) {
        unsigned long e, g;
        if (sscanf(riga, "E %lu %lu", &e, &g) == 2) logger02_rec_esposizione(e, g);
    } else if (!strcmp(riga, "P") && !logger02_ruolo()->is_a) {
        logger02_rec_pausa(true);
    } else if (!strcmp(riga, "R") && !logger02_ruolo()->is_a) {
        logger02_rec_pausa(false);
    } else if (!strcmp(riga, "M") && !logger02_ruolo()->is_a) {
        logger02_rec_moto();                         /* 25/11: la A ha visto movimento vero */
    } else if (riga[0] == 'N' && logger02_ruolo()->is_a) {
        int n;
        if (sscanf(riga, "N %d", &n) == 1) { s_b_pend = n; s_b_pend_t = esp_timer_get_time(); }
    } else if (!strcmp(riga, "Z")) {
        logger02_dormi("comando dalla A");
    } else if (!strncmp(riga, "L ", 2)) {
        ESP_LOGI(TAG, "dall'altra scheda: %s", riga + 2);
    }
}

static void rx_task(void *arg)
{
    char riga[96];
    int n = 0;
    uint8_t c;
    while (1) {
        if (uart_read_bytes(UARTN, &c, 1, portMAX_DELAY) == 1) {
            if (c == '\n' || n == sizeof(riga) - 1) {
                riga[n] = 0;
                if (n) comando(riga);
                n = 0;
            } else if (c != '\r') {
                riga[n++] = c;
            }
        }
    }
}

static void sync_task(void *arg)
{
    uint32_t seq = 0;
    TickType_t t0 = xTaskGetTickCount();
    while (1) {
        vTaskDelayUntil(&t0, pdMS_TO_TICKS(1000));
        int64_t ta;
        portDISABLE_INTERRUPTS();
        ta = esp_timer_get_time();
        gpio_set_level(L02_PIN_SYNC_A, 1);
        portENABLE_INTERRUPTS();
        int64_t tf;
        uint32_t ff;
        double pf;
        logger02_rec_fase(&tf, &ff, &pf);
        char m[96];
        snprintf(m, sizeof(m), "S %lu %lld %lu %lld %.3f", (unsigned long)++seq, (long long)ta, (unsigned long)ff,
                 (long long)tf, pf);
        logger02_link_invia(m);
        vTaskDelay(pdMS_TO_TICKS(5));
        gpio_set_level(L02_PIN_SYNC_A, 0);
    }
}

esp_err_t logger02_link_init(void)
{
    uart_config_t cfg = {.baud_rate = 921600, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
                         .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_driver_install(UARTN, 2048, 2048, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UARTN, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(UARTN, L02_PIN_UART_TX, L02_PIN_UART_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    xTaskCreate(rx_task, "link_rx", 4096, NULL, 6, NULL);

    if (logger02_ruolo()->is_a) {
        gpio_config_t o = {.pin_bit_mask = (1ULL << L02_PIN_SYNC_A) | (1ULL << L02_PIN_WAKE), .mode = GPIO_MODE_OUTPUT};
        gpio_config(&o);
        gpio_set_level(L02_PIN_SYNC_A, 0);
        gpio_set_level(L02_PIN_WAKE, 1);            /* sveglia la B (resta alto finché A è sveglia) */
        xTaskCreate(sync_task, "sync", 3072, NULL, 10, NULL);
    } else {
        gpio_config_t wk = {.pin_bit_mask = 1ULL << L02_PIN_WAKE, .mode = GPIO_MODE_INPUT,
                            .pull_down_en = GPIO_PULLDOWN_ENABLE};
        gpio_config(&wk);
        gpio_config_t i = {.pin_bit_mask = 1ULL << L02_PIN_SYNC_B, .mode = GPIO_MODE_INPUT,
                           .pull_down_en = GPIO_PULLDOWN_ENABLE, .intr_type = GPIO_INTR_POSEDGE};
        gpio_config(&i);
        gpio_install_isr_service(ESP_INTR_FLAG_IRAM | ESP_INTR_FLAG_LEVEL3);
        gpio_isr_handler_add(L02_PIN_SYNC_B, sync_isr, NULL);
        xTaskCreate(wake_task, "wake", 3072, NULL, 4, NULL);
    }
    ESP_LOGI(TAG, "link A↔B pronto (%s)", logger02_ruolo()->is_a ? "master" : "slave");
    return ESP_OK;
}

void logger02_sync_stato(char *json, size_t n)
{
    if (logger02_ruolo()->is_a) {
        snprintf(json, n, "{\"ruolo\":\"A\",\"nota\":\"orologio di riferimento\"}");
        return;
    }
    int nh = s_fh < N_FIT ? s_fh : N_FIT;
    double mx = 0, somma = 0;
    for (int i = 0; i < nh; i++) { if (s_fase_hist[i] > mx) mx = s_fase_hist[i]; somma += s_fase_hist[i]; }
    snprintf(json, n,
             "{\"ruolo\":\"B\",\"valido\":%s,\"campioni\":%lu,\"fronti\":%lu,\"offset_us\":%.1f,"
             "\"deriva_ppm\":%.3f,\"scarto_orologi_rms_us\":%.2f,\"scarto_orologi_max_us\":%.2f,"
             "\"fase_camere_us\":%.1f,\"fase_camere_media_30s_us\":%.1f,\"fase_camere_max_30s_us\":%.1f,"
             "\"riga_us\":%.2f,\"correzioni\":%lu}",
             s_valido ? "true" : "false", (unsigned long)s_campioni, (unsigned long)s_fronti, s_a, s_b,
             s_resid_us, s_resid_max_us, s_fase_us, nh ? somma / nh : -1, mx, logger02_rec_riga_us(),
             (unsigned long)logger02_rec_correzioni());
}
