# Collaudo e accensione — logger HW4 (strato 6)

Niente di questo si fa su logger02 (logger di prova di Daniele, firmware congelato). Tutto su schede HW4 nuove.

## Prima di ordinare (le prove che tolgono i rischi grossi) — vedi DESIGN.md §6
P1 pin 1 del modulo Waveshare (Daniele, a occhio + tester) · P3 lato contatti del cavo FFC delle camere · P7 flash
della B da J22 con un adattatore USB-UART · P8 3V3 a cella bassa · P9 hot-plug/9 V · P10 stacco USB in registrazione ·
P6 corrente di logger02 in registrazione (autonomia) · driver IMU LSM6DS3TR-C provato sulla dev-kit di banco con un
breakout (stesso GPIO4 di risveglio). P2/P5 servono solo per HW4-v2.

## Accensione della prima scheda (bring-up), un passo alla volta
| # | Cosa | Come | Atteso | Se no |
|---|---|---|---|---|
| 1 | a vista | lente: ponti di stagno su modulo, USB-C, IMU LGA | nessuno | rilavorare |
| 2 | corti | tester fra VSYS, 3V3_A, 3V3_B, VBUS e GND (scheda spenta) | > 1 kΩ | cercare il corto prima di alimentare |
| 3 | USB-C senza batteria, **J3 aperto** | alimentatore da banco 5 V con **limite 1 A** su J1 (con J3 chiuso la scheda assorbe dalla USB: 200 mA non bastano a far partire due P4 + C6) | J3 aperto: VBUS 5 V, < 5 mA (TP4056 + OVP); CHRG lampeggia/alto senza cella. J3 chiuso: VSYS ≈ 4,5 V (SS14), 3V3_A/B 3,30 V, < 1 A | U2, R5, U7, D5, D6 |
| 4 | cella con limite + **stacco USB** | (a) alimentatore 3,8 V limite 2 A su J2 pin 1(+)/3(−), J3 ponticellato. (b) A e B in registrazione con USB-C collegato; **sonda su 3V3_A** (oscilloscopio, trigger sul fronte di discesa di VBUS); togliere il cavo USB 20 volte | (a) VSYS ≈ 3,7 V; 3V3_A e 3V3_B 3,30 ± 0,05 V; J3 aperto → VSYS = 0. (b) **3V3_A ≥ 3,0 V a ogni stacco**, nessun reset (log della A su J12 continuo), registrazione senza buchi | U4/U5, Q3, **D8, R35 10k** (`modello_power_path.py`) |
| 5 | protezione | abbassare l'alimentatore a 2,4 V | DW01A apre (VSYS → 0) sotto 2,5 V; si richiude sopra 2,9 V | Q1, U3 |
| 5b | **hot-plug e sovratensione** | (a) caricatore 5 V con cavo da 2 m inserito 20 volte, sonda su VBUS_RAW e su VBUS (dopo l'OVP), banda ≥ 50 MHz; (b) alimentatore da banco a 9 V su J1 per 10 s | (a) picco su VBUS ≤ 6,0 V (VCC max TP4056 6,5 V, VIN max TLV62569 6 V); (b) VBUS = 0 V (AW32901 aperto), nessun pezzo caldo; tolto il 9 V e messo 5 V la scheda riparte | U7, D6, R36 |
| 6 | moduli | cella vera; USB-C al Mac; adattatore USB-UART su **J12** per la console UART0 della A | /dev/cu.usbmodem della A; `esptool chip_id` = ESP32-P4; log di avvio su J12 | EN_A, BOOT_A, R3/R4 |
| 7 | **flash della B** | **(a) collaudo/produzione:** adattatore USB-UART 3,3 V (es. CP2102 con DTR/RTS) a pogo sul pad **J22 PROG B**: 1 GND, 2 U0TXD_B→RX adattatore, 3 U0RXD_B←TX, 4 EN_B←RTS, 5 BOOT_B (GPIO35)←DTR, 6 3V3 (non alimentare da qui: la scheda va dalla sua cella). `esptool --chip esp32p4 -p /dev/cu.usbserial-X write_flash @flash_args` · **(b) alternativa:** pogo su TP30/TP31 (USB-Serial/JTAG della B, D−/D+) + GND, cavo USB → `idf.py -p /dev/cu.usbmodem… flash` · **(c) in campo:** OTA wifi della B (ha la sua C6) come HW3, `ota.sh` · **(d) A che forza la B:** firmware di prova sulla A tiene GPIO49 basso (BOOT_B) e dà un impulso basso su GPIO33 (EN_B) → B in ROM download; serve comunque (a) o (b) per i dati | esptool legge chip_id della B; il firmware hw3-def parte con ruolo B | R54/R55, BOOT_B pull-up R44, pad J22 |
| 8 | firmware + identità | prima `hw3-def` così com'è (A da USB-C, B da J22); **NVS "ident"** scritta su A e su B come fa `flasha_nuovo.sh` (A sull'USB-C, B sull'adattatore di J22); deve partire senza danni (I2S del saluto su pad liberi), camere e SD ok; poi il firmware HW4 (driver IMU, flag saluto→buzzer, LED) | A e B si riconoscono (ruolo dalla NVS), camere PID 0x9281, SD montate, bip all'avvio col firmware HW4 | CAM_EN GPIO11 pull-up, FFC, `PIN_HW4.md` |
| 8b | **calibrazione batteria** | alimentatore a 3,80 V esatti (tester 0,1 %) su J2, firmware di collaudo legge 16 volte GPIO20 con la stessa sequenza di `leggi_batteria()` e salva il fattore nella NVS | dopo la calibrazione: errore < 1 % a 3,0 / 3,45 / 4,2 V | R10/R11 100k/33k, **C4 non montato** |
| 9 | stereo | prova 4 di PROVA_20261117 (cronometro ripreso da entrambe) | stesso numero sui due video | SYNC_M→SYNC_B |
| 10 | consumo | tester in serie alla cella: registra / wifi / deep sleep | registra ≈ come logger02; sleep < 1 mA | B non addormentata, LED |
| 11 | carica | cella mezza carica + USB-C; poi NTC scaldato col phon (> 45 °C) e raffreddato (< 0 °C, spray) | ~1 A (o il valore scelto da Daniele per R5), CHRG basso → alto a fine carica (C/10 raggiunto: la scheda va da VBUS); carica sospesa sopra 39-42 °C e sotto 0-4 °C | R_PROG, R7/RT1, Q3/D5 |

## Collaudo di serie (da L3 in su)
Firmware di test su A (≤ 3 min): rail misurate dall'ADC (batteria, VBUS), IMU risponde a 0x6A, SD A e B scritte/lette,
camere A e B: 30 fotogrammi con luminosità media in un intervallo, SYNC A→B visto dalla B, buzzer e LED accesi a turno
(l'operatore conferma), wifi su rete di collaudo. Esito + MAC in `flotta.csv`. Scarto = qualunque voce fuori.
Handoff firmware: asmile-flotta (driver IMU, firmware di test).
