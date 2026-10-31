#!/usr/bin/env python3
"""
validate.py — validazione metrica col METRO + muro-test della focale.

Il metro e' la nostra ancora metrica al posto della scacchiera. Misurando un
target a distanza NOTA ricaviamo:
  - la FOCALE reale:  f_px = disparita_mediana * Z_true / B   (fixa lo scarto 13%)
  - l'ERRORE %:       |Z_stimato - Z_true| / Z_true           (sei a 1-2%?)

PROTOCOLLO (vedi README): metti un oggetto piano/ben visibile sull'asse della
camera a distanze note col metro (1,2,3,5,10 m), registra ~10s fermo a ciascuna,
poi:
  # muro-test singolo (una distanza):
  python3 validate.py --video 3m.h264 --calib calib_logger.json --distance 3.0
  # tabella completa (piu' distanze):
  python3 validate.py --calib calib_logger.json --targets targets.json
dove targets.json = [{"video":"1m.h264","distance_m":1.0}, {"video":"3m.h264","distance_m":3.0}, ...]
"""
import argparse
import json
import numpy as np
import cv2

from stereo_common import Calib, split_sbs, depth_from_disparity, CAM_W, CAM_H
from depth import disparity_sgbm


def measure(video, calib, rect, roi_frac=0.15, max_frames=30, order="LR", flip=True):
    """Disparita' e profondita' mediane in una ROI centrale, su piu' frame."""
    f, B = rect["focal_px"], rect["baseline_m"]
    cap = cv2.VideoCapture(video)
    w, h = CAM_W, CAM_H
    x0, x1 = int(w * (0.5 - roi_frac)), int(w * (0.5 + roi_frac))
    y0, y1 = int(h * (0.5 - roi_frac)), int(h * (0.5 + roi_frac))
    disps, depths, n = [], [], 0
    while n < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        left, right = split_sbs(frame, order=order, flip180=flip)
        lr = cv2.remap(left, rect["m1x"], rect["m1y"], cv2.INTER_LINEAR)
        rr = cv2.remap(right, rect["m2x"], rect["m2y"], cv2.INTER_LINEAR)
        disp = disparity_sgbm(lr, rr)
        depth = depth_from_disparity(disp, f, B)
        d_roi = disp[y0:y1, x0:x1]; z_roi = depth[y0:y1, x0:x1]
        d_roi = d_roi[d_roi > 0]; z_roi = z_roi[z_roi > 0]
        if d_roi.size:
            disps.append(np.median(d_roi)); depths.append(np.median(z_roi))
        n += 1
    cap.release()
    if not disps:
        return None
    return float(np.median(disps)), float(np.median(depths))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", required=True)
    ap.add_argument("--video")
    ap.add_argument("--distance", type=float, help="distanza reale (m) misurata col metro")
    ap.add_argument("--targets", help="JSON lista {video, distance_m}")
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true")
    args = ap.parse_args()

    calib = Calib.load(args.calib)
    rect = calib.rectify()
    f, B = rect["focal_px"], rect["baseline_m"]
    flip = not args.no_flip
    print(f"calib: focal={f:.1f}px  baseline={B*1000:.1f}mm")

    items = json.load(open(args.targets)) if args.targets else \
        [{"video": args.video, "distance_m": args.distance}]

    print(f"\n{'dist_reale':>10} {'Z_stim':>8} {'err%':>7} {'disp':>7} {'f_misurata':>11}")
    print("-" * 48)
    focals = []
    for it in items:
        r = measure(it["video"], calib, rect, order=args.order, flip=flip)
        if r is None:
            print(f"{it['distance_m']:>10.2f}  (nessuna disparita' valida)"); continue
        disp, z = r
        Zt = it["distance_m"]
        err = abs(z - Zt) / Zt * 100
        f_meas = disp * Zt / B                 # focale implicata dal metro
        focals.append(f_meas)
        print(f"{Zt:>10.2f} {z:>8.2f} {err:>6.1f}% {disp:>7.2f} {f_meas:>11.1f}")

    if focals:
        fm = float(np.median(focals))
        print("-" * 48)
        print(f"FOCALE misurata col metro = {fm:.1f}px  (calib attuale {f:.1f}px, "
              f"scarto {abs(fm-f)/f*100:.1f}%)")
        if abs(fm - f) / f > 0.03:
            print(f"  -> aggiorna la focale: rifai bootstrap con --focal-px {fm:.0f} "
                  f"e ri-lancia autorectify, oppure scala K di {fm/f:.4f}")


if __name__ == "__main__":
    main()
