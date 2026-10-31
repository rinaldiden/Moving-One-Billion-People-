# Pipeline Depth — logger asmile (Camarray stereo, baseline 200mm)

Depth metrica dalle 2 OV9281 della Camarray (side-by-side 2560x800, baseline
**200mm** fissa). Pensata per il kit logger: si **auto-calibra senza scacchiera**
dai video girati, valida l'errore col **metro**, e dà depth sia offline (Mac,
teacher forte) sia on-edge (Pi 5, SGBM leggero). Da testare appena il kit è acceso.

## La diagnosi (perché oggi siamo al 7.8%, non all'1-2%)

Le due ricerche (Tesla + SOTA stereo 2026) convergono: **il problema è la
CALIBRAZIONE, non il matcher.** Due cause spiegano quasi tutto il delta:
1. **Focale incerta ~13%** (`config/calibration/depth_config.json`: 1048 vs 1183px).
   Un errore di focale si trasferisce **1:1** sulla profondità.
2. **`dy = 3.75px`** di disallineamento verticale nella rettifica → le righe
   epipolari non sono orizzontali → l'SGBM cerca la disparità sulla riga sbagliata.

Terzo fattore minore: SGBM senza WLS/subpixel/left-right consistency.

## Il limite FISICO del rig (non software)

`Z = f·B/d`, errore relativo `dZ/Z = (Z/(f·B))·δd`. Con B=200mm, lente ~2.7mm (f≈902px):

| Z | 1-2% con δd=1px | con δd=0.5px | con δd=0.25px |
|---|---|---|---|
| ≤3.6m | ✅ | ✅ | ✅ |
| ≤7.2m | ❌ (2.8%) | ✅ | ✅ |
| ≤14m | ❌ | ❌ | ✅ |

→ **Per 1-2% fino a ~7m** basta calibrazione buona + subpixel 0.5px (fattibile
con SGBM+WLS). **Per 1-2% fino a 10-20m** serve subpixel ~0.25px (reti deep) e/o
**lente 4mm** (f≈1333px, ma FOV più stretto → meno visione laterale). Con la
lente attuale, oltre i ~7m è il rig a limitare, non il codice.

## Cosa ruba a Tesla (e cosa salta)

- **Baseline nota = scala metrica GRATIS** → saltiamo tutto il circo di Tesla per
  recuperare la scala (auto-labeling di flotta, IMU-EKF, radar, occupancy per
  stabilizzare l'orizzonte). `Z=f·B/d` è già metrico.
- **Flow-guided rectification** (brevetto Tesla US 12470683 / ICRA-2024): si stima
  la rotazione relativa che azzera la disparità verticale → `autorectify.py`.
- **Teacher-offline → student-edge**: Mac fa il denso forte, Pi gira SGBM distillato.
- **Monitor di drift continuo** (bici che vibra) → `drift_monitor.py`.

## Flusso di lavoro (ordine d'attacco al 7.8%)

```
# 0) misura col metro (vedi sotto) e registra i target a distanze note

# 1) AUTO-CALIBRAZIONE senza scacchiera: azzera il dy
python3 autorectify.py --video sessione_texture.h264 --out calib_logger.json \
        --focal-px 902 --frames 60
#    (se hai un prior: --prior ../../config/calibration/stereo_auto_sift.json)

# 2) MURO-TEST col metro: fissa la focale reale + misura l'errore %
python3 validate.py --calib calib_logger.json --targets targets.json
#    se la focale misurata diverge >3%: rifai (1) con --focal-px <valore misurato>

# 3) DEPTH
python3 depth.py --video clip.h264 --calib calib_logger.json --out /tmp/depth      # SGBM (edge/Pi)
python3 depth.py --video clip.h264 --calib calib_logger.json --model crestereo.onnx # teacher (Mac)

# 4) QUALITY-GATE drift (ripetibile, anche in cron sul Pi)
python3 drift_monitor.py --video clip.h264 --calib calib_logger.json --thresh 0.5
```

## 📏 Cosa misurare col metro (dammi questi numeri)

1. **Baseline reale**: distanza **centro-a-centro delle due lenti**, al mm
   (nominale 200 → `--baseline-mm`). Scala la depth 1:1.
2. **Altezza camera da terra** (per piano terra / spazio guidabile).
3. **Target a distanze note** (il più importante): oggetto piano/ben visibile
   sull'asse della camera a **1.0 / 2.0 / 3.0 / 5.0 / 7.0 / 10.0 m**, misurati col
   metro, ~10s di stereo fermo a ciascuna. Compila `targets.json`:
   ```json
   [{"video":"1m.h264","distance_m":1.0},{"video":"3m.h264","distance_m":3.0}]
   ```
   Da qui ricavo focale reale + errore % a ogni distanza.
4. *(opz.)* sigla della lente (focale mm / FOV) per sanity-check.

Per l'auto-calibrazione serve anche un clip con **texture varia e profondità
diverse** (muri, strada, oggetti vicini+lontani) + un po' di movimento.

## ⚙️ Dettagli hardware / gotcha

- **Montaggio capovolto**: le OV9281 sono montate sottosopra → il frame va ruotato
  180° (`split_sbs(flip180=True)`, default). Il 180° **scambia anche L↔R**: se la
  depth esce negativa/assurda, prova `--order RL`.
- **Sync delle 2 camere**: ora è software → su oggetti in movimento la disparità
  sfasa. Valutare trigger hardware **FSIN** del Camarray per frame simultanei
  (fonte d'errore indipendente dalla calibrazione).
- **Rettifica non-calibrata (Hartley) NO**: perderebbe la scala metrica. Teniamo
  intrinseci+baseline come ancora, auto-calibriamo solo la rotazione relativa.

## 🧰 Ambiente (Mac M1, offline)

`pip install -r requirements.txt` in un venv (il Mac di default ha Python 3.14;
usa un venv 3.12). `opencv-contrib-python` serve per il filtro WLS (`ximgproc`).
Teacher denso consigliato su M1: **CREStereo via onnxruntime** (nativo, no CUDA).
Modelli ONNX: [ONNX-CREStereo](https://github.com/ibaiGorordo/ONNX-CREStereo-Depth-Estimation).
Se hai una GPU CUDA in prestito: FoundationStereo ViT-L dà il top.

## 🚀 Deploy
- **Pi 5 (edge)**: `stereo_common.py` + `depth.py` (path SGBM+WLS) + `drift_monitor.py`.
  Depth per-oggetto incrociando le maschere della segmentazione (`object_depth()`).
- **Mac (reference/training)**: tutto, con `--model` CREStereo per il denso metrico
  (pseudo-GT per il training, à la auto-labeling di Tesla).
