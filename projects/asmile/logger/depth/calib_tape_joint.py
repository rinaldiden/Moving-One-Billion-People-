#!/usr/bin/env python3
"""
calib_tape_joint.py — calibrazione stereo COMPLETA col solo metro (niente scacchiera).

Video a bici FERMA davanti a un bersaglio a distanze note (1,2,3,5,7,10,15 m, ~10 s ciascuna;
vedi calib_tape.py per il protocollo). Da fermi lo sfasamento software fra le due camere
non conta, quindi la geometria è pulita.

Incognite: rotazione relativa R (3 angoli) + focale f. Vincoli fisici:
  - baseline ORIZZONTALE e nota (200 mm): T = [-B, 0, 0]
  - dopo la rettifica, ogni match L↔R ha dy = 0
  - sui match del BERSAGLIO (ROI centrale, larga ~0.8 m reali) la disparità vale f'·B/Z_metro
Least-squares robusto (soft-L1) su tutto insieme → calib JSON drop-in (stereo_common.Calib),
d0 = 0 per costruzione, + scala fissa della depth densa YOLO26 + tabella errore %.

Uso:
  python3 calib_tape_joint.py --left L.h264 --right R.h264 --order RL --no-flip \
      --distances 1 2 3 5 7 10 15 --out calib_asmile-001.json [--base calib_asmile-001.json]
"""
import argparse
import json
import os
import sys
import tempfile

import cv2
import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asmile_perception import Source, ensure_model   # noqa: E402
from calib_tape import still_segments                 # noqa: E402

W, H = 1280, 800
TARGET_HALF_M = 0.4
MIN_HALF_PX = 25                                     # da lontano il bersaglio è piccolo: ROI minima


def collect(src, segs, per_seg=8):
    sift = cv2.SIFT_create(5000)
    bf = cv2.BFMatcher()
    out = []                                         # per segmento: (P1, P2)
    for s, e in segs:
        P1, P2 = [], []
        for idx in np.linspace(s + 20, e - 20, per_seg).astype(int):
            L, R = src.read(idx)
            k1, d1 = sift.detectAndCompute(L, None)
            k2, d2 = sift.detectAndCompute(R, None)
            if d1 is None or d2 is None:
                continue
            m = [x for x, y in bf.knnMatch(d1, d2, k=2) if x.distance < 0.7 * y.distance]
            if len(m) < 10:
                continue
            p1 = np.float32([k1[x.queryIdx].pt for x in m]); p2 = np.float32([k2[x.trainIdx].pt for x in m])
            _, inl = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.999)
            if inl is None:
                continue
            i = inl.ravel() > 0
            P1.append(p1[i]); P2.append(p2[i])
        out.append((np.vstack(P1), np.vstack(P2)) if P1 else (np.zeros((0, 2)), np.zeros((0, 2))))
    return out


