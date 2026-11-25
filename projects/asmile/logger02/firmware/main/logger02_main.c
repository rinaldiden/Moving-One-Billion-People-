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
#include "driver/gpio.h"
#include "nvs_flash.h"
#include "mdns.h"
#include "lwip/apps/netbiosns.h"
#include "protocol_examples_common.h"
#include "example_video_common.h"
#include "freertos/event_groups.h"
#include "lwip/netdb.h"
#include "logger02.h"

static const char *TAG = "logger02";
static EventGroupHandle_t s_ev;

/* wifi in background: riprova all'infinito (CONFIG_EXAMPLE_WIFI_CONN_MAX_RETRY=-1), la registrazione non lo aspetta */
/* firmware appena arrivato via OTA: se in 2 minuti la rete non va, riavvio → il bootloader torna alla versione buona */
/* Firmware nuovo (OTA): si conferma SOLO dopo 3 minuti di rete che funziona davvero (DNS risolto), se no si torna al
 * precedente. 18/11: un firmware col wifi che moriva dopo ~60 s era stato confermato al primo IP → niente rollback. */
static bool rete_vera(void)
{
    for (int i = 0; i < 3; i++) {
        struct addrinfo *res = NULL, hint = {.ai_family = AF_INET};
        if (getaddrinfo("controlplane.tailscale.com", NULL, &hint, &res) == 0 && res) {
            freeaddrinfo(res);
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
    return false;
}

static void guardia_ota(void *arg)
{
    esp_ota_img_states_t st;
    if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY) {
        if (!(xEventGroupWaitBits(s_ev, 1, pdFALSE, pdTRUE, pdMS_TO_TICKS(120000)) & 1)) {
            ESP_LOGE(TAG, "firmware nuovo senza rete: torno al precedente");
            esp_ota_mark_app_invalid_rollback_and_reboot();
        }
        vTaskDelay(pdMS_TO_TICKS(180000));
        if (!rete_vera()) {
            ESP_LOGE(TAG, "firmware nuovo: dopo 3 minuti la rete non passa dati, torno al precedente");
            esp_ota_mark_app_invalid_rollback_and_reboot();
        }
        esp_ota_mark_app_valid_cancel_rollback();
        ESP_LOGI(TAG, "firmware nuovo confermato (3 min di rete vera)");
    }
    vTaskDelete(NULL);
}

static void rete_task(void *arg)
{
    vTaskDelay(pdMS_TO_TICKS(300));                   /* la C6 appena sbloccata ha bisogno di un attimo */
    if (example_connect() == ESP_OK) {
        logger02_ip_fisso();
        mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0);
        xEventGroupSetBits(s_ev, 1);
        ESP_LOGI(TAG, "wifi connesso");
        if (!logger02_ruolo()->is_a) {             /* la B dice alla A il suo IP (ogni 30 s: la A può riavviarsi) */
            esp_netif_ip_info_t ip;
            char m[32];
            for (int k = 0; esp_netif_get_ip_info(get_example_netif(), &ip) == ESP_OK; k++) {
                if (k % 3 == 0) {
                    snprintf(m, sizeof(m), "I " IPSTR, IP2STR(&ip.ip));
                    logger02_link_invia(m);
                }
                snprintf(m, sizeof(m), "N %d", logger02_rec_da_scaricare_moto());   /* 25/11: pezzi IN MOTO ancora da scaricare */
                logger02_link_invia(m);
                vTaskDelay(pdMS_TO_TICKS(10000));
            }
        }
        logger02_tailscale_start();         /* A: compare come "loggerNN" su Tailscale */
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
    logger02_salute_presto();
    logger02_riavvio_init();               /* 25/11: stato salvato da un riavvio pulito della rete di sicurezza */
    /* al risveglio dal deep sleep: sblocca i pin tenuti fermi (la C6 poi la gestisce esp_hosted, come prima) */
    const int sblocca[] = {L02_PIN_C6_EN, L02_PIN_SD_PWR, L02_PIN_PA, L02_PIN_WAKE, L02_PIN_ETH_RST};
    for (size_t i = 0; i < sizeof(sblocca) / sizeof(sblocca[0]); i++) gpio_hold_dis(sblocca[i]);
    ESP_ERROR_CHECK(example_video_init());
    logger02_saluto();
    const logger02_ruolo_t *ru = logger02_ruolo();
    ESP_LOGI(TAG, "scheda %c, risveglio: %d", ru->is_a ? 'A' : 'B', (int)esp_sleep_get_wakeup_cause());

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(mdns_init());
    mdns_hostname_set(ru->nome);
    netbiosns_init();
    netbiosns_set_name(ru->nome);
    logger02_link_init();                  /* prima del wifi: SYNC e WAKE subito attivi */
    s_ev = xEventGroupCreate();
    logger02_rete_sicurezza_start();       /* 25/11: eventi wifi nel registro + (A) rete di sicurezza */
    xTaskCreate(rete_task, "rete", 6144, NULL, 5, NULL);
    xTaskCreate(guardia_ota, "guardia_ota", 4096, NULL, 5, NULL);
    if (!(xEventGroupWaitBits(s_ev, 1, pdFALSE, pdTRUE, pdMS_TO_TICKS(15000)) & 1)) {
        ESP_LOGW(TAG, "wifi non ancora connesso: registro lo stesso, lui continua a riprovare");
    }
    logger02_ora_init();
    if (logger02_sd_monta() == ESP_OK) {
        logger02_rec_start();
        logger02_salute_start();
    }
    if (ru->is_a) {
        logger02_imu_start();
    }
    logger02_web_start();
    ESP_LOGI(TAG, "pronto");
}
