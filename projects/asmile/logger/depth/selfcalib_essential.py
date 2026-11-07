#!/usr/bin/env python3
"""
selfcalib_essential.py — auto-calibrazione stereo SENZA scacchiera, posa relativa COMPLETA.

Per rig con camere separate montate a mano (asmile #001, 2x OV9281 Inno-Maker), dove la
rotazione relativa è grande (misurato 2026-11-07: ~7° di pitch, ~3.7° di yaw) e il modello
a piccola rotazione di autorectify.py resta a dy~5px.

Metodo: match SIFT L<->R accumulati su molti frame (bici in moto = scene diverse) →
matrice essenziale con K noto (focale a priori, poi fissata col METRO via validate.py) →
recoverPose → R completo + direzione di T → |T| riscalato alla baseline nota 200mm.
Scrive lo stesso JSON di stereo_common.Calib (drop-in per depth.py / validate.py).

Uso:
  python3 selfcalib_essential.py --video sbs.mp4 --out calib.json --focal-px 930 --no-flip
"""
import argparse
import json
import numpy as np
import cv2

from stereo_common import split_sbs, CAM_W, CAM_H, BASELINE_MM


def collect_matches(video, frames, order, flip, ratio=0.7):
    cap = cv2.VideoCapture(video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sift = cv2.SIFT_create(nfeatures=4000)
    bf = cv2.BFMatcher()
    P1, P2 = [], []
    for idx in np.linspace(30, n - 30, frames).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        L, R = split_sbs(frame, order=order, flip180=flip)
        k1, d1 = sift.detectAndCompute(L, None)
        k2, d2 = sift.detectAndCompute(R, None)
        if d1 is None or d2 is None or len(k1) < 20 or len(k2) < 20:
            continue
        m = [a for a, b in bf.knnMatch(d1, d2, k=2) if a.distance < ratio * b.distance]
        if len(m) < 15:
            continue
        p1 = np.float32([k1[x.queryIdx].pt for x in m])
        p2 = np.float32([k2[x.trainIdx].pt for x in m])
        # filtro per-frame (scarta match sbagliati prima di accumulare)
        _, inl = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.999)
        if inl is None:
            continue
        i = inl.ravel() > 0
        P1.append(p1[i]); P2.append(p2[i])
    cap.release()
    return np.vstack(P1), np.vstack(P2)


def rect_dy(P1, P2, K, R, T, size):
    R1, R2, Pr1, Pr2, *_ = cv2.stereoRectify(K, None, K, None, size, R, T, alpha=0)
    u1 = cv2.undistortPoints(P1.reshape(-1, 1, 2), K, None, R=R1, P=Pr1).reshape(-1, 2)
    u2 = cv2.undistortPoints(P2.reshape(-1, 1, 2), K, None, R=R2, P=Pr2).reshape(-1, 2)
    return u1[:, 1] - u2[:, 1], u1[:, 0] - u2[:, 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--focal-px", type=float, default=930.0)
    ap.add_argument("--baseline-mm", type=float, default=BASELINE_MM)
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true")
    a = ap.parse_args()

    size = (CAM_W, CAM_H)
    K = np.array([[a.focal_px, 0, CAM_W / 2], [0, a.focal_px, CAM_H / 2], [0, 0, 1]], float)
    P1, P2 = collect_matches(a.video, a.frames, a.order, not a.no_flip)
    print(f"[1] match accumulati: {len(P1)}")

    E, inl = cv2.findEssentialMat(P1, P2, K, cv2.RANSAC, 0.999, 1.0)
    i = inl.ravel() > 0
    _, R, t, _ = cv2.recoverPose(E, P1[i], P2[i], K)
    t = t.ravel() / np.linalg.norm(t)
    if t[0] > 0:                         # convenzione OpenCV: T_x < 0 con camera destra a dx
        t = -t
    T = (t * a.baseline_mm).reshape(3, 1)
    rv = cv2.Rodrigues(R)[0].ravel()
    print(f"[2] rotazione relativa (deg) rx/ry/rz = {np.degrees(rv).round(2)}  "
          f"direzione baseline = {t.round(3)}")

    dy0 = P1[i, 1] - P2[i, 1]
    dy, dx = rect_dy(P1[i], P2[i], K, R, T, size)
    print(f"[3] dy PRIMA {np.median(np.abs(dy0)):.2f}px  →  DOPO mediana {np.median(np.abs(dy)):.2f}px "
          f"(p90 {np.percentile(np.abs(dy), 90):.2f})  disparità>0: {100 * np.mean(dx > 0):.0f}%")

    out = {
        "K_left": K.tolist(), "dist_left": [0.0] * 5,
        "K_right": K.tolist(), "dist_right": [0.0] * 5,
        "R": R.tolist(), "T": T.ravel().tolist(),
        "size": list(size), "baseline_mm": a.baseline_mm,
        "method": "selfcalib_essential (SIFT+E, K a priori, |T|=baseline nota)",
        "n_matches": int(i.sum()),
        "rect_dy_median_px": round(float(np.median(np.abs(dy))), 3),
        "order": a.order, "flip180": not a.no_flip,
        "note": "Focale a priori: FISSARLA col metro (validate.py), poi rilanciare con --focal-px misurata.",
    }
    with open(a.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[4] calib salvata -> {a.out}")


if __name__ == "__main__":
    main()
