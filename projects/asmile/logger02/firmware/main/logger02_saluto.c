/* Saluto all'accensione: "Narmade Har!" (saluto dei pellegrini sulla Narmada) dall'altoparlante della scheda.
 * Codec ES8311 sul bus I2C già aperto dalla camera (GPIO7/8), I2S 9-13, amplificatore PA su GPIO53 (tabella Waveshare). */
#include "freertos/FreeRTOS.h"
#include <stdlib.h>
#include <math.h>
#include "freertos/task.h"
#include "driver/i2s_std.h"
#include "driver/i2c_master.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"
#include "logger02.h"

static const char *TAG = "saluto";

#define SAL_RATE      16000
#define SAL_MCLK_MULT 256
#define SAL_VOLUME    100

extern const uint8_t saluto_start[] asm("_binary_saluto_pcm_start");
extern const uint8_t saluto_end[] asm("_binary_saluto_pcm_end");

static volatile bool s_occupato;               /* I2S/codec in uso: il beep di batteria aspetta il saluto */

/* arg: NULL = saluto "Narmade Har!"; altrimenti = task da avvisare, e suona 3 beep corti (batteria scarica, 24/11) */
static void saluto_task(void *arg)
{
    TaskHandle_t avvisa = (TaskHandle_t)arg;
    s_occupato = true;
    i2c_master_bus_handle_t bus = NULL;
    if (i2c_master_get_bus_handle(0, &bus) != ESP_OK) {
        ESP_LOGE(TAG, "bus I2C 0 non aperto (la camera deve partire prima)");
        s_occupato = false;
        if (avvisa) xTaskNotifyGive(avvisa);
        vTaskDelete(NULL);
    }

    i2s_chan_handle_t tx = NULL;
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.auto_clear = true;
    if (i2s_new_channel(&chan_cfg, &tx, NULL) != ESP_OK) {
        ESP_LOGE(TAG, "I2S non disponibile");
        s_occupato = false;
        if (avvisa) xTaskNotifyGive(avvisa);
        vTaskDelete(NULL);
    }
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SAL_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {.mclk = 13, .bclk = 12, .ws = 10, .dout = 9, .din = I2S_GPIO_UNUSED},
    };
    std_cfg.clk_cfg.mclk_multiple = SAL_MCLK_MULT;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(tx));

    audio_codec_i2c_cfg_t i2c_cfg = {.port = 0, .addr = ES8311_CODEC_DEFAULT_ADDR, .bus_handle = bus};
    audio_codec_i2s_cfg_t i2s_cfg = {.port = I2S_NUM_0, .tx_handle = tx};
    es8311_codec_cfg_t es_cfg = {
        .ctrl_if = audio_codec_new_i2c_ctrl(&i2c_cfg),
        .gpio_if = audio_codec_new_gpio(),
        .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC,
        .master_mode = false,
        .use_mclk = true,
        .pa_pin = 53,
        .hw_gain = {.pa_voltage = 5.0, .codec_dac_voltage = 3.3},
        .mclk_div = SAL_MCLK_MULT,
    };
    esp_codec_dev_cfg_t dev_cfg = {
        .dev_type = ESP_CODEC_DEV_TYPE_OUT,
        .codec_if = es8311_codec_new(&es_cfg),
        .data_if = audio_codec_new_i2s_data(&i2s_cfg),
    };
    esp_codec_dev_handle_t dev = esp_codec_dev_new(&dev_cfg);
    esp_codec_dev_sample_info_t fs = {.bits_per_sample = 16, .channel = 2, .channel_mask = 0x03, .sample_rate = SAL_RATE};
    if (!dev || esp_codec_dev_open(dev, &fs) != ESP_CODEC_DEV_OK) {
        ESP_LOGE(TAG, "codec ES8311 non risponde");
        s_occupato = false;
        if (avvisa) xTaskNotifyGive(avvisa);
        vTaskDelete(NULL);
    }
    esp_codec_dev_set_out_vol(dev, SAL_VOLUME);
    if (avvisa) {
        /* 3 beep da 1 kHz, 150 ms con 150 ms di pausa: distinto dal saluto. "tre beep e niente saluto = batteria scarica" */
        enum { N = SAL_RATE * 150 / 1000 };
        int16_t *b = calloc(N * 2, sizeof(int16_t)), *z = calloc(N * 2, sizeof(int16_t));
        if (b && z) {
            for (int i = 0; i < N; i++) b[2 * i] = b[2 * i + 1] = (int16_t)(20000.0f * sinf(2.0f * 3.14159265f * 1000.0f * i / SAL_RATE));
            for (int k = 0; k < 3; k++) {
                esp_codec_dev_write(dev, b, N * 4);
                esp_codec_dev_write(dev, z, N * 4);
            }
        }
        free(b); free(z);
        ESP_LOGW(TAG, "tre beep: batteria scarica");
    } else {
        esp_codec_dev_write(dev, (void *)saluto_start, saluto_end - saluto_start);
        ESP_LOGI(TAG, "Narmade Har!");
    }
    vTaskDelay(pdMS_TO_TICKS(300));
    esp_codec_dev_close(dev);       /* spegne anche il PA: niente fruscio dopo */
    s_occupato = false;
    if (avvisa) xTaskNotifyGive(avvisa);
    vTaskDelete(NULL);
}

esp_err_t logger02_saluto(void)
{
    return xTaskCreate(saluto_task, "saluto", 6144, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

/* Segnale di batteria scarica prima del sonno (bloccante, max ~6 s): tre beep corti. Aspetta che il saluto abbia finito. */
void logger02_beep_batteria(void)
{
    for (int i = 0; i < 60 && s_occupato; i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (xTaskCreate(saluto_task, "beep", 6144, (void *)xTaskGetCurrentTaskHandle(), 3, NULL) == pdPASS)
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(4000));
}
