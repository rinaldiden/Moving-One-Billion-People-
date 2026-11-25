/* 25/11: eventi wifi nel registro + rete di sicurezza della A + aggiornamento del firmware del C6.
 * Il 25/11 la A si è svegliata, il wifi si è collegato, dopo ~2 minuti è caduto e non è più tornato (DNS fallito per
 * sempre) finché Daniele non l'ha spenta e riaccesa; nel registro c'erano solo W/E, gli eventi wifi (INFO) no.
 *  - eventi wifi ed esp_hosted scritti come AVVISI (tag "wifi_ev") → finiscono in errori_*.log: disconnessione col
 *    motivo (reason) e l'RSSI, collegamento, IP preso/perso, start/stop, riavvio del C6, guasto del trasporto SDIO.
 *    Gli errori RPC di esp_hosted (rpc_core, livello E) ci finiscono già da soli.
 *    I gestori girano nel task degli eventi (stack 2,3 KB): mettono solo in coda, scrive il task "rete_mon".
 *  - rete di sicurezza (solo A): logica pura in logger02_rete_logic.h (host_test/test_rete_logic.c). */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "lwip/netdb.h"
#include "esp_hosted.h"
#include "esp_hosted_event.h"
#include "esp_hosted_ota.h"
#include "esp_hosted_host_fw_ver.h"
#include "protocol_examples_common.h"
#include "logger02.h"
#include "logger02_rete_logic.h"

static const char *TEV = "wifi_ev";

enum { EV_DISC = 1, EV_CONN, EV_IP, EV_IP_PERSO, EV_START, EV_STOP, EV_C6_INIT, EV_TR_GUASTO, EV_TR_SU, EV_TR_GIU };
typedef struct { uint8_t tipo; int16_t a, b; } ev_t;
static QueueHandle_t s_q;
static volatile int64_t s_noap_t;          /* ultimo "rete non trovata" dal C6 */
static volatile int s_rssi;                /* 0 = non noto */
static volatile int s_ult_motivo;
static volatile uint32_t s_n_disc, s_n_c6_reset;
static volatile int s_fase;
static volatile int64_t s_giu_dal;
static volatile bool s_blocca_reset;       /* prova: il reset del C6 "non funziona" → si arriva al riavvio */

static bool motivo_noap(int r)
{
    return r == WIFI_REASON_NO_AP_FOUND || r == WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY ||
           r == WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD || r == WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD;
}

static void metti(uint8_t tipo, int a, int b)
{
    ev_t e = {.tipo = tipo, .a = (int16_t)a, .b = (int16_t)b};
    if (s_q) xQueueSend(s_q, &e, 0);
}

static void su_wifi(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WIFI_EVENT_STA_DISCONNECTED && data) {
        wifi_event_sta_disconnected_t *d = data;
        s_ult_motivo = d->reason;
        s_n_disc++;
        if (motivo_noap(d->reason)) s_noap_t = esp_timer_get_time();
        metti(EV_DISC, d->reason, d->rssi);
    } else if (id == WIFI_EVENT_STA_CONNECTED && data) {
        metti(EV_CONN, ((wifi_event_sta_connected_t *)data)->channel, 0);
    } else if (id == WIFI_EVENT_STA_START) {
        metti(EV_START, 0, 0);
    } else if (id == WIFI_EVENT_STA_STOP) {
        metti(EV_STOP, 0, 0);
    }
}

static void su_ip(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    metti(id == IP_EVENT_STA_GOT_IP ? EV_IP : EV_IP_PERSO, 0, 0);
}

static void su_hosted(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == ESP_HOSTED_EVENT_CP_INIT) metti(EV_C6_INIT, data ? (int)((esp_hosted_event_init_t *)data)->reason : -1, 0);
    else if (id == ESP_HOSTED_EVENT_TRANSPORT_FAILURE) metti(EV_TR_GUASTO, 0, 0);
    else if (id == ESP_HOSTED_EVENT_TRANSPORT_UP) metti(EV_TR_SU, 0, 0);
    else if (id == ESP_HOSTED_EVENT_TRANSPORT_DOWN) metti(EV_TR_GIU, 0, 0);
}

