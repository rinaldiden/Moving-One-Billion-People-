#!/usr/bin/env python3
"""regress_v5_v6.py — le regole di distanza sono rimaste quelle di v5? Confronta gli oggetti di v5 (out_20261112_v5/<sess>_f/objects.csv, campionati 1/s) con quelli
di depth_fluido_a_001.py sugli stessi fotogrammi: stesso src, IoU box>0.7 -> rapporto Z_picco v6/v5. Uso: regress_v5_v6.py 20261109_094146 [...]"""
import os, sys, csv, json, pickle
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)
out = []
for sid in sys.argv[1:]:
    sess = "session_" + sid
    A = {f["frame"]: f for f in pickle.load(open(os.path.join(HERE, "out_20261112_v6", sess + "_A", "frames.pkl"), "rb"))}
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, "out_20261112_v5", sess + "_f", "objects.csv"))) if int(r["frame"]) in A]
    n = m = 0; ratios = []; nomatch = []; fr5 = set()
    for r in rows:
        fr5.add(int(r["frame"])); n += 1; b5 = [int(x) for x in r["box"].split()]
        c = [(iou(b5, o["box"]), o) for o in A[int(r["frame"])]["objs"] if o["src"] == r["src"]]
        best = max(c, key=lambda t: t[0], default=(0, None))
        if best[0] > 0.7: m += 1; ratios.append(best[1]["Z_picco"] / float(r["Z_picco"]))
        else: nomatch.append((int(r["frame"]), r["src"], r["classe"], float(r["Z_picco"])))
    ratios = np.array(ratios)
    # oggetti v6 corridoio-dritta (non ext) senza corrispondente in v5
    extra = 0; nv6 = 0
    for f in fr5:
        v5 = [(r["src"], [int(x) for x in r["box"].split()]) for r in rows if int(r["frame"]) == f]
        for o in A[f]["objs"]:
            nv6 += 1
            if not any(s == o["src"] and iou(b, o["box"]) > 0.7 for s, b in v5): extra += 1
    out.append(dict(sess=sess, frame_confrontati=len(fr5), oggetti_v5=n, ritrovati_iou07=m, Z_ratio_mediana=round(float(np.median(ratios)), 4), Z_ratio_p5_p95=[round(float(np.percentile(ratios, 5)), 3), round(float(np.percentile(ratios, 95)), 3)],
                    frac_Z_entro_1pct=round(float(np.mean(np.abs(ratios - 1) < 0.01)), 3), frac_Z_entro_5pct=round(float(np.mean(np.abs(ratios - 1) < 0.05)), 3), oggetti_v6=nv6, oggetti_v6_senza_v5=extra, non_ritrovati_esempi=nomatch[:8]))
print(json.dumps(out, indent=1)); json.dump(out, open(os.path.join(HERE, "out_20261112_v6", "regress_v5_v6.json"), "w"), indent=1)
