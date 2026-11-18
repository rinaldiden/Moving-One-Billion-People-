/* Tailscale sulla A (MicroLink): il logger02 compare come "logger02" nel tailnet di Daniele, come il logger001.
 * Il server web ascolta su tutte le interfacce: risponde anche sull'IP 100.x. La B resta dietro la A (/b/...).
 * La chiave auth NON è nel firmware (17/11: era finita nel .bin su GitHub). Sta nella NVS della scheda
 * ("logger02"/"ts_key"), scritta una volta con logger02/chiave_tailscale.sh → POST /tskey. Dopo la prima
 * registrazione MicroLink tiene le sue chiavi macchina in NVS ("microlink") e si ricollega anche senza chiave. */
#include <string.h>
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "microlink.h"
#include "logger02.h"

static const char *TAG = "tailscale";
static microlink_t *s_ml;
static char s_chiave[128];   /* deve restare viva: MicroLink tiene il puntatore */

esp_err_t logger02_tailscale_salva_chiave(const char *k)
{
    nvs_handle_t h;
    if (strncmp(k, "tskey-auth-", 11) != 0 || strlen(k) >= sizeof(s_chiave)) return ESP_ERR_INVALID_ARG;
    if (nvs_open("logger02", NVS_READWRITE, &h) != ESP_OK) return ESP_FAIL;
    esp_err_t r = nvs_set_str(h, "ts_key", k);
    if (r == ESP_OK) r = nvs_commit(h);
    nvs_close(h);
    return r;
}

static void stato_cb(microlink_t *ml, microlink_state_t st, void *ctx)
{
    ESP_LOGI(TAG, "stato %d%s", (int)st, microlink_is_connected(ml) ? " (connesso)" : "");
}

esp_err_t logger02_tailscale_start(void)
{
    if (s_ml || !logger02_ruolo()->is_a) return ESP_OK;
    nvs_handle_t h;
    size_t len = sizeof(s_chiave);
    s_chiave[0] = 0;
    if (nvs_open("logger02", NVS_READONLY, &h) == ESP_OK) {
        if (nvs_get_str(h, "ts_key", s_chiave, &len) != ESP_OK) s_chiave[0] = 0;
        nvs_close(h);
    }
    /* "" = nessuna chiave: va bene se la scheda è già registrata (logger02 lo è, scadenza disattivata) */
    ESP_LOGI(TAG, "%s", s_chiave[0] ? "chiave dalla NVS" : "nessuna chiave in NVS: mi ricollego con le chiavi macchina");
    microlink_config_t cfg = {.auth_key = s_chiave, .device_name = logger02_ruolo()->base};
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
