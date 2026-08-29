#!/usr/bin/env python3
"""
check_traj.py — La traiettoria da sterzo istantaneo coincide con dove va DAVVERO Asmile?
========================================================================================
Confronta, sull'immagine strada, due cose:
  VERDE  = arco da STERZO ISTANTANEO (dove andrebbe se tenesse questo sterzo fermo)
  CIANO  = traiettoria REALMENTE percorsa nei metri successivi (integrando gyro+speed)
Se coincidono => lo sterzo istantaneo predice bene il percorso (curva stabile).
Se divergono => la bici sta CAMBIANDO sterzo (ingresso/uscita curva): l'arco istantaneo
e' solo una previsione a corto raggio.

Uso:
  python3 check_traj.py --report reports/shadow_X.csv --session /path/session_X \
    --calib ../../config/stereo_calibration.yaml --output reports/check_X.mp4
"""
from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import project_path as pp

GREEN = (60, 200, 60)
CYAN = (230, 230, 40)
WHITE = (245, 245, 245)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def future_path(rows, i, S=7.0):
    """Traiettoria realmente percorsa da riga i in poi (frame bici: avanti d, lat l)."""
    theta, x, y, dist = 0.0, 0.0, 0.0, 0.0
    pts = [(0.0, 0.0)]
    prev_t = datetime.fromisoformat(rows[i]["timestamp"]).timestamp()
    j = i
    while j + 1 < len(rows) and dist < S:
        j += 1
        tj = datetime.fromisoformat(rows[j]["timestamp"]).timestamp()
        dt = min(0.5, max(0.0, tj - prev_t)); prev_t = tj
        v = float(rows[j]["speed_ms"]); w = math.radians(float(rows[j]["gyro_z"]))
        x += v * math.cos(theta) * dt
        y += v * math.sin(theta) * dt          # +l = sinistra (gyro+)
        theta += w * dt
        dist += v * dt
        pts.append((x, y))
    return pts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=10)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.report)))
    fx, fy, cx, cy, W, H = pp.load_intrinsics(args.calib)
    slope = pp.fit_slope(rows)
    import statistics as st
    hs_med = st.median(float(r["human_steering"]) for r in rows)

    vid = Path(args.session) / "video.mp4"
    if not vid.is_file():
        vid = Path(args.session) / "video.h264"
    cap = cv2.VideoCapture(str(vid))
    OUT_W, OUT_H = 960, 620
    sx, sy = OUT_W / W, OUT_H / H
    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"),
                             args.fps, (OUT_W, OUT_H))
    n = 0
    for i, r in enumerate(rows):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(float(r["frame_idx"])))
        ok, frame = cap.read()
        if not ok:
            continue
        road = cv2.resize(cv2.flip(frame[:, : frame.shape[1] // 2], -1), (OUT_W, OUT_H))

        # arco da sterzo istantaneo
        kh = slope * (float(r["human_steering"]) - hs_med)
        arc = pp.project(pp.arc_points(kh), fx, fy, cx, cy, W, H, sx, sy)
        # traiettoria realmente percorsa
        real = pp.project(future_path(rows, i), fx, fy, cx, cy, W, H, sx, sy)
        pp.draw_poly(road, arc, GREEN)
        for k in range(1, len(real)):
            cv2.line(road, real[k - 1], real[k], CYAN, 4, cv2.LINE_AA)

        cv2.rectangle(road, (0, 0), (OUT_W, 52), (0, 0, 0), -1)
        cv2.putText(road, "VERDE = arco da STERZO ORA (se lo tenesse fermo)",
                    (10, 21), FONT, 0.55, GREEN, 2)
        cv2.putText(road, "CIANO = dove Asmile va DAVVERO nei prossimi metri",
                    (10, 44), FONT, 0.55, CYAN, 2)
        writer.write(road)
        n += 1
        if n % 100 == 0:
            print(f"  {n}/{len(rows)}")

    writer.release(); cap.release()
    print(f"\nVideo: {args.output}  ({n} frame)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
