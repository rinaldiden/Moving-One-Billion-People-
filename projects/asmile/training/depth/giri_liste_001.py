#!/usr/bin/env python3
"""giri_liste_001.py — liste fotogrammi dei giri 13/11 di #001: (a) 1 Hz a bici in moto (v>0.3 m/s, come depth_video_001), (b) tratti 15 fps (frenate + controsole). Scrive CSV in out_20261113_giri."""
import os, sys, csv, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import depth_seg_001 as D
from depth_video_001 import enc_session
OUT = os.path.join(D.HERE, "out_20261113_giri")
S1, S2 = "session_20261113_150337", "session_20261113_151400"
SEG = [("frenata1", S1, 0, 224), ("frenata2_monovolume", S1, 4438, 4739), ("controsole_a", S1, 990, 1170), ("controsole_b", S1, 2325, 2505), ("controsole_c", S2, 3000, 3270)]
for s in (S1, S2):
    t = np.array(D.read_t(s, "right")); enc, n = enc_session(s); v = enc(t + 500) - enc(t - 500)
    sel, last = [], -1e9
    for i in range(len(t)):
        if v[i] > 0.3 and t[i] - last >= 1000: sel.append(i); last = t[i]
    w = csv.writer(open(os.path.join(OUT, f"lista_1hz_{s[8:]}.csv"), "w")); w.writerow(["frame"]); [w.writerow([i]) for i in sel]
    print(s, len(t), "frame; moto >0.3 m/s:", round(float((v > 0.3).mean()), 3), "campioni 1Hz:", len(sel), "fermo (s):", round(float((v <= 0.3).sum() / 14.7)))
for n, s, a, b in SEG:
    t = np.array(D.read_t(s, "right")); enc, _ = enc_session(s); v = (enc(t + 500) - enc(t - 500))
    print(n, s[8:], a, b, "v media m/s", round(float(v[a:b].mean()), 2), "min", round(float(v[a:b].min()), 2), "max", round(float(v[a:b].max()), 2))
    w = csv.writer(open(os.path.join(OUT, f"lista_15fps_{n}.csv"), "w")); w.writerow(["sess", "frame"]); [w.writerow([s, i]) for i in range(a, b)]
