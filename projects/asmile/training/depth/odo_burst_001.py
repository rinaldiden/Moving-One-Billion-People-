#!/usr/bin/env python3
"""odo_burst_001.py — controllo di coerenza gratuito (indicazione, non gate): feature statiche tracciate con KLT su raffiche di 10 fotogrammi
CONSECUTIVI (passo 1/15 s: a 4 m/s il passo da 1 s di depth_video_001 e' troppo lungo), Z dalla depth SGBM (calib B30, baseline_m),
pendenza -dZ/ds con s = encoder ruota della sola sessione (wheel_circum 0.3374 attivo). Attesa 1.0. Nessun filtro sulle feature in moto
(si usa la mediana). Uso: odo_burst_001.py SESSIONE [--every 150] [--vmin 1.5]
"""
import os, sys, json, argparse
import numpy as np, cv2
import depth_seg_001 as D
from depth_video_001 import disparity, enc_session

ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--every", type=int, default=150)
ap.add_argument("--vmin", type=float, default=1.5); ap.add_argument("--len", type=int, default=10); a = ap.parse_args()
sess = "session_" + a.session
rc = D.Rect(); f_px, Bm = rc.f, rc.r["baseline_m"]
t = np.array(D.read_t(sess, "right")); enc, _ = enc_session(sess)
s_all = enc(t); v_all = enc(t + 500) - enc(t - 500)
starts, last = [], -10 ** 9
for i in range(len(t) - a.len):
    if i - last >= a.every and v_all[i:i + a.len].min() > a.vmin:
        starts.append(i); last = i
sset = {j: k for k, i in enumerate(starts) for j in range(i, i + a.len)}
print(sess, "raffiche", len(starts), flush=True)
gl = D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264")); gr = D.gray_frames(os.path.join(D.LOGS, sess + "_left.h264"))
tracks, prev, cur_b, res = [], None, -1, []


def Zat(disp, x, y):
    dd = disp[y - 2:y + 3, x - 2:x + 3]; dd = dd[dd > 4]
    return f_px * Bm / float(np.median(dd)) if len(dd) >= 8 else None


def close(tracks):
    for tr in tracks:
        if len(tr["z"]) >= 7 and tr["s"][-1] - tr["s"][0] >= 1.0:
            sl = np.polyfit(tr["s"], tr["z"], 1)[0]
            res.append((-sl, float(np.mean(tr["z"])), cur_b))


for i, (Lr, Rr) in enumerate(zip(gl, gr)):
    if i > starts[-1] + a.len: break
    if i not in sset: continue
    b = sset[i]
    L, R = rc(Lr, Rr); disp = disparity(L, R)
    if b != cur_b:
        close(tracks); tracks = []; prev = None; cur_b = b
    if prev is not None and tracks:
        p0 = np.array([tr["p"] for tr in tracks], np.float32).reshape(-1, 1, 2)
        p1, s1, _ = cv2.calcOpticalFlowPyrLK(prev, L, p0, None, winSize=(31, 31), maxLevel=4)
        pb, s2, _ = cv2.calcOpticalFlowPyrLK(L, prev, p1, None, winSize=(31, 31), maxLevel=4)
        ok = (s1[:, 0] == 1) & (s2[:, 0] == 1) & (np.abs(pb - p0).reshape(-1, 2).max(1) < 1.0)
        keep = []
        for tr, p, o in zip(tracks, p1.reshape(-1, 2), ok):
            x, y = int(round(p[0])), int(round(p[1]))
            if o and 5 <= x < 1275 and 5 <= y < 795:
                z = Zat(disp, x, y)
                if z and 2.5 <= z <= 14:
                    tr["p"] = (float(p[0]), float(p[1])); tr["z"].append(z); tr["s"].append(float(s_all[i])); keep.append(tr); continue
            close([tr])
        tracks = keep
    else:
        pts = cv2.goodFeaturesToTrack(L[:520], 400, 0.01, 10)
        if pts is not None:
            for p in pts.reshape(-1, 2):
                z = Zat(disp, int(p[0]), int(p[1]))
                if z and 2.5 <= z <= 14: tracks.append(dict(p=(float(p[0]), float(p[1])), z=[z], s=[float(s_all[i])]))
    prev = L.copy()
close(tracks)
r = np.array(res)
out = dict(sess=sess, raffiche=len(starts), n_tracce=int(len(r)))
if len(r):
    for nome, m in (("tutte", np.ones(len(r), bool)), ("Z<8", r[:, 1] < 8), ("Z>=8", r[:, 1] >= 8)):
        if m.sum():
            out[nome] = dict(n=int(m.sum()), mediana=round(float(np.median(r[m, 0])), 3),
                             iqr=[round(float(np.percentile(r[m, 0], 25)), 3), round(float(np.percentile(r[m, 0], 75)), 3)])
    pb = [np.median(r[r[:, 2] == k, 0]) for k in set(r[:, 2]) if (r[:, 2] == k).sum() >= 5]
    out["mediana_per_raffica"] = dict(n=len(pb), mediana=round(float(np.median(pb)), 3), iqr=[round(float(np.percentile(pb, 25)), 3), round(float(np.percentile(pb, 75)), 3)])
print(json.dumps(out, indent=1))
os.makedirs(os.path.join(D.HERE, "out_20261112", sess), exist_ok=True)
json.dump(out, open(os.path.join(D.HERE, "out_20261112", sess, "odo_burst.json"), "w"), indent=1)
