#!/usr/bin/env python3
"""
calib_tape.py — calibrazione metrica COL METRO, senza scacchiera (scelta di Daniele 2026-11-07).

Protocollo: bersaglio FISSO (pannello piano ~1x1m con disegno contrastato, centrato davanti
alla bici, ~altezza camere). La bici parte a 1 m e arretra: 1, 2, 3, 5, 7, 10, 15 m (misurati
dal piano delle lenti), ferma ~10 s a ogni distanza. UN SOLO video.

Cosa fa:
  1. trova i tratti FERMI (bici immobile >= --min-still s) e li abbina in ordine alle distanze;
  2. per ogni distanza: disparità del bersaglio nella zona centrale (larga ~0.8 m reali →
     la ROI si stringe con la distanza) da match SIFT L↔R rettificati (subpixel) + SGBM;
  3. fit lineare  d = (f·B)·(1/Z) + d0   → focale effettiva + offset d0 (yaw/sync residui);
  4. scala FISSA della depth densa YOLO26:  Z_vero = s · Z_modello  (mediana dei rapporti);
  5. tabella errore % a ogni distanza (stereo e depth densa) + scrive i campi nella calib.

Uso:
  python3 calib_tape.py --left L.h264 --right R.h264 --calib calib_asmile-001.json \
      --distances 1 2 3 5 7 10 15 --write
  (logger Camarray: --video sbs.h264 al posto di --left/--right)
"""
import argparse
import json
import os
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_common import Calib                      # noqa: E402
from depth import disparity_sgbm                     # noqa: E402
from asmile_perception import Source, ensure_model   # noqa: E402

TARGET_HALF_M = 0.4                                   # metà larghezza utile del bersaglio


