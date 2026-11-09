#!/usr/bin/env python3
"""eval_dy.py: dy dopo rettifica con una calib JSON (via stereo_common.Calib, lo stesso codice della depth), su match SIFT
di frame in movimento (m4). Tabella 3x3 + 4 angoli + centro. Uso: eval_dy.py CALIB.json MOVING.pkl"""
import sys, pickle, os, numpy as np, cv2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from stereo_common import Calib
c = Calib.load(sys.argv[1]); r = c.rectify(); M = pickle.load(open(sys.argv[2], 'rb'))
def rp(p, K, D, R, P): return cv2.undistortPoints(p.reshape(-1, 1, 2).astype(np.float64), K, D, R=R, P=P).reshape(-1, 2)
W, H = c.size
for sid, (p1, p2) in M.items():
    u1 = rp(p1, c.K1, c.d1, r['R1'], r['P1']); u2 = rp(p2, c.K2, c.d2, r['R2'], r['P2']); dy = u1[:, 1] - u2[:, 1]
    ok = np.abs(dy) < 20
    print(f'sessione {sid}: n={ok.sum()}  mediana|dy|={np.median(abs(dy[ok])):.3f}  p95|dy|={np.percentile(abs(dy[ok]), 95):.3f}  mediana(dy) segno={np.median(dy[ok]):+.3f}')
    x, y = p1[:, 0], p1[:, 1]
    for rr in range(3):
        row = []
        for cc in range(3):
            m = ok & (x >= cc * W / 3) & (x < (cc + 1) * W / 3) & (y >= rr * H / 3) & (y < (rr + 1) * H / 3)
            row.append(f'{np.median(abs(dy[m])):4.2f}/{np.percentile(abs(dy[m]), 95):4.1f} [{m.sum():4d}]' if m.sum() > 15 else '   --   ')
        print('   ' + '   '.join(row))
