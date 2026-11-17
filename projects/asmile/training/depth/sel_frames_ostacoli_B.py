#!/usr/bin/env python3
"""Set dev (10) + set B (30) per L1.ostacoli v2 (2026-11-10). Stesso criterio di sel_frames_ostacoli.py, offset diverso,
nessun frame entro +-30 da A (frames_ostacoli.json), dai dev, e tra B/dev. NON legge verita_occhio.json."""
import json, os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D
SESS = "session_20261109_094146"
idx = json.load(open(os.path.join(D.ROOT, "asmile-loggers/_solo_movimento/asmile-001", SESS, "index.json")))
t = np.array(D.read_t(SESS, "right"), float)
enc = D.enc_interp(t[0], t[-1]); s = enc(t)
tenuto = np.zeros(len(t), bool)
for tr in idx["tratti"]:
    if tr["stato"] == "tenuto": tenuto[tr["frame_da"]:tr["frame_a"] + 1] = True
v = (enc(t + 500) - enc(t - 500)) / 1.0
vmin = np.array([min((enc(t[i] + dt) - enc(t[i] + dt - 100)) / 0.1 for dt in (-500, -250, 0, 250, 500)) for i in range(len(t))])
cand = np.nonzero(tenuto & (v > 0.3) & (vmin > 0.3))[0]
A = [f["frame"] for f in json.load(open(os.path.join(HERE, "out_20261110/frames_ostacoli.json")))["frames"]]
taken = list(A)
def pick(n, off, step=1):
    out = []
    for k in range(0, n * step, step):
        j = int((k + off) * len(cand) / (n * step))
        for dj in sorted(range(-60, 61), key=abs):
            if 0 <= j + dj < len(cand):
                f = int(cand[j + dj])
                if all(abs(f - x) > 30 for x in taken): out.append(f); taken.append(f); break
    return out
dev = pick(10, 0.25, 3)
B = pick(30, 0.75)
def rows(fs): return [{"frame": f, "t_ms": int(t[f]), "v_enc_ms": round(float(v[f]), 3)} for f in sorted(fs)]
meta = {"sessione": SESS, "unita": "asmile-001", "calib": "PROVVISORIA, punto A in corso", "n_candidati": int(len(cand))}
json.dump({**meta, "uso": "SVILUPPO v2 (tarare qui)", "frames": rows(dev)}, open(os.path.join(HERE, "out_20261110/frames_dev.json"), "w"), indent=1)
json.dump({**meta, "uso": "TEST B alla cieca (mai usato per sviluppo)", "criterio": "come set A, offset 0.75, nessun frame entro +-30 da A e dev", "frames": rows(B)}, open(os.path.join(HERE, "out_20261110/frames_ostacoli_B.json"), "w"), indent=1)
print(len(dev), sorted(dev)); print(len(B), sorted(B))
