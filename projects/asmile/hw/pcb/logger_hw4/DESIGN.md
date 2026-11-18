# Logger HW4 — scheda dedicata (DESIGN)

> **Maturità: L0 → verso L1.** Oggi: studio + schema KiCad generato. Niente è ancora stato acceso né ordinato.
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
   │ SD-A, IMU, USB-C   │                                                          │ SD-B (opz.)        │
   └─────────┬──────────┘                                                          └─────────┬──────────┘
          3V3_A (buck TLV62569)            VSYS ← interruttore esterno ← cella 1S protetta      3V3_B (buck TLV62569)
                                       USB-C 5 V → TP4056 1 A → cella   (DW01A + FS8205A)
```
- **Stessi GPIO di HW3** (logger02.h): SD 39-44 + accensione GPIO45, I2C 7/8, IMU INT 4, SYNC A3→B21, UART 22/23,
  WAKE 5, batteria GPIO20 con 100k/33k, buzzer sul pin del PA (GPIO53) → il firmware `hw3-def` gira con **un solo
  cambio: il driver IMU** (LSM6DS3TR-C al posto del MPU6050, che su LCSC costa 16 $ ed è a fine vita); il saluto vocale
  diventa un bip. CAM_EN (GPIO12) ha un pull-up: camera accesa anche se il firmware non tocca il pin. Nuovi: TRIG camere GPIO2 della A, LED R/G su GPIO9/10, CHRG su GPIO26,
  VBUS su GPIO21 della A, reset e boot di B da A (GPIO33/49), SPI A↔B GPIO28-32.
- **Alimentazione:** due buck TLV62569 (stesso pezzo, uno per modulo, 2 A, duty 100 % → 3,3 V finché la cella sta
  sopra ~3,4 V), ingresso diretto dalla cella dopo protezione e interruttore. Spariscono MT3608 (5 V) e MH-CD42.
  Datasheet TLV62569: Vin 2,5-5,5 V, 2 A, 100 % duty cycle (TI SLVSDB6, §7.4). DA VERIFICARE pagina esatta.
- **Carica:** TP4056 1 A lineare (R_PROG 1,2 kΩ → 1000 mA, tabella del datasheet). Lento (~6 h per 6000 mAh) ma
  semplice; IP2312 (switching 3 A) è l'alternativa se Daniele vuole la ricarica in 3 h (stock basso al 18/11).
- **Protezione cella:** DW01A + FS8205A (schema di riferimento del datasheet DW01A). Spesa: 0,09 $.
- **Antenne:** si usa la versione del modulo con connettore IPEX (antenna adesiva fuori dal case); footprint u.FL +
  0 Ω non montati sulla scheda come piano B per la versione a castello senza IPEX.
- **SD:** due slot (una per modulo, come HW3: firmware invariato). Piano: quando il firmware manderà il video della B
  alla A via SPI, lo slot B resta non montato.
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
| TP4056: PROG 1,2 kΩ = 1 A, CHRG open-drain | datasheet TP4056 (NanJing Top Power) tab. R_PROG | CHRG con pull-up a 3V3_A → GPIO26 |

## 6. Rischi e prove PRIMA di ordinare
| # | Rischio | Prova (su hardware di banco, MAI su logger02) | Passa se |
|---|---|---|---|
| P1 | pin 1 / numerazione del footprint del modulo (DXF senza numeri) | Daniele guarda un modulo vero: punto/triangolo del pin 1 e pad GND 1, 3, 15 col tester verso lo schermo | numerazione = `kicad/lib/hw4.pretty/Waveshare_ESP32-P4-Module.kicad_mod` |
| P2 | (solo per K2/v2) 2 flussi H.264 1280×720 su un P4 | esempio `esp_h264 hw_dual_enc` sulla dev-kit di banco con 2 flussi 1280×720 GRAY/YUV a 16,7 fps, 10 min | ≥16,7 fps entrambi, 0 perdite |
| P3 | connettore FFC 15 pin: lato dei contatti compatibile coi cavi delle camere di HW3 | Daniele: foto del cavo (contatti stesso lato o opposti) | pezzo C7529394 scelto di conseguenza |
| P4 | luce della sera con OV9281 | giro serale con logger02 (già fatto dal firmware) | luminosità media ≥ 60 a 50 lux |
| P5 | (v2) SC132GS al posto di OV9281 | 1 modulo sulla dev-kit di banco | immagini e depth confrontabili |
| P6 | autonomia: 2 moduli + 2 camere su 2 × 18650 | misura corrente di logger02 in registrazione | ≥ 4 h |

## 7. Costi (USD → € a 1 € = 1,10 $; dettaglio `BOM.csv`, `kicad/costi_bom.json`, `PREVENTIVO_PCBWAY.md`)
Voci per scheda: PCB PCBWay 4 strati ENIG + DHL (prezzo vero a 10/100, stima a 1000) · pezzi LCSC dal BOM (prezzo vero
API JLC) · montaggio stimato con le tariffe JLC (NON VERIFICATO) · moduli Waveshare 9,99-10,99 $ · antenne IPEX (stima).
| | a 10 | a 100 | a 1000 |
|---|---|---|---|
| PCB nudo + spedizione | 17,12 $ | 4,28 $ | 2,30 $ (stima) |
| pezzi LCSC (116 montati) | 4,48 $ | 3,74 $ | 2,94 $ |
| montaggio | 13,18 $ | 2,77 $ | 1,22 $ |
| **carrier senza moduli** | 34,78 $ | **10,79 $ (9,8 €)** | 6,46 $ |
| **K1 = carrier + 2 moduli + 2 antenne** | 58,76 $ (53,4 €) | **31,97 $ (29,1 €)** | 27,24 $ (24,8 €) |
| K2 = 1 modulo, camera DX in DVP (piano B) | 45,97 $ (41,8 €) | 20,58 $ (18,7 €) | 16,05 $ (14,6 €) |

**Lettura 1 — "25 € tutto compreso" (scheda + 2 camere):**
| | a 100 | a 1000 |
|---|---|---|
| K1 + 2 × OV9281 modulo (prezzo in volume stimato 18 $ / 14 $) | 61,8 € | 50,2 € |
| K1 + 2 × OV9281 modulo DFRobot (22 $ / 20 $) | 69,1 € | 61,1 € |
| K2 + 2 × OV9281 nudo + M12 (oggi non comprabile) | 35,1 € | **27,3 €** |
→ **25 € tutto compreso non si raggiunge** con OV9281 a 100 pz. Il minimo realistico è ~27 € a 1000 pz con un solo P4,
camere a sensore saldato (via modulista) e DVP: tre rischi insieme. Con il P4 nudo, quando tornerà a stock, -3/4 € → ~24 €.

**Lettura 2 — "25 € la scheda, camere a parte":**
- **K1 (raccomandata) a 100 pz: 29,1 €** → sopra di 4 €. Il 63 % sono i due moduli Waveshare (18 €): è il prezzo di
  avere firmware HW3 invariato, compute doppio e nessun progetto RF/alimentazione P4. A 1000 pz 24,8 € (dentro).
- K2 a 100 pz: 18,7 € (dentro), ma solo dopo la prova P2 e con un modulo OV9281 DVP che oggi non si trova.

Dove si limerebbe senza cambiare architettura: preventivo Waveshare a 100 pz (oggi prezzo da sito), 17 Extended → meno
codici (es. un solo valore di LED e di condensatore), seconda SD non montata quando il video della B passerà via SPI (−0,5 $).

## 8. Layout (strato 4) — NON ancora fatto
Meccanica prima: 250 × 50 mm (proposta), camere a 200 mm fra gli assi ottici, fori delle camere e del case da
concordare col Doppio. Il generatore piazza i footprint per zone (camere agli estremi, moduli vicino alle camere,
alimentazione al centro), lo sbroglio non è fatto: niente gerber di produzione finché il layout non regge.

## 9. Bozze ai fornitori (partono solo col tap di Daniele, `~/progetti/CONTATTI-ESTERNI.md`)
In `BOZZE_FORNITORI.md`: Waveshare (prezzo moduli a 100/1000), Arducam + Inno-Maker (OV9281 M12 con trigger a 100 pz),
Sinoseen (barra stereo COB 2 × OV9281 a 200 mm), OmniVision/distributore (datasheet completo OV9281 sotto NDA).
