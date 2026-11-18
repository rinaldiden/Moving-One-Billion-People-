# STACK_HW — hardware della flotta e software che ci gira (e ci girerà)

Scritto da asmile-hw-pcb (STAGNO) il 18/11/2026 per la scheda logger HW4. Fonti: README/PIN/PROVA di logger02,
firmware `logger02/firmware/main/*.c` (tag `hw3-def-20261118`), memoria di Claude (MEMORY.md, feedback_logger_vs_001_*),
decisioni di Daniele in `agents/lezioni/`. Ogni unità ha hardware suo: **mai trasferire calib, codice camera o
"validato" da un'unità all'altra** (feedback_logger_vs_001_hw).

## 1. Inventario per unità

| Unità | Compute | Camere | Sensori | Attuatori | Energia | Scopo |
|---|---|---|---|---|---|---|
| **asmile #001** (Tirano, hw1) | Raspberry Pi 5 | 2 × OV9281 Inno-Maker separate, 2 CSI, `rpicam --sync` | encoder sterzo AMT22, encoder ruota, IMU, (GPS), INA219 | VESC sterzo, servofreno GPIO12 (≤60°) | batteria bici | **insegnante**: sterzo/freno/accelerazione fatti bene |
| **asmile2** | Raspberry Pi 5 | (OV9281) | encoder, CooSpo BLE | VESC sterzo, freno | batteria bici | sviluppo sterzo |
| **asmile-logger001** (hw v2) | Raspberry Pi 5 | Arducam **Camarray** SBS 2560×800, 1 CSI, `arducam_fix.so` | IMU (HW-123), batteria | nessuno | Li-ion, overlay FS | **video e situazioni nuove** |
| **logger02** (HW3, banco/prova) | 2 × Waveshare ESP32-P4-Module-DEV-KIT (A master, B slave) | 2 × Inno-Maker OV9281 MIPI, 1 per scheda, 1280×720 RAW8 | MPU6050 su A (INT → sveglia), partitore batteria su ADC | nessuno | 2 × 18650 2P + MH-CD42 + MT3608 5,1 V | logger economico, stessa funzione di logger001 |
| **logger HW4** (questa scheda) | vedi `logger_hw4/DESIGN.md` | 2 × OV9281 (stesso sensore di #001 e HW3) | IMU su scheda, batteria | nessuno | 1S Li-ion su scheda | logger di serie (flotta grande) |

## 2. Lo stack che gira oggi su HW3 (firmware ESP-IDF 5.5.6, codice letto)
| Funzione | Come la fa HW3 oggi | sw o hw | Carico misurato / dato |
|---|---|---|---|
| cattura camera | OV9281 MIPI 2 lane, sensore a 50 fps, si tiene 1 fotogramma su 3 (`REC_DIV 3`) → 16,7 fps | hw (CSI) | 1280×720 RAW8 |
| RAW8 → YUV420 | ISP del P4 (pipeline IPA Espressif spenta) | hw | 1 ISP per P4 |
| compressione | H.264 hardware, 2 Mbps, I-frame ogni 17, QP 22-38 | hw | 272 MB in 10 min (prova 18/11) |
| scrittura | microSD slot 0 4 bit (GPIO39-44), LDO interno canale 4, accensione SD da GPIO45, pezzi da 60 s + CSV frame | hw+sw | ~0,45 MB/s |
| esposizione automatica | **software** sulla A (media luminosità → esposizione/guadagno), stessi valori mandati alla B via UART, group hold 0x3208 | sw | il driver Espressif non ha AE |
| sincronia stereo | **software**: impulso 1 Hz A GPIO3 → B GPIO21, la B sposta il VTS del sensore per agganciare la fase (non usa FSIN) | sw (+2 fili) | errore da misurare (prova 4 di PROVA_20261117) |
| orologio comune | `t_a_us` nel CSV della B = tempo della A | sw | — |
| IMU | MPU6050 I2C (stesso bus della camera, GPIO7/8), 50 Hz nel CSV `sensors_*` | hw sensore + sw | INT GPIO4 = risveglio |
| batteria | partitore 100k/33k su GPIO20 (ADC1_CH4), "non collegata" riconosciuta | hw minimo + sw | — |
| sonno/risveglio | deep sleep della A, B addormentata via GPIO5, risveglio dal movimento IMU, autospegnimento 5 min | sw | provato da Daniele |
| wifi | C6 (ESP-Hosted SDIO, GPIO14-19 interni al modulo, reset GPIO54), IP fisso, buffer in PSRAM | hw modulo | crash risolto 18/11 (buffer PSRAM) |
| scarico dati | server HTTP sulla scheda, pull dal Mac; Tailscale (MicroLink), chiave in NVS | sw | — |
| aggiornamento | OTA via wifi con guardia 3 min + rollback, solo sul logger di prova | sw | regola ferrea 18/11 |
| saluto all'accensione | ES8311 + altoparlante (PA GPIO53) | hw | da togliere: basta un buzzer |
| stato | LED RGB KY-016 | hw | — |

## 3. Cosa ci girerà (direzione, decisioni di Daniele 09-12/11)
- **Il logger resta un raccoglitore di situazioni** (video stereo + IMU), niente GPS, niente attuatori: la velocità
  la danno IMU + video o il sensore ruota BLE CooSpo (via C6, già provato su asmile2).
- **Il modello leggero di guida (seg + depth ostacoli → freno/sterzo) gira sul Pi di #001**, allenato sul Mac
  (maestro SAM 3 + depth stereo). Sul logger servono soprattutto **dati identici a quelli che vedrà la bici**:
  stesso sensore OV9281 global shutter mono, stessa risoluzione, stereo sincrono.
- Possibili in futuro sul logger (spazio da lasciare, non da montare): filtro "frame fermi" a bordo
  (taglia_fermi oggi sul Mac), un gate di interesse leggero (MOG2/statistiche) per non salvare scene inutili,
  BLE ruota, scarico più veloce. Tutto software: chiede **compute e RAM liberi**, non chip in più.
- Calibrazione per modello + autoregistrazione in strada (proposta, DA FIRMARE): chiede **baseline rigida e
  ripetibile** fra le due camere → scheda unica lunga, camere avvitate sulla stessa scheda.
- Sicurezza (ARCHITETTURA_SICUREZZA.md): riguarda #001 (ESP32 di sicurezza), non il logger.

## 4. Per funzione: software o hardware nel logger HW4
| Funzione | Decisione | Perché |
|---|---|---|
| esposizione, sync di fase, filtri, LED a pattern, debounce, sonno, misura batteria a campione, watchdog | **software** | già fatto in HW3, zero pezzi |
| trigger camere | **una pista** (GPIO della A → TRIG di entrambe le camere), opzionale | sul circuito costa zero; il firmware attuale non lo usa, resta per la sync hardware vera |
| filo SYNC A→B, UART A↔B, WAKE A→B | **piste** sulla scheda (non più fili) | stessi GPIO di HW3 → firmware invariato |
| saluto vocale | **buzzer attivo** sul pin del PA (GPIO53) | il firmware che accende il PA fa suonare il buzzer senza cambiare una riga |
| caricatore + step-up 5 V + modulo carica | **un caricatore 1S + buck 3,3 V a duty 100 %** su scheda | i moduli P4 vanno a 3,3 V: lo step-up a 5 V e i regolatori delle dev-kit spariscono |
| protezione cella | **DW01A + FS8205A** (pochi centesimi) | le 18650 spesso non sono protette; cortocircuito in bici = incendio |
| IMU | chip su scheda (LSM6DS3TR-C) | MPU6050 è a fine vita; INT di risveglio sullo stesso GPIO4 |
| audio codec, Ethernet, pettine 40 pin, USB-UART delle dev-kit | **via** | non servono al logger |
