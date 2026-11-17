#!/usr/bin/env python3
"""Set C (L1.ostacoli v3, 2026-11-10) — FISSATO PRIMA di far girare la v3. Nessuna lettura di verita_occhio*.json, nessun uso del rilevatore.
Candidati: come B (tenuto, v_enc>0.3 m/s su finestra +-0.5 s e in 5 istanti, sessione #001 094146).
Esclusi: frame entro +-30 da A, B, dev e tra C stessi.
Arricchimento (criterio AUTOMATICO, indipendente dal rilevatore v3): classi SAM 3 gia' salvate in out_20261109/objects_giro.csv:
  score(frame) = n oggetti person/car con conf>=0.5 e 2<=Z_m<=12; si prendono avidamente (score decrescente, frame crescente) fino a N_ENRICH=17.
Il resto (fino a 57) a passo regolare (offset 0.5, poi passate con offset 0.25, 0.75, ... se mancano) dai candidati."""
import json, csv, os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D
SESS = "session_20261109_094146"; N_TOT, N_ENRICH = 57, 17
idx = json.load(open(os.path.join(D.ROOT, "asmile-loggers/_solo_movimento/asmile-001", SESS, "index.json")))
t = np.array(D.read_t(SESS, "right"), float)
enc = D.enc_interp(t[0], t[-1])
tenuto = np.zeros(len(t), bool)
for tr in idx["tratti"]:
    if tr["stato"] == "tenuto": tenuto[tr["frame_da"]:tr["frame_a"] + 1] = True
v = (enc(t + 500) - enc(t - 500)) / 1.0
vmin = np.array([min((enc(t[i] + dt) - enc(t[i] + dt - 100)) / 0.1 for dt in (-500, -250, 0, 250, 500)) for i in range(len(t))])
cand = set(int(i) for i in np.nonzero(tenuto & (v > 0.3) & (vmin > 0.3))[0])
ld = lambda n: [f["frame"] for f in json.load(open(os.path.join(HERE, "out_20261110", n)))["frames"]]
taken = ld("frames_ostacoli.json") + ld("frames_ostacoli_B.json") + ld("frames_dev.json")
score = {}
for r in csv.DictReader(open(os.path.join(HERE, "out_20261109/objects_giro.csv"))):
    if r["classe"] in ("person", "car") and float(r["conf"]) >= 0.5 and r["Z_m"] not in ("", "nan", "None") and 2 <= float(r["Z_m"]) <= 12:
        score[int(r["frame"])] = score.get(int(r["frame"]), 0) + 1
C = []; enriched = []
ok = lambda f: all(abs(f - x) > 30 for x in taken + C)
for f, s in sorted(score.items(), key=lambda kv: (-kv[1], kv[0])):
    if len(enriched) >= N_ENRICH: break
    if f in cand and ok(f): C.append(f); enriched.append(f)
cl = sorted(cand); n_reg = N_TOT - len(C)
for off in (0.5, 0.25, 0.75, 0.125, 0.375, 0.625, 0.875):   # passate successive a passo regolare finche' si arriva a N_TOT
    for k in range(n_reg):
        if len(C) >= N_TOT: break
        j = int((k + off) * len(cl) / n_reg)
        for dj in sorted(range(-80, 81), key=abs):
            if 0 <= j + dj < len(cl) and ok(cl[j + dj]): C.append(cl[j + dj]); break
rows = [{"frame": f, "t_ms": int(t[f]), "v_enc_ms": round(float(v[f]), 3), "origine": "arricchito_SAM3_person_car" if f in enriched else "regolare"} for f in sorted(C)]
json.dump({"sessione": SESS, "unita": "asmile-001", "calib": "PROVVISORIA, punto A in corso", "uso": "TEST C alla cieca v3 (mai usato per sviluppo)",
           "criterio": __doc__, "n_candidati": len(cand), "n_arricchiti": len(enriched), "frames": rows}, open(os.path.join(HERE, "out_20261110/frames_ostacoli_C.json"), "w"), indent=1)
print(len(C), "arricchiti", len(enriched)); print(sorted(C))
