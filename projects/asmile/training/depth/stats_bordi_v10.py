#!/usr/bin/env python3
"""stats_bordi_v10.py — conteggi allarmi bordo / blob 'bordo' da tracks_*.pkl di v10 (sola lettura). Uso: stats_bordi_v10.py DIR SESS"""
import sys, pickle, os, numpy as np
T = pickle.load(open(os.path.join(sys.argv[1], f"tracks_{sys.argv[2]}.pkl"), "rb")); cs = T["cs"]; n = len(cs)
al = [c["bord"]["alarm"] if c["bord"] else None for c in cs]; na = sum(a is not None for a in al)
first_b = 0
for i, c in enumerate(cs):
    fid = c["first"]["arc"]
    if fid is not None and fid < 0: first_b += 1
runs = []; st = None
for i, a in enumerate(al):
    if a is not None and st is None: st = i
    if a is None and st is not None: runs.append((st, i - 1)); st = None
if st is not None: runs.append((st, n - 1))
nb = sum(1 for rows in T["per"] for r in rows if r.get("bordo") and not r["coast"])
print("fotogrammi", n, "con allarme", na, "primo=bordo", first_b, "episodi", len(runs), "righe blob bordo", nb, "con stuff", sum(1 for c in cs if c["bord"] and c["bord"]["lab"]))
print("kind:", {k: sum(1 for a in al if a and a["kind"] == k) for k in ("bordo", "muro davanti")}, "lato:", {k: sum(1 for a in al if a and a["side"] == k) for k in ("sx", "dx")})
print("episodi (frame inizio-fine, durata fr):", [(T["frames"][a], T["frames"][b], b - a + 1) for a, b in runs][:80])
