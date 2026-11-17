#include <string.h>
#include <stdio.h>
#include "esp_mac.h"
#include "esp_log.h"
#include "logger02.h"

static const char *TAG = "ruolo";

/* MAC della scheda A (letto al primo flash, 17/11/2026). Tutte le altre sono B. */
static const uint8_t MAC_A[6] = {0xe8, 0xf6, 0x0a, 0xe8, 0xcb, 0xae};

const logger02_ruolo_t *logger02_ruolo(void)
{
    static logger02_ruolo_t r;
    static bool fatto;
    if (!fatto) {
        uint8_t mac[6];
        esp_read_mac(mac, ESP_MAC_BASE);
        r.is_a = memcmp(mac, MAC_A, 6) == 0;
        snprintf(r.nome, sizeof(r.nome), "logger02%c", r.is_a ? 'a' : 'b');
        r.ip = r.is_a ? "192.168.1.122" : "192.168.1.124";
        ESP_LOGI(TAG, "MAC %02x:%02x:%02x:%02x:%02x:%02x -> scheda %c (%s, %s)", mac[0], mac[1], mac[2], mac[3], mac[4],
                 mac[5], r.is_a ? 'A' : 'B', r.nome, r.ip);
        fatto = true;
    }
    return &r;
}