/* "rete non trovata" ogni 3-5 s quando la bici è fuori casa: nel registro una riga al minuto per motivo, col conto */
static void scrivi_evento(const ev_t *e)
{
    static int ult_motivo = -1, ripetuti;
    static int64_t ult_t;
    int64_t t = esp_timer_get_time();
    switch (e->tipo) {
    case EV_DISC:
        if (e->a == ult_motivo && t - ult_t < 60000000LL) { ripetuti++; return; }
        if (ripetuti) ESP_LOGW(TEV, "(motivo %d ripetuto altre %d volte)", ult_motivo, ripetuti);
        ESP_LOGW(TEV, "disconnesso: motivo %d, rssi %d", e->a, e->b);
        ult_motivo = e->a; ult_t = t; ripetuti = 0;
        break;
    case EV_CONN: ult_motivo = -1; ESP_LOGW(TEV, "collegato all'AP, canale %d", e->a); break;
    case EV_IP: ESP_LOGW(TEV, "IP preso"); break;
    case EV_IP_PERSO: ESP_LOGW(TEV, "IP perso"); break;
    case EV_START: ESP_LOGW(TEV, "wifi C6 avviato"); break;
    case EV_STOP: ESP_LOGW(TEV, "wifi C6 fermato"); break;
    case EV_C6_INIT: ESP_LOGW(TEV, "C6 ripartito (motivo reset del C6: %d)", e->a); break;
    case EV_TR_GUASTO: ESP_LOGE(TEV, "esp_hosted: guasto del trasporto SDIO"); break;
    case EV_TR_SU: ESP_LOGW(TEV, "esp_hosted: trasporto su"); break;
    case EV_TR_GIU: ESP_LOGW(TEV, "esp_hosted: trasporto giu'"); break;
    }
}

static bool ip_ok(void)
{
    esp_netif_t *n = get_example_netif();
    esp_netif_ip_info_t ip;
    return n && esp_netif_is_netif_up(n) && esp_netif_get_ip_info(n, &ip) == ESP_OK && ip.ip.addr != 0;
}

static bool dns_ok(void)
{
    struct addrinfo *res = NULL, hint = {.ai_family = AF_INET};
    if (getaddrinfo("controlplane.tailscale.com", NULL, &hint, &res) == 0 && res) {
        freeaddrinfo(res);
        return true;
    }
    return false;
}

#define NOME(r) esp_err_to_name(r)

/* Reset del C6 senza riavviare la A: esp_hosted da capo (connect_to_slave rimette il C6 in reset col GPIO54), poi il
 * wifi da capo con la stessa configurazione di example_connect. Il gestore di example_connect resta registrato e
 * continua a ritentare sulle disconnessioni. Se qualcosa qui si pianta o va in crash, il passo dopo (riavvio della A)
 * o il riavvio del crash riportano comunque il C6 in reset. */
