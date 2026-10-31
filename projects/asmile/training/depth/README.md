# Depth Asmile — pipeline stereo metrica (Mac reference + edge Pi)

Depth dalle 2 cam **OV9281** (baseline **200mm** fissa). Due strade, provate sui video stereo di maggio (2560x800 side-by-side).

## Dato fisso
- **baseline = 200mm** (fisico, da `config/calibration/depth_config.json`, `auto_calibration.py`). Niente scacchiera: basta focale (nota per OV9281 / dalla calibrazione) + baseline.

## 1) `stereo_depth.py` — SGBM metrico (edge/Pi + Mac) ✅
Side-by-side → SGBM + **check LEFT-RIGHT consistency** (no ximgproc) → depth in metri.
- **Fixa l'artefatto "1.24m stuck"** di `depth_test1.py` (verificato: **0/15 frame**).
- Metrico accurato dove c'è texture (SGBM validato ~1% sul muro), **ma SPARSO** (~11% su scene outdoor a bassa texture — limite intrinseco di SGBM).
- Preset `camarray2560` (focal 1183, baseline 200) + `--calib <yaml>` per le OV9281 di #001.
- **Leggero → è l'approccio EDGE da deployare sul Pi** per la depth per-oggetto (mediana nella maschera della segmentazione).
```
python3 stereo_depth.py --video <session/video.h264> --preset camarray2560 --out /tmp/depth
```

## 2) `dense_metric_depth.py` — reference DENSO+metrico (Mac, venv torch) ✅
Fonde **monoculare learned (Depth-Anything-V2, denso)** + **scala ancorata allo SGBM (metrico)**.
- Scoperta: il "metrico" monoculare ha scala assoluta **sbagliata** (tarata KITTI: centro 20m vs 7m reali). Ancorandolo allo SGBM la scala si corregge con un **fattore per-cam STABILE** (0.210 ± 0.007 su tutti i frame → un solo numero per camera).
- Col modello SMALL resta ~25% di disaccordo locale vs SGBM → per il denso PRECISO serve **DA-V2-Large** o **FoundationStereo** (stereo denso, elimina l'ambiguità monoculare).
```
~/.asmile_depth_venv/bin/python dense_metric_depth.py --video <...> --preset camarray2560 --out /tmp/dense
```

## Ambiente ML (Mac, fuori dal repo)
`~/.asmile_depth_venv` (Python 3.12 + **torch 2.15 MPS** + transformers + opencv). Creato con `uv`. Il Mac di default ha Python 3.14 (torch non disponibile) → usare il venv.

## Architettura consigliata ("strada migliore")
- **Edge/Pi (#001)**: `stereo_depth.py` (SGBM metrico, leggero) → depth per-oggetto incrociando le maschere della segmentazione. Accurato dove serve (oggetti con texture).
- **Mac (reference/training)**: `dense_metric_depth.py` con un modello forte (DA-V2-Large o FoundationStereo) → depth denso+metrico come ground-truth per training/validazione.
- **Calibration-free**: la scacchiera NON serve; baseline 200mm (righello) + focale + self-calib (`auto_calibration.py`) per la rettifica.

## TODO (prossimi passi del loop)
1. Testare **DA-V2-Large** / **FoundationStereo** per il denso preciso (<10% err).
2. **Depth per-oggetto**: incrociare maschere segment_gate × depth-map → distanza mediana.
3. **Deploy SGBM su #001** (quando si accende) con la SUA calibrazione (focale OV9281).
4. **Sync hardware-trigger** delle 2 OV9281 (ora software_timestamp → sfasa la disparità su oggetti in movimento): valutare il trigger esterno (FSIN) per frame simultanei.
