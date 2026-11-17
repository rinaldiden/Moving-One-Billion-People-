/* SD (slot 0, 4 bit, pin 39-44, alimentazione dal LDO interno canale 4 + GPIO45) e ora (SNTP). */
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/gpio.h"
#include "sd_pwr_ctrl_by_on_chip_ldo.h"
#include "nvs.h"
#include "logger02.h"

static const char *TAG = "sd";
static sdmmc_card_t *s_card;
static uint32_t s_boot;

static esp_err_t monta(bool formatta)
{
    gpio_set_direction(L02_PIN_SD_PWR, GPIO_MODE_OUTPUT);
    gpio_set_level(L02_PIN_SD_PWR, 0);              /* PWR_CTRL della Waveshare: basso = SD alimentata */

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.max_freq_khz = SDMMC_FREQ_HIGHSPEED;
    sd_pwr_ctrl_ldo_config_t ldo = {.ldo_chan_id = 4};
    sd_pwr_ctrl_handle_t pwr = NULL;
    if (sd_pwr_ctrl_new_on_chip_ldo(&ldo, &pwr) == ESP_OK) {
        host.pwr_ctrl_handle = pwr;
    }
    sdmmc_slot_config_t slot = SDMMC_SLOT_CONFIG_DEFAULT();
    slot.width = 4;
    slot.clk = 43;
    slot.cmd = 44;
    slot.d0 = 39;
    slot.d1 = 40;
    slot.d2 = 41;
    slot.d3 = 42;
    slot.flags |= SDMMC_SLOT_FLAG_INTERNAL_PULLUP;
    esp_vfs_fat_mount_config_t mc = {.format_if_mount_failed = formatta, .max_files = 8, .allocation_unit_size = 64 * 1024};
    esp_err_t r = esp_vfs_fat_sdmmc_mount(L02_SD, &host, &slot, &mc, &s_card);
    if (r != ESP_OK) {
        ESP_LOGE(TAG, "SD non montata: %s", esp_err_to_name(r));
        return r;
    }
    mkdir(L02_REC_DIR, 0775);
    ESP_LOGI(TAG, "SD montata: %llu MB liberi", logger02_sd_libero_mb());
    return ESP_OK;
}

esp_err_t logger02_sd_monta(void)
{
    uint8_t f = 0;
    nvs_handle_t h;
    if (nvs_open("logger02", NVS_READWRITE, &h) == ESP_OK) {
        nvs_get_u8(h, "formatta", &f);
        if (f) { nvs_set_u8(h, "formatta", 0); nvs_commit(h); }
        nvs_close(h);
    }
    if (f) ESP_LOGW(TAG, "formatto la SD in FAT32 (richiesto)");
    esp_err_t r = monta(f);
    if (r == ESP_OK && f && s_card) {
        r = esp_vfs_fat_sdcard_format(L02_SD, s_card);    /* anche se era già FAT: la ripulisce */
        mkdir(L02_REC_DIR, 0775);
    }
    return r;
}

/* SD exFAT (da 64 GB in su) → FAT32. Solo con l'ok di Daniele: cancella tutto.
 * Si fa al riavvio: il controller SDMMC è condiviso con la C6 (wifi) e non si può spegnere a caldo. */
esp_err_t logger02_sd_formatta(void)
{
    nvs_handle_t h;
    if (nvs_open("logger02", NVS_READWRITE, &h) != ESP_OK) return ESP_FAIL;
    nvs_set_u8(h, "formatta", 1);
    nvs_commit(h);
    nvs_close(h);
    return ESP_OK;
}

uint64_t logger02_sd_libero_mb(void)
{
    uint64_t tot = 0, lib = 0;
    if (!s_card || esp_vfs_fat_info(L02_SD, &tot, &lib) != ESP_OK) {
        return 0;
    }
    return lib / (1024 * 1024);
}

void logger02_ora_init(void)
{
    setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3", 1);
    tzset();
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "192.168.1.1");
    esp_sntp_init();

    nvs_handle_t h;
    if (nvs_open("logger02", NVS_READWRITE, &h) == ESP_OK) {
        nvs_get_u32(h, "boot", &s_boot);
        nvs_set_u32(h, "boot", ++s_boot);
        nvs_commit(h);
        nvs_close(h);
    }
    for (int i = 0; i < 50 && !logger02_ora_valida(); i++) {   /* fino a 5 s: poi si parte lo stesso */
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    ESP_LOGI(TAG, "ora %s, avvio n. %lu", logger02_ora_valida() ? "OK" : "NON ancora valida", (unsigned long)s_boot);
}

bool logger02_ora_valida(void)
{
    return time(NULL) > 1767225600;   /* dopo 1/1/2026 */
}

void logger02_nome_sessione(char *out, size_t n)
{
    if (logger02_ora_valida()) {
        time_t t = time(NULL);
        struct tm tm;
        localtime_r(&t, &tm);
        strftime(out, n, "%Y%m%d_%H%M%S", &tm);
    } else {
        snprintf(out, n, "boot%04lu", (unsigned long)s_boot);
    }
}
