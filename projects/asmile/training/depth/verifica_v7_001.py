#!/usr/bin/env python3
"""verifica_v7_001.py — confronto prima/dopo del giro 7 (12/11/2026) con la traiettoria REALE ricostruita (encoder ruota + giroscopio gz, integrati nel tempo)
e oggetti considerati FERMI (posizione mondo = mediana sulla vita della traccia, retrospettiva). Regole fissate prima:
 - verita' 'in percorso reale': distanza minima dell'oggetto dai punti reali percorsi dalla bici da t fino a s(t)+Z+2 m <= 1.5 m; tracce con >=6 fotogrammi di vita, non declassate/sospette;
 - verita' primo ostacolo <5 m = oggetto vero piu' vicino in percorso reale con Z<5;
 - ritardo = corsa piu' lunga di fotogrammi consecutivi con verita' <5 m presente e primo ostacolo del sistema (corridoio) assente o >=5 m.
Uso: verifica_v7_001.py DIR_TRACKS [SESSIONE]"""
import sys, os, pickle, json, numpy as np
from ego_001 import Ego
d = sys.argv[1]; sess = sys.argv[2] if len(sys.argv) > 2 else "20261109_094146"
T = pickle.load(open(os.path.join(d, f"tracks_{sess}.pkl"), "rb")); ego = Ego("session_" + sess)
t = np.array(T["t_ms"]); n = len(t)
# traiettoria reale su griglia ego
psi = np.concatenate([[0], np.cumsum(np.radians(0.5 * (ego.yaw_s[1:] + ego.yaw_s[:-1])) * np.diff(ego.t) / 1000)])
vv = ego.v_s; pe = np.concatenate([[0], np.cumsum(0.5 * (vv[1:] + vv[:-1]) * np.diff(ego.t) / 1000)])
pn = np.concatenate([[0], np.cumsum(np.cos(psi[:-1]) * 0.5 * (vv[1:] + vv[:-1]) * np.diff(ego.t) / 1000)])
pe = np.concatenate([[0], np.cumsum(np.sin(psi[:-1]) * 0.5 * (vv[1:] + vv[:-1]) * np.diff(ego.t) / 1000)])
sarc = ego.s - ego.s[0]
I = lambda a, x: np.interp(x, ego.t, a)
# posizione mondo di ogni traccia (mediana)
W = {}
for i, rows in enumerate(T["per"]):
    for r in rows:
        if r["coast"]: continue
        ps, e0, n0 = I(psi, t[i]), I(pe, t[i]), I(pn, t[i]); Z = r["Z"]; X = r["tan"] * Z
        W.setdefault(r["id"], []).append((e0 + Z * np.sin(ps) + X * np.cos(ps), n0 + Z * np.cos(ps) - X * np.sin(ps)))
life = {k: len(v) for k, v in W.items()}; Wm = {k: np.median(np.array(v), 0) for k, v in W.items()}
def dpath(k, i):
    s0 = I(sarc, t[i]); Z = None
    msk = (ego.t >= t[i]) & (sarc <= s0 + 80)
    return None
truth = []; missrun = 0; best = 0; runs = []
veh_out = []; first_Z = []
for i, rows in enumerate(T["per"]):
    s0 = I(sarc, t[i]); idx = np.nonzero((ego.t >= t[i] - 200))[0]
    best_o = None
    for r in rows:
        if r["coast"] or r["decl"] or r["sosp"] or life[r["id"]] < 6 or r["Z"] > 25: continue
        Z = r["Z"]; m = (ego.t >= t[i]) & (sarc <= s0 + Z + 2.0)
        if m.sum() < 2: continue
        dm = np.hypot(pe[m] - Wm[r["id"]][0], pn[m] - Wm[r["id"]][1]).min()
        r["dreal"] = dm
        if dm <= 1.5 and (best_o is None or Z < best_o["Z"]): best_o = r
        if dm <= 1.5 and r["fam"] == "veicolo" and not r["in_arc"] and Z < 25: veh_out.append((i, r["id"], round(Z, 1), round(dm, 2)))
    truth.append(best_o)
fz = T["cs"]; sysfirst = [c["firstZ"]["arc"] for c in fz]
cur = 0; runs = []; start = None
for i in range(n):
    tr = truth[i]
    if tr is not None and tr["Z"] < 5 and (sysfirst[i] is None or sysfirst[i] >= 5):
        if start is None: start = i
    else:
        if start is not None: runs.append((start, i - start)); start = None
if start is not None: runs.append((start, n - start))
runs.sort(key=lambda x: -x[1])
fr = np.array([tr is not None and tr["Z"] < 5 for tr in truth]); nsys = int(sum(1 for i in range(n) if fr[i] and (sysfirst[i] is None or sysfirst[i] >= 5)))
tf = {k: 0 for k in ("vehicle", "tot")}
vids = {}
for (i, k, z, dm) in veh_out: vids.setdefault(k, []).append(i)
# Kalman: Z_filtrata - Z_grezza > 0.7 sotto 8 m
gap = [(r["Zf"] if "Zf" in r else r["Z"]) - r["Zraw"] for rows in T["per"] for r in rows if not r["coast"] and r["Zraw"] < 8 and r["Z"] < 8]
usegap = [r["Z"] - r["Zraw"] for rows in T["per"] for r in rows if not r["coast"] and r["Zraw"] < 8 and r["Z"] < 8]
gapn = int(sum(g > 0.7 for g in gap)); usen = int(sum(g > 0.7 for g in usegap))
# primo ostacolo con classe/senza
fam_first = {}
for i, c in enumerate(T["cs"]):
    fid = c["first"]["arc"]
    if fid is None: continue
    r = next((q for q in T["per"][i] if q["id"] == fid), None)
    if r: fam_first[r["fam"]] = fam_first.get(r["fam"], 0) + 1
out = dict(sess=sess, n=n, fotogrammi_verita_sotto5=int(fr.sum()), fotogrammi_sistema_manca=nsys, corsa_max_fr=runs[0][1] if runs else 0, corsa_max_s=round((runs[0][1] / 15), 2) if runs else 0,
           corse_top=[(int(a), int(b)) for a, b in runs[:5]], veicoli_vicini_traiett_fuori_corridoio_fotogrammi=len(veh_out), veicoli_id=sorted(vids), veicoli_fotogrammi_per_id={str(k): (min(v), max(v), len(v)) for k, v in vids.items()},
           kalman_gap_gt07_sotto8=gapn, kalman_gap_dopo_uso=usen, righe_sotto8=len(gap), primo_per_famiglia=fam_first,
           fotogrammi_con_primo=int(sum(z is not None for z in sysfirst)), fotogrammi_primo_sotto5=int(sum(z is not None and z < 5 for z in sysfirst)))
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(d, f"verifica_{sess}.json"), "w"), indent=1)
