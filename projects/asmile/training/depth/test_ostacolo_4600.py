#!/usr/bin/env python3
"""test_ostacolo_4600.py — caso fisso (veto asmile-occhio): fotogramma 4600 della sessione 094146 di #001.
A destra del corridoio ci sono una botte (box ~x1140-1270,y420-560, Z~7.1 m) e vasi/cassette (x1070-1150,y490-560, Z~7.3 m;
x940-1040,y455-520, Z~10 m). Lo strato "ostacolo senza classe" (obstacles(), NESSUNA maschera SAM = covered vuoto) deve dare almeno una
componente che copre la botte e una che copre i vasi, con Z fra 4 e 9 m. Falliva con corridoio |X|<=3 m (botte a X=3.06 m).
Uso: ~/.asmile_depth_venv/bin/python training/depth/test_ostacolo_4600.py   (richiede il video locale di #001)
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depth_seg_001 import Rect, gray_frames, obstacles, LOGS, H, W

FRAME = 4600
ATTESI = {"botte": (1140, 420, 1270, 560), "vasi": (1070, 490, 1150, 560)}


def main():
    rc = Rect()
    sess = "session_20261109_094146"
    for i, (a, b) in enumerate(zip(gray_frames(os.path.join(LOGS, f"{sess}_right.h264")),
                                   gray_frames(os.path.join(LOGS, f"{sess}_left.h264")))):
        if i == FRAME:
            L, R = rc(a, b)
            break
    disp = rc.disparity(L, R)
    obs = obstacles(rc, disp, np.zeros((H, W), np.uint8))
    ok_all = True
    for nome, (x0, y0, x1, y1) in ATTESI.items():
        box = np.zeros((H, W), bool); box[y0:y1, x0:x1] = True
        best = None
        for o in obs:
            cov = float((o[2] > 0)[box].sum()) / box.sum()
            if cov > 0.25 and (best is None or cov > best[0]):
                best = (cov, o[0])
        ok = best is not None and 4.0 <= best[1] <= 9.0
        ok_all &= ok
        print(f"{nome:6s}", "TROVATO copertura %.0f%% Z=%.1f m" % (100 * best[0], best[1]) if best else "NON TROVATO", "OK" if ok else "FAIL")
    print("PASSA" if ok_all else "FALLISCE")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