static volatile bool s_c6_in_corso;
static void c6_reset_task(void *arg)
{
    s_n_c6_reset++;
    if (s_blocca_reset) {
        ESP_LOGW(TEV, "reset C6: SALTATO (prova del riavvio)");
    } else {
        ESP_LOGW(TEV, "reset C6 n.%lu: stop wifi -> %s", (unsigned long)s_n_c6_reset, NOME(esp_wifi_stop()));
        vTaskDelay(pdMS_TO_TICKS(2000));             /* eventi di disconnessione in coda: smaltiti prima del deinit */
        ESP_LOGW(TEV, "reset C6: esp_hosted deinit");
        esp_hosted_deinit();
        esp_hosted_init();
        int r = esp_hosted_connect_to_slave();
        ESP_LOGW(TEV, "reset C6: esp_hosted di nuovo su -> %d", r);
        wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
        esp_err_t e1 = esp_wifi_init(&cfg);
        esp_err_t e2 = esp_wifi_set_storage(WIFI_STORAGE_RAM);
        esp_err_t e3 = esp_wifi_set_mode(WIFI_MODE_STA);
        wifi_config_t wc = {0};
        strlcpy((char *)wc.sta.ssid, CONFIG_EXAMPLE_WIFI_SSID, sizeof(wc.sta.ssid));
        strlcpy((char *)wc.sta.password, CONFIG_EXAMPLE_WIFI_PASSWORD, sizeof(wc.sta.password));
        wc.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
        wc.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
        wc.sta.threshold.rssi = -127;
        wc.sta.threshold.authmode = WIFI_AUTH_OPEN;
        esp_err_t e4 = esp_wifi_set_config(WIFI_IF_STA, &wc);
        esp_err_t e5 = esp_wifi_start();
        esp_err_t e6 = esp_wifi_connect();
        ESP_LOGW(TEV, "reset C6: init %s, storage %s, mode %s, config %s, start %s, connect %s", NOME(e1), NOME(e2),
                 NOME(e3), NOME(e4), NOME(e5), NOME(e6));
    }
    s_c6_in_corso = false;
    vTaskDelete(NULL);
}

static void avvia_reset_c6(void)
{
    if (s_c6_in_corso) return;
    s_c6_in_corso = true;
    if (xTaskCreate(c6_reset_task, "c6_reset", 6144, NULL, 5, NULL) != pdPASS) s_c6_in_corso = false;
}

static void rete_mon(void *arg)
{
    const bool a = logger02_ruolo()->is_a;
    l02_rete_st_t st = {.ok_t = esp_timer_get_time()};
    int64_t prossimo = 0, dns_t = 0, rssi_t = 0, aspetta_log = 0;
    bool dns = false;
    for (;;) {
        ev_t e;
        if (xQueueReceive(s_q, &e, pdMS_TO_TICKS(1000)) == pdTRUE) scrivi_evento(&e);
        int64_t t = esp_timer_get_time();
        if (t < prossimo) continue;
        prossimo = t + 5000000LL;
        bool ip = ip_ok();
        if (!ip) dns = false;
        else if (!dns || t - dns_t >= 30000000LL) { dns = dns_ok(); dns_t = t; }
        if (ip && t - rssi_t >= 60000000LL) {        /* RSSI una volta al minuto (va nel CSV salute) */
            wifi_ap_record_t ap;
            if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) s_rssi = ap.rssi;
            rssi_t = t;
        }
        if (!ip) { s_rssi = 0; rssi_t = 0; }
        if (!a) continue;                            /* B: solo registro */
        l02_rete_in_t in = {.ok = ip && dns, .noap_t = s_noap_t, .pausa = logger02_in_pausa(),
                            .scarico = logger02_scarico_in_corso(), .riavvii = logger02_rete_riavvii()};
        int64_t giu = t - st.ok_t;
        l02_rete_azione_t az = l02_rete_passo(t, &st, &in);
        s_fase = st.fase;
        s_giu_dal = in.ok ? 0 : st.ok_t;
        switch (az) {
        case L02_R_TORNATA:
            ESP_LOGW(TEV, "rete tornata dopo %lld s senza", (long long)(giu / 1000000));
            break;
        case L02_R_RIPROVA:
            ESP_LOGW(TEV, "rete giu' da %lld s (IP %s, DNS %s, ultimo motivo %d): riprovo il collegamento -> %s",
                     (long long)(giu / 1000000), ip ? "si" : "no", dns ? "si" : "no", s_ult_motivo, NOME(esp_wifi_connect()));
            break;
        case L02_R_RESET_C6:
            ESP_LOGE(TEV, "rete giu' da %lld s: reset del C6", (long long)(giu / 1000000));
            avvia_reset_c6();
            break;
        case L02_R_ASPETTA:
            if (!aspetta_log || t - aspetta_log > 300000000LL) {
                ESP_LOGW(TEV, "rete giu' da %lld s anche dopo il reset del C6: riavvio appena %s", (long long)(giu / 1000000),
                         in.scarico ? "finisce lo scarico" : "la bici e' ferma");
                aspetta_log = t;
            }
            break;
        case L02_R_RIAVVIA:
            logger02_riavvio_pulito("rete di sicurezza: rete giu' anche dopo il reset del C6");
            break;
        default:
            break;
        }
    }
}

