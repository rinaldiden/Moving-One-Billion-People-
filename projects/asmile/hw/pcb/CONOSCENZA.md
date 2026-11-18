# Conoscenza PCB di Asmile — dove risparmiare, dove spendere, regole provate

Casa di **asmile-hw-pcb** (la aggiorna lui, con prova e fonte per ogni riga) e del suo critico **asmile-pcb-critico**.
Principi di Daniele (18/11/2026): tutto quello che si fa in software si fa in software; meno hardware = meglio;
semplifica e unifica; lato compute stai largo (margine per metterci mano); obiettivo logger ~25 € scheda + camere.
Ogni riga rimanda al `REGISTRO.md` (quando/fonte) — qui sta solo la regola.

## Punti di partenza del capo (18/11) — esito della verifica
| Punto | Esito | Fonte |
|---|---|---|
| P4 regge MIPI-CSI + DVP insieme | **vero sulla carta**: l'ISP ha 3 ingressi (CSI, DVP, AXI-DMA) ma è **uno solo**; DVP 8/16 bit su qualunque GPIO | datasheet P4 v0.7 §4.2.1.2 p.63, LCD_CAM p.64-65 |
| H.264 a 2 flussi | **vero**: dual-stream con totale ≤ 1080p30; accetta anche GRAY. 2×720p@16,7 = 49 % del limite. Esempi esp_h264 chiedono P4 rev ≥ 3.1 e IDF ≥ 5.5.3 | datasheet P4 v0.7 §4.2.1.5 p.65; esp_h264 1.5.0 |
| OV9281 ha anche DVP, esp_cam_sensor solo MIPI | **vero** (PB OVT v1.4: D[9:0], FSIN, SID); driver DVP OV9281 non esiste | OVT PB v1.4; README esp_cam_sensor |
| chip OV9281 stock 0 su LCSC | **vero** (10,75 $, stock 0; anche Arrow 0, 16 sett.). Datasheet completo (mappa sfere, sequenza alimentazioni) **non pubblico** | LCSC C5182169, Arrow |
| OV9782 = versione colore | vero, ma **senza driver** esp_cam_sensor | README esp_cam_sensor |
| SC035HGS = VGA GS MIPI+DVP | vero, driver c'è; a 20 m la depth sbaglia 1,1 m (VGA) → scartato | conto ΔZ in DESIGN.md §3 |
| P4NRW32 EOL → P4NRW32X | vero, ma **anche la X è a stock 0** (LCSC/JLC/DigiKey, rientro apr-2027, Espressif MOQ 2000) | API JLC 18/11, DigiKey AU |
| un solo P4 + sensori saldati, niente moduli/flat | **non fattibile oggi**: nessun sensore nudo comprabile via JLC, chip P4 nudo a stock 0 → HW4 v1 su 2 moduli Waveshare + camere FFC | REGISTRO 14:58-15:27 |

## Dove si può risparmiare (con prova)
- **Moduli Waveshare ESP32-P4-Module (~10 $) invece del chip nudo**: P4 + PSRAM 32 MB + flash + C6 + DCDC core + quarzo
  già fatti, stesso pinout di HW3 → firmware riusato. Il chip nudo costerebbe ~2-3 $ in meno a scheda e oggi non si compra.
- **Stessi GPIO della versione precedente** = firmware riusato (HW4 tiene i pin di HW3: SD 39-45, I2C 7/8, IMU 4, SYNC 3→21,
  UART 22/23, WAKE 5, batteria 20). Unico cambio sw: driver IMU (LSM6DS3TR-C al posto di MPU6050).
- **Saluto vocale → buzzer attivo sul pin del PA (GPIO53)**: via ES8311 + amplificatore + altoparlante; il firmware che
  accende il PA fa suonare il buzzer. 0,33 $ + transistor.
- **Step-up 5 V + modulo carica + regolatori delle dev-kit → caricatore 1S + 2 buck 3,3 V a duty 100 %** (TLV62569, 0,05 $,
  stock 548k, stesso pezzo per entrambi i moduli = un solo codice in BOM).
- **Protezione cella DW01A + FS8205A**: 0,09 $ per non avere una 18650 in corto in bici. Si spende poco, si salva tanto.
- **Footprint non montati (DNP) per i piani B**: u.FL se il modulo arriva senza IPEX, header di debug, ponticello per
  spegnere la B da A, header espansione. Costano zero.
- **Passivi tutti Basic JLC** tranne 1,2 kΩ (R_PROG): un Extended in più costa ~3 $ a ordine, non a scheda.

