/* A: sensore ruota BLE (Cycling Speed and Cadence, servizio 0x1816, misura 0x2A5B) via il Bluetooth del C6 (esp_hosted,
 * NimBLE sul P4). CSV ruota_<sessione>_<pezzo>.csv con lo stesso orologio di frame e IMU (t_us della A):
 *   t_us,frame,giri,t_evento_1024      giri = giri ruota cumulativi, t_evento_1024 = tempo dell'ultimo giro (1/1024 s)
 * La velocita' NON si calcola qui: la fa il Mac (circonferenza per bici).
 *
 * Accoppiamento AUTOMATICO (Daniele 26/11: sui logger nuovi nessuno configura a mano, niente nome nel codice):
 *  - sensore salvato in NVS "ruota" → mi collego solo a lui;
 *  - nessun sensore salvato → cerco il servizio 0x1816, prendo il segnale piu' forte sopra RUOTA_RSSI_MIN, mi collego
 *    e lo metto in PROVA: lo salvo solo se i giri aumentano PROVA_OK volte mentre l'IMU dice che la bici si muove.
 *    Giri che aumentano a bici ferma = ruota di un'altra bici → scartato (lista nera per NERA_S), riprovo un altro.
 *  - POST /ruota/dimentica cancella il sensore salvato (cambio sensore).
 * Solo la A; la B ha lo stesso firmware ma non avvia nulla di questo. */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "esp_hosted.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/util/util.h"
#include "logger02.h"

static const char *TAG = "ruota";

#define UUID_CSC        0x1816
#define UUID_MISURA     0x2A5B
#define RUOTA_RSSI_MIN  (-70)      /* sotto: troppo lontano per essere sulla nostra bici */
#define CERCA_MS        4000       /* una passata di ricerca */
#define PROVA_OK        3          /* aumenti dei giri a bici in moto per accettare il sensore */
#define PROVA_MOTO_S    30         /* secondi di bici in moto senza aumenti → non e' il nostro */
#define NERA_S          300
#define CONNETTI_MS     15000

typedef enum { R_INIZIO, R_CERCA, R_CONNETTE, R_SCOPRE, R_PROVA, R_OK } stato_t;
static const char *NOMI[] = {"inizio", "cerca", "connette", "scopre", "prova", "connesso"};

static volatile stato_t s_st = R_INIZIO;
static volatile bool s_sync, s_cercando, s_dimentica;
static uint8_t s_own;
static uint16_t s_conn = BLE_HS_CONN_HANDLE_NONE;
static uint16_t s_val, s_fine;
static ble_addr_t s_salvato, s_cand;
static bool s_ha_salvato;
static int s_cand_rssi, s_rssi;
static struct { ble_addr_t a; int64_t fino; } s_nera[4];
static uint32_t s_giri, s_prev_giri, s_notifiche;
static uint16_t s_t1024;
static bool s_prev_ok;
static int s_prova_ok;
static int64_t s_prova_moto_us, s_ultimo_us, s_ultimo_check;
static FILE *s_csv;
static char s_sess[24];
static uint32_t s_pezzo;
static int64_t s_pezzo_t0;
static volatile bool s_chiuso;
static char s_c6[24] = "?";

static void addr_str(const ble_addr_t *a, char *o, size_t n)
{
    snprintf(o, n, "%02x:%02x:%02x:%02x:%02x:%02x", a->val[5], a->val[4], a->val[3], a->val[2], a->val[1], a->val[0]);
}

/* ---- NVS ---- */
static void nvs_carica(void)
{
    nvs_handle_t h;
    size_t n = sizeof(s_salvato);
    if (nvs_open("ruota", NVS_READONLY, &h) != ESP_OK) return;
    s_ha_salvato = nvs_get_blob(h, "addr", &s_salvato, &n) == ESP_OK && n == sizeof(s_salvato);
    nvs_close(h);
}

static void nvs_salva(const ble_addr_t *a)
{
    nvs_handle_t h;
    if (nvs_open("ruota", NVS_READWRITE, &h) != ESP_OK) return;
    if (a) nvs_set_blob(h, "addr", a, sizeof(*a)); else nvs_erase_key(h, "addr");
    nvs_commit(h);
    nvs_close(h);
}

/* ---- CSV, un pezzo al minuto come l'IMU ---- */
static void apri_csv(void)
{
    char p[112];
    if (!s_sess[0]) logger02_nome_sessione(s_sess, sizeof(s_sess));
    snprintf(p, sizeof(p), L02_REC_DIR "/ruota_%s_%05lu.csv", s_sess, (unsigned long)s_pezzo++);
    s_pezzo_t0 = esp_timer_get_time();
    s_csv = fopen(p, "w");
    if (s_csv) {
        setvbuf(s_csv, NULL, _IOFBF, 4096);
        fprintf(s_csv, "t_us,frame,giri,t_evento_1024\n");
    }
}

