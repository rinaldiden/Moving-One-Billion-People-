/* Saluto all'accensione: "Narmade Har!" (saluto dei pellegrini sulla Narmada) dall'altoparlante della scheda.
 * Codec ES8311 sul bus I2C già aperto dalla camera (GPIO7/8), I2S 9-13, amplificatore PA su GPIO53 (tabella Waveshare). */
#include "freertos/FreeRTOS.h"
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

static void saluto_task(void *arg)
{
    i2c_master_bus_handle_t bus = NULL;
    if (i2c_master_get_bus_handle(0, &bus) != ESP_OK) {
        ESP_LOGE(TAG, "bus I2C 0 non aperto (la camera deve partire prima)");
        vTaskDelete(NULL);
    }

    i2s_chan_handle_t tx = NULL;
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx, NULL));
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
        vTaskDelete(NULL);
    }
    esp_codec_dev_set_out_vol(dev, SAL_VOLUME);
    esp_codec_dev_write(dev, (void *)saluto_start, saluto_end - saluto_start);
    ESP_LOGI(TAG, "Narmade Har!");
    vTaskDelay(pdMS_TO_TICKS(300));
    esp_codec_dev_close(dev);       /* spegne anche il PA: niente fruscio dopo */
    vTaskDelete(NULL);
}

esp_err_t logger02_saluto(void)
{
    return xTaskCreate(saluto_task, "saluto", 6144, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}