esp_err_t logger02_rete_sicurezza_start(void)
{
    s_q = xQueueCreate(16, sizeof(ev_t));
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, su_wifi, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, su_ip, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_LOST_IP, su_ip, NULL);
    esp_event_handler_register(ESP_HOSTED_EVENT, ESP_EVENT_ANY_ID, su_hosted, NULL);
    xTaskCreate(rete_mon, "rete_mon", 5120, NULL, 4, NULL);
    return ESP_OK;
}

int logger02_rete_rssi(void)
{
    return s_rssi;
}

void logger02_rete_stato(char *json, size_t n)
{
    int64_t giu = s_giu_dal ? (esp_timer_get_time() - s_giu_dal) / 1000000 : 0;
    snprintf(json, n, "{\"rssi\":%d,\"ultimo_motivo\":%d,\"disconnessioni\":%lu,\"fase\":%d,\"giu_s\":%lld,"
             "\"reset_c6\":%lu,\"riavvii_rete\":%d,\"c6_ota\":\"%s\"}", s_rssi, s_ult_motivo, (unsigned long)s_n_disc,
             s_fase, (long long)giu, (unsigned long)s_n_c6_reset, logger02_rete_riavvii(), logger02_c6_ota_esito());
}

/* prove (POST /rete_prova?azione=...&conferma=si): rete giù provocata per vedere la rete di sicurezza scattare */
esp_err_t logger02_rete_prova(const char *azione, char *out, size_t n)
{
    if (!strcmp(azione, "versione")) {
        esp_hosted_coprocessor_fwver_t v = {0};
        int r = esp_hosted_get_coprocessor_fwversion(&v);
        ESP_LOGW(TEV, "versione C6 (RPC): %s %lu.%lu.%lu", r == ESP_OK ? "ok" : "NON RISPONDE", (unsigned long)v.major1,
                 (unsigned long)v.minor1, (unsigned long)v.patch1);
        snprintf(out, n, "{\"rpc\":%s,\"c6\":\"%lu.%lu.%lu\",\"host\":\"%d.%d.%d\"}", r == ESP_OK ? "true" : "false",
                 (unsigned long)v.major1, (unsigned long)v.minor1, (unsigned long)v.patch1, ESP_HOSTED_VERSION_MAJOR_1,
                 ESP_HOSTED_VERSION_MINOR_1, ESP_HOSTED_VERSION_PATCH_1);
        return ESP_OK;
    }
    if (!logger02_ruolo()->is_a) return ESP_ERR_NOT_SUPPORTED;
    if (!strcmp(azione, "wifi_off") || !strcmp(azione, "wifi_off_blocca")) {
        s_blocca_reset = !strcmp(azione, "wifi_off_blocca");
        logger02_prova_sveglio(600);                 /* 10 min: la prova non deve finire in deep sleep */
        ESP_LOGW(TEV, "PROVA: spengo il wifi del C6 (%s)", s_blocca_reset ? "reset C6 bloccato -> riavvio" : "rete di sicurezza");
        esp_err_t r = esp_wifi_stop();
        snprintf(out, n, "{\"wifi_stop\":\"%s\"}", NOME(r));
        return ESP_OK;
    }
    if (!strcmp(azione, "c6")) {
        logger02_prova_sveglio(600);
        ESP_LOGW(TEV, "PROVA: reset del C6 a mano");
        avvia_reset_c6();
        snprintf(out, n, "{\"reset_c6\":\"avviato\"}");
        return ESP_OK;
    }
    return ESP_ERR_INVALID_ARG;
}

