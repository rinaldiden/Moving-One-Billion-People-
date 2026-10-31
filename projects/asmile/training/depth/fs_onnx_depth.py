#!/usr/bin/env python3
"""
fs_onnx_depth.py — FoundationStereo (NVIDIA, CVPR2025) via ONNX → depth DENSO+METRICO.

Stereo vero (niente ambiguità di scala del monoculare), zero-shot (nessuna calibrazione
per-scena), gira su Mac via onnxruntime (CPU/CoreML, niente CUDA). Output disparità densa →
depth metrica con focale+baseline (200mm).

Modello: nvidia/c-foundationstereo-s onnx/deployable_foundationstereo_small_576x960_v2.0.onnx
Input: left/right [1,3,576,960] float. Output: disparity [1,1,576,960].

Gira nel venv: ~/.asmile_depth_venv/bin/python
Uso:
  ~/.asmile_depth_venv/bin/python fs_onnx_depth.py \
      --video <session/video.h264> --preset camarray2560 --out /tmp/fs --nframes 6
"""
import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_depth import PRESETS, compute_depth, colorize  # noqa

ONNX_REPO = "nvidia/c-foundationstereo-s"
# 320x736 = ~11s/frame su Mac CoreML (il 576x960 e' ~77s). Per batch veloce serve una GPU CUDA.
ONNX_FILE = "onnx/deployable_foundationstereo_small_320x736_v2.0.onnx"
IN_W, IN_H = 736, 320


def prep(gray):
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    r = cv2.resize(rgb, (IN_W, IN_H)).astype(np.float32) / 255.0
    return r.transpose(2, 0, 1)[None]              # 1,3,576,960


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", default="camarray2560", choices=list(PRESETS))
    ap.add_argument("--out", default="/tmp/fs")
    ap.add_argument("--nframes", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = PRESETS[a.preset]

    path = hf_hub_download(ONNX_REPO, ONNX_FILE)
    provs = ort.get_available_providers()
    use = ["CoreMLExecutionProvider", "CPUExecutionProvider"] if "CoreMLExecutionProvider" in provs else ["CPUExecutionProvider"]
    sess = ort.InferenceSession(path, providers=use)
    print(f"[init] FoundationStereo-ONNX providers={sess.get_providers()} · focal={cfg['focal_px']} baseline={cfg['baseline_mm']}mm")

    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    step = max(1, n // a.nframes)
    i = done = 0
    while done < a.nframes:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mid = g.shape[1] // 2
            L, R = g[:, :mid], g[:, mid:]
            # FoundationStereo: disparità densa nello spazio 960x576
            if cfg["sgbm_swap"]:
                a_img, b_img = R, L
            else:
                a_img, b_img = L, R
            disp = sess.run(["disparity"], {"left_image": prep(a_img),
                                            "right_image": prep(b_img)})[0][0, 0]
            # depth metrica: focale scalata allo spazio 960 larghezza
            focal_960 = cfg["focal_px"] * (IN_W / L.shape[1])
            disp_c = np.clip(disp, 0.3, None)
            depth = focal_960 * cfg["baseline_mm"] / disp_c / 1000.0
            depth[(depth < 0.3) | (depth > 40)] = 0
            depth_full = cv2.resize(depth, (L.shape[1], L.shape[0]))
            # confronto con SGBM metrico
            sgbm_d, _ = compute_depth(L, R, cfg["focal_px"], cfg["baseline_mm"],
                                      cfg["sgbm"], cfg["sgbm_swap"])
            m = (sgbm_d > 0.3) & (depth_full > 0.3)
            err = float(np.median(np.abs(depth_full[m] - sgbm_d[m]) / sgbm_d[m])) * 100 if m.sum() > 200 else -1
            h, w = depth_full.shape
            creg = depth_full[h//2-40:h//2+40, w//2-60:w//2+60]
            cv = creg[creg > 0]
            cen = float(np.median(cv)) if cv.size else 0.0
            valid = 100.0 * (depth_full > 0).sum() / depth_full.size
            print(f"  frame {i}: FS centro={cen:.2f}m · valid={valid:.0f}% (denso!) · err_vs_sgbm={err:.1f}%", flush=True)
            if done < 4:
                cv2.imwrite(f"{a.out}/fs_{i:05d}.png", colorize(depth_full))
            done += 1
        i += 1
    cap.release()
    print(f"[ok] FoundationStereo denso+metrico in {a.out}")


if __name__ == "__main__":
    main()
