#!/usr/bin/env python3
"""regress_v8_casi.py — regressione FINALE sui casi fissi del critico (SOLO lettura, mai per tarare): per ogni fotogramma, primo ostacolo scritto in v7 e in v8.
Uso: regress_v8_casi.py CASI.json DIR_V7 DIR_V8"""
import sys, json, pickle, os
casi = json.load(open(sys.argv[1]))["casi"]; T = {}
for nm, d in (("v7", sys.argv[2]), ("v8", sys.argv[3])): T[nm] = pickle.load(open(os.path.join(d, "tracks_20261109_094146.pkl"), "rb"))
res = []
for c in casi:
    f = c["frame"]; row = dict(frame=f, atteso=c.get("atteso", c.get("nota")))
    for nm, t in T.items():
        i = t["frames"].index(f); fid = t["cs"][i]["first"]["arc"]
        r = None if fid is None else next(q for q in t["per"][i] if q["id"] == fid)
        row[nm] = None if r is None else dict(fam=r["fam"], Z=round(r["Z"], 2), box=r["box"], coast=r["coast"])
    res.append(row)
vero = [r for r in res if "vero" in (r["atteso"] or "")]; falsi = [r for r in res if "vero" not in (r["atteso"] or "")]
for nm in ("v7", "v8"):
    nf = sum(1 for r in falsi if r[nm] is not None); nv = sum(1 for r in vero if r[nm] is not None)
    print(f"{nm}: falsi con banner {nf}/{len(falsi)}; veri con banner {nv}/{len(vero)}")
json.dump(res, open(os.path.join(sys.argv[3], "regress_casi.json"), "w"), indent=1)
for r in res: print(r["frame"], (r["atteso"] or "")[:28], "| v7", r["v7"], "| v8", r["v8"])
