#!/usr/bin/env python3
"""
replay_video.py — Rende VISIBILE il replay: video annotato modello-vs-umano
===========================================================================
Prende un report shadow (CSV gia' calcolato da shadow_analyzer.py) + il video
della sessione e produce un mp4 in cui vedi, separati e chiari:
  - sulla strada: due FRECCE di sterzata (verde = umano, arancio = modello v4);
  - sotto: due RIQUADRI separati, uno "TU" e uno "MODELLO", con sterzo e freno a parole.
E' la "video inspection" della ricetta Microduck. Non ri-esegue il modello: legge le
predizioni gia' nel CSV.

Uso:
  python3 replay_video.py --report reports/shadow_X.csv \
    --session /path/session_X --output reports/replay_X.mp4 [--fps 10] [--rotate 180]
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics as st
from pathlib import Path

import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_SIMPLEX
GREEN = (60, 200, 60)      # umano
ORANGE = (0, 160, 255)     # modello
GREY = (150, 150, 150)
WHITE = (245, 245, 245)
RED = (0, 0, 255)


def steer_word(v):
    if abs(v) < 0.04:
        return "DRITTO"
    d = "DESTRA" if v > 0 else "SINISTRA"
    return f"gira MOLTO a {d}" if abs(v) > 0.15 else f"gira a {d}"


def brake_word(b):
    if b < 0.05:
        return "non frena"
    if b < 0.25:
        return "frena appena"
    if b < 0.6:
        return "frena"
    return "FRENA FORTE!"


def draw_arrow(img, origin, rel, color, length):
    """Freccia di sterzata dal punto origin. rel = sterzo relativo al dritto."""
    theta = math.radians(max(-70, min(70, rel * 220)))     # dritto = su
    end = (int(origin[0] + length * math.sin(theta)),
           int(origin[1] - length * math.cos(theta)))
    cv2.arrowedLine(img, origin, end, color, 8, tipLength=0.3)


def draw_driver_box(panel, x0, x1, title, color, steer_rel, brake):
    cv2.rectangle(panel, (x0 + 6, 6), (x1 - 6, 205), color, 2)
    cv2.putText(panel, title, (x0 + 20, 40), FONT, 0.9, color, 2)
    cv2.putText(panel, "STERZO:", (x0 + 20, 90), FONT, 0.6, GREY, 1)
    cv2.putText(panel, steer_word(steer_rel), (x0 + 120, 90), FONT, 0.75, WHITE, 2)
    cv2.putText(panel, "FRENO:", (x0 + 20, 140), FONT, 0.6, GREY, 1)
    cv2.putText(panel, brake_word(brake), (x0 + 120, 140), FONT, 0.75, WHITE, 2)
    # barra freno 0..1
    cv2.rectangle(panel, (x0 + 20, 160), (x0 + 320, 182), GREY, 1)
    cv2.rectangle(panel, (x0 + 20, 160),
                  (x0 + 20 + int(max(0, min(1, brake)) * 300), 182), color, -1)


def rotate(img, deg):
    if deg == 180:
        return cv2.flip(img, -1)
    if deg == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if deg == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def render(report, session, output, fps, rot) -> int:
    rows = list(csv.DictReader(open(report)))
    if not rows:
        print("[replay_video] report vuoto"); return 1
    h_center = st.median(float(r["human_steering"]) for r in rows)
    m_center = st.median(float(r["model_steering"]) for r in rows)

    vid = Path(session) / "video.mp4"
    if not vid.is_file():
        vid = Path(session) / "video.h264"
    cap = cv2.VideoCapture(str(vid))
    if not cap.isOpened():
        print(f"[replay_video] non apro il video: {vid}"); return 1

    OUT_W, ROAD_H, PANEL_H = 960, 520, 250
    writer = cv2.VideoWriter(output, cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (OUT_W, ROAD_H + PANEL_H))
    n = 0
    for r in rows:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(float(r["frame_idx"])))
        ok, frame = cap.read()
        if not ok:
            continue
        left = frame[:, : frame.shape[1] // 2]              # stereo -> sinistra
        left = rotate(left, rot)
        road = cv2.resize(left, (OUT_W, ROAD_H))

        hs = float(r["human_steering"]) - h_center          # sterzo relativo al dritto
        ms = float(r["model_steering"]) - m_center
        hb, mb = float(r["human_brake"]), float(r["model_brake"])

        # frecce di sterzata sulla strada, dal centro-basso
        origin = (OUT_W // 2, ROAD_H - 20)
        draw_arrow(road, origin, hs, GREEN, 170)
        draw_arrow(road, origin, ms, ORANGE, 130)

        # pannello: due riquadri separati + verdetto in fondo
        panel = np.full((PANEL_H, OUT_W, 3), 22, np.uint8)
        draw_driver_box(panel, 0, OUT_W // 2, "TU (l'umano)", GREEN, hs, hb)
        draw_driver_box(panel, OUT_W // 2, OUT_W, "MODELLO v4", ORANGE, ms, mb)
        cv2.line(panel, (OUT_W // 2, 8), (OUT_W // 2, 200), (70, 70, 70), 1)
        speed = float(r["speed_ms"])
        cv2.putText(panel, f"{speed*3.6:.0f} km/h", (OUT_W//2 - 55, 28), FONT, 0.6, WHITE, 2)
        # verdetto esplicito: sterzo e freno, uguale o diverso?
        steer_same = abs(hs - ms) < 0.08
        brake_same = abs(hb - mb) < 0.20
        yv = PANEL_H - 16
        cv2.putText(panel, "STERZO:", (30, yv), FONT, 0.6, GREY, 1)
        cv2.putText(panel, "UGUALE" if steer_same else "DIVERSO", (150, yv), FONT, 0.7,
                    GREEN if steer_same else RED, 2)
        cv2.putText(panel, "FRENO:", (OUT_W // 2 + 20, yv), FONT, 0.6, GREY, 1)
        cv2.putText(panel, "UGUALE" if brake_same else "DIVERSO", (OUT_W // 2 + 130, yv), FONT, 0.7,
                    GREEN if brake_same else RED, 2)

        canvas = np.vstack([road, panel])
        dis = r.get("is_disagreement", "0") in ("1", "True", "true")
        if dis:
            cv2.rectangle(canvas, (0, 0), (OUT_W - 1, ROAD_H + PANEL_H - 1), RED, 8)
        cv2.rectangle(canvas, (0, 0), (OUT_W, 32), (0, 0, 0), -1)
        cv2.putText(canvas, "FRECCIA VERDE = come guidi TU   |   FRECCIA ARANCIO = cosa farebbe il MODELLO",
                    (10, 22), FONT, 0.52, WHITE, 1)
        writer.write(canvas)
        n += 1
        if n % 100 == 0:
            print(f"  {n}/{len(rows)} frame resi")

    writer.release(); cap.release()
    print(f"\nVideo scritto: {output}  ({n} frame, {fps} fps, ~{n/fps:.0f}s, rot={rot})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Video annotato modello-vs-umano dal report shadow")
    ap.add_argument("--report", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270],
                    help="gradi di rotazione del frame (camere capovolte = 180)")
    args = ap.parse_args()
    return render(args.report, args.session, args.output, args.fps, args.rotate)


if __name__ == "__main__":
    raise SystemExit(main())
