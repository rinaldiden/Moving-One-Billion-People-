# Logger HW4 — scheda dedicata (DESIGN)

> **Maturità: L0 → verso L1.** Oggi: studio + schema KiCad generato e corretto dopo il VETO 1 e il VETO 2 del critico (18/11).
> Niente è ancora stato acceso né ordinato.
> Salto dopo: L1 = 10 schede montate, rail e bus verificati a banco con il firmware `hw3-def-20261118`.

## CONTESTO PROGETTO CORRENTE (18/11/2026)
| | |
|---|---|
| Scheda | logger HW4: una scheda unica che sostituisce le 2 dev-kit Waveshare + moduli di alimentazione di HW3 |
| Unità che la useranno | flotta logger (raccolta video/situazioni); NON #001 (controllo) né asmile2 |
| Funzioni | 2 camere stereo sincrone (baseline 200 mm) → H.264 su SD a pezzi da 60 s + CSV frame; IMU 50 Hz con risveglio dal movimento; batteria 1S con carica USB-C e misura; wifi per scarico/OTA/Tailscale; saluto/avvisi sonori; LED |
| Vincoli | costo ~25 € (Daniele: "schedina + cam", ambiguo → do entrambe le letture); batteria 2 × 18650 in parallelo (la fa Daniele); case da disegnare col Doppio DOPO aver fissato fori e connettori (feedback_case_montaggio_prima) |
| Fase | studio → schema (questo giro); layout e produzione dopo il PASSA del critico e la prova di banco |
| Esiste già | HW3 = logger02 (2 × Waveshare ESP32-P4-Module-DEV-KIT + 2 × Inno-Maker OV9281 + MPU6050 + MH-CD42 + MT3608 + ES8311), firmware congelato `hw3-def-20261118` |
| Domande aperte | Q1 lettura dei 25 €; Q2 lente (FOV) uguale a #001?; Q3 posizione fori camera/case (Doppio); Q4 una o due SD; Q5 antenne esterne IPEX ok? |

## 1. Requisiti (strato 0, da `../STACK_HW.md`)
R1 due camere global shutter mono, 1280×720 (o più), ≥15 fps, **stesso sensore di #001** (OV9281) per non cambiare dominio
fra i dati del logger e la bici che guiderà · R2 sincronia fra le due ≤1 riga (oggi software via VTS; predisporre il
trigger hardware) · R3 baseline 200 mm **rigida** (la scheda è la barra) · R4 H.264 ~2 Mbps × 2, SD ~0,5 MB/s ·
R5 IMU con interrupt di risveglio · R6 1S Li-ion, carica da USB-C, misura batteria, protezione cella · R7 wifi
(scarico, OTA, Tailscale), BLE per il sensore ruota CooSpo · R8 firmware HW3 riusabile (stessi GPIO) · R9 compute e RAM liberi per
filtri a bordo futuri (frame fermi, gate di interesse) · R10 collaudabile (test point, UART, boot) e riparabile.

## 2. Compute (strato 1-2) — DECISO: 2 moduli Waveshare ESP32-P4-Module su una scheda
Candidati e prove (righe del `../REGISTRO.md` 14:50-15:04):
| | K1 2 × modulo Waveshare P4 (come HW3) | K2 1 × modulo P4, cam 1 MIPI + cam 2 DVP | K3 chip P4 nudo + C6-MINI |
|---|---|---|---|
| Funzione | 2 ISP, 2 encoder, 2 C6: ogni camera ha la sua catena come in HW3 (provato) | 1 ISP (3 ingressi ma uno solo: datasheet P4 v0.7 §4.2.1.2 p.63); H.264 dual-stream ≤1080p30 totale (§4.2.1.5 p.65) → 2×720p@16,7 = 49 % del limite sulla carta | come K1 o K2 |
| Costo | ~2 × 10 $ moduli | ~10 $ | chip 4,47 $ + flash + C6 2,99 $ + DCDC/quarzo |
| Supply | Waveshare, in vendita (un solo fornitore) | idem + **modulo OV9281 DVP non trovato a catalogo** | **stock 0** LCSC/JLC/DigiKey (rientro apr-2027), Espressif MOQ 2000 |
| Software | **firmware HW3 invariato** | driver OV9281 DVP da scrivere (esp_cam_sensor ha solo MIPI), catena DVP senza ISP | come K1/K2 + bring-up alimentazione/RF |
| Montaggio | modulo a castello passo 1 mm (non è in libreria JLC: va fornito o saldato a parte) | idem | QFN-104 + 4 strati + RF |
| Futuro | 2 × (2 core 360 MHz + 32 MB PSRAM): margine per filtri a bordo | metà | come K1/K2 |
| **Punteggio** (pesi strato 2: 0,25/0,20/0,20/0,15/0,10/0,10) | 9/5/6/10/7/9 → **7,55** | 6/8/4/3/7/6 → 5,65 | 8/7/2/8/5/9 → 6,40 |

