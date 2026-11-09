#!/usr/bin/env python3
"""analisi_movimento_v2_001.py — odometria SENZA filtro su Z (risposta al veto 1/3 di asmile-occhio).
Tracce solo per IoU (>= --iou) e stessa classe fra passate consecutive (gap max 2 passate), nessun uso di Z ne' dell'encoder
per associare. Oggetti COMPATTI (palo, bollard, cestino, cono). Per traccia: pendenza libera ΔZ_stereo/ΔS (Theil-Sen e OLS)
con S = metri encoder ruota; atteso = cos(pitch 7.4) = 0.992 (componente lungo l'asse ottico). Residuo = rms di Z - retta (m).
Uso: python3 analisi_movimento_v2_001.py objects.csv [--iou 0.4] [--zmax 12] [--min-span 3] [--dump]"""
import argparse, csv, os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analisi_movimento_001 import load_S, iou
C = np.cos(np.radians(7.4))
COMPACT = {"pole", "bollard", "trash can", "traffic cone"}

def theil_sen(x, y):
    sl = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x)) for j in range(i + 1, len(x)) if abs(x[j] - x[i]) > 0.3]
    return float(np.median(sl)) if sl else float('nan')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--iou", type=float, default=0.4)
    ap.add_argument("--zmax", type=float, default=12.0); ap.add_argument("--min-span", type=float, default=3.0)
    ap.add_argument("--min-n", type=int, default=4); ap.add_argument("--classes", default=",".join(COMPACT))
    ap.add_argument("--dump", action="store_true"); ap.add_argument("--out")
    a = ap.parse_args(); cls = set(a.classes.split(","))
    rows = []
    for r in csv.DictReader(open(a.csv)):
        if not r["Z_m"] or float(r["conf"]) < 0.5 or int(r["n_valid"]) < 100 or r["classe"] not in cls: continue
        Z = float(r["Z_m"])
        if Z > a.zmax: continue
        rows.append(dict(frame=int(r["frame"]), t=int(r["t_ms"]), classe=r["classe"], Z=Z, u=float(r["u_c"]),
                         box=[float(r[k]) for k in ("x1", "y1", "x2", "y2")]))
    Sf = load_S(min(r["t"] for r in rows), max(r["t"] for r in rows))
    for r in rows: r["S"] = float(Sf(r["t"]))
    passes = sorted({r["frame"] for r in rows}); step = min(b - a_ for a_, b in zip(passes, passes[1:]) if b > a_)
    by = {p: [r for r in rows if r["frame"] == p] for p in passes}
    tracks, live = [], []
    for p in passes:
        used = set()
        for tr in list(live):
            if p - tr[-1]["frame"] > 2 * step: live.remove(tr); continue
            best, bs = None, 0
            for k, r in enumerate(by[p]):
                if k in used or r["classe"] != tr[0]["classe"]: continue
                s = iou(tr[-1]["box"], r["box"])
                if s > bs and s >= a.iou: best, bs = k, s
            if best is not None: used.add(best); tr.append(by[p][best])
        for k, r in enumerate(by[p]):
            if k not in used: nt = [r]; tracks.append(nt); live.append(nt)
    out = []
    for tr in tracks:
        S = np.array([r["S"] for r in tr]); Z = np.array([r["Z"] for r in tr])
        span = S.max() - S.min()
        if len(tr) < a.min_n or span < a.min_span: continue
        ols = np.polyfit(S, Z, 1); res = Z - np.polyval(ols, S)
        ts = theil_sen(S, Z)
        out.append(dict(classe=tr[0]["classe"], f0=tr[0]["frame"], f1=tr[-1]["frame"], n=len(tr), span=round(float(span), 1),
                        Z0=round(float(Z[0]), 1), Z1=round(float(Z[-1]), 1), slope_ols=round(float(-ols[0]), 2),
                        slope_ts=round(-ts, 2), rms_m=round(float(np.sqrt(np.mean(res ** 2))), 2),
                        u_med=round(float(np.median([r["u"] for r in tr]))),
                        pts=[(r["frame"], round(r["Z"], 2), round(r["S"], 2), round(r["u"])) for r in tr]))
    print(f"tracce compatte (IoU>={a.iou}, Z<={a.zmax}, n>={a.min_n}, span>={a.min_span} m): {len(out)}  atteso pendenza {C:.3f}")
    for t in out:
        print(f"{t['classe']:12s} f{t['f0']}-{t['f1']} n={t['n']:3d} S={t['span']:5.1f} m Z {t['Z0']}->{t['Z1']}  pendenza OLS {t['slope_ols']:+.2f} TS {t['slope_ts']:+.2f}  rms {t['rms_m']} m  u~{t['u_med']}")
        if a.dump: print("   ", [(p[1], p[2]) for p in t['pts']][:40])
    if a.out: json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__": main()
