#!/usr/bin/env python3
"""
stereo_depth.py — pipeline SGBM metrica PULITA per Asmile (reference Mac + base edge Pi).

Side-by-side stereo → (rettifica opzionale) → SGBM + check LEFT-RIGHT consistency →
depth METRICA in metri, usando baseline 200mm. Il check LR (senza ximgproc) uccide
l'artefatto "depth 1.24m stuck" di depth_test1.

Preset validati:
  - camarray2560 : video di maggio (2560x800 side-by-side). focal 1183px, baseline 200mm,
    ordine SGBM swappato — da config/calibration/depth_config.json (muro 1%, persona 1.5% err).
Per le OV9281 separate di #001: usa --calib <stereo_calibration.yaml> --baseline 200 (rettifica piena).

Uso:
  python3 stereo_depth.py --video <session/video.h264> --preset camarray2560 --out /tmp/depth --nframes 15
  python3 stereo_depth.py --video <...> --calib ../config/stereo_calibration.yaml --baseline 200 --out ...
"""
import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np

ASMILE = Path(__file__).resolve().parents[1]      # projects/asmile

PRESETS = {
    "camarray2560": dict(
        focal_px=1183.0, baseline_mm=200.0, split=True, sgbm_swap=True,
        sgbm=dict(minDisparity=0, numDisparities=192, blockSize=9,
                  P1=8 * 3 * 9 * 9, P2=32 * 3 * 9 * 9, disp12MaxDiff=1,
                  uniquenessRatio=5, speckleWindowSize=200, speckleRange=2,
                  preFilterCap=63),
    ),
}


def make_sgbm(p):
    return cv2.StereoSGBM_create(mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY, **p)


def lr_consistency(dispL, dispR, thresh=1.5):
    """Maschera i pixel incoerenti tra disparità L e R (uccide gli artefatti stuck)."""
    h, w = dispL.shape
    xs = np.arange(w)[None, :].repeat(h, 0)
    xr = (xs - dispL).astype(np.int32)
    xr_c = np.clip(xr, 0, w - 1)
    dR_at = np.take_along_axis(dispR, xr_c, axis=1)
    return (xr >= 0) & (np.abs(dispL - dR_at) <= thresh) & (dispL > 0)


def compute_depth(left_gray, right_gray, focal_px, baseline_mm, sgbm_params, swap):
    sg = make_sgbm(sgbm_params)
    a, b = (right_gray, left_gray) if swap else (left_gray, right_gray)
    dispL = sg.compute(a, b).astype(np.float32) / 16.0
    # right-disparity via flip (trucco standard, no ximgproc) per il check LR
    af, bf = np.fliplr(a), np.fliplr(b)
    dispR = np.fliplr(sg.compute(bf, af).astype(np.float32) / 16.0)
    mask = lr_consistency(dispL, dispR)
    # scarta disparità SATURATA al bordo della ricerca (= match inaffidabile / troppo
    # vicino per misurare: su video mal-rettificati dava la falsa "1.24m stuck")
    nd = sgbm_params["numDisparities"]
    mask &= dispL < (nd - 1)
    disp = dispL.copy()
    disp[~mask] = 0
    # speckle extra (SGBM lo fa gia' internamente; qui opzionale su int16)
    d16 = (disp * 16).astype(np.int16)
    cv2.filterSpeckles(d16, 0, sgbm_params["speckleWindowSize"],
                       sgbm_params["speckleRange"] * 16)
    disp[d16 == 0] = 0
    depth_m = np.zeros_like(disp)
    good = disp > 0.5
    depth_m[good] = (focal_px * baseline_mm / disp[good]) / 1000.0
    depth_m[(depth_m < 0.3) | (depth_m > 30)] = 0      # clamp realistico
    return depth_m, disp


def object_depth(depth_m, mask_bool):
    """Distanza (m) di un oggetto = mediana robusta della depth valida dentro la maschera."""
    vals = depth_m[mask_bool & (depth_m > 0)]
    return float(np.median(vals)) if vals.size > 20 else None


