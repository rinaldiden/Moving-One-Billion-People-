#!/usr/bin/env python3
"""
object_depth_demo.py — DEPTH PER-OGGETTO (il cuore: profondità degli oggetti che vediamo).

Segmentazione (YOLO11-seg, = segment_gate) × depth-map (SGBM metrico) →
per ogni oggetto: distanza = MEDIANA robusta della depth valida dentro la sua maschera.
È ciò che poi gira sul Pi (SGBM leggero) per capire "quanto è lontano quell'ostacolo".

Gira nel venv: ~/.asmile_depth_venv/bin/python
Uso:
  ~/.asmile_depth_venv/bin/python object_depth_demo.py \
      --video <session/video.h264> --preset camarray2560 --out /tmp/objdepth --nframes 6
"""
import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_depth import PRESETS, compute_depth, colorize, object_depth  # noqa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", default="camarray2560", choices=list(PRESETS))
    ap.add_argument("--out", default="/tmp/objdepth")
    ap.add_argument("--nframes", type=int, default=6)
    ap.add_argument("--conf", type=float, default=0.35)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = PRESETS[a.preset]

    model = YOLO("yolo11n-seg.pt")   # scarica ~6MB al primo run
    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    step = max(1, n // a.nframes)
    i = done = 0
    all_rows = []
    while done < a.nframes:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mid = g.shape[1] // 2
            L, R = g[:, :mid], g[:, mid:]
            depth, _ = compute_depth(L, R, cfg["focal_px"], cfg["baseline_mm"],
                                     cfg["sgbm"], cfg["sgbm_swap"])
            Lbgr = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
            res = model.predict(Lbgr, conf=a.conf, verbose=False)[0]
            vis = Lbgr.copy()
            objs = []
            if res.masks is not None:
                masks = res.masks.data.cpu().numpy()       # (N,h,w) in scala YOLO
                boxes = res.boxes
                for k in range(len(masks)):
                    m = cv2.resize(masks[k], (depth.shape[1], depth.shape[0])) > 0.5
                    dist = object_depth(depth, m)
                    cls = model.names[int(boxes.cls[k])]
                    conf = float(boxes.conf[k])
                    x1, y1, x2, y2 = boxes.xyxy[k].cpu().numpy().astype(int)
                    label = f"{cls} {dist:.1f}m" if dist else f"{cls} ?"
                    col = (0, 255, 0) if dist else (0, 0, 255)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), col, 2)
                    cv2.putText(vis, label, (x1, max(15, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
                    objs.append({"cls": cls, "conf": round(conf, 2),
                                 "dist_m": round(dist, 2) if dist else None,
                                 "box": [int(x1), int(y1), int(x2), int(y2)]})
            print(f"frame {i}: {len(objs)} oggetti → " +
                  ", ".join(f"{o['cls']}@{o['dist_m']}m" for o in objs if o['dist_m']) or "(nessuna distanza)")
            all_rows.append({"frame": i, "objects": objs})
            if done < 4:
                cv2.imwrite(f"{a.out}/obj_{i:05d}.png", vis)
                cv2.imwrite(f"{a.out}/depth_{i:05d}.png", colorize(depth))
            done += 1
        i += 1
    cap.release()
    json.dump(all_rows, open(f"{a.out}/objects.json", "w"), indent=2)
    tot = sum(len([o for o in r["objects"] if o["dist_m"]]) for r in all_rows)
    print(f"[ok] {tot} oggetti con distanza su {done} frame · annotati in {a.out}")


if __name__ == "__main__":
    main()
