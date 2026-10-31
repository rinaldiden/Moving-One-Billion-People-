#!/usr/bin/env python3
"""
drift_monitor.py — monitor di drift della calibrazione (gate qualita').

Su una bici che vibra, la rotazione relativa tra le camere driftta nel tempo ->
la rettifica si rompe -> la depth sballa. Come Tesla (flow-guided rectification)
misuriamo la DISPARITA' VERTICALE residua dei match L<->R: in uno stereo
rettificato bene e' ~0; se cresce oltre soglia -> la calib va rifatta.

Leggero: puo' girare sul Pi come quality-gate (marca i tratti scalibrati, da
scartare nel training, à la harvester) o lanciare un flag "ricalibra".

Uso:
  python3 drift_monitor.py --video clip.h264 --calib calib_logger.json [--thresh 0.5]
  -> exit code 0 se ok, 2 se drift oltre soglia (comodo in script/cron).
"""
import argparse
import sys
import numpy as np
import cv2

from stereo_common import Calib, split_sbs, CAM_W, CAM_H
from autorectify import match_LR, mean_abs_dy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--thresh", type=float, default=0.5,
                    help="soglia dy px oltre cui = drift (rettifica buona <0.3)")
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true")
    args = ap.parse_args()

    calib = Calib.load(args.calib)
    cap = cv2.VideoCapture(args.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // max(1, args.frames))
    dys, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            left, right = split_sbs(frame, order=args.order, flip180=not args.no_flip)
            pL, pR = match_LR(left, right)
            if len(pL) >= 30:
                dys.append(mean_abs_dy(calib, pL, pR))
        i += 1
    cap.release()

    if not dys:
        print("drift: indeterminato (pochi match - scena senza texture)")
        sys.exit(1)
    dy = float(np.median(dys))
    status = "OK" if dy <= args.thresh else "DRIFT -> RICALIBRARE"
    print(f"dy mediano = {dy:.3f}px  (soglia {args.thresh}) -> {status}")
    sys.exit(0 if dy <= args.thresh else 2)


if __name__ == "__main__":
    main()
