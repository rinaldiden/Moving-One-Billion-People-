# Collaudo e accensione — logger HW4 (strato 6)

Niente di questo si fa su logger02 (logger di prova di Daniele, firmware congelato). Tutto su schede HW4 nuove.

## Prima di ordinare (le prove che tolgono i rischi grossi) — vedi DESIGN.md §6
P1 pin 1 del modulo Waveshare (Daniele, a occhio + tester) · P3 lato contatti del cavo FFC delle camere · P7 flash
della B da J22 con un adattatore USB-UART · P8 3V3 a cella bassa ·
P6 corrente di logger02 in registrazione (autonomia) · driver IMU LSM6DS3TR-C provato sulla dev-kit di banco con un
breakout (stesso GPIO4 di risveglio). P2/P5 servono solo per HW4-v2.

## Accensione della prima scheda (bring-up), un passo alla volta
| # | Cosa | Come | Atteso | Se no |
|---|---|---|---|---|
| 1 | a vista | lente: ponti di stagno su modulo, USB-C, IMU LGA | nessuno | rilavorare |
| 2 | corti | tester fra VSYS, 3V3_A, 3V3_B, VBUS e GND (scheda spenta) | > 1 kΩ | cercare il corto prima di alimentare |
| 3 | USB-C senza batteria, **J3 aperto** | alimentatore da banco 5 V con limite 200 mA su VBUS | VBUS 5 V, corrente < 5 mA (solo TP4056: con J3 aperto il power-path non alimenta la scheda); TP4056 senza cella: CHRG lampeggia/alto; poi J3 chiuso: VSYS ≈ 4,5 V (SS14), 3V3 ok | U2, R5, D5, D6 |
| 4 | cella con limite | alimentatore 3,8 V limite 300 mA su J2 pin 1(+)/3(−), J3 ponticellato | VSYS ≈ 3,7 V (cella − P-MOS); 3V3_A e 3V3_B 3,30 ± 0,05 V; con J3 aperto VSYS = 0 | U4/U5, partitore 100k/22k, Q3 |
| 5 | protezione | abbassare l'alimentatore a 2,4 V | DW01A apre (VSYS → 0) sotto 2,5 V; si richiude sopra 2,9 V | Q1, U3 |
| 6 | moduli | cella vera; USB-C al Mac | /dev/cu.usbmodem della A; `esptool chip_id` = ESP32-P4 | EN_A, BOOT_A, R3/R4 |
| 7 | **flash della B** | **(a) collaudo/produzione:** adattatore USB-UART 3,3 V (es. CP2102 con DTR/RTS) a pogo sul pad **J22 PROG B**: 1 GND, 2 U0TXD_B→RX adattatore, 3 U0RXD_B←TX, 4 EN_B←RTS, 5 BOOT_B (GPIO35)←DTR, 6 3V3 (non alimentare da qui: la scheda va dalla sua cella). `esptool --chip esp32p4 -p /dev/cu.usbserial-X write_flash @flash_args` · **(b) alternativa:** pogo su TP30/TP31 (USB-Serial/JTAG della B, D−/D+) + GND, cavo USB → `idf.py -p /dev/cu.usbmodem… flash` · **(c) in campo:** OTA wifi della B (ha la sua C6) come HW3, `ota.sh` · **(d) A che forza la B:** firmware di prova sulla A tiene GPIO49 basso (BOOT_B) e dà un impulso basso su GPIO33 (EN_B) → B in ROM download; serve comunque (a) o (b) per i dati | esptool legge chip_id della B; il firmware hw3-def parte con ruolo B | R54/R55, BOOT_B pull-up R44, pad J22 |
| 8 | firmware | prima `hw3-def` così com'è (A da USB-C, B da J22): deve partire senza danni (I2S del saluto su pad liberi), camere e SD ok; poi il firmware HW4 (driver IMU, flag saluto→buzzer, LED) | camere riconosciute (PID 0x9281), SD montate, bip all'avvio col firmware HW4 | CAM_EN GPIO11 pull-up, FFC, `PIN_HW4.md` |
| 9 | stereo | prova 4 di PROVA_20261117 (cronometro ripreso da entrambe) | stesso numero sui due video | SYNC_M→SYNC_B |
| 10 | consumo | tester in serie alla cella: registra / wifi / deep sleep | registra ≈ come logger02; sleep < 1 mA | B non addormentata, LED |
| 11 | carica | cella mezza carica + USB-C; poi NTC scaldato col phon (> 45 °C) e raffreddato (< 0 °C, spray) | ~1 A, CHRG basso → alto a fine carica (C/10 raggiunto: la scheda va da VBUS); carica sospesa fuori da ~3-42 °C | R_PROG, R7/RT1, Q3/D5 |

## Collaudo di serie (da L3 in su)
Firmware di test su A (≤ 3 min): rail misurate dall'ADC (batteria, VBUS), IMU risponde a 0x6A, SD A e B scritte/lette,
camere A e B: 30 fotogrammi con luminosità media in un intervallo, SYNC A→B visto dalla B, buzzer e LED accesi a turno
(l'operatore conferma), wifi su rete di collaudo. Esito + MAC in `flotta.csv`. Scarto = qualunque voce fuori.
Handoff firmware: asmile-flotta (driver IMU, firmware di test).
