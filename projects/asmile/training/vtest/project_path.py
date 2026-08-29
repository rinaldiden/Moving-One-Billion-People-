#!/usr/bin/env python3
"""
project_path.py — Traiettoria di curva proiettata SULLA STRADA nel video
========================================================================
Disegna sul video, davanti alla bici, la linea curva che imboccherebbe l'UMANO
(verde) e quella che imboccherebbe il MODELLO (arancio), come gli overlay di guida
autonoma. Niente depth: usa solo lo sterzo → raggio → arco sul piano strada →
proiezione con la camera calibrata.

Catena:
  encoder/sterzo --(calibrazione gyro+speed)--> curvatura 1/R --> arco a terra
  arco a terra --(intrinseci camera + altezza 0.77 m)--> pixel --> polilinea sul frame

Uso:
  python3 project_path.py --report reports/shadow_X.csv --session /path/session_X \
    --calib ../../config/stereo_calibration.yaml --output reports/proj_X.mp4
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics as st
from pathlib import Path

import cv2
import numpy as np

GREEN = (60, 200, 60)
ORANGE = (0, 160, 255)
WHITE = (245, 245, 245)
GREY = (150, 150, 150)
RED = (0, 0, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX

CAM_H = 0.77           # m, altezza camera da terra (CLAUDE.md)
BIKE_W = 1.10          # m, larghezza reale di Asmile (driving_patterns.md)
HALF_W = BIKE_W / 2
CURVE_GYRO_DEG = 8.0
CURVE_VMIN = 0.8
ARC_LEN = 7.0          # m davanti alla bici
ARC_STEPS = 40


def load_intrinsics(calib_path: str):
    fs = cv2.FileStorage(calib_path, cv2.FILE_STORAGE_READ)
    K = fs.getNode("camera_matrix_left").mat()
    w = int(fs.getNode("image_width").real())
    h = int(fs.getNode("image_height").real())
    fs.release()
    return float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2]), w, h


def fit_slope(report_rows):
    """curvatura (1/m) per unita' di sterzo normalizzato, dai tratti in curva."""
    s, k = [], []
    for r in report_rows:
        v = float(r["speed_ms"]); gz = math.radians(float(r["gyro_z"]))
        if abs(gz) > math.radians(CURVE_GYRO_DEG) and v > CURVE_VMIN:
            s.append(float(r["human_steering"]))   # gia' normalizzato [-1,1]
            k.append(gz / v)
    if len(s) < 20:
        return None
    s = np.array(s); k = np.array(k)
    A = np.vstack([s, np.ones_like(s)]).T
    (slope, _), *_ = np.linalg.lstsq(A, k, rcond=None)
    return float(slope)


def arc_points(kappa, n=ARC_STEPS, S=ARC_LEN):
    """Punti (avanti d, laterale l) lungo l'arco a curvatura kappa (segno = verso)."""
    out = []
    for i in range(1, n + 1):
        s = S * i / n
        if abs(kappa) < 1e-4:
            d, l = s, 0.0
        else:
            psi = kappa * s
            d = math.sin(psi) / kappa
            l = (1 - math.cos(psi)) / kappa
        out.append((d, l))
    return out


def project(points, fx, fy, cx, cy, W, H, sx, sy, keep=False):
    """Da (avanti d, laterale l) a pixel sul frame RUOTATO 180 (display) e riscalato.
    Camera capovolta: lavoro direttamente in coordinate display. Orizzonte a (H-1-cy),
    terra piu' in basso (+fy*CAM_H/d); curva a sinistra (kappa>0) = a sinistra in immagine.
    keep=True: non scarta i punti fuori campo (serve per chiudere il poligono corridoio)."""
    px = []
    u0, v0 = (W - 1 - cx), (H - 1 - cy)
    for d, l in points:
        if d < 0.3:
            continue
        u = u0 - fx * l / d          # l>0 (curva sx) -> verso sinistra immagine
        v = v0 + fy * CAM_H / d      # terra sotto l'orizzonte
        if keep:
            px.append((int(np.clip(u * sx, -8000, 8000)),
                       int(np.clip(v * sy, -8000, 8000))))
        elif 0 <= v < H and -300 <= u < W + 300:
            px.append((int(u * sx), int(v * sy)))
    return px


def corridor_edges(kappa, n=ARC_STEPS, S=ARC_LEN):
    """Bordi sinistro/destro dell'ingombro reale (larghezza BIKE_W) lungo l'arco."""
    L, R = [], []
    for i in range(1, n + 1):
        s = S * i / n
        if abs(kappa) < 1e-4:
            x, y, psi = s, 0.0, 0.0
        else:
            psi = kappa * s
            x = math.sin(psi) / kappa
            y = (1 - math.cos(psi)) / kappa
        sn, cs = math.sin(psi), math.cos(psi)      # normale sinistra = (-sn, cs)
        L.append((x - HALF_W * sn, y + HALF_W * cs))
        R.append((x + HALF_W * sn, y - HALF_W * cs))
    return L, R


def draw_corridor(img, ptsL, ptsR, color, alpha=0.32):
    """Fascia semitrasparente (ingombro a terra) + bordi."""
    if len(ptsL) < 2 or len(ptsR) < 2:
        return
    poly = np.array(ptsL + ptsR[::-1], np.int32)
    ov = img.copy()
    cv2.fillPoly(ov, [poly], color)
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)
    cv2.polylines(img, [np.array(ptsL, np.int32)], False, color, 3, cv2.LINE_AA)
    cv2.polylines(img, [np.array(ptsR, np.int32)], False, color, 3, cv2.LINE_AA)


