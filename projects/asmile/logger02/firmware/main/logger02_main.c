/* logger02 (HW3): porta del logger001 su 2 × ESP32-P4. Ordine di partenza:
 * camera (deve partire subito dopo il reset) → saluto → rete (wifi C6, IP fisso) → ora → SD → link A↔B
 * → registrazione → (A) IMU + batteria + autospegnimento → server web. */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_sleep.h"
#include "esp_ota_ops.h"
#include "nvs_flash.h"
#include "mdns.h"
#include "lwip/apps/netbiosns.h"
#include "protocol_examples_common.h"
#include "example_video_common.h"
#include "freertos/event_groups.h"
#include "logger02.h"

static const char *TAG = "logger02";
static EventGroupHandle_t s_ev;

/* wifi in background: riprova all'infinito (CONFIG_EXAMPLE_WIFI_CONN_MAX_RETRY=-1), la registrazione non lo aspetta */
static void rete_task(void *arg)
{
    if (example_connect() == ESP_OK) {
        logger02_ip_fisso();
        mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0);
        xEventGroupSetBits(s_ev, 1);
        ESP_LOGI(TAG, "wifi connesso");
    }
    vTaskDelete(NULL);
}

void app_main(void)
{
    esp_err_t r = nvs_flash_init();
    if (r == ESP_ERR_NVS_NO_FREE_PAGES || r == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }
    ESP_ERROR_CHECK(example_video_init());
    logger02_saluto();
    const logger02_ruolo_t *ru = logger02_ruolo();
    ESP_LOGI(TAG, "scheda %c, risveglio: %d", ru->is_a ? 'A' : 'B', (int)esp_sleep_get_wakeup_cause());
    esp_ota_mark_app_valid_cancel_rollback();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(mdns_init());
    mdns_hostname_set(ru->nome);
    netbiosns_init();
    netbiosns_set_name(ru->nome);
    logger02_link_init();                  /* prima del wifi: SYNC e WAKE subito attivi */
    s_ev = xEventGroupCreate();
    xTaskCreate(rete_task, "rete", 6144, NULL, 5, NULL);
    if (!(xEventGroupWaitBits(s_ev, 1, pdFALSE, pdTRUE, pdMS_TO_TICKS(15000)) & 1)) {
        ESP_LOGW(TAG, "wifi non ancora connesso: registro lo stesso, lui continua a riprovare");
    }
    logger02_ora_init();
    if (logger02_sd_monta() == ESP_OK) {
        logger02_rec_start();
    }
    if (ru->is_a) {
        logger02_imu_start();
    }
    logger02_web_start();
    ESP_LOGI(TAG, "pronto");
}