Scelta K1 (decisione registrata in `agents/decisioni/asmile-hw-pcb.md`). K2 resta il **piano B a costo minore** (HW4-v2),
solo dopo la prova P2 (sotto) e solo se si trova un modulo OV9281 DVP.

## 3. Camere (strato 1-2) — la scelta che conta di più
### 3.1 Cosa serve davvero (dai requisiti, non dal catalogo)
- **Global shutter obbligatorio.** In bici: vibrazioni e moto laterale; un rolling shutter legge le righe in ~20-30 ms →
  righe storte e, peggio, le due camere storte in modo diverso → la disparità stereo diventa rumore. Scarta OV2640,
  OV5640, GC2145, SC2336 ecc. anche se hanno driver.
- **Depth stereo B = 200 mm fino a 10-20 m.** Errore ΔZ ≈ Z² · Δd / (f · B) con Δd = 0,25 px (subpixel realistico):
  | sensore / lente | f (px) | ΔZ a 5 m | a 10 m | a 20 m |
  |---|---|---|---|---|
  | 1280 px, HFOV 58° (come #001) | 1155 | 2,7 cm | 11 cm | 43 cm |
  | 1280 px, HFOV 70° | 914 | 3,4 cm | 14 cm | 55 cm |
  | 640 px (VGA), HFOV 70° | 457 | 6,8 cm | 27 cm | **1,1 m** |
  → serve **≥1280 px di larghezza**: il VGA a 20 m sbaglia di un metro.
- **Mono, non colore.** #001 (che userà il modello) ha OV9281 mono: dati del logger nello stesso dominio. Il filtro
  Bayer toglie ~2/3 della luce (peggio la sera) e chiede l'ISP per la demosaicizzazione su entrambe le camere.
- **Poca luce la sera:** pixel grande + esposizione lunga + guadagno; il global shutter mono è il migliore dei mondi
  economici. Nessun sensore di questa fascia "vede di notte": la sera resta un limite noto (MEMORY: auto-EV). Da misurare (P4).
- **Sync hardware:** il sensore deve avere FSIN/trigger, e il modulo deve portarlo fuori.
- **Driver esp_cam_sensor MIPI già esistente** (README esp-video-components, letto 18/11): OV9281 sì (1280×720 RAW8 mono),
  SC132GS sì (1080×1280 RAW mono/colore), SC035HGS sì (640×480, MIPI+DVP), Mira220 sì; **OV9782, OV9282, AR0144, OG01A1B no**.

### 3.2 Candidati concreti (comprabili oggi, prezzi del 18/11/2026)
| | C1 **OV9281 modulo Pi 15 pin + trigger** | C2 SC132GS modulo MIPI | C3 SC035HGS VGA | C4 OV9782 colore | C5 sensore saldato sulla carrier |
|---|---|---|---|---|---|
| Sensore | OV9281 1/4", 1280×800, 3 µm, GS mono, FSIN (OVT PB v1.4) | SC132GS 1/3", 1080×1280 (verticale: si ruota il modulo → 1280×1080), 2,7 µm, GS | 640×480, 3,75 µm, GS | 1280×800 GS **colore** | OV9281 CSP-64 o SC132GS PLCC-28 |
| Moduli/ottica | Inno-Maker CAM-MIPIOV9281 (HW3, ingresso TRIG optoisolato J3); Arducam OV9281 M12 (FSIN su J2 3 pin); DFRobot SEN0634 (79°) | Camemake CM_MIPI_SC132GS (M6.5, HFOV 74°); Sinoseen; Waveshare GS130W (coppia a 80 mm: baseline sbagliata) | moduli Sinoseen ecc. | moduli Alibaba | portalente M12 su scheda (~1,5 $) |
| Connettore | FFC 15 pin 1 mm (standard Pi) + 2-3 fili trigger | FPC MIPI (pinout da chiedere) | MIPI/DVP | — | nessuno (piste corte) |
| Prezzo a 10 | 41 €/pz (makersheet, 79°), 54 €/pz Arducam M12 (robotics-3d), 24 $/pz DFRobot a 10+ | **77,84 $/pz** a 10 (DigiKey) | ~10-15 $ (stima, nessun listino affidabile) | ~11 $ a 10.000 (Alibaba) | chip OV9281 10,75 $ LCSC (stock 0), 5,38 $ Arrow (stock 0, 16 sett.) |
| Prezzo a 100 | da chiedere (bozza email §9) — stima 15-25 $ | ~10,8 $ a 500, 8,8 $ a 1000 | — | — | chip ~5-8 $ + portalente/lente 1,5 $ |
| Stock | sì (rivenditori, DigiKey DFRobot) | DigiKey 1000 ma spedizione dal produttore ~25 gg | incerto | incerto | **0** (LCSC/JLC/Arrow) |
| Driver esp_cam_sensor | **sì, provato su HW3** | sì (non provato da noi) | sì (MIPI e DVP) | **no** | sì se OV9281/SC132GS |
| Dominio dati = #001 | **sì** | no (altro sensore, altra resa) | no | no (colore) | sì se OV9281 |
| Note | soluzione di HW3, nessuna incognita | migliore risoluzione verticale, trigger e pinout del modulo da chiedere | depth a 20 m inaccettabile (1,1 m) | toglie luce, ISP ×2, driver da scrivere | datasheet completo OV9281 sotto NDA (mappa sfere e sequenza di accensione non pubbliche), montaggio in camera pulita, messa a fuoco a mano |

### 3.3 Punteggio (pesi strato 2: funzione 0,25 · costo 0,20 · supply 0,20 · software 0,15 · montaggio 0,10 · futuro 0,10)
| | funz | costo | supply | sw | mont | futuro | **tot** |
|---|---|---|---|---|---|---|---|
| C1 OV9281 modulo + trigger | 9 | 4 | 7 | 10 | 9 | 7 | **7,55** |
| C2 SC132GS modulo | 8 | 3 (a 10) / 7 (a 500) | 5 | 7 | 8 | 8 | 6,25 (a 10) |
| C3 SC035HGS VGA | 4 | 7 | 5 | 8 | 8 | 4 | 5,80 |
| C4 OV9782 colore | 5 | 6 | 4 | 2 | 6 | 6 | 4,75 |
| C5 sensore saldato | 9 | 9 | 1 | 6 | 2 | 8 | 6,15 |

### 3.4 Raccomandazione
**C1: OV9281 mono global shutter su modulo Pi 15 pin con ingresso trigger, lente M12 con lo stesso campo di #001
(~58-70°, Q2 a Daniele).** È lo stesso sensore di #001 e di HW3 (driver provato, calibrazione "per modello" coerente),
e sulla scheda costa solo un connettore FFC + un JST di trigger per lato. Il prezzo del modulo a 100 pz è il buco:
bozza di richiesta preventivo pronta (§9) ad Arducam, Inno-Maker, Sinoseen.
- **C2 (SC132GS)** è il candidato da tenere d'occhio per HW4-v2: driver Espressif esistente, 1280×1080, ~9-11 $ in volume.
  Prova da fare prima (P5): 1 modulo SC132GS sulla dev-kit Waveshare di banco, immagini di sera e di giorno vs OV9281.
- **C5 (sensore saldato)** solo con un modulista: non è comprabile oggi, e un CSP-64 in camera non pulita è il modo più
  rapido per buttare 100 schede. La via giusta è chiedere a un modulista una **barra stereo COB con 2 sensori a 200 mm**
  (lo fanno di mestiere) e montarla sulla nostra scheda: bozza in §9.
- **Colore no** sul logger. Se un giorno il maestro avrà bisogno del colore, si aggiunge una terza camera solo per lui.

## 4. Architettura della scheda (schema in `kicad/`)
```
        CAM SX (FFC 15p + TRIG)                                               CAM DX (FFC 15p + TRIG)
             │ CSI 2 lane, I2C, EN                                                  │
   ┌─────────┴──────────┐   SYNC 1Hz, UART, WAKE, SPI (dati futuri), EN/BOOT di B  ┌┴───────────────────┐
   │ modulo A (P4+C6)   │══════════════════════ piste sulla scheda ════════════════│ modulo B (P4+C6)   │
   │ SD-A, IMU, USB-C   │                                                          │ SD-B, pad PROG B   │
   └─────────┬──────────┘                                                          └─────────┬──────────┘
          3V3_A (buck TLV62569) ← VSYS ← interruttore J3 ← OR(cella via P-MOS, VBUS via SS34) → 3V3_B (buck TLV62569)
     USB-C 5 V → R36 → TVS + USBLC6 → OVP AW32901 (5,95 V) → TP4056 1 A con NTC → cella 1S su J2 (3 poli) protetta DW01A + FS8205A
```
- **GPIO (VETO 1, corretto 18/11):** tabella completa hw↔fw in **`PIN_HW4.md`**, generata da `kicad/controlla_pin_fw.py`
  che cerca ogni GPIO in tutto il firmware hw3-def (macro L02_PIN_*, numeri scritti a mano come l'I2S del saluto,
  CONFIG_*PIN di sdkconfig) → **0 conflitti**. Regola applicata: su HW4 i pad che il firmware pilota senza servire
  (I2S del saluto 9/10/12/13, PA 53, reset Ethernet 51, C6 54) restano **liberi**: il firmware hw3-def può pilotarli
  senza danni. Errore di prima: avevo messo LED R/G su 9/10 e CAM_EN su 12, che il saluto apre in I2S
  (`logger02_saluto.c:36`) e lascia acceso se il codec non risponde.
  - Restano come HW3: SD 39-44 + accensione 45, I2C 7/8, IMU INT 4, SYNC A3→B21, UART 22/23, WAKE 5, batteria 20.
  - Nuovi (pad liberi per il firmware): CAM_EN **GPIO11** (pull-up 10k: camera accesa di default), LED R/G **GPIO50/52**
    sulla A, LED B **GPIO50** sulla B, buzzer **GPIO27**, TRIG camere GPIO2, CHRG GPIO26, VBUS GPIO21 (solo A: il
    firmware usa il 21 solo sulla B, `logger02_link.c:216-225`), reset/boot di B da A GPIO33/49, SPI A↔B 28-32.
  - Il saluto vocale non c'è più: col firmware hw3-def il task del saluto apre l'I2S su pad liberi, non trova il codec
    ed esce; il bip lo fa il firmware HW4 (proposta in `PROPOSTA_FIRMWARE_HW4.md`, flag `CONFIG_LOGGER02_HW4`).
    Cambi firmware per HW4: driver IMU, flag saluto→buzzer, pin LED. Nessuna modifica a logger02.
- **Alimentazione (corretta 18/11):** cella 1S → protezione DW01A+FS8205A → **power-path** (P-MOS AO3401A dalla cella,
  Schottky **SS34** da VBUS — 3 A, al posto di SS14 da 1 A che portava ~1,2 A, critico giro 3) → **interruttore esterno su J3** → VSYS → due buck TLV62569 (uno per modulo).
  **Stacco del cavo in registrazione (VETO 2, A12):** prima il gate di Q3 era la net VBUS, con 10 µF sopra: allo stacco
  la scheda restava sul diodo di body di Q3 (cella − 0,8 V) per 130-170 ms con R35 100k e **ancora 60-80 ms con R35 10k**,
  con la 3V3 a 2,5-3,0 V (`kicad/modello_power_path.py`). Abbassare R35 da solo non basta: ho messo R35 a 10k **e**
  alimentato il gate da VBUS attraverso **D8 (SS14: porta solo la corrente del gate, ~0,5 mA)**. Allo stacco D8 si interdice, il gate si scarica
  solo con la sua Ciss (645 pF + diodo) su 10k: **τ ≈ 7 µs**, mentre VBUS + VSYS impiegano 35-48 µs a scendere fino al
  diodo di body → Q3 conduce prima e la 3V3 resta a 3,30 V (3,14 V a cella 3,5 V). Con USB presente il gate sta a
  VBUS − 0,2 V e la sorgente a VBUS − 0,45 V: Q3 resta spento (Vgs ≈ +0,25 V, soglia −0,5…−1,3 V). Prova al COLLAUDO passo 4.
  Con USB collegato la scheda va da VBUS e la cella si carica da sola, così il TP4056 termina davvero a C/10 (prima, col
  carico sulla cella, la terminazione non scattava). Interruttore dopo l'OR: spento = spento anche in carica.
  **Tensione minima di cella (datasheet TI SLVSDG1C §7.3.2 pag. 6: VIN(MIN) = VOUT + IOUT·(RDS(ON) + RL); RDS(ON) FET
  alto 100 mΩ tip. a VIN 5 V, §6.5 pag. 5)** con 0,8 A di picco per buck, L 58 mΩ, RDS(ON) stimato 130 mΩ a 3,5 V:
  VSYS ≥ 3,30 + 0,8·0,19 = **3,45 V**. A monte cadono FS8205A (~0,08 V a 1,6 A), P-MOS (~0,11 V), cavo+interruttore
  (~0,05 V) → **cella ≥ ~3,7 V per 3,30 V pieni al picco**; fra 3,7 e ~3,4 V la 3V3 scende ma resta ≥ 3,0 V (minimo P4,
  checklist §Power); **spegnimento firmware a 3,45 V di cella a riposo**. Correzione: prima avevo scritto "sopra ~3,4 V"
  e citato "SLVSDB6": era sbagliato (critico, REGISTRO 16:58).
- **Carica:** TP4056 1 A lineare (R_PROG 1,2 kΩ → 1000 mA, tabella del datasheet) **con NTC sul TEMP** (VETO 1):
  6,8 kΩ da VBUS + NTC 10 kΩ B3950 (C51597) sulla scheda accanto al portabatteria. **Finestra reale** con le soglie del
  datasheet UMW (caldo 42-45 % di VCC, freddo 80-83 %), calcolo β del critico (REGISTRO 23:20): **sospende sopra 39-42 °C
  e sotto 0-4 °C**. J2 ha un 3° polo per l'NTC del pacco (piano B, 0 Ω da spostare).
- **Protezione cella:** DW01A + FS8205A (circuito tipico del datasheet DW01A): sovraccarica 4,30 V, sovrascarica
  2,5 V con rilascio 2,9 V (valori riletti dal critico sul datasheet PUOLOP).
- **VBUS (VETO 2):** J1 → **R36 0805 serie (0 Ω montato, posto per PTC o perla)** → VBUS_RAW con **TVS SMF5.0A** + USBLC6
  + 100 nF/50 V → **OVP AW32901** (Awinic, C407920, 0,24 $, stock 9526) → VBUS interna (C1 10 µF + 1 µF).
  Perché: SMF5.0A conduce da 6,4 V e limita a **9,2 V** a 21,7 A, sopra il **VCC max 6,5 V del TP4056 UMW** e il **VIN max
  6 V del TLV62569** (SLVSDG1C §6.1; arriva VBUS − D5). AW32901: soglia **5,83-6,07 V in salita, spegnimento in 50 ns,
  regge 120 V di surge, 27 mΩ, 5 A** (datasheet Awinic V1.0, tab. elettrica pag. 7, applicazione pag. 4: CIN 0,1 µF ≥ clamp
  del TVS, COUT 1 µF, OVLO a GND = soglia di default, EN attivo basso a GND, ACOK libero). Scartati: TVS a basso clamp
  (PESD5V0S1UL, TPD1E10B06 = ESD da 60-90 W, clamp 9-14 V: proteggono dalle scariche, non da un caricatore a 9 V) e la
  sola perla in serie (rallenta il picco ma non limita una sovratensione continua). Footprint secondo il land pattern del datasheet (pag. 19): **pad NSMD Ø0,23 mm, apertura solder mask Ø0,33 mm**, rinominato `FCQFN-12_1.3x1.8mm_P0.4mm_AW32901` (prima "BGA" con pad 0,20, critico giro 3). Rischio: CSP 3×4 passo 0,4 mm →
  fuga dei pad sul top unendo i pad della stessa net (IN/OUT/GND); da controllare allo sbroglio con le regole JLC.
  R36 è 0805 e non 0603 come chiedeva il critico: ci passano fino a 2 A (carica 1 A + scheda via D5) e lo 0 Ω 0603 è da
  1 A; lo 0 Ω 0805 (C17477) è da 2 A (valore tipico UniOhm, DA VERIFICARE sul datasheet).
- **Connettori batteria e interruttore non invertibili:** J2 cella = JST PH **3 poli** (+, NTC, −) S3B-PH-SM4-TB
  originale (C265101, stock 21k); J3 interruttore = PH **2 poli** (C2763693, stock 36k).
- **Programmazione (VETO 1):** il ROM del P4 scarica solo da UART0 (GPIO37/38) o USB-Serial/JTAG (24/25).
  A: USB-C. B: **J22 = pad PROG a 2,54 mm** (GND, U0TXD, U0RXD, EN, BOOT, 3V3) per pogo in collaudo o header saldato al
  banco + TP30/TP31 (USB-Serial/JTAG della B) per pogo; in campo la B si aggiorna via OTA wifi (ha la sua C6, come HW3).
  La A può resettare la B e metterla in download (GPIO33/49) ma non le parla sull'UART0: il recupero della B a firmware
  morto passa da J22 (case da aprire). Dettaglio passo per passo in `COLLAUDO.md` §7.
  - **Joint Download Mode = GPIO35 a 0 e GPIO36 a 1** (checklist P4 §Strapping). Su HW4 GPIO36 non è collegato: dentro il
    modulo c'è **R46 10 kΩ verso ESP_3V3** (schema Waveshare ESP32-P4-Module V1.1, letto dal critico a 400 dpi) → alto garantito.
  - **Console:** il firmware ha la console primaria su **UART0** (`CONFIG_ESP_CONSOLE_UART_DEFAULT`, sdkconfig:1693) e la
    secondaria su USB-Serial/JTAG. Sulla A i log completi escono solo da **J12** (DEBUG A, non montato): al bring-up si usa
    un adattatore USB-UART su J12; sull'USB-C arriva la console secondaria. Sulla B: J22.
  - **Identità A/B:** il ruolo lo dà la NVS "ident" scritta da `logger02/flasha_nuovo.sh` (logger02_ruolo.c), non un pin. Su
    HW4 lo script va lanciato con A sull'USB-C e B via adattatore su J22 (oggi chiede "attacca la A, poi la B" sul cavo USB:
    serve la porta seriale della B come argomento — da adattare in asmile-flotta, logger02 non si tocca).
