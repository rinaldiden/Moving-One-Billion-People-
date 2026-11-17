/* Tailscale sulla A (MicroLink): il logger02 compare come "logger02" nel tailnet di Daniele, come il logger001.
 * Il server web ascolta su tutte le interfacce: risponde anche sull'IP 100.x. La B resta dietro la A (/b/...). */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "microlink.h"
#include "logger02.h"

static const char *TAG = "tailscale";
static microlink_t *s_ml;

static void stato_cb(microlink_t *ml, microlink_state_t st, void *ctx)
{
    ESP_LOGI(TAG, "stato %d%s", (int)st, microlink_is_connected(ml) ? " (connesso)" : "");
}

esp_err_t logger02_tailscale_start(void)
{
    if (s_ml || !logger02_ruolo()->is_a) return ESP_OK;
    if (strlen(CONFIG_L02_TS_AUTHKEY) < 20) {
        ESP_LOGW(TAG, "nessuna chiave: Tailscale spento");
        return ESP_ERR_INVALID_STATE;
    }
    microlink_config_t cfg = {.auth_key = CONFIG_L02_TS_AUTHKEY, .device_name = CONFIG_L02_TS_NOME};
    s_ml = microlink_init(&cfg);
    if (!s_ml) return ESP_FAIL;
    microlink_set_state_callback(s_ml, stato_cb, NULL);
    return microlink_start(s_ml);
}

void logger02_tailscale_stato(char *out, size_t n)
{
    if (!s_ml) {
        snprintf(out, n, "{\"attivo\":false}");
        return;
    }
    uint32_t ip = microlink_get_vpn_ip(s_ml);
    snprintf(out, n, "{\"attivo\":true,\"connesso\":%s,\"ip\":\"%lu.%lu.%lu.%lu\"}", microlink_is_connected(s_ml) ? "true" : "false",
             (unsigned long)(ip >> 24) & 255, (unsigned long)(ip >> 16) & 255, (unsigned long)(ip >> 8) & 255,
             (unsigned long)ip & 255);
}
