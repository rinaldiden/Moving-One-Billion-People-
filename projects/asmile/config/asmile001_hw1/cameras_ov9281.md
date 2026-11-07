# asmile #001: camere stereo (SOLO questo set)

Due moduli **separati** Inno-Maker **CAM-MIPIOV9281V2** (Amazon ASIN B09WTP5GZH, UPC 781520762493),
uno per porta CSI del Pi 5. NON Arducam Camarray. Valgono solo per #001: asmile2 e asmile-logger
hanno camere e calibrazioni loro (`logger/depth/calib_<nome>.json`, mai fallback).

## Specifiche del venditore (pagina Amazon, letta da Daniele 2026-11-07)
| voce | valore |
|---|---|
| sensore | OmniVision OV9281, monocromatico, global shutter, NIR |
| risoluzione | 1280 x 800, pixel 3 x 3 µm, area 3896 x 2453 µm, ottica 1/4" |
| S/N, gamma dinamica | 38 dB, 68 dB |
| uscita | MIPI 2 lane, RAW 8/10 bit |
| lente | 2,8 mm, F2.2, fuoco manuale (regolabile), distorsione TV < -17% |
| campo visivo dichiarato | diagonale 148°, orizzontale 118° |
| scheda | 32 x 32 mm, 40 g |
| setup | `dtparam=i2c_vc=on`, `dtoverlay=ov9281` (+ `cam0`/`cam1` per porta), `cma=128M` |

Modalità:
- **driver ufficiale Raspberry Pi** (quello usato): 1280x800 Y10 120 fps, Y8 144 fps.
  Secondo il venditore **non supporta il trigger esterno**.
- **driver Inno-Maker** (legato alla versione del kernel): 12 modalità, comprese
  1280x800/1280x720/640x400 in **EXT_TRIG** (pin J3) e 640x400 fino a 253 fps.

Conseguenza: per l'FSIN hardware serve probabilmente il driver Inno-Maker, da verificare su
questo kernel prima di comprare/cablare. Oggi non serve: il sync software
`rpicam-vid --sync server/client` è misurato a ≤ 0,045 ms fra le coppie (vedi
`docs/ov9281_hardware_sync.md`).

## Cosa NON torna con la calibrazione col metro (da chiarire, 2026-11-07)
- Focale nominale: 2,8 mm / 3 µm = **933 px**.
- Calibrazione col metro (`calib_asmile-001.json`): `f·B = 261,3 px·m` → con B = 200 mm
  la focale effettiva è **1306 px** (≈ 3,9 mm). Con 933 px la baseline sarebbe **280 mm**.
- Il campo visivo dichiarato (118° orizzontali) con 3,84 mm di sensore non è compatibile
  né con 933 px (69° senza distorsione) né con 1306 px (52°). La scheda del venditore è incoerente.

Due misure col metro decidono:
1. **baseline vera**: distanza fra i centri delle due lenti;
2. **campo visivo vero**: bici a 1,00 m da un muro, segnare i bordi sinistro e destro
   dell'immagine; larghezza visibile ≈ 0,98 m se f = 1306 px, ≈ 1,37 m se f = 933 px.

Per la depth conta solo il prodotto f·B, già misurato col metro: le distanze restano giuste
comunque. Il valore separato di f serve alla rettifica e alla stima dell'altezza dei bordi.