- **Partitore batteria (VETO 2, A11):** sulla cella (in carica VSYS vale VBUS), **100k/33k come HW3, C4 non montato**.
  Il giro precedente (1M/330k + 100 nF) leggeva il **31,9 % in meno** perché `leggi_batteria()` (logger02_imu.c:77-84) mette il
  pull-down interno per 2 ms e rilegge dopo 2 ms: con 100 nF su 248 kΩ la costante è 24,8 ms. Modello con quella sequenza
  (`kicad/modello_partitore.py`): con 100k/33k e nodo da 20 pF (anche con 1 nF di sporco) **errore della RC 0,000 % fra
  3,0 e 4,2 V**, controllo "collegato" sempre sì. Restano errori non di RC: resistenze 1 % → ±1,36 % (99 % delle schede);
  ADC P4 con l'attenuazione del firmware (12 dB) **±15 mV = ±1,4-2,0 %** (datasheet P4 v0.7 Tab. 5-6 pag. 90). Per stare
  sotto l'1 % complessivo serve una **calibrazione a un punto in collaudo** (alimentatore a 3,80 V su J2 → fattore nella NVS);
  resistenze allo 0,1 % non bastano da sole perché domina l'ADC. Consumo: 32 µA sempre (≈ 23 mAh/mese, ~15 % in più
  dell'autoscarica di 2 × 18650).