def still_segments(src, min_still_s, thr=3.0):
    """Tratti con la camera ferma: differenza media fra frame consecutivi, mediana su 1 s
    (da fermo ~0.2 con picchi isolati da compressione; in moto ~10)."""
    prev, diffs = None, []
    for _ in range(src.n):
        pair = src.read()
        if pair is None:
            break
        g = cv2.resize(pair[0], (320, 200)).astype(np.float32)
        diffs.append(0.0 if prev is None else float(np.mean(np.abs(g - prev))))
        prev = g
    k = int(src.fps)
    sm = np.array([np.median(diffs[max(0, i - k // 2):i + k // 2 + 1]) for i in range(len(diffs))])
    still = sm < thr
    segs, start = [], None
    for i, s in enumerate(list(still) + [False]):
        if s and start is None:
            start = i
        elif not s and start is not None:
            if (i - start) / src.fps >= min_still_s:
                segs.append((start, i))
            start = None
    return segs


def roi_for(Z, f, w=1280, h=800):
    half = int(np.clip(TARGET_HALF_M * f / Z, 25, w * 0.2))
    return w // 2 - half, w // 2 + half, h // 2 - half, h // 2 + half


def measure(src, rect, seg, Z_guess, dmodel, nframes=12):
    f = rect["focal_px"]
    x0, x1, y0, y1 = roi_for(Z_guess, f)
    sift = cv2.SIFT_create(2000)
    bf = cv2.BFMatcher()
    d_sift, d_sgbm, z_mono = [], [], []
    for idx in np.linspace(seg[0] + 15, seg[1] - 15, nframes).astype(int):
        L, R = src.read(idx)
        L = cv2.remap(L, rect["m1x"], rect["m1y"], cv2.INTER_LINEAR)
        R = cv2.remap(R, rect["m2x"], rect["m2y"], cv2.INTER_LINEAR)
        # SIFT: punti nella ROI sinistra, match su tutta la destra, vincolo epipolare |dy|<1.5
        mL = np.zeros_like(L); mL[y0:y1, x0:x1] = 255
        k1, s1 = sift.detectAndCompute(L, mL)
        k2, s2 = sift.detectAndCompute(R, None)
        if s1 is not None and s2 is not None and len(k1) > 5:
            for a, b in bf.knnMatch(s1, s2, k=2):
                if a.distance < 0.75 * b.distance:
                    p, q = k1[a.queryIdx].pt, k2[a.trainIdx].pt
                    if abs(p[1] - q[1]) < 1.5 and p[0] - q[0] > 0:
                        d_sift.append(p[0] - q[0])
        disp = disparity_sgbm(L, R, 256, wls=False)[y0:y1, x0:x1]
        v = disp[disp > 0.5]
        if v.size:
            d_sgbm.append(float(np.median(v)))
        dense = dmodel(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), verbose=False)[0].depth.data.cpu().numpy()
        dense = cv2.resize(dense, (L.shape[1], L.shape[0]))
        z_mono.append(float(np.median(dense[y0:y1, x0:x1])))
    ds = float(np.median(d_sift)) if len(d_sift) >= 10 else None
    dg = float(np.median(d_sgbm)) if d_sgbm else None
    return ds, dg, float(np.median(z_mono)), len(d_sift)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video"); ap.add_argument("--left"); ap.add_argument("--right")
    ap.add_argument("--calib", required=True)
    ap.add_argument("--distances", type=float, nargs="+", default=[1, 2, 3, 5, 7, 10, 15])
    ap.add_argument("--min-still", type=float, default=5.0)
    ap.add_argument("--write", action="store_true", help="scrive focal_fit_px/d0_px/scale_fixed nella calib")
    a = ap.parse_args()
    a.out = tempfile.mkdtemp()

    meta = json.load(open(a.calib))
    rect = Calib.load(a.calib).rectify()
    B = rect["baseline_m"]
    src = Source(a, meta.get("order", "LR"), meta.get("flip180", bool(a.video)))
    from ultralytics import YOLO
    dmodel = YOLO(ensure_model("yolo26m-depth.pt"))

    segs = still_segments(src, a.min_still)
    print(f"[1] tratti fermi trovati: {len(segs)} -> " +
          ", ".join(f"{s / src.fps:.0f}-{e / src.fps:.0f}s" for s, e in segs))
    if len(segs) != len(a.distances):
        print(f"    ATTENZIONE: {len(segs)} tratti vs {len(a.distances)} distanze -> "
              f"uso i primi {min(len(segs), len(a.distances))} in ordine (controlla!)")
    rows = []
    for (s, e), Z in zip(segs, a.distances):
        ds, dg, zm, n = measure(src, rect, (s, e), Z, dmodel)
        d = ds if ds is not None else dg
        rows.append((Z, d, ds, dg, zm, n))
        print(f"    Z={Z:5.1f}m  disparità SIFT={ds if ds is None else round(ds, 2)} (n={n})  "
              f"SGBM={dg if dg is None else round(dg, 2)}  depth-modello={zm:.2f}m")

    ok = [(Z, d) for Z, d, *_ in rows if d is not None]
    if len(ok) < 3:
        print("[!] servono almeno 3 distanze misurate"); return
    invZ = np.array([1 / Z for Z, _ in ok]); dd = np.array([d for _, d in ok])
    A = np.vstack([invZ, np.ones_like(invZ)]).T
    (fB, d0), *_ = np.linalg.lstsq(A, dd, rcond=None)
    f_fit = fB / B
    s_fixed = float(np.median([r[0] / r[4] for r in rows if r[4] > 0]))
    print(f"\n[2] FIT:  f_effettiva = {f_fit:.1f}px (rettifica {rect['focal_px']:.1f})   d0 = {d0:.2f}px")
    print(f"[3] scala fissa depth densa YOLO26: x{s_fixed:.3f}")
    print("\n   Z vero | stereo Z   err%  | depth densa Z  err%")
    for Z, d, _ds, _dg, zm, _n in rows:
        zs = fB / (d - d0) if d is not None and d - d0 > 0 else float("nan")
        zd = s_fixed * zm
        print(f"   {Z:6.1f} | {zs:8.2f}  {100 * (zs - Z) / Z:+6.1f}% | {zd:8.2f}  {100 * (zd - Z) / Z:+6.1f}%")

    if a.write:
        meta.update({"focal_fit_px": round(float(f_fit), 2), "d0_px": round(float(d0), 3),
                     "scale_fixed": round(s_fixed, 4),
                     "d0_note": "dal fit col METRO (calib_tape.py)",
                     "tape_points": [{"Z_m": Z, "disp_px": d, "z_model_m": zm} for Z, d, _a, _b, zm, _n in rows]})
        json.dump(meta, open(a.calib, "w"), indent=2)
        print(f"\n[4] scritto in {a.calib}")


if __name__ == "__main__":
    main()
