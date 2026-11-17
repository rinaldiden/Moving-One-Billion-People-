#!/usr/bin/env python3
"""Lista FISSA frame per L1.ostacoli in ombra (2026-11-10). #001 session_20261109_094146.
Criterio: frame in tratto 'tenuto' dell'index, v_encoder (derivata su +-0.5 s) > 0.3 m/s su tutta la finestra, passo regolare."""
import json, os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D
SESS = "session_20261109_094146"
idx = json.load(open(os.path.join(D.ROOT, "asmile-loggers/_solo_movimento/asmile-001", SESS, "index.json")))
t = np.array(D.read_t(SESS, "right"), float)
enc = D.enc_interp(t[0], t[-1])
s = enc(t)
tenuto = np.zeros(len(t), bool)
for tr in idx["tratti"]:
    if tr["stato"] == "tenuto": tenuto[tr["frame_da"]:tr["frame_a"] + 1] = True
v = (enc(t + 500) - enc(t - 500)) / 1.0
vmin = np.array([min((enc(t[i] + dt) - enc(t[i] + dt - 100)) / 0.1 for dt in (-500, -250, 0, 250, 500)) for i in range(len(t))])
ok = tenuto & (v > 0.3) & (vmin > 0.3)
cand = np.nonzero(ok)[0]
N = 30
pick = [int(cand[int((k + 0.5) * len(cand) / N)]) for k in range(N)]
out = {"sessione": SESS, "unita": "asmile-001", "criterio": "tenuto & v_enc(+-0.5s)>0.3 & v_enc locale>0.3 su 5 istanti; passo regolare sui candidati",
       "calib": "PROVVISORIA, punto A in corso", "n_candidati": int(len(cand)), "n_totale": len(t),
       "frames": [{"frame": f, "t_ms": int(t[f]), "v_enc_ms": round(float(v[f]), 3)} for f in pick]}
json.dump(out, open(os.path.join(HERE, "out_20261110", "frames_ostacoli.json"), "w"), indent=1)
print(len(cand), pick)
