#!/usr/bin/env python3
"""
approach_tracker.py — AVVICINA/ALLONTANA a bordo (per l'avoid-collision di Asmile).

Traccia ogni oggetto nel tempo (YOLO track = ID persistenti) e, per ognuno, segue la sua
DEPTH frame-per-frame → ricava:
  - velocità di chiusura  v = -d(depth)/dt  (>0 = si AVVICINA, <0 = si allontana) [m/s]
  - **TTC** = tempo-a-collisione = depth / v   (se si avvicina) [s]  ← il segnale per frenare
Il Δdepth è RELATIVO (moto bici + moto oggetto) = esattamente ciò che conta per la collisione.

Gira nel venv. Uso:
  ~/.asmile_depth_venv/bin/python approach_tracker.py --video <...> --preset camarray2560 \
      --fps 15 --maxframes 80 --out /tmp/track
"""
import argparse
import os
import sys
from collections import defaultdict, deque

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_depth import PRESETS, compute_depth, object_depth, colorize  # noqa


def closing_speed(hist):
    """hist: deque di (t, depth). Fit lineare → v_chiusura [m/s] (>0 avvicina) + TTC."""
    if len(hist) < 4:
        return None, None
    t = np.array([x[0] for x in hist])
    d = np.array([x[1] for x in hist])
    slope = float(np.polyfit(t, d, 1)[0])      # m/s (positivo = si allontana)
    v_close = -slope                            # >0 = si avvicina
    ttc = (d[-1] / v_close) if v_close > 0.15 else None
    return v_close, ttc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", default="camarray2560", choices=list(PRESETS))
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--maxframes", type=int, default=80)
    ap.add_argument("--out", default="/tmp/track")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = PRESETS[a.preset]
    model = YOLO("yolo11n-seg.pt")

    cap = cv2.VideoCapture(a.video)
    hist = defaultdict(lambda: deque(maxlen=10))
    fidx = done = 0
    alerts = 0
    while done < a.maxframes:
        ok, frame = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mid = g.shape[1] // 2
        L, R = g[:, :mid], g[:, mid:]
        depth, _ = compute_depth(L, R, cfg["focal_px"], cfg["baseline_mm"],
                                 cfg["sgbm"], cfg["sgbm_swap"])
        Lbgr = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
        res = model.track(Lbgr, persist=True, conf=0.4, verbose=False)[0]
        t = fidx / a.fps
        lines = []
        vis = Lbgr.copy()
        if res.boxes is not None and res.boxes.id is not None and res.masks is not None:
            ids = res.boxes.id.cpu().numpy().astype(int)
            masks = res.masks.data.cpu().numpy()
            for j, oid in enumerate(ids):
                m = cv2.resize(masks[j], (depth.shape[1], depth.shape[0])) > 0.5
                d = object_depth(depth, m)
                if d is None:
                    continue
                hist[oid].append((t, d))
                v, ttc = closing_speed(hist[oid])
                cls = model.names[int(res.boxes.cls[j])]
                x1, y1, x2, y2 = res.boxes.xyxy[j].cpu().numpy().astype(int)
                if v is None:
                    tag, col = f"{cls}#{oid} {d:.1f}m", (200, 200, 200)
                elif v > 0.15:
                    tag = f"{cls}#{oid} {d:.1f}m AVVICINA {v:.1f}m/s" + (f" TTC={ttc:.1f}s" if ttc else "")
                    col = (0, 0, 255) if (ttc and ttc < 3) else (0, 165, 255)
                    if ttc and ttc < 3:
                        alerts += 1
                elif v < -0.15:
                    tag, col = f"{cls}#{oid} {d:.1f}m allontana {-v:.1f}m/s", (0, 255, 0)
                else:
                    tag, col = f"{cls}#{oid} {d:.1f}m fermo", (255, 255, 0)
                cv2.rectangle(vis, (x1, y1), (x2, y2), col, 2)
                cv2.putText(vis, tag, (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
                if v is not None and abs(v) > 0.15:
                    lines.append(tag)
        if lines:
            print(f"t={t:.2f}s: " + " | ".join(lines))
        if done < 6:
            cv2.imwrite(f"{a.out}/track_{fidx:05d}.png", vis)
        fidx += 1
        done += 1
    cap.release()
    print(f"\n[ok] tracciati su {done} frame · {alerts} alert TTC<3s (frenata) · annotati in {a.out}")


if __name__ == "__main__":
    main()
