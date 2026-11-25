/* logger02 (HW3): 2 × Waveshare ESP32-P4-Module-DEV-KIT. Stesso firmware su A e B e su tutti i logger HW3: nome/ruolo/IP dalla NVS "ident" (flasha_nuovo.sh).
 * Orologio unico: esp_timer (µs dal boot) di ogni scheda; B converte i suoi tempi in quelli di A col filo SYNC. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

#define L02_SD          "/sd"
#define L02_REC_DIR     L02_SD "/rec"

/* pin (PIN_logger002.md) */
#define L02_PIN_IMU_INT     4       /* A: INT MPU6050, LP GPIO → risveglio dal deep sleep */
#define L02_PIN_WAKE        5       /* A out → B in (LP GPIO su B) */
#define L02_PIN_SYNC_A      3       /* A out (pin 19) → B GPIO21 (pin 11): impulso ogni secondo per allineare gli orologi */
#define L02_PIN_SYNC_B      21
#define L02_PIN_UART_TX     22
#define L02_PIN_UART_RX     23
#define L02_PIN_BATT_ADC    20      /* A: partitore 100k/33k */
#define L02_PIN_C6_EN       54      /* reset della C6 (wifi): basso prima del deep sleep */
#define L02_PIN_SD_PWR      45
#define L02_PIN_ETH_RST     51      /* PHY Ethernet (non usato): tenuto in reset = consuma meno */
#define L02_PIN_PA          53      /* amplificatore audio */

typedef struct {
    bool is_a;            /* A = master: IMU, batteria, BLE, faccia verso l'esterno; B = slave */
    char base[12];        /* nome del logger: "logger02", "logger03"... (Tailscale) */
    char nome[16];        /* hostname = base + a/b (NetBIOS: max 15 caratteri) */
    const char *ip;       /* IP fisso su EOLO; NULL = DHCP (la B dei logger nuovi) */
} logger02_ruolo_t;

const logger02_ruolo_t *logger02_ruolo(void);
esp_err_t logger02_saluto(void);              /* "Narmade Har!" dall'altoparlante, una volta a ogni accensione */
esp_err_t logger02_ip_fisso(void);            /* dopo example_connect(): passa da DHCP all'IP fisso del ruolo */
void logger02_ora_init(void);                 /* SNTP + fuso Italia */
bool logger02_ora_valida(void);
void logger02_nome_sessione(char *out, size_t n);  /* YYYYmmdd_HHMMSS, o bootNNNN se l'ora non c'è ancora */

esp_err_t logger02_sd_monta(void);
uint64_t logger02_sd_libero_mb(void);
esp_err_t logger02_sd_formatta(void);        /* cancella tutto: solo con l'ok di Daniele */

/* sync A↔B */
esp_err_t logger02_link_init(void);
int64_t logger02_t_a(int64_t t_locale_us);    /* tempo locale → tempo della A (su A è identità) */
void logger02_link_invia(const char *riga);   /* comando all'altra scheda via UART (riga senza \n) */
void logger02_sync_stato(char *json, size_t n);

/* registrazione */
esp_err_t logger02_rec_start(void);
void logger02_rec_stop(void);                 /* chiude i file (prima del deep sleep) */
uint32_t logger02_rec_frame(void);            /* indice dell'ultimo fotogramma */
uint32_t logger02_rec_scritti(void);
void logger02_rec_pausa(bool p);              /* bici ferma: chiude il pezzo e non ne apre altri finché p */
int logger02_rec_da_scaricare(void);           /* pezzi video chiusi ancora sulla SD (contatore, niente scansioni) */
void logger02_rec_pezzo_tolto(void);           /* lo scarico ha cancellato un pezzo */
int logger02_b_da_scaricare(void);             /* A: pezzi della B (detti dalla B ogni 10 s), -1 se non noto */          /* fotogrammi scritti su SD */
void logger02_rec_stato(char *json, size_t n);
size_t logger02_rec_jpeg(uint8_t *out, size_t max);   /* ultimo fotogramma in JPEG per lo streaming (0 = niente) */
void logger02_rec_ultimi(char *json, size_t n);       /* ultimi tempi dei fotogrammi, già in tempo A */
void logger02_rec_fase(int64_t *t_ultimo_locale, uint32_t *frame, double *periodo_us);
void logger02_rec_riferimento(int64_t t_rif_a, uint32_t f_rif, double p_us);   /* B: numerazione comune */
void logger02_rec_ritarda(int64_t us);                          /* B: sposta la fase della camera */
uint32_t logger02_rec_correzioni(void);
void logger02_rec_standby(void);
void logger02_rec_esposizione(uint32_t exp16, uint32_t gain);  /* B: valori decisi dalla A */              /* camera in standby software (prima del deep sleep) */
double logger02_rec_riga_us(void);

/* A: IMU, batteria, autospegnimento */
esp_err_t logger02_imu_start(void);
void logger02_imu_stato(char *json, size_t n);
float logger02_batteria_v(void);              /* <0 se non collegata */
void logger02_dormi(const char *motivo);      /* chiude tutto e va in deep sleep (A sveglia con IMU, B con WAKE) */
void logger02_scarico_inizio(void);           /* 24/11: trasferimento aperto (/dl, proxy /b): contatore >0 = mai dormire */
void logger02_scarico_fine(void);             /* da chiamare SEMPRE in uscita, anche in errore */
void logger02_scarico_visto(void);            /* il Mac sta scaricando (web): A resta sveglia finché finisce */
/* 25/11: rete di sicurezza (logger02_wifi.c) */
bool logger02_in_pausa(void);                 /* A: bici ferma, registrazione in pausa */
bool logger02_scarico_in_corso(void);         /* trasferimento aperto e non appeso (blocchi negli ultimi 3 min) */
void logger02_prova_sveglio(int s);           /* prove: non dormire per s secondi (anche dopo un riavvio pulito) */
void logger02_riavvio_init(void);             /* all'avvio: riprende lo stato salvato da logger02_riavvio_pulito */
void logger02_riavvio_pulito(const char *motivo);  /* chiude registrazione e file come prima del sonno, poi riavvia */
int logger02_rete_riavvii(void);              /* riavvii della rete di sicurezza in questo risveglio */
esp_err_t logger02_rete_sicurezza_start(void);   /* eventi wifi nel registro + (A) rete di sicurezza */
int logger02_rete_rssi(void);                 /* 0 = non noto */
void logger02_rete_stato(char *json, size_t n);
esp_err_t logger02_rete_prova(const char *azione, char *out, size_t n);
esp_err_t logger02_c6_ota(uint8_t *buf, size_t len);   /* aggiorna il C6 (esp_hosted slave); prende buf (PSRAM) */
const char *logger02_c6_ota_esito(void);

/* salute (A e B): una riga al secondo + errori del log, come asmile_health.csv del logger001 */
void logger02_salute_presto(void);            /* all'avvio, prima di tutto: aggancia il log, conta il riavvio */
esp_err_t logger02_salute_start(void);        /* dopo la SD */
void logger02_salute_chiudi(void);            /* prima del deep sleep */
void logger02_salute_stato(char *json, size_t n);
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
extern SemaphoreHandle_t logger02_analogico;  /* ADC batteria e sensore di temperatura: uno alla volta */

esp_err_t logger02_web_start(void);
esp_err_t logger02_tailscale_start(void);       /* A: MicroLink, nome "logger02" */
void logger02_tailscale_stato(char *out, size_t n);
esp_err_t logger02_tailscale_salva_chiave(const char *k);   /* scrive la chiave auth nella NVS (mai nel firmware) */