/* ---- aggiornamento del firmware del C6 (esp_hosted slave) dall'host: POST /c6_ota, corpo = network_adapter.bin ----
 * Il C6 scrive nella sua partizione OTA libera; esp_ota_end sul C6 controlla l'immagine (sha256) prima di cambiare
 * partizione di avvio: un trasferimento rovinato viene rifiutato e il C6 resta com'è. Il C6 vecchio (0.0.x) nell'"end"
 * cambia partizione e si riavvia da solo dopo qualche secondo (slave_control.c a166100a): la A si riavvia subito in
 * modo pulito (all'avvio esp_hosted rimette il C6 in reset col GPIO54 → parte il firmware nuovo). */
static uint8_t *s_c6_bin;
static size_t s_c6_len;
static volatile bool s_c6_ota_in_corso;
static char s_c6_esito[96] = "mai fatto";

const char *logger02_c6_ota_esito(void)
{
    return s_c6_esito;
}

static void c6_ota_task(void *arg)
{
    logger02_scarico_inizio();                       /* conta come trasferimento: niente sonno né riavvii di rete */
    int64_t t0 = esp_timer_get_time();
    /* versione del C6 prima: >= 2.6 vuole "activate" dopo l'end; il vecchio (RPC versione assente) cambia da solo */
    esp_hosted_coprocessor_fwver_t v = {0};
    bool nuovo = esp_hosted_get_coprocessor_fwversion(&v) == ESP_OK && (v.major1 > 2 || (v.major1 == 2 && v.minor1 >= 6));
    ESP_LOGW(TEV, "C6 OTA: %u byte, C6 ora %lu.%lu.%lu (%s), begin", (unsigned)s_c6_len, (unsigned long)v.major1,
             (unsigned long)v.minor1, (unsigned long)v.patch1, nuovo ? "con activate" : "vecchio, senza activate");
    esp_err_t r = esp_hosted_slave_ota_begin();
    size_t fatto = 0;
    if (r == ESP_OK) {
        while (fatto < s_c6_len) {
            size_t k = s_c6_len - fatto > 1400 ? 1400 : s_c6_len - fatto;
            r = esp_hosted_slave_ota_write(s_c6_bin + fatto, k);
            if (r != ESP_OK) break;
            fatto += k;
            if (fatto % (1400 * 200) == 0) ESP_LOGW(TEV, "C6 OTA: %u/%u", (unsigned)fatto, (unsigned)s_c6_len);
        }
    }
    esp_err_t re = ESP_FAIL;
    if (r == ESP_OK) re = esp_hosted_slave_ota_end();
    snprintf(s_c6_esito, sizeof(s_c6_esito), "begin/write %s a %u/%u, end %s, %lld s", NOME(r), (unsigned)fatto,
             (unsigned)s_c6_len, r == ESP_OK ? NOME(re) : "-", (long long)((esp_timer_get_time() - t0) / 1000000));
    ESP_LOGW(TEV, "C6 OTA: %s", s_c6_esito);
    free(s_c6_bin);
    s_c6_bin = NULL;
    logger02_scarico_fine();
    if (r == ESP_OK && re == ESP_OK) {
        if (nuovo) ESP_LOGW(TEV, "C6 OTA: activate %s", NOME(esp_hosted_slave_ota_activate()));
        /* il C6 vecchio ha già cambiato partizione nell'end e si sta riavviando: riavvio pulito subito */
        logger02_riavvio_pulito("C6 aggiornato: riavvio la A per ripartire col C6 nuovo");
    }
    s_c6_ota_in_corso = false;
    vTaskDelete(NULL);
}

/* buf in PSRAM, già controllato dal chiamante (web); ne prende la proprietà */
esp_err_t logger02_c6_ota(uint8_t *buf, size_t len)
{
    if (s_c6_ota_in_corso) { free(buf); return ESP_ERR_INVALID_STATE; }
    s_c6_ota_in_corso = true;
    s_c6_bin = buf;
    s_c6_len = len;
    logger02_prova_sveglio(600);
    if (xTaskCreate(c6_ota_task, "c6_ota", 6144, NULL, 5, NULL) != pdPASS) {
        free(buf);
        s_c6_bin = NULL;
        s_c6_ota_in_corso = false;
        return ESP_FAIL;
    }
    return ESP_OK;
}
