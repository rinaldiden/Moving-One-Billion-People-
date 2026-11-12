#!/usr/bin/env python3
"""regress_v10_casi.py — regressione (sola lettura) sui casi fissi del critico: v7/v8/v9/v10. 'bordo' = primo ostacolo sintetico dell'allarme bordo (id<0), contato a parte.
Uso: regress_v10_casi.py CASI_V7.json CASI_V8.json DIR_V7 DIR_V8 DIR_V9 DIR_V10"""
import sys, json, pickle, os
c7 = json.load(open(sys.argv[1]))["casi"]; c8 = json.load(open(sys.argv[2]))["casi"]
T = {nm: pickle.load(open(os.path.join(d, "tracks_20261109_094146.pkl"), "rb")) for nm, d in (("v7", sys.argv[3]), ("v8", sys.argv[4]), ("v9", sys.argv[5]), ("v10", sys.argv[6]))}
def first(t, f):
    i = t["frames"].index(f); fid = t["cs"][i]["first"]["arc"]
    return None if fid is None else next(q for q in t["per"][i] if q["id"] == fid)
def brief(r): return None if r is None else (r["fam"], round(float(r["Z"]), 2), r["coast"], round(r["inside"], 2))
falsi = [c["frame"] for c in c7 if "vero" not in (c.get("atteso") or "") and isinstance(c["frame"], int) and c["frame"] in T["v10"]["frames"]]
veri = [c["frame"] for c in c7 if "vero" in (c.get("atteso") or "") and isinstance(c["frame"], int)]
print("campione v7 critico: falsi", len(falsi), "veri", len(veri)); out = {}
for nm, t in T.items():
    ff5 = [f for f in falsi if (first(t, f) is not None and first(t, f)["Z"] < 5 and first(t, f)["fam"] != "bordo")]
    fb = [f for f in falsi if (first(t, f) is not None and first(t, f)["fam"] == "bordo")]
    vv = [f for f in veri if first(t, f) is not None]
    print(nm, "falsi con primo ostacolo <5 m (esclusi bordo):", len(ff5), ff5, "| falsi col primo = ALLARME BORDO:", len(fb), fb, "| veri con primo", len(vv), "/", len(veri))
    out[nm] = dict(falsi_sotto5=len(ff5), lista=ff5, falsi_bordo=len(fb), lista_bordo=fb, veri=len(vv), veri_tot=len(veri))
print("--- casi v8 critico")
def rng(f): return range(f[0], f[1] + 1) if isinstance(f, list) and len(f) == 2 and 1 < f[1] - f[0] < 40 else (f if isinstance(f, list) else [f])
for c in c8:
    if "frame" not in c: continue
    fs = [x for x in rng(c["frame"]) if x in T["v10"]["frames"]]; print(c["frame"], "|", (c.get("atteso") or "")[:70])
    for nm in ("v9", "v10"): print("   ", nm, [(f, brief(first(T[nm], f))) for f in fs][:14])
for nm in ("v9", "v10"):
    n = 0
    for i, c in enumerate(T[nm]["cs"]):
        fid = c["first"]["arc"]
        if fid is not None and next(q for q in T[nm]["per"][i] if q["id"] == fid)["inside"] < 0.5: n += 1
    print(nm, "primo ostacolo con box <50% dentro:", n)
for tid in (854, 1384, 1427):
    rows = [(i, r) for i, rr in enumerate(T["v10"]["per"]) for r in rr if r["id"] == tid]
    print("paletto", tid, "righe", len(rows), "escl", sum(1 for _, r in rows if r.get("escl")), "bordo", sum(1 for _, r in rows if r.get("bordo")), "cand", sum(1 for _, r in rows if r["cand"]), "primo", sum(1 for i, r in rows if T["v10"]["cs"][i]["first"]["arc"] == tid))
json.dump(out, open(os.path.join(sys.argv[6], "regress_v10.json"), "w"), indent=1)
