#!/usr/bin/env python3
"""giri_report_001.py — numeri per il rapporto dei giri 13/11 di #001 (uscite in out_20261113_giri). Stampa e salva giri_stats.json."""
import os, sys, json, csv, pickle, glob, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); O = os.path.join(HERE, "out_20261113_giri")
R = {}
def rd(p): return list(csv.DictReader(open(p)))
S = {"150337": "session_20261113_150337", "151400": "session_20261113_151400"}
# 1) 1 Hz: depth per campione + luma
for k, s in S.items():
    fr = rd(os.path.join(O, "d1hz", s, "frames.csv")); cs = rd(os.path.join(O, f"controsole_20261113_{k}.csv"))
    ct = np.array([float(r["t_ms"]) for r in cs]); luma = np.array([float(r["luma"]) for r in cs]); sat = np.array([float(r["sat_alto_pct"]) for r in cs])
    vf = np.array([float(r["valid_frac_basso"]) for r in fr]); tm = np.array([float(r["t_ms"]) for r in fr])
    ix = np.abs(ct[None, :] - tm[:, None]).argmin(1); L = luma[ix]; SA = sat[ix]
    pz = [float(r["primo_corridoio_m"]) if r["primo_corridoio_m"] else None for r in fr]
    d = dict(n=len(fr), valid_med=float(np.median(vf)), con_primo=sum(p is not None for p in pz))
    for nm, m in (("normale_luma<120", L < 120), ("media_120-150", (L >= 120) & (L < 150)), ("controsole_luma>=150", L >= 150), ("sat_alto>=30%", SA >= 30)):
        d[nm] = dict(n=int(m.sum()), valid_med=float(np.median(vf[m])) if m.sum() else None, valid_p10=float(np.percentile(vf[m], 10)) if m.sum() else None)
    pzz = np.array([p for p in pz if p is not None]); d["primo_m"] = {"<2": int((pzz < 2).sum()), "2-5": int(((pzz >= 2) & (pzz < 5)).sum()), "5-10": int(((pzz >= 5) & (pzz < 10)).sum()), ">=10": int((pzz >= 10).sum())}
    d["summary"] = json.load(open(os.path.join(O, "d1hz", s, "summary.json")))
    R["1hz_" + k] = d
    ob = rd(os.path.join(O, "d1hz", s, "objects.csv")); R["1hz_" + k]["oggetti"] = dict(collections.Counter(r["classe"] for r in ob).most_common(12))
# 2) tratti 15 fps
for nm in ("frenata1", "frenata2_monovolume", "controsole_a", "controsole_b", "controsole_c"):
    p = glob.glob(os.path.join(O, f"video_{nm}", "tracks_*.pkl"))
    if not p: continue
    d = pickle.load(open(p[0], "rb")); sid = os.path.basename(p[0])[7:-4]
    cs = d["cs"]; acts = collections.Counter((c["act"]["act"] if c["act"] and c["act"]["act"] else "nessuna") for c in cs)
    alm = collections.Counter(c["bord"]["alarm"]["side"] for c in cs if c["bord"] and c["bord"]["alarm"])
    fz = np.array([c["firstZ"]["arc"] for c in cs if c["firstZ"]["arc"] is not None])
    z = np.load(glob.glob(os.path.join(O, f"A_{nm}", "session_*_A", "zmap.npz"))[0])
    vv = np.array([float((z[k][100:190, 50:270] != 255).mean()) for k in z.files])
    r = dict(sess=sid, n=len(cs), acts=dict(acts), allarmi_bordo=dict(alm), primo_arc_min=float(fz.min()) if len(fz) else None, primo_arc_n=int(len(fz)),
             valid_zmap_med=float(np.median(vv)), valid_zmap_p10=float(np.percentile(vv, 10)), valid_zmap_p90=float(np.percentile(vv, 90)), frames=[d["frames"][0], d["frames"][-1]])
    # luma per frame
    cc = rd(os.path.join(O, f"controsole_20261113_{sid[-6:]}.csv")); ct = np.array([float(x["t_ms"]) for x in cc]); lu = np.array([float(x["luma"]) for x in cc])
    tm = np.array(d["t_ms"], float); L = lu[np.abs(ct[None, :] - tm[:, None]).argmin(1)]
    fk = [int(k[1:]) for k in z.files]; r["luma_med"] = float(np.median(L)); r["frac_luma>=150"] = float((L >= 150).mean())
    ok = np.array([c["firstZ"]["arc"] is not None for c in cs])
    r["valid_zmap_luma>=150"] = float(np.median(vv[L[:len(vv)] >= 150])) if (L[:len(vv)] >= 150).sum() else None
    r["valid_zmap_luma<150"] = float(np.median(vv[L[:len(vv)] < 150])) if (L[:len(vv)] < 150).sum() else None
    R[nm] = r
    # SAM
    idx = os.path.join(HERE, "..", "..", "asmile-loggers", "_seg_sam3", "session_20261113_" + sid[-6:] + "_001_fluido", "index.jsonl")
    f0, f1 = r["frames"]; nd, cl = [], collections.Counter()
    for l in open(idx):
        try: q = json.loads(l)
        except Exception: continue
        if f0 <= q["frame"] <= f1:
            nd.append(q["n_det"]); cl.update(x["class_final"] for x in q["detections"] if x["tier"] != "unknown")
    r["sam_det_medio"] = float(np.mean(nd)); r["sam_classi"] = dict(cl.most_common(10)); r["sam_n"] = len(nd)
# SAM 1 Hz
for k, s in S.items():
    idx = os.path.join(HERE, "..", "..", "asmile-loggers", "_seg_sam3", s + "_001", "index.jsonl"); nd = []; cl = collections.Counter()
    for l in open(idx):
        q = json.loads(l); nd.append(q["n_det"]); cl.update(x["class_final"] for x in q["detections"] if x["tier"] != "unknown")
    R["sam1hz_" + k] = dict(n=len(nd), det_medio=float(np.mean(nd)), classi=dict(cl.most_common(12)))
json.dump(R, open(os.path.join(O, "giri_stats.json"), "w"), indent=1); print(json.dumps(R, indent=1))
