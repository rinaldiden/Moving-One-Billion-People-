#!/usr/bin/env python3
"""
dense_metric_depth.py — REFERENCE depth denso+metrico sul Mac (per training/validazione).

Fonde il meglio di due mondi:
  - SGBM stereo (calibrato, METRICO accurato — validato 1% sul muro — ma SPARSO)
  - monoculare learned (Depth-Anything-V2, DENSO ma scala assoluta sbagliata, tarata KITTI)
→ allinea la scala del monoculare ai punti accurati dello SGBM (ratio mediano robusto)
→ depth DENSO + METRICO + accurato. Calibration-light: basta focale+baseline (200mm) dello stereo.

Gira nel venv torch: ~/.asmile_depth_venv/bin/python  (MPS su Apple silicon).
Uso:
  ~/.asmile_depth_venv/bin/python dense_metric_depth.py \
      --video <session/video.h264> --preset camarray2560 --out /tmp/dense --nframes 8
"""
import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch
from transformers import pipeline

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_depth import PRESETS, compute_depth, colorize, object_depth  # noqa

MONO_MODEL = "depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf"


def align_scale(sgbm_depth, mono_depth):
    """Scala robusta s t.c. s*mono ~ sgbm sui pixel validi in entrambi (ratio mediano)."""
    m = (sgbm_depth > 0.3) & (mono_depth > 0.3)
    if m.sum() < 200:
        return None, 0
    ratio = sgbm_depth[m] / mono_depth[m]
    return float(np.median(ratio)), int(m.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", default="camarray2560", choices=list(PRESETS))
    ap.add_argument("--out", default="/tmp/dense")
    ap.add_argument("--nframes", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    cfg = PRESETS[a.preset]
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[init] mono={MONO_MODEL} dev={dev} · stereo focal={cfg['focal_px']} baseline={cfg['baseline_mm']}mm")
    mono = pipeline("depth-estimation", model=MONO_MODEL, device=dev)

    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    step = max(1, n // a.nframes)
    scales = []
    i = done = 0
    while done < a.nframes:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mid = g.shape[1] // 2
            L, R = g[:, :mid], g[:, mid:]
            # SGBM metrico sparso (ancora)
            sgbm_d, _ = compute_depth(L, R, cfg["focal_px"], cfg["baseline_mm"],
                                      cfg["sgbm"], cfg["sgbm_swap"])
            # monoculare denso
            rgb = Image.fromarray(cv2.cvtColor(L, cv2.COLOR_GRAY2RGB))
            out = mono(rgb)
            md = np.asarray(out.get("predicted_depth", out.get("depth")), dtype=np.float32)
            if md.ndim == 3:
                md = md[0]
            md = cv2.resize(md, (sgbm_d.shape[1], sgbm_d.shape[0]))
            s, npts = align_scale(sgbm_d, md)
            if s is None:
                i += 1
                continue
            dense = md * s                       # denso + metrico (scala ancorata)
            scales.append(s)
            # qualità: errore mediano dense-vs-sgbm sui punti ancora
            m = (sgbm_d > 0.3) & (dense > 0.3)
            err = float(np.median(np.abs(dense[m] - sgbm_d[m]) / sgbm_d[m])) * 100
            h, w = dense.shape
            cen = float(np.median(dense[h//2-40:h//2+40, w//2-60:w//2+60]))
            print(f"  frame {i}: scala={s:.3f} ancore={npts} centro_dense={cen:.2f}m err_vs_sgbm={err:.1f}%")
            if done < 4:
                cv2.imwrite(f"{a.out}/dense_{i:05d}.png", colorize(dense))
                cv2.imwrite(f"{a.out}/sgbm_{i:05d}.png", colorize(sgbm_d))
            done += 1
        i += 1
    cap.release()
    if scales:
        print(f"[ok] scala monoculare→metrico mediana = {np.median(scales):.3f} "
              f"(stabile: {np.std(scales):.3f}) · dense+metrico pronto in {a.out}")


if __name__ == "__main__":
    main()
