#include <string.h>
#include <stdio.h>
#include "esp_mac.h"
#include "esp_log.h"
#include "nvs.h"
#include "logger02.h"

static const char *TAG = "ruolo";

/* Identità della scheda, scritta UNA volta al primo flash da logger02/flasha_nuovo.sh nella NVS "ident"
 * (18/11/2026, Daniele: ogni logger nuovo = logger03, 04... con un solo IP fisso crescente, quello della A):
 *   nome  = "logger03"   (Tailscale; hostname = nome + a/b)
 *   ruolo = 'A' o 'B'
 *   ip    = IP fisso su EOLO, solo la A (la B prende il DHCP e lo dice alla A con "I <ip>")
 * NVS vuota = logger02 di prima: A riconosciuta dal MAC, IP .122/.124 (così le due schede già montate non cambiano). */
static const uint8_t MAC_A_LOGGER02[6] = {0xe8, 0xf6, 0x0a, 0xe8, 0xcb, 0xae};

const logger02_ruolo_t *logger02_ruolo(void)
{
    static logger02_ruolo_t r;
    static char ip[16];
    static bool fatto;
    if (fatto) return &r;
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BASE);
    nvs_handle_t h;
    bool da_nvs = false;
    if (nvs_open("ident", NVS_READONLY, &h) == ESP_OK) {
        uint8_t ru = 0;
        size_t ln = sizeof(r.base), li = sizeof(ip);
        if (nvs_get_str(h, "nome", r.base, &ln) == ESP_OK && nvs_get_u8(h, "ruolo", &ru) == ESP_OK && (ru == 'A' || ru == 'B')) {
            r.is_a = ru == 'A';
            if (nvs_get_str(h, "ip", ip, &li) != ESP_OK) ip[0] = 0;
            da_nvs = true;
        }
        nvs_close(h);
    }
    if (!da_nvs) {
        r.is_a = memcmp(mac, MAC_A_LOGGER02, 6) == 0;
        strcpy(r.base, "logger02");
        strcpy(ip, r.is_a ? "192.168.1.122" : "192.168.1.124");
    }
    snprintf(r.nome, sizeof(r.nome), "%s%c", r.base, r.is_a ? 'a' : 'b');
    r.ip = ip[0] ? ip : NULL;
    ESP_LOGI(TAG, "MAC %02x:%02x:%02x:%02x:%02x:%02x -> %s scheda %c (%s, %s)%s", mac[0], mac[1], mac[2], mac[3], mac[4],
             mac[5], r.base, r.is_a ? 'A' : 'B', r.nome, r.ip ? r.ip : "DHCP", da_nvs ? "" : " [NVS ident vuota: logger02]");
    fatto = true;
    return &r;
}
