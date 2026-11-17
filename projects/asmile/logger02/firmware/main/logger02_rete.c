#include "esp_netif.h"
#include "esp_log.h"
#include "lwip/ip4_addr.h"
#include "protocol_examples_common.h"
#include "logger02.h"

static const char *TAG = "rete";

esp_err_t logger02_ip_fisso(void)
{
    esp_netif_t *netif = get_example_netif();
    if (!netif) {
        return ESP_FAIL;
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
