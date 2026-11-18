# Collaudo e accensione — logger HW4 (strato 6)

Niente di questo si fa su logger02 (logger di prova di Daniele, firmware congelato). Tutto su schede HW4 nuove.

## Prima di ordinare (le prove che tolgono i rischi grossi) — vedi DESIGN.md §6
P1 pin 1 del modulo Waveshare (Daniele, a occhio + tester) · P3 lato contatti del cavo FFC delle camere ·
P6 corrente di logger02 in registrazione (autonomia) · driver IMU LSM6DS3TR-C provato sulla dev-kit di banco con un
breakout (stesso GPIO4 di risveglio). P2/P5 servono solo per HW4-v2.

## Accensione della prima scheda (bring-up), un passo alla volta
| # | Cosa | Come | Atteso | Se no |
|---|---|---|---|---|
| 1 | a vista | lente: ponti di stagno su modulo, USB-C, IMU LGA | nessuno | rilavorare |
| 2 | corti | tester fra VSYS, 3V3_A, 3V3_B, VBUS e GND (scheda spenta) | > 1 kΩ | cercare il corto prima di alimentare |
| 3 | USB-C senza batteria | alimentatore da banco 5 V con limite 200 mA su VBUS | VBUS 5 V, corrente < 5 mA, TP4056 senza cella: CHRG lampeggia/alto | U2, R5 |
| 4 | cella con limite | alimentatore 3,8 V limite 300 mA su J2 (al posto della cella), J3 ponticellato | VSYS 3,8 V; 3V3_A e 3V3_B 3,30 ± 0,05 V | U4/U5, partitore 100k/22k |
| 5 | protezione | abbassare l'alimentatore a 2,4 V | DW01A apre (VSYS → 0) sotto ~2,4 V; si richiude sopra ~3,0 V | Q1, U3 |
| 6 | moduli | cella vera; USB-C al Mac | /dev/cu.usbmodem della A; `esptool chip_id` = ESP32-P4 | EN_A, BOOT_A, R3/R4 |
| 7 | B da A | firmware di prova sulla A: B_BOOT_CTL basso + reset → B in download via UART 22/23 | esptool vede la B attraverso la A | R54/R55, UART |
| 8 | firmware | `flasha_nuovo.sh` (set hw3-def) su A e B, con driver IMU nuovo | saluto = bip, camere riconosciute (PID 0x9281), SD montate | CAM_EN pull-up, FFC |
| 9 | stereo | prova 4 di PROVA_20261117 (cronometro ripreso da entrambe) | stesso numero sui due video | SYNC_M→SYNC_B |
| 10 | consumo | tester in serie alla cella: registra / wifi / deep sleep | registra ≈ come logger02; sleep < 1 mA | B non addormentata, LED |
| 11 | carica | cella mezza carica + USB-C | ~1 A, CHRG basso → alto a fine carica | R_PROG |

## Collaudo di serie (da L3 in su)
Firmware di test su A (≤ 3 min): rail misurate dall'ADC (batteria, VBUS), IMU risponde a 0x6A, SD A e B scritte/lette,
camere A e B: 30 fotogrammi con luminosità media in un intervallo, SYNC A→B visto dalla B, buzzer e LED accesi a turno
(l'operatore conferma), wifi su rete di collaudo. Esito + MAC in `flotta.csv`. Scarto = qualunque voce fuori.
Handoff firmware: asmile-flotta (driver IMU, firmware di test).