- **Antenne:** si usa la versione del modulo con connettore IPEX (antenna adesiva fuori dal case); footprint u.FL +
  0 Ω non montati sulla scheda come piano B per la versione a castello senza IPEX.
- **SD:** due slot (una per modulo, come HW3). Piano: quando il firmware manderà il video della B alla A via SPI, lo
  slot B resta non montato.
- **Rischio back-feed:** se un giorno la B verrà spenta (buck B con EN da A, ponticello non montato), le linee A→B
  devono essere basse/alte impedenza: resistenze serie 1 kΩ su UART/EN/BOOT, 33 Ω su SPI (lezione ADS1115 del 17/11).

## 5. Datasheet incrociati (cosa ho controllato e dove)
| Punto | Fonte | Esito |
|---|---|---|
| P4: alimentazione unica 3,3 V, ≥380 mA con flash+PSRAM | Espressif HW design guidelines P4 — Schematic Checklist §Power | il modulo Waveshare prende 3,3 V (pad ESP_3V3); budget per modulo 0,5 A picco con C6 |
| P4: GPIO35 strapping (pull-up, niente C grandi), 34-38 strapping | idem §Strapping | GPIO35 = BOOT con 10 kΩ + pulsante; 34/36 non usati |
| P4: USB serial/JTAG su GPIO24/25 | idem §USB | USB-C → 22 Ω serie → GPIO24/25 della A, ESD USBLC6 |
| P4: SD slot 0 fisso su GPIO39-48, pull-up su ogni linea | idem §SD/MMC | pull-up 10 kΩ al pad ESP_LDO_VO4 (VDD_IO_5 del modulo, come la dev-kit) |
| P4: un solo ISP, H.264 dual-stream ≤1080p30, H.264 accetta GRAY | datasheet P4 v0.7 §4.2.1.2 p.63, §4.2.1.5 p.65 | regge K2 sulla carta → prova P2 |
| P4: domini IO (VDD_LP 0-15, VDD_IO_0 16-23, VDD_IO_4 24-38, VDD_IO_5 39-48, VDD_IO_6 49-54) | datasheet P4 v0.7 Tab. 2-1 p.14-16 | tutto a 3,3 V sul modulo |
| Modulo Waveshare: 88 pad, GPIO14-19 interni (C6 SDIO), C6 reset GPIO54 | wiki Waveshare + logger02.h | pad 82 lasciato libero |
| OV9281: MIPI 2 lane + DVP, FSIN, SID, XVCLK 6-27 MHz, 2,8/1,8/1,2 V | OVT PB v1.4 | sul modulo Pi le tensioni le fa il modulo: alla scheda servono solo 3,3 V |
| LSM6DS3TR-C: INT1 programmabile wake-up, I2C 0x6A (SA0 a GND), aux non usati | ST DS LSM6DS3TR-C §4 pin description | INT1 → GPIO4 (come MPU6050 di HW3) |
| TP4056: PROG 1,2 kΩ = 1 A, CHRG open-drain; TEMP fra 45 % e 80 % di VCC, a GND = funzione disabilitata | datasheet TP4056 (NanJing Top Power) tab. R_PROG, pin TEMP | CHRG con pull-up a 3V3_A → GPIO26; NTC 10k B3950 + 6,8k (finestra reale 0-4 °C … 39-42 °C) |
| TLV62569DBV: RDS(on) 100/60 mΩ, ILIM 3 A, 100 % duty: VIN(MIN) = VOUT + IOUT·(RDS(ON)+RL) | TI **SLVSDG1C** §6.5 pag. 5, §7.3.2 pag. 6 | cella ≥ ~3,7 V per 3,30 V pieni a 0,8 A; ≥ 3,0 V fino a ~3,4 V di cella |
| P4: ROM download solo da UART0 37/38 e USB-Serial/JTAG | checklist P4 §Strapping (Joint Download Mode) e §UART | A da USB-C; B da pad J22 (UART0+EN+BOOT) o TP30/31 (USB) |
| TP4056 UMW (C725790): VCC max 6,5 V; TEMP caldo 42-45 %, freddo 80-83 % di VCC | datasheet UMW (riletto dal critico) | OVP a 5,95 V davanti; NTC 39-42 °C / 0-4 °C |
| AW32901: OVP 5,83-6,07 V, tOFF 50 ns, surge 120 V, RON 27 mΩ, CIN 0,1 µF, COUT 1 µF, OVLO a GND | Awinic AW329xx V1.0, pag. 4 (applicazione) e 7 (protezioni) | U7 su VBUS |
| ADC P4: errore totale ±15 mV con ATTEN3 (0-3300 mV), misurato con 100 nF sull'ingresso | datasheet P4 v0.7 Tab. 5-6 pag. 90 | partitore: calibrazione a un punto in collaudo per < 1 % |
| AO3401A: Ciss 645 pF, Vgs(th) −0,5/−0,9/−1,3 V, Vsd ≤ 1 V a 1 A | datasheet AOS AO3401A | gate di Q3 via D8, R35 10k: τ 7 µs |
| DW01A/FS8205A: piedinatura e soglie | datasheet PUOLOP DW01A Rev B, FS8205A TECH PUBLIC (riletti dal critico) | 4,30 V / 2,5 V (rilascio 2,9 V) |

