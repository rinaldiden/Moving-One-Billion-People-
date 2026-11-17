/* logger02 (HW3): 2 × Waveshare ESP32-P4-Module-DEV-KIT. Stesso firmware su A e B, il ruolo lo dà il MAC. */
#pragma once
#include <stdbool.h>
#include "esp_err.h"

typedef struct {
    bool is_a;            /* A = master: IMU, batteria, trigger, BLE; B = slave */
    char nome[16];        /* hostname (NetBIOS: max 15 caratteri) */
    const char *ip;       /* IP fisso su EOLO */
} logger02_ruolo_t;

const logger02_ruolo_t *logger02_ruolo(void);
esp_err_t logger02_saluto(void);              /* "Narmade Har!" dall'altoparlante, una volta a ogni accensione */
esp_err_t logger02_ip_fisso(void);            /* dopo example_connect(): passa da DHCP all'IP fisso del ruolo */
