#include "esp_netif.h"
#include "esp_log.h"
#include "lwip/ip4_addr.h"
#include "lwip/def.h"
#include "protocol_examples_common.h"
#include "logger02.h"

static const char *TAG = "rete";

esp_err_t logger02_ip_fisso(void)
{
    esp_netif_t *netif = get_example_netif();
    if (!logger02_ruolo()->ip) return ESP_OK;      /* B dei logger nuovi: DHCP */
    if (!netif) {
        return ESP_FAIL;
    }
    /* Con lo stesso nome EOLO_378899 ci sono DUE reti: casa (192.168.1.x) e un'altra (10.16.156.x).
     * L'IP fisso va messo SOLO sulla rete di casa: sull'altra si tiene quello del DHCP (17/11, idea di Daniele). */
    esp_netif_ip_info_t dhcp;
    if (esp_netif_get_ip_info(netif, &dhcp) == ESP_OK && (ntohl(dhcp.ip.addr) & 0xFFFFFF00) != 0xC0A80100) {
        ESP_LOGW(TAG, "rete diversa da casa (" IPSTR "): tengo l'IP del DHCP, niente IP fisso", IP2STR(&dhcp.ip));
        return ESP_OK;
    }
    esp_netif_ip_info_t ip = {0};
    ip.ip.addr = ipaddr_addr(logger02_ruolo()->ip);
    ip.gw.addr = ipaddr_addr("192.168.1.1");
    ip.netmask.addr = ipaddr_addr("255.255.255.0");
    esp_netif_dhcpc_stop(netif);
    ESP_ERROR_CHECK(esp_netif_set_ip_info(netif, &ip));
    esp_netif_dns_info_t dns = {.ip.u_addr.ip4.addr = ipaddr_addr("192.168.1.1"), .ip.type = ESP_IPADDR_TYPE_V4};
    esp_netif_set_dns_info(netif, ESP_NETIF_DNS_MAIN, &dns);
    ESP_LOGI(TAG, "IP fisso %s (EOLO)", logger02_ruolo()->ip);
    return ESP_OK;
}
