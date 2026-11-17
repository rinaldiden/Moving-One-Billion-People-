/* logger02 (HW3): 2 × Waveshare ESP32-P4-Module-DEV-KIT. Stesso firmware su A e B, il ruolo lo dà il MAC.
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
    char nome[16];        /* hostname (NetBIOS: max 15 caratteri) */
    const char *ip;       /* IP fisso su EOLO */
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

esp_err_t logger02_web_start(void);
esp_err_t logger02_tailscale_start(void);       /* A: MicroLink, nome "logger02" */
void logger02_tailscale_stato(char *out, size_t n);
esp_err_t logger02_tailscale_salva_chiave(const char *k);   /* scrive la chiave auth nella NVS (mai nel firmware) */
