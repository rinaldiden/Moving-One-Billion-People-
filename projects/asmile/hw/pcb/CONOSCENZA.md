# Conoscenza PCB di Asmile — dove risparmiare, dove spendere, regole provate

Casa di **asmile-hw-pcb** (la aggiorna lui, con prova e fonte per ogni riga) e del suo critico **asmile-pcb-critico**.
Principi di Daniele (18/11/2026): tutto quello che si fa in software si fa in software; meno hardware = meglio;
semplifica e unifica; lato compute stai largo (margine per metterci mano); obiettivo logger ~25 € scheda + camere.

## Punti di partenza (capo, 18/11/2026 — DA VERIFICARE sui datasheet, non sono ancora regole)
- ESP32-P4 regge **una camera MIPI-CSI e una DVP insieme** (blog Arduino ESP_Video di Espressif, 09/2026; driver IDF
  `esp_cam_ctlr_csi` + `esp_cam_ctlr_dvp`). Se regge davvero 2×1280×720@16,7 → un solo P4 per logger invece di due.
- Encoder H.264 hardware del P4: >1080p30 per un flusso, **due flussi indipendenti** supportati (esp_h264). Due 720p a
  16,7 fps ≈ metà del limite 1080p30 sulla carta: MISURARE prima di ordinare.
- OV9281: datasheet OmniVision = uscite MIPI 2 lane **e** DVP; esp_cam_sensor ha solo il driver MIPI (DVP = da scrivere).
  Chip OV09281-H64A su LCSC C5182169: ~5 $ a 840 pz, ~11-14 $ a 1 pz, stock 0 al 18/11, un aggregatore lo dà obsoleto.
- OV9782 = stessa famiglia a colori (global shutter, 1280×800, MIPI+DVP). SC035HGS = global shutter VGA, MIPI+DVP.
  SC132GS = solo MIPI. OG01A1B = solo MIPI.
- ESP32-P4NRW32 è EOL → ESP32-P4NRW32X (LCSC/JLC C54540373), ~4-5 $. Espressif raccomanda almeno 4 strati.
- HW3 di oggi (2 × Waveshare P4 DEV-KIT + 2 × Inno-Maker OV9281 + MPU6050 + MH-CD42 + MT3608 + ES8311/altoparlante):
  la sincronia A↔B passa da fili GPIO/UART fra due schede; su una scheda sola basta FSIN comune + stesso XCLK.

## Dove si può risparmiare (da riempire con le prove)
## Dove bisogna spendere (da riempire con le prove)
## Errori fatti e regola che ne è nata
