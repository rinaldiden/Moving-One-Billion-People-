/* A: LED RGB KY-016 (catodo comune) che respira col colore della batteria (Daniele 26/11/2026, logger02_led_logic.h).
 * Tre canali LEDC (timer 3, canali 5-7: lontani da quelli che userebbe l'XCLK di una camera SPI, qui non usata),
 * 4 kHz 13 bit, aggiornati a 50 Hz. Pin in logger02.h (L02_PIN_LED_*), cablaggio in ../../logger/hw3/PIN_logger002.md.
 * Tensione: logger02_batteria_media_v() (vera, tarata 1,025*lettura+0,01, media mobile delle ultime 5 letture, 1 al secondo).
 * Sonno: logger02_led_spegni() da spegni_periferiche(); in deep sleep i pin tornano liberi = LED spento, zero consumo. */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/ledc.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "logger02.h"
#include "logger02_led_logic.h"

static const char *TAG = "led";

#define LED_TIMER   LEDC_TIMER_3
#define LED_MODO    LEDC_LOW_SPEED_MODE
#define LED_BIT     LEDC_TIMER_13_BIT
#define LED_PIENO   ((1 << 13) - 1)

static const int s_pin[3] = {L02_PIN_LED_R, L02_PIN_LED_G, L02_PIN_LED_B};
static const ledc_channel_t s_ch[3] = {LEDC_CHANNEL_5, LEDC_CHANNEL_6, LEDC_CHANNEL_7};
static volatile bool s_acceso;
static volatile l02_led_colore_t s_colore = L02_LED_SPENTO;

static void led_task(void *arg)
{
    TickType_t t0 = xTaskGetTickCount();
    while (s_acceso) {
        vTaskDelayUntil(&t0, pdMS_TO_TICKS(20));
        s_colore = l02_led_colore(s_colore, logger02_batteria_media_v());
        float rgb[3];
        l02_led_rgb(s_colore, l02_led_respiro((uint32_t)(esp_timer_get_time() / 1000)), rgb);
        for (int k = 0; k < 3 && s_acceso; k++) {
            ledc_set_duty(LED_MODO, s_ch[k], (uint32_t)(rgb[k] * LED_PIENO));
            ledc_update_duty(LED_MODO, s_ch[k]);
        }
    }
    vTaskDelete(NULL);
}

void logger02_led_start(void)
{
    if (!logger02_ruolo()->is_a || s_acceso) return;
    ledc_timer_config_t tc = {.speed_mode = LED_MODO, .duty_resolution = LED_BIT, .timer_num = LED_TIMER,
                              .freq_hz = 4000, .clk_cfg = LEDC_AUTO_CLK};
    if (ledc_timer_config(&tc) != ESP_OK) { ESP_LOGW(TAG, "timer LEDC non configurato: LED spento"); return; }
    for (int k = 0; k < 3; k++) {
        ledc_channel_config_t cc = {.gpio_num = s_pin[k], .speed_mode = LED_MODO, .channel = s_ch[k],
                                    .timer_sel = LED_TIMER, .duty = 0, .hpoint = 0};
        if (ledc_channel_config(&cc) != ESP_OK) { ESP_LOGW(TAG, "canale LED %d non configurato: LED spento", k); return; }
    }
    s_acceso = true;
    xTaskCreatePinnedToCore(led_task, "led", 3072, NULL, 3, NULL, 1);   /* priorita' bassa: e' solo una luce */
    ESP_LOGI(TAG, "LED batteria: respiro %u ms, verde >= %.1f V, arancione >= %.1f V, sotto rosso",
             L02_LED_RESPIRO_MS, L02_LED_VERDE_V, L02_LED_ARANCIO_V);
}

void logger02_led_spegni(void)
{
    if (!s_acceso) return;
    s_acceso = false;
    for (int k = 0; k < 3; k++) ledc_stop(LED_MODO, s_ch[k], 0);   /* uscita bassa = LED spento */
    s_colore = L02_LED_SPENTO;
}

const char *logger02_led_stato(void)
{
    return l02_led_nome(s_colore);
}
