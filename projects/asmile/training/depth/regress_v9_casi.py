#!/usr/bin/env python3
"""regress_v9_casi.py — regressione (solo lettura) sui casi fissi del critico, v7/v8/v9.
Uso: regress_v9_casi.py CASI_V7.json CASI_V8.json DIR_V7 DIR_V8 DIR_V9"""
import sys, json, pickle, os
c7 = json.load(open(sys.argv[1]))["casi"]; c8 = json.load(open(sys.argv[2]))["casi"]
T = {nm: pickle.load(open(os.path.join(d, "tracks_20261109_094146.pkl"), "rb")) for nm, d in (("v7", sys.argv[3]), ("v8", sys.argv[4]), ("v9", sys.argv[5]))}
def first(t, f):
    i = t["frames"].index(f); fid = t["cs"][i]["first"]["arc"]
    return None if fid is None else next(q for q in t["per"][i] if q["id"] == fid)
def brief(r): return None if r is None else (r["fam"], round(r["Z"], 2), r["coast"], round(r["inside"], 2))
falsi = [c["frame"] for c in c7 if "vero" not in (c.get("atteso") or "") and isinstance(c["frame"], int) and c["frame"] in T["v9"]["frames"]]
veri = [c["frame"] for c in c7 if "vero" in (c.get("atteso") or "") and isinstance(c["frame"], int)]
print("campione v7 critico: falsi", len(falsi), "veri", len(veri))
out = {}
for nm, t in T.items():
    ff = [f for f in falsi if (first(t, f) is not None)]; ff5 = [f for f in falsi if (first(t, f) is not None and first(t, f)["Z"] < 5)]
    vv = [f for f in veri if first(t, f) is not None]
    print(nm, "falsi con primo ostacolo", len(ff), "(<5 m:", len(ff5), ")", ff5, "| veri con primo ostacolo", len(vv), "/", len(veri))
    out[nm] = dict(falsi_primo=len(ff), falsi_primo_sotto5=len(ff5), lista_sotto5=ff5, veri_primo=len(vv), veri_tot=len(veri))
print("--- casi v8 critico")
def rng(f): return range(f[0], f[1] + 1) if isinstance(f, list) and len(f) == 2 and f[1] - f[0] > 1 and f[1] - f[0] < 40 else (f if isinstance(f, list) else [f])
for c in c8:
    if "frame" not in c: continue
    fs = [x for x in rng(c["frame"]) if x in T["v9"]["frames"]]
    print(c["frame"], "|", (c.get("atteso") or "")[:60])
    for nm in ("v8", "v9"):
        print("   ", nm, [(f, brief(first(T[nm], f))) for f in fs][:14])
# fuori immagine
for nm in ("v8", "v9"):
    n = 0
    for i, c in enumerate(T[nm]["cs"]):
        fid = c["first"]["arc"]
        if fid is not None:
            r = next(q for q in T[nm]["per"][i] if q["id"] == fid)
            if r["inside"] < 0.5: n += 1
    print(nm, "primo ostacolo con box <50% dentro:", n)
# paletti
for tid in (854, 1384, 1427):
    rows = [(i, r) for i, rr in enumerate(T["v9"]["per"]) for r in rr if r["id"] == tid]
    print("paletto", tid, "righe", len(rows), "escl", sum(1 for _, r in rows if r.get("escl")), "cand", sum(1 for _, r in rows if r["cand"]), "primo", sum(1 for i, r in rows if T["v9"]["cs"][i]["first"]["arc"] == tid), "fam", set(r["fam"] for _, r in rows))
json.dump(out, open(os.path.join(sys.argv[5], "regress_v9.json"), "w"), indent=1)