## 6. Rischi e prove PRIMA di ordinare
| # | Rischio | Prova (su hardware di banco, MAI su logger02) | Passa se |
|---|---|---|---|
| P1 | pin 1 / numerazione del footprint del modulo (DXF senza numeri) | Daniele guarda un modulo vero: punto/triangolo del pin 1 e pad GND 1, 3, 15 col tester verso lo schermo | numerazione = `kicad/lib/hw4.pretty/Waveshare_ESP32-P4-Module.kicad_mod` |
| P2 | (solo per K2/v2) 2 flussi H.264 1280×720 su un P4 | esempio `esp_h264 hw_dual_enc` sulla dev-kit di banco con 2 flussi 1280×720 GRAY/YUV a 16,7 fps, 10 min | ≥16,7 fps entrambi, 0 perdite |
| P3 | connettore FFC 15 pin: lato dei contatti compatibile coi cavi delle camere di HW3 | Daniele: foto del cavo (contatti stesso lato o opposti) | pezzo C7529394 scelto di conseguenza |
| P4 | luce della sera con OV9281 | giro serale con logger02 (già fatto dal firmware) | luminosità media ≥ 60 a 50 lux |
| P5 | (v2) SC132GS al posto di OV9281 | 1 modulo sulla dev-kit di banco | immagini e depth confrontabili |
| P6 | autonomia: 2 moduli + 2 camere su 2 × 18650 | misura corrente di logger02 in registrazione | ≥ 4 h |
| P7 | flash della B in collaudo | adattatore USB-UART 3,3 V con DTR/RTS su pad J22 di una scheda (o pogo su TP30/31) | `esptool --chip esp32p4 chip_id` sulla B |
| P9 | hot-plug USB e sovratensione | caricatore da 5 V con cavo lungo inserito 20 volte con sonda (10×, 50 MHz) su VBUS_RAW e VBUS; poi alimentatore da banco a 9 V su J1 | picco su VBUS ≤ 6,0 V; con 9 V VBUS = 0 (OVP aperto) e nulla si scalda | 
| P10 | stacco USB in registrazione | sonda su 3V3_A, trigger sul fronte di discesa di VBUS, cavo tolto 20 volte con le camere che registrano | 3V3_A ≥ 3,0 V sempre, nessun reset (log della A continuo) |
| P8 | 3V3 sotto carico a cella bassa | alimentatore al posto della cella, 3,6 → 3,3 V, B e A in registrazione + wifi | 3V3 ≥ 3,0 V fino a 3,4 V; firmware si spegne a 3,45 V |