def rectify(params, B):
    rx, ry, rz, f, k1 = params                       # k1 = distorsione radiale (stessa lente sulle 2 cam)
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])
    D = np.array([k1, 0, 0, 0, 0], float)
    R = cv2.Rodrigues(np.radians([rx, ry, rz]))[0]
    T = np.array([[-B], [0.0], [0.0]])
    R1, R2, P1, P2, *_ = cv2.stereoRectify(K, D, K, D, (W, H), R, T,
                                           flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    return K, D, R, T, R1, R2, P1, P2


def project(params, B, p1, p2):
    K, D, _, _, R1, R2, P1, P2 = rectify(params, B)
    u1 = cv2.undistortPoints(p1.reshape(-1, 1, 2).astype(np.float64), K, D, R=R1, P=P1).reshape(-1, 2)
    u2 = cv2.undistortPoints(p2.reshape(-1, 1, 2).astype(np.float64), K, D, R=R2, P=P2).reshape(-1, 2)
    return u1, u2, P1[0, 0]


def target_mask(p1, Z, f):
    half = np.clip(TARGET_HALF_M * f / Z, MIN_HALF_PX, W * 0.2)
    return (np.abs(p1[:, 0] - W / 2) < half) & (np.abs(p1[:, 1] - H / 2) < half)


def residuals(params, B, data, Zs, masks, w_tape):
    res = []
    for (p1, p2), Z, t in zip(data, Zs, masks):
        if len(p1) == 0:
            continue
        u1, u2, fr = project(params, B, p1, p2)
        res.append(u1[:, 1] - u2[:, 1])                          # dy = 0 ovunque
        if w_tape > 0 and t.sum() >= 5:                          # maschera FISSA: n residui costante
            d = np.median(u1[t, 0] - u2[t, 0])
            res.append(np.atleast_1d(w_tape * (d - fr * B / Z) / np.sqrt(t.sum()) * np.sqrt(len(p1))))
    return np.concatenate(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video"); ap.add_argument("--left"); ap.add_argument("--right")
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true")
    ap.add_argument("--distances", type=float, nargs="+", default=[1, 2, 3, 5, 7, 10, 15])
    ap.add_argument("--baseline-mm", type=float, default=200.0)
    ap.add_argument("--focal-px", type=float, default=930.0, help="valore iniziale")
    ap.add_argument("--init-deg", type=float, nargs=3, default=[0, 0, 0], help="rotazione iniziale rx ry rz")
    ap.add_argument("--fit-k1", action="store_true",
                    help="stima anche la distorsione radiale (2026-11-07 su #001: peggiora, overfit)")
    ap.add_argument("--base", help="calib JSON da cui ereditare i metadati (order, flip...)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    a.out_dir = tempfile.mkdtemp()
    B = a.baseline_mm / 1000.0

    src = Source(argparse.Namespace(video=a.video, left=a.left, right=a.right, out=a.out_dir),
                 a.order, not a.no_flip)
    segs = still_segments(src, 5.0)
    print(f"[1] tratti fermi: {len(segs)} -> " + ", ".join(f"{s / 15:.0f}-{e / 15:.0f}s" for s, e in segs))
    n = min(len(segs), len(a.distances))
    segs, Zs = segs[:n], a.distances[:n]
    data = collect(src, segs)
    print(f"[2] match per distanza: " + ", ".join(f"{Z:g}m={len(p)}" for (p, _), Z in zip(data, Zs)))

    masks = [target_mask(p1, Z, a.focal_px) for (p1, _), Z in zip(data, Zs)]
    best = None
    for f0 in (a.focal_px, 1100.0, 1300.0):                     # più partenze: la focale è la più incerta
        x0 = np.array(list(a.init_deg) + [f0, 0.0])
        r = least_squares(residuals, x0, args=(B, data, Zs, masks, 0.0), loss="soft_l1", f_scale=1.0,
                          bounds=([-20, -20, -20, 500, -0.6 if a.fit_k1 else -1e-9],
                                  [20, 20, 20, 2500, 0.6 if a.fit_k1 else 1e-9]))
        if best is None or r.cost < best.cost:
            best = r
    rx, ry, rz, f, k1 = best.x
    K, D, R, T, R1, R2, P1, P2 = rectify(best.x, B)
    print(f"[3] SOLUZIONE: rotazione rx/ry/rz = {rx:.2f}/{ry:.2f}/{rz:.2f}°   focale = {f:.1f}px "
          f"(rettificata {P1[0, 0]:.1f}px)   distorsione k1 = {k1:+.4f}")

    from ultralytics import YOLO
    dmodel = YOLO(ensure_model("yolo26m-depth.pt"))
    rows = []
    for (p1, p2), Z, (s, e) in zip(data, Zs, segs):
        if len(p1) == 0:
            print(f"   {Z:6.1f}  | nessun match L↔R (troppo vicino o senza texture) — escluso")
            continue
        u1, u2, fr = project(best.x, B, p1, p2)
        dy = np.median(np.abs(u1[:, 1] - u2[:, 1])) if len(p1) else float("nan")
        t = target_mask(p1, Z, f)
        d = float(np.median(u1[t, 0] - u2[t, 0])) if t.sum() >= 5 else float("nan")
        Zs_ = fr * B / d if d > 0 else float("nan")
        L, _ = src.read((s + e) // 2)
        maps = cv2.initUndistortRectifyMap(K, D, R1, P1, (W, H), cv2.CV_32FC1)
        Lr = cv2.remap(L, maps[0], maps[1], cv2.INTER_LINEAR)
        dense = dmodel(cv2.cvtColor(Lr, cv2.COLOR_GRAY2BGR), verbose=False)[0].depth.data.cpu().numpy()
        dense = cv2.resize(dense, (W, H))
        half = int(np.clip(TARGET_HALF_M * fr / Z, MIN_HALF_PX, W * 0.2))
        zm = float(np.median(dense[H // 2 - half:H // 2 + half, W // 2 - half:W // 2 + half]))
        rows.append((Z, d, Zs_, dy, zm, int(t.sum())))
    ok = [(Z, d) for Z, d, *_ in rows if d == d]
    invZ = np.array([1 / Z for Z, _ in ok]); dd = np.array([d for _, d in ok])
    (fB, d0), *_ = np.linalg.lstsq(np.vstack([invZ, np.ones_like(invZ)]).T, dd, rcond=None)
    f_fit = fB / B
    s_fixed = float(np.median([Z / zm for Z, _d, _z, _dy, zm, _n in rows if zm > 0]))
    print(f"\n[4] FIT COL METRO:  d = {fB:.1f}/Z + {d0:.2f}   →  focale effettiva {f_fit:.1f}px, "
          f"offset d0 {d0:.2f}px (≈ yaw {np.degrees(np.arctan(d0 / P1[0, 0])):.2f}°)")
    print(f"\n   Z metro | disparità | stereo Z    err%  | dy px | depth densa Z  err%   (scala fissa x{s_fixed:.3f})")
    for Z, d, _z, dy, zm, nt in rows:
        Zs_ = fB / (d - d0) if d - d0 > 0 else float("nan")
        print(f"   {Z:6.1f}  | {d:8.2f}  | {Zs_:7.2f}  {100 * (Zs_ - Z) / Z:+6.1f}% | {dy:4.2f}  | "
              f"{s_fixed * zm:7.2f}  {100 * (s_fixed * zm - Z) / Z:+6.1f}%   (punti bersaglio {nt})")

    meta = json.load(open(a.base)) if a.base else {}
    meta.update({
        "K_left": K.tolist(), "dist_left": D.tolist(), "K_right": K.tolist(), "dist_right": D.tolist(),
        "R": R.tolist(), "T": T.ravel().tolist(), "size": [W, H], "baseline_mm": a.baseline_mm,
        "order": a.order, "flip180": not a.no_flip, "d0_px": round(float(d0), 3),
        "focal_fit_px": round(float(f_fit), 2), "scale_fixed_dense": round(s_fixed, 4),
        "method": "calib_tape_joint: R da dy=0 su match a bici FERMA + fit col METRO d=fB/Z+d0 (T orizz. 200mm)",
        "tape_points": [{"Z_m": Z, "disp_px": round(d, 3), "Z_stereo_m": round(fB / (d - d0), 3) if d - d0 > 0 else None,
                         "z_model_m": round(zm, 3)} for Z, d, Zs_, _dy, zm, _n in rows],
    })
    for k in ("d0_note", "scale_fixed"):
        meta.pop(k, None)
    json.dump(meta, open(a.out, "w"), indent=2)
    print(f"\n[5] calib scritta -> {a.out}")


if __name__ == "__main__":
    main()