## Dove bisogna spendere (con prova)
- **Sensore = quello del veicolo che userà i dati** (OV9281 mono global shutter come #001): cambiare sensore per
  risparmiare cambia il dominio dei dati di training. Global shutter obbligatorio in bici (vibrazioni, rolling = righe storte
  diverse sulle due camere).
- **Risoluzione orizzontale ≥ 1280 px** per la depth a 10-20 m con B = 200 mm (ΔZ = Z²·Δd/(f·B)).
- **Finitura ENIG** (non HASL) con modulo a castello passo 1 mm, IMU LGA e USB-C a passo fine: planarità. DA CONFERMARE col
  preventivo (differenza di prezzo in PREVENTIVO_PCBWAY.md).
- **Traccia/spazio 4/4 mil** solo perché il footprint USB-C del costruttore ha pad a 0,10 mm (regola limitata a J1 nel .kicad_dru).
- **ESD sull'USB-C** (USBLC6) — unico connettore esposto all'utente.

## Regole di metodo (provate oggi)
- **Footprint dei pezzi LCSC con easyeda2kicad**: è il disegno che usa JLC per montare quel codice → niente footprint "simili".
  Dopo l'import: pin "unspecified" → tipi veri (ERC), fori di centraggio PTH-senza-rame → NPTH, blocco `(model …)` tolto intero.
- **Netlist in Python come unica fonte**, schema e PCB generati: le modifiche si fanno nella netlist (A1).
- **ERC = 0 non basta**: esportare la netlist da KiCad e confrontarla pin per pin con quella voluta (verifica_netlist.py).
- **Prima del datasheet, il codice che gira**: i pin veri di HW3 erano nel firmware (logger02.h), non nel brief
  (es. SYNC GPIO3 è un impulso 1 Hz, non il trigger delle camere; la sync è software via VTS).
- **Prezzi e stock dall'API parti JLC** (`selectSmtComponentList`), con data; `componentLibraryType == base` = Basic.
- **KiCad senza installazione**: il DMG già scaricato montato in sola lettura dà kicad-cli e il Python di pcbnew (10.0.8).
  L'installazione con brew chiede la password del Mac → la fa Daniele.

## Lezioni dai registri del progetto (sw e hw) che valgono per le schede
- **Ritorno di corrente (ADS1115, 17/11)**: su un bus con un dispositivo sempre alimentato, i moduli alimentati da un'altra
  rail non devono avere pull-up proprie. HW4: tutto il bus I2C della A (camera SX, IMU, pull-up) sta sulla stessa 3V3_A; le
  linee A↔B hanno 1 kΩ in serie (33 Ω su SPI) per il giorno in cui la B si spegnerà da sola. Fonte: agents/lezioni/asmile-banco-hw.md.
- **La prova prima/dopo di Daniele vince sulla teoria** (feedback_prova_prima_dopo): in collaudo, un pezzo alla volta.
- **OTA una scheda alla volta, rollback solo a rete OK** (feedback_ota_una_scheda, flotta HW3): la scheda HW4 ha UART e
  BOOT di B raggiungibili da A e da header → si può sempre recuperare una B senza aprire il case.
- **Segreti mai nel firmware** (feedback_segreti_mai_nel_firmware): nessun dato di rete nei file di progetto KiCad/BOM.
- **Case: montaggio prima della forma** (feedback_case_montaggio_prima): fori camere, viti, connettori e passaggio cavi si
  fissano col Doppio PRIMA dello sbroglio.

## Prezzi verificati (18/11/2026, USD, API JLC/LCSC salvo nota) — tabella viva in `logger_hw4/kicad/prezzi_jlc.json`
| Pezzo | Codice | a 100 | Stock | Nota |
|---|---|---|---|---|
| ESP32-P4NRW32X | C54540373 | 4,47 | 0 | Extended |
| Waveshare ESP32-P4-Module | — | 9,99-10,99 | sì | waveshare.com |
| ESP32-C6-MINI-1-N4 | C5736265 | 2,99 | 7098 | |
| W25Q128JVSIQ | C97521 | 1,54 | 73783 | Basic |
| TLV62569DBVR | C141836 | 0,053 | 548054 | |
| TP4056 | C725790 | 0,061 | 305434 | |
| LSM6DS3TR-C | C967633 | 0,86 | 16153 | |
| MPU-6050 | C24112 | 16,21 | 6150 | a fine vita: non usare |
| OV09281-H64A | C5182169 | 10,75 | 0 | |
| modulo OV9281 Pi | — | 24 (DFRobot a 10+) – 45 (dettaglio IT) | sì | |
| modulo SC132GS Camemake | — | 77,84 a 10 · 8,80 a 1000 | 1000 (25 gg) | DigiKey |

## FONTI DEL MIO SAPERE (verificate, con data) — da copiare nella scheda agente dal capo
- Espressif ESP32-P4 Schematic Checklist · docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32p4/schematic-checklist-esp32p4.html · alimentazione, DCDC, strapping, USB, SD, MIPI · 18/11
- ESP32-P4 Datasheet v0.7 · espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf · pin/domini IO, ISP, H.264 · 18/11
- espressif/kicad-libraries · github · simbolo ESP32-P4X + footprint QFN-104 · 18/11
- esp-video-components/esp_cam_sensor README · github · sensori con driver · 18/11
- Waveshare ESP32-P4-Module wiki + land pattern DXF · waveshare.com/wiki/ESP32-P4-Module · 88 pad, pinout · 18/11
- OVT OV9281 product brief v1.4 · ovt.com · interfacce e alimentazioni · 18/11
- API parti JLCPCB `selectSmtComponentList` + wmsc.lcsc.com product/detail · prezzi/stock · 18/11
- easyeda2kicad 1.0.1 (pip) · simboli/footprint dei codici LCSC · 18/11
- PCBWay preventivo online `orderonline.aspx` (senza login) · prezzo PCB · 18/11

## Errori fatti e regola che ne è nata → `ANTIPATTERN.md`