## 7. Costi (rifatti dopo il VETO 1: PCB e montaggio dallo **stesso fornitore, JLCPCB**; `kicad/costi.py`)
Fonti: PCB nudo = preventivo JLCPCB vero (4 strati 250×50 ENIG, 18/11, `preventivo/jlcpcb_*.jpg`; PCBWay per confronto
in `PREVENTIVO_PCBWAY.md`) · pezzi = API JLC (`kicad/prezzi_jlc.json`, 127 montati; **24 codici Extended nel BOM = 23 montati + l'u.FL C88374 solo non montato**: la tassa JLC da 3,07 $ si paga sui 23 montati) · montaggio = tariffe
JLCPCB standard pubblicate (setup 25,56 $, stencil 15,72 $, 3,07 $/Extended, 0,0016 $/giunto) **+ saldatura a mano dei 2
moduli castellati forniti da noi** (176 giunti × 0,0164 $ + 3,58 $/ordine, FAQ JLC) · moduli 9,99-10,99 $ (sito
Waveshare) · cambio 1 € = 1,10 $. Il montaggio resta **NON VERIFICATO** (serve il preventivo coi file veri).

| per scheda | 10 pz | 100 pz | 1000 pz |
|---|---|---|---|
| PCB nudo + spedizione (JLC) | 9.11 $ | 3.58 $ | 2.30 $ |
| pezzi LCSC | 5.23 $ | 4.35 $ | 3.39 $ |
| montaggio JLC (macchina + moduli a mano) | 15.04 $ | 4.64 $ | 3.60 $ |
| 2 moduli Waveshare + 2 antenne | 23.98 $ | 21.18 $ | 20.78 $ |
| **netto (senza IVA)** | **53.35 $ = 48.5 €** | **33.75 $ = 30.7 €** | **30.08 $ = 27.3 €** |
| con dazio 3,5 % + IVA 22 % (IVA non recuperata) | 60.4 € | 38.0 € | 33.8 € |

IVA recuperabile se l'acquisto è fatto con la P.IVA della ditta individuale di Daniele: allora conta la riga netta. Spedizione JLC in DDP = dazi già pagati alla consegna; altrimenti +25-75 € di sdoganamento a spedizione (≈ +0,5 € a scheda su 100).


| Scenario completo (€, netto IVA) | 100 pz | 1000 pz |
|---|---|---|
| K1 + 2 OV9281 modulo (volume stimato 18 $ / 14 $) | 63,4 € | 52,8 € |
| K1 + 2 OV9281 DFRobot (22 $ / 20 $) | 70,7 € | 63,7 € |
| K2 (1 modulo + DVP) senza camere | 19,2 € | 16,1 € |
| K2 + 2 OV9281 nudi (oggi non comprabili) | 35,6 € | 28,8 € |

**Lettura 1 — "25 € tutto compreso":** non raggiungibile con OV9281 (minimo ~29 € a 1000 pz con un solo P4, sensori
saldati e DVP: tre rischi insieme). **Lettura 2 — "25 € la scheda":** K1 a 100 pz = 30,7 € netti (6 € sopra; i moduli
sono 19 €), a 1000 pz 27,3 €; K2 19,2 € ma con driver DVP da scrivere e modulo DVP da trovare.

**Scorte a 1000 schede (VETO 1):** FFC 15p C7529394 stock **935** (ne servono 2000): alternative FC-10A15P11H20
C23397372 (1655) e C23397383 (1512) — pad di segnale uguali (±0,07 mm) ma linguette a 9,2 vs 8,75 mm → **footprint
combinato da fare allo sbroglio**, oppure ordine in pre-ordine. Connettori batteria: tolto il clone C54582899
(2723); ora J2 = S3B-PH-SM4-TB JST (21 731) e J3 = PH-2AWT (36 152): coprono 1000 schede. Tutti gli altri codici
hanno ≥ 7000 pezzi tranne LSM6DS3TR-C (16 153, ok) e ESP32-C6/P4 non usati.

**IVA e dogana:** la tabella mostra anche il caso peggiore (dazio 3,5 % sul montato + IVA 22 % non recuperata).
JLC spedisce in DDP (dazi pagati); con la P.IVA della ditta di Daniele l'IVA si recupera e conta la riga netta. I due
moduli Waveshare arrivano a parte: stessa IVA, spedizione da aggiungere al loro preventivo.

## 8. Verifiche KiCad e layout (strato 3-4)
KiCad 10.0.8 installato in `/Applications/KiCad` (senza modelli 3D, disco al 98 %). Dopo l'ultima netlist (18/11/2026):
- **ERC: 0 violazioni** — `kicad/ERC.rpt` del **2026-11-18T23:02:09**.
- **Netlist esportata da KiCad = `netlist_hw4.py` pin per pin: 526 pin, 0 differenze** (`kicad/verifica_netlist.py`).
- **Tabella pin hw↔fw: 0 conflitti** (`PIN_HW4.md`, `kicad/controlla_pin_fw.py`).
- **DRC del piazzamento: 0 errori di rame/sovrapposizione**; restano 391 collegamenti da sbrogliare + 195 avvisi di
  serigrafia — `kicad/DRC.rpt` del **2026-11-18T23:02:18**. Nota del critico: il DRC non controlla le sovrapposizioni dei
  footprint senza courtyard; il piazzamento le evita per costruzione (ingombro = courtyard ∪ pad, `genera_pcb.py`).
Layout: 250 × 50 mm (proposta), camere a 200 mm fra gli assi ottici. Fori camere e case da concordare col Doppio;
lo sbroglio non è fatto → niente gerber di produzione finché il layout non regge.

## 9. Bozze ai fornitori (partono solo col tap di Daniele, `~/progetti/CONTATTI-ESTERNI.md`)
In `BOZZE_FORNITORI.md`: Waveshare (prezzo moduli a 100/1000), Arducam + Inno-Maker (OV9281 M12 con trigger a 100 pz),
Sinoseen (barra stereo COB 2 × OV9281 a 200 mm), OmniVision/distributore (datasheet completo OV9281 sotto NDA).
