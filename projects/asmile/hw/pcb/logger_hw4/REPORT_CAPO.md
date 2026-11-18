# Report al capo — logger HW4 (asmile-hw-pcb, 18/11/2026) · maturità L0 → L1

**Scelta.** Una scheda unica 250 × 50 mm, 4 strati, con **2 moduli Waveshare ESP32-P4-Module** (gli stessi di HW3) e
**2 camere OV9281 mono global shutter** su FFC 15 pin + trigger, baseline 200 mm rigida. Stessi GPIO di HW3: il
firmware `hw3-def` gira con **un solo cambio (driver IMU LSM6DS3TR-C)**. Spariscono: 2 dev-kit, MH-CD42, MT3608,
ES8311+altoparlante, MPU6050, fili A↔B. Arrivano: 1S con TP4056 + protezione DW01A/FS8205A, 2 buck TLV62569, buzzer.
Perché non "1 P4 + sensori saldati": chip P4 nudo e TUTTI i sensori nudi a **stock 0** (LCSC/JLC/DigiKey), datasheet
OV9281 completo sotto NDA, nessun modulo OV9281 DVP a catalogo. Resta piano B (HW4-v2) dopo le prove P2/P5.

**Costo per scheda (USD→€ 1,10; PCB = preventivo PCBWay vero, pezzi = API JLC, montaggio = stima tariffe JLC):**
| | 10 pz | 100 pz | 1000 pz |
|---|---|---|---|
| scheda K1 (2 moduli) senza camere | 53,4 € | **29,1 €** | 24,8 € |
| piano B K2 (1 modulo + DVP) senza camere | 41,8 € | 18,7 € | 14,6 € |
| K1 + 2 OV9281 modulo (stima volume) | — | 61,8 € | 50,2 € |
| K2 + 2 OV9281 nudi (non comprabili oggi) | — | 35,1 € | 27,3 € |
"25 € tutto": non raggiungibile con OV9281 (minimo ~27 € a 1000 pz con 3 rischi insieme). "25 € scheda": K1 sta
4 € sopra a 100 pz (i moduli sono 18 €), dentro a 1000; K2 dentro ma con driver DVP da scrivere.

**Verificato:** datasheet P4 v0.7 + checklist Espressif (alimentazione, strapping, USB, SD, domini IO, ISP unico,
H.264 dual ≤1080p30) · driver esp_cam_sensor · stock/prezzi 18/11 (API JLC) · ERC 0 e **netlist KiCad = netlist voluta
pin per pin (494 pin)** · DRC del piazzamento: 0 errori rame · PCB PCBWay 10 pz 130,89 $, 100 pz 350,89 $ (ENIG 4/4 mil).
**NON verificato:** pin 1 del footprint del modulo (dal DXF, P1) · lato contatti FFC (P3) · prezzo Waveshare e camere a
100 pz · montaggio PCBWay (serve upload file + login) · spedizione Italia · sbroglio (non fatto: 364 collegamenti) ·
nessun pezzo acceso.

**Decisioni per Daniele:**
1. Lettura dei 25 €: accetti K1 a ~29 € (firmware riusato, compute doppio) o vuoi spingere K2 (~19 €, driver DVP e modulo DVP da trovare)?
2. Lente/FOV delle camere: uguale a #001 (~58°) per avere dati nello stesso dominio? E una SD sola (video B via SPI, firmware nuovo) o due come HW3?
3. Mandare le 4 bozze fornitori (`BOZZE_FORNITORI.md`: Waveshare, Arducam/Inno-Maker, Sinoseen, OmniVision)?

File: `DESIGN.md`, `BOM.csv`/`BOM_JLC.csv`, `kicad/` (genera tutto da `netlist_hw4.py`), `PREVENTIVO_PCBWAY.md`,
`COLLAUDO.md`, `../STACK_HW.md`, `../CONOSCENZA.md`, `../REGISTRO.md`. KiCad usato dal DMG (brew chiedeva la password).