void logger02_ruota_chiudi(void)
{
    s_chiuso = true;                 /* da qui niente scritture: deep sleep o riavvio pulito */
    if (s_csv) { fclose(s_csv); s_csv = NULL; }
}

/* ---- lista nera (sensori scartati in prova) ---- */
static bool in_nera(const ble_addr_t *a, int64_t t)
{
    for (int i = 0; i < 4; i++) if (s_nera[i].fino > t && !ble_addr_cmp(&s_nera[i].a, a)) return true;
    return false;
}

static void metti_in_nera(const ble_addr_t *a)
{
    int k = 0;
    for (int i = 1; i < 4; i++) if (s_nera[i].fino < s_nera[k].fino) k = i;
    s_nera[k].a = *a;
    s_nera[k].fino = esp_timer_get_time() + NERA_S * 1000000LL;
}

static void scarta(const char *perche)
{
    char a[20];
    addr_str(&s_cand, a, sizeof(a));
    ESP_LOGW(TAG, "sensore %s scartato: %s", a, perche);
    metti_in_nera(&s_cand);
    if (s_conn != BLE_HS_CONN_HANDLE_NONE) ble_gap_terminate(s_conn, BLE_ERR_REM_USER_CONN_TERM);
}

/* ---- misura ---- */
static void misura(const uint8_t *b, int n)
{
    if (n < 1) return;
    if (!(b[0] & 1) || n < 7) {      /* niente giri ruota: sensore in modalita' cadenza */
        if (s_st == R_PROVA) scarta("manda la cadenza, non i giri ruota");
        return;
    }
    uint32_t giri = b[1] | b[2] << 8 | b[3] << 16 | (uint32_t)b[4] << 24;
    uint16_t t1024 = b[5] | b[6] << 8;
    int64_t t = esp_timer_get_time();
    bool nuovo = s_prev_ok && (giri != s_prev_giri);
    if (s_st == R_PROVA && nuovo) {
        if (!logger02_imu_in_moto()) { scarta("i giri aumentano ma la bici e' ferma: e' un'altra bici"); return; }
        if (giri > s_prev_giri && ++s_prova_ok >= PROVA_OK) {
            char a[20];
            addr_str(&s_cand, a, sizeof(a));
            s_salvato = s_cand; s_ha_salvato = true;
            nvs_salva(&s_salvato);
            s_st = R_OK;
            ESP_LOGI(TAG, "sensore %s accoppiato e salvato", a);
        }
    }
    s_prev_giri = giri; s_prev_ok = true;
    s_giri = giri; s_t1024 = t1024; s_notifiche++; s_ultimo_us = t;
    if (s_st == R_OK && !s_chiuso) {
        if (!s_csv) apri_csv();
        if (s_csv) {
            fprintf(s_csv, "%lld,%lu,%lu,%u\n", (long long)t, (unsigned long)logger02_rec_frame(), (unsigned long)giri, t1024);
            if (t - s_pezzo_t0 > 60000000LL) { fclose(s_csv); s_csv = NULL; }
        }
    }
}

/* ---- GATT: servizio → caratteristica → descrittore 0x2902 → notifiche ---- */
static int su_dsc(uint16_t c, const struct ble_gatt_error *e, uint16_t chr, const struct ble_gatt_dsc *d, void *arg)
{
    static uint16_t cccd;
    if (e->status == 0 && d && !ble_uuid_cmp(&d->uuid.u, BLE_UUID16_DECLARE(BLE_GATT_DSC_CLT_CFG_UUID16))) cccd = d->handle;
    if (e->status == BLE_HS_EDONE) {
        uint8_t on[2] = {1, 0};
        if (!cccd) cccd = s_val + 1;             /* quasi tutti i sensori lo mettono subito dopo il valore */
        if (ble_gattc_write_flat(c, cccd, on, 2, NULL, NULL) == 0) {
            s_prev_ok = false; s_prova_ok = 0; s_prova_moto_us = 0;
            s_st = s_ha_salvato ? R_OK : R_PROVA;
            ESP_LOGI(TAG, "notifiche attive (%s)", NOMI[s_st]);
        } else {
            ble_gap_terminate(c, BLE_ERR_REM_USER_CONN_TERM);
        }
        cccd = 0;
    }
    return 0;
}

