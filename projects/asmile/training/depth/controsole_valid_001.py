#!/usr/bin/env python3
"""controsole_valid_001.py — nei tratti controsole a 15 fps: quota di depth valida DENTRO le zone sature (luma>=250, rettificata, 320x200) vs FUORI, ogni 5 fotogrammi. Scrive controsole_valid.json."""
import os, sys, glob, json, numpy as np, cv2
import depth_seg_001 as D
O = os.path.join(D.HERE, "out_20261113_giri"); rc = D.Rect(); R = {}
for nm, s in (("controsole_a", "session_20261113_150337"), ("controsole_b", "session_20261113_150337"), ("controsole_c", "session_20261113_151400")):
    z = np.load(glob.glob(os.path.join(O, f"A_{nm}", "session_*_A", "zmap.npz"))[0]); ks = sorted(int(k[1:]) for k in z.files); want = set(ks[::5]); f1 = ks[-1]
    ins, outs, sat = [], [], []
    for i, g in enumerate(D.gray_frames(os.path.join(D.LOGS, s + "_right.h264"))):
        if i > f1: break
        if i not in want: continue
        L = cv2.remap(g, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR); m = cv2.resize((L >= 250).astype(np.uint8), (320, 200), interpolation=cv2.INTER_AREA) > 0
        m = cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0; v = z[f"f{i}"] != 255
        sat.append(float(m.mean()))
        if m.sum() > 200: ins.append(float(v[m].mean()))
        if (~m).sum() > 200: outs.append(float(v[~m].mean()))
    R[nm] = dict(n=len(want), sat_quota_med=float(np.median(sat)), valid_dentro_sat=float(np.median(ins)) if ins else None, valid_fuori_sat=float(np.median(outs)), n_dentro=len(ins))
    print(nm, R[nm], flush=True)
json.dump(R, open(os.path.join(O, "controsole_valid.json"), "w"), indent=1)