def colorize(depth_m, dmax=15.0):
    d = np.clip(depth_m / dmax, 0, 1)
    d8 = (d * 255).astype(np.uint8)
    col = cv2.applyColorMap(d8, cv2.COLORMAP_TURBO)
    col[depth_m <= 0] = (0, 0, 0)
    return col


def load_yaml_calib(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    out = {}
    for k in ("camera_matrix_left", "dist_coeffs_left", "camera_matrix_right",
              "dist_coeffs_right", "R1", "R2", "P1", "P2", "T"):
        n = fs.getNode(k)
        out[k] = None if n.empty() else n.mat()
    fs.release()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--calib", help="yaml calibrazione (rettifica piena, es. #001)")
    ap.add_argument("--baseline", type=float, default=200.0)
    ap.add_argument("--out", default="/tmp/depth_out")
    ap.add_argument("--nframes", type=int, default=15)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    if a.preset:
        cfg = PRESETS[a.preset]
        focal, baseline, split, swap, sgbm = (cfg["focal_px"], cfg["baseline_mm"],
                                              cfg["split"], cfg["sgbm_swap"], cfg["sgbm"])
        maps = None
    else:
        cal = load_yaml_calib(a.calib)
        focal = float(cal["P1"][0, 0]) if cal["P1"] is not None else None
        baseline = a.baseline
        split, swap = True, False
        sgbm = PRESETS["camarray2560"]["sgbm"]
        # rettifica piena
        sz = (1280, 800)
        mlx, mly = cv2.initUndistortRectifyMap(cal["camera_matrix_left"], cal["dist_coeffs_left"],
                                               cal["R1"], cal["P1"], sz, cv2.CV_32FC1)
        mrx, mry = cv2.initUndistortRectifyMap(cal["camera_matrix_right"], cal["dist_coeffs_right"],
                                               cal["R2"], cal["P2"], sz, cv2.CV_32FC1)
        maps = (mlx, mly, mrx, mry)
    print(f"[cfg] focal={focal:.1f}px baseline={baseline:.0f}mm swap={swap} rectify={'yes' if maps else 'no'}")

    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    step = max(1, n // a.nframes)
    stats = []
    i = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if split:
                mid = g.shape[1] // 2
                L, R = g[:, :mid], g[:, mid:]
            else:
                L = R = g
            if maps:
                L = cv2.remap(L, maps[0], maps[1], cv2.INTER_LINEAR)
                R = cv2.remap(R, maps[2], maps[3], cv2.INTER_LINEAR)
            depth, disp = compute_depth(L, R, focal, baseline, sgbm, swap)
            h, w = depth.shape
            cen = depth[h//2-40:h//2+40, w//2-60:w//2+60]
            cen_v = cen[cen > 0]
            valid_pct = 100.0 * (depth > 0).sum() / depth.size
            med = float(np.median(cen_v)) if cen_v.size else 0.0
            stats.append((i, valid_pct, med))
            if saved < 5:
                cv2.imwrite(f"{a.out}/depth_{i:05d}.png", colorize(depth))
                cv2.imwrite(f"{a.out}/left_{i:05d}.png", L)
                saved += 1
        i += 1
        if len(stats) >= a.nframes:
            break
    cap.release()

    if stats:
        meds = [m for _, _, m in stats if m > 0]
        valids = [v for _, v, _ in stats]
        print(f"[risultato] {len(stats)} frame · valid medio={np.mean(valids):.0f}% · "
              f"depth centro mediana={np.median(meds):.2f}m (range {min(meds):.2f}-{max(meds):.2f}m)" if meds else "nessuna depth valida")
        stuck = sum(1 for m in meds if abs(m - 1.24) < 0.03)
        print(f"[artefatto 1.24m] {stuck}/{len(meds)} frame (0 = risolto) · PNG in {a.out}")
        json.dump({"frames": stats, "focal_px": focal, "baseline_mm": baseline},
                  open(f"{a.out}/report.json", "w"), indent=2)


if __name__ == "__main__":
    main()