static int su_chr(uint16_t c, const struct ble_gatt_error *e, const struct ble_gatt_chr *ch, void *arg)
{
    if (e->status == 0 && ch) s_val = ch->val_handle;
    else if (e->status == BLE_HS_EDONE) {
        if (s_val && ble_gattc_disc_all_dscs(c, s_val, s_fine, su_dsc, NULL) == 0) return 0;
        ble_gap_terminate(c, BLE_ERR_REM_USER_CONN_TERM);
    }
    return 0;
}

static int su_svc(uint16_t c, const struct ble_gatt_error *e, const struct ble_gatt_svc *s, void *arg)
{
    if (e->status == 0 && s) { s_fine = s->end_handle; s_val = 0;
        if (ble_gattc_disc_chrs_by_uuid(c, s->start_handle, s->end_handle, BLE_UUID16_DECLARE(UUID_MISURA), su_chr, NULL))
            ble_gap_terminate(c, BLE_ERR_REM_USER_CONN_TERM);
    } else if (e->status != BLE_HS_EDONE) {
        ble_gap_terminate(c, BLE_ERR_REM_USER_CONN_TERM);
    }
    return 0;
}

static bool annuncia_csc(const struct ble_gap_disc_desc *d)
{
    struct ble_hs_adv_fields f;
    if (ble_hs_adv_parse_fields(&f, d->data, d->length_data) != 0) return false;
    for (int i = 0; i < f.num_uuids16; i++) if (ble_uuid_u16(&f.uuids16[i].u) == UUID_CSC) return true;
    return false;
}

static int evento(struct ble_gap_event *ev, void *arg)
{
    switch (ev->type) {
    case BLE_GAP_EVENT_DISC:
        if (annuncia_csc(&ev->disc) && ev->disc.rssi > RUOTA_RSSI_MIN && ev->disc.rssi > s_cand_rssi &&
            !in_nera(&ev->disc.addr, esp_timer_get_time())) {
            s_cand = ev->disc.addr; s_cand_rssi = ev->disc.rssi;
        }
        return 0;
    case BLE_GAP_EVENT_DISC_COMPLETE:
        s_cercando = false;
        return 0;
    case BLE_GAP_EVENT_CONNECT:
        if (ev->connect.status == 0) {
            s_conn = ev->connect.conn_handle; s_st = R_SCOPRE;
            if (ble_gattc_disc_svc_by_uuid(s_conn, BLE_UUID16_DECLARE(UUID_CSC), su_svc, NULL))
                ble_gap_terminate(s_conn, BLE_ERR_REM_USER_CONN_TERM);
        } else {
            s_st = R_CERCA;
        }
        return 0;
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGW(TAG, "sensore perso (motivo %d): lo ricerco", ev->disconnect.reason);
        s_conn = BLE_HS_CONN_HANDLE_NONE; s_st = R_CERCA;
        if (s_csv) { fclose(s_csv); s_csv = NULL; }
        return 0;
    case BLE_GAP_EVENT_NOTIFY_RX: {
        uint8_t b[24];
        int n = OS_MBUF_PKTLEN(ev->notify_rx.om);
        if (n > (int)sizeof(b)) n = sizeof(b);
        if (ev->notify_rx.attr_handle == s_val && os_mbuf_copydata(ev->notify_rx.om, 0, n, b) == 0) misura(b, n);
        return 0;
    }
    default:
        return 0;
    }
}

