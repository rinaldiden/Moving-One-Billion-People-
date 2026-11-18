# Proposta firmware per HW4 (handoff ad asmile-flotta) — NON tocca logger02

logger02 e il suo firmware restano congelati (`hw3-def-20261118`). Questa è la lista delle modifiche che servono SOLO
quando esisterà una scheda HW4. Vanno in un ramo/flag nuovo; regola ferrea OTA: prima una scheda col cavo.

## Flag
`CONFIG_LOGGER02_HW4` (Kconfig, default **n**): con `n` il firmware resta byte per byte quello di HW3.

## Cosa cambia con `CONFIG_LOGGER02_HW4=y`
| # | Dove | Oggi (HW3) | HW4 | Perché |
|---|---|---|---|---|
| 1 | `logger02_saluto.c` | apre I2S su 13/12/10/9 (riga 36) e cerca l'ES8311 | **non apre l'I2S**: tre bip col buzzer su GPIO27 (alto = suona, buzzer attivo) | su HW4 non c'è codec; anche col firmware vecchio i pad 9/10/12/13 sono liberi (nessun danno) |
| 2 | `logger02_imu.c` | MPU6050 0x68, registri MPU | **LSM6DS3TR-C 0x6A**: WHO_AM_I 0x0F = 0x6A; CTRL1_XL 0x10 = 0x40 (104 Hz, ±2 g), CTRL2_G 0x11 = 0x40 (104 Hz, ±250 dps); lettura 0x22-0x2D; wake-up: TAP_CFG 0x58 bit7 INTERRUPTS_ENABLE, WAKE_UP_THS 0x5B, WAKE_UP_DUR 0x5C, MD1_CFG 0x5E bit5 INT1_WU → INT1 su GPIO4 attivo alto (come oggi, `ESP_EXT1_WAKEUP_ANY_HIGH`) | MPU6050 a fine vita (16 $ su LCSC). Valori registro da RILEGGERE sul datasheet ST DocID029416 prima di scriverli |
| 3 | `logger02.h` | — | `L02_PIN_LED_R 50`, `L02_PIN_LED_G 52` (A), `L02_PIN_LED_B 50` (B), `L02_PIN_BUZZER 27`, `L02_PIN_CAM_EN 11` (pull-up in hw: toccarlo solo per spegnere la camera), `L02_PIN_VBUS 21` (solo A, ADC1_CH5 o digitale), `L02_PIN_CHRG 26` (basso = in carica) | pin scelti fra quelli che hw3-def non tocca (`PIN_HW4.md`) |
| 4 | `logger02_imu.c` batteria | partitore 100k/33k | 1M/330k, **stesso rapporto** → costante invariata; più tempo di assestamento (100 nF) prima della lettura | partitore sulla cella, sempre collegato (3 µA) |
| 5 | spegnimento per batteria | soglia di HW3 | **3,45 V di cella a riposo** | sotto ~3,4 V la 3V3 scende sotto 3,0 V al picco (DESIGN §4) |
| 6 | deep sleep | tiene bassi PA 53 / ETH 51 | invariato (pad liberi su HW4); aggiungere buzzer 27 basso e LED spenti in hold | nessun consumo da LED/buzzer in sonno |
| 7 | (opzionale) recupero della B | — | sulla A: comando web "B in download" = GPIO49 basso + impulso basso su GPIO33 | il flash vero passa da J22 o OTA della B |

Verifica dopo: `kicad/controlla_pin_fw.py <firmware HW4>` deve dare 0 conflitti anche sul firmware nuovo.