def draw_poly(img, pts, color):
    for i in range(1, len(pts)):
        cv2.line(img, pts[i - 1], pts[i], color, 5, cv2.LINE_AA)
    if pts:
        cv2.circle(img, pts[-1], 6, color, -1)


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


def draw_driver_box(panel, x0, x1, title, color, steer_rel, brake):
    cv2.rectangle(panel, (x0 + 6, 6), (x1 - 6, 150), color, 2)
    cv2.putText(panel, title, (x0 + 20, 38), FONT, 0.85, color, 2)
    cv2.putText(panel, "STERZO:", (x0 + 20, 78), FONT, 0.55, GREY, 1)
    cv2.putText(panel, steer_word(steer_rel), (x0 + 115, 78), FONT, 0.7, WHITE, 2)
    cv2.putText(panel, "FRENO:", (x0 + 20, 118), FONT, 0.55, GREY, 1)
    cv2.putText(panel, brake_word(brake), (x0 + 115, 118), FONT, 0.7, WHITE, 2)
    cv2.rectangle(panel, (x0 + 20, 130), (x0 + 300, 146), GREY, 1)
    cv2.rectangle(panel, (x0 + 20, 130),
                  (x0 + 20 + int(max(0, min(1, brake)) * 280), 146), color, -1)


def draw_panel(w, hs, ms, hb, mb, speed):
    PANEL_H = 200
    panel = np.full((PANEL_H, w, 3), 22, np.uint8)
    draw_driver_box(panel, 0, w // 2, "TU (l'umano)", GREEN, hs, hb)
    draw_driver_box(panel, w // 2, w, "MODELLO v4", ORANGE, ms, mb)
    cv2.line(panel, (w // 2, 8), (w // 2, 150), (70, 70, 70), 1)
    cv2.putText(panel, f"{speed*3.6:.0f} km/h", (w // 2 - 55, 30), FONT, 0.6, WHITE, 2)
    # verdetto coerente con le parole scritte nei riquadri
    steer_same = steer_word(hs) == steer_word(ms)
    brake_same = brake_word(hb) == brake_word(mb)
    yv = PANEL_H - 14
    cv2.putText(panel, "STERZO:", (30, yv), FONT, 0.6, GREY, 1)
    cv2.putText(panel, "UGUALE" if steer_same else "DIVERSO", (150, yv), FONT, 0.7,
                GREEN if steer_same else RED, 2)
    cv2.putText(panel, "FRENO:", (w // 2 + 20, yv), FONT, 0.6, GREY, 1)
    cv2.putText(panel, "UGUALE" if brake_same else "DIVERSO", (w // 2 + 130, yv), FONT, 0.7,
                GREEN if brake_same else RED, 2)
    return panel


def main() -> int:
    ap = argparse.ArgumentParser(description="Proietta la traiettoria di curva sulla strada")
    ap.add_argument("--report", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--fps", type=int, default=10)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.report)))
    fx, fy, cx, cy, W, H = load_intrinsics(args.calib)
    slope = fit_slope(rows)
    if slope is None:
        print("[proj] non riesco a calibrare la curvatura su questa sessione")
        return 1
    hs_med = st.median(float(r["human_steering"]) for r in rows)
    ms_med = st.median(float(r["model_steering"]) for r in rows)
    print(f"intrinseci: fx={fx:.0f} cx={cx:.0f} cy={cy:.0f} {W}x{H} | slope={slope:.2f} 1/m per sterzo")

    vid = Path(args.session) / "video.mp4"
    if not vid.is_file():
        vid = Path(args.session) / "video.h264"
    cap = cv2.VideoCapture(str(vid))
    OUT_W, ROAD_H = 960, 540
    sx, sy = OUT_W / W, ROAD_H / H
    origin = (int((W - 1 - cx) * sx), ROAD_H - 4)            # centro-basso: le ruote
    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"),
                             args.fps, (OUT_W, ROAD_H + 200))
    n = 0
    for r in rows:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(float(r["frame_idx"])))
        ok, frame = cap.read()
        if not ok:
            continue
        road = cv2.resize(cv2.flip(frame[:, : frame.shape[1] // 2], -1), (OUT_W, ROAD_H))

        hs = float(r["human_steering"]) - hs_med             # sterzo relativo al dritto
        ms = float(r["model_steering"]) - ms_med
        hb, mb = float(r["human_brake"]), float(r["model_brake"])
        # ingombro reale a terra (larghezza 110 cm) proiettato, umano e modello
        for kappa, color in ((slope * hs, GREEN), (slope * ms, ORANGE)):
            L, R = corridor_edges(kappa)
            pL = project(L, fx, fy, cx, cy, W, H, sx, sy, keep=True)
            pR = project(R, fx, fy, cx, cy, W, H, sx, sy, keep=True)
            draw_corridor(road, pL, pR, color)
        cv2.circle(road, origin, 7, WHITE, -1)               # le ruote (origine comune)

        cv2.rectangle(road, (0, 0), (OUT_W, 30), (0, 0, 0), -1)
        cv2.putText(road, "VERDE = dove vai TU   |   ARANCIO = dove andrebbe il MODELLO",
                    (10, 21), FONT, 0.55, WHITE, 1)

        panel = draw_panel(OUT_W, hs, ms, hb, mb, float(r["speed_ms"]))
        writer.write(np.vstack([road, panel]))
        n += 1
        if n % 100 == 0:
            print(f"  {n}/{len(rows)}")

    writer.release(); cap.release()
    print(f"\nVideo: {args.output}  ({n} frame)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