/* ---- regista: una decisione ogni mezzo secondo ---- */
static void regista(void *arg)
{
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(500));
        if (!s_sync || s_chiuso) continue;
        int64_t t = esp_timer_get_time();
        if (s_dimentica) {
            s_dimentica = false;
            nvs_salva(NULL); s_ha_salvato = false;
            ESP_LOGW(TAG, "sensore dimenticato: ne cerco uno nuovo");
            if (s_conn != BLE_HS_CONN_HANDLE_NONE) ble_gap_terminate(s_conn, BLE_ERR_REM_USER_CONN_TERM);
            else s_st = R_CERCA;
            continue;
        }
        if (s_st == R_PROVA) {                    /* in moto senza aumenti per PROVA_MOTO_S → non e' il nostro */
            if (logger02_imu_in_moto()) s_prova_moto_us += t - s_ultimo_check;
            if (s_prova_moto_us > PROVA_MOTO_S * 1000000LL) scarta("bici in moto e i giri non aumentano");
        }
        s_ultimo_check = t;
        if (s_st == R_INIZIO) s_st = R_CERCA;
        if (s_st != R_CERCA || s_cercando || ble_gap_conn_active()) continue;
        if (s_ha_salvato) {                       /* sensore noto: mi collego direttamente a lui */
            s_cand = s_salvato;
            if (ble_gap_connect(s_own, &s_salvato, CONNETTI_MS, NULL, evento, NULL) == 0) s_st = R_CONNETTE;
            continue;
        }
        if (s_cand_rssi > -127) {                 /* fine di una passata: il piu' forte trovato */
            char a[20];
            addr_str(&s_cand, a, sizeof(a));
            ESP_LOGI(TAG, "candidato %s rssi %d: lo provo", a, s_cand_rssi);
            s_rssi = s_cand_rssi; s_cand_rssi = -127;
            if (ble_gap_connect(s_own, &s_cand, CONNETTI_MS, NULL, evento, NULL) == 0) { s_st = R_CONNETTE; continue; }
        }
        struct ble_gap_disc_params dp = {.itvl = 0x50, .window = 0x30, .filter_duplicates = 1};
        s_cand_rssi = -127;
        if (ble_gap_disc(s_own, CERCA_MS, &dp, evento, NULL) == 0) s_cercando = true;
    }
}

static void su_sync(void)
{
    ble_hs_util_ensure_addr(0);
    ble_hs_id_infer_auto(0, &s_own);
    s_sync = true;
}

static void su_reset(int motivo)
{
    s_sync = false;
    ESP_LOGW(TAG, "stack BLE resettato (%d)", motivo);
}

static void host_task(void *arg)
{
    nimble_port_run();
    nimble_port_freertos_deinit();
}

static void avvio(void *arg)
{
    /* il wifi ha gia' agganciato il C6: aspetto che la rete parta per non disturbare il primo collegamento */
    vTaskDelay(pdMS_TO_TICKS(20000));
    esp_hosted_coprocessor_fwver_t v;
    if (esp_hosted_get_coprocessor_fwversion(&v) == ESP_OK)
        snprintf(s_c6, sizeof(s_c6), "%lu.%lu.%lu", (unsigned long)v.major1, (unsigned long)v.minor1, (unsigned long)v.patch1);
    /* da esp_hosted 2.5.2 il controller BT del C6 parte spento: lo accendo. Firmware C6 piu' vecchi lo hanno gia' acceso
     * e rispondono errore: vado avanti lo stesso. */
    if (esp_hosted_bt_controller_init() != ESP_OK) ESP_LOGW(TAG, "init controller BT del C6: errore (C6 %s)", s_c6);
    if (esp_hosted_bt_controller_enable() != ESP_OK) ESP_LOGW(TAG, "enable controller BT del C6: errore (C6 %s)", s_c6);
    if (nimble_port_init() != ESP_OK) { ESP_LOGE(TAG, "NimBLE non parte: niente ruota"); vTaskDelete(NULL); }
    ble_hs_cfg.sync_cb = su_sync;
    ble_hs_cfg.reset_cb = su_reset;
    nimble_port_freertos_init(host_task);
    xTaskCreate(regista, "ruota", 4096, NULL, 4, NULL);
    ESP_LOGI(TAG, "BLE pronto (C6 %s), sensore %s", s_c6, s_ha_salvato ? "salvato" : "da accoppiare");
    vTaskDelete(NULL);
}

esp_err_t logger02_ruota_start(void)
{
    if (!logger02_ruolo()->is_a) return ESP_OK;
    nvs_carica();
    xTaskCreate(avvio, "ruota_avvio", 4096, NULL, 4, NULL);
    return ESP_OK;
}

void logger02_ruota_dimentica(void)
{
    s_dimentica = true;
}

void logger02_ruota_stato(char *json, size_t n)
{
    char a[24] = "null";
    if (s_ha_salvato) { a[0] = '"'; addr_str(&s_salvato, a + 1, sizeof(a) - 2); strcat(a, "\""); }
    long long ultimo = s_ultimo_us ? (esp_timer_get_time() - s_ultimo_us) / 1000 : -1;
    snprintf(json, n, "{\"stato\":\"%s\",\"connesso\":%s,\"salvato\":%s,\"giri\":%lu,\"t_evento_1024\":%u,\"notifiche\":%lu,"
             "\"ultimo_ms\":%lld,\"rssi_aggancio\":%d,\"c6\":\"%s\"}",
             NOMI[s_st], (s_st == R_OK || s_st == R_PROVA) ? "true" : "false", a, (unsigned long)s_giri, s_t1024, (unsigned long)s_notifiche,
             ultimo, s_rssi, s_c6);
}
