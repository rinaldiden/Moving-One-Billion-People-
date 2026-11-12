#!/usr/bin/env python3
"""stats_fluido_001.py — numeri del video fluido v6 da tracks_<sess>.pkl (prodotto da video_fluido_001.py). Uso: stats_fluido_001.py 20261109_094146 [...]"""
import os, sys, json, pickle
import numpy as np
from collections import defaultdict, Counter
import depth_seg_001 as D
from ego_001 import Ego
OUT = os.path.join(D.HERE, "out_20261112_v6")


def pct(x, q): return None if len(x) == 0 else round(float(np.percentile(x, q)), 3)


def stats(sid):
    sess = "session_" + sid; T = pickle.load(open(os.path.join(OUT, f"tracks_{sid}.pkl"), "rb")); ego = Ego(sess)
    per, cs, fr, tm = T["per"], T["cs"], T["frames"], T["t_ms"]
    tr = defaultdict(list)
    for n, rows in enumerate(per):
        for r in rows:
            if not r.get("coast"): tr[r["id"]].append((n, r))
    life = np.array([len(v) for v in tr.values()])
    S = dict(sess=sess, n_frames=len(fr), durata_s=round((tm[-1] - tm[0]) / 1000, 1), n_tracce_confermate=len(tr), vita_mediana_frame=float(np.median(life)), vita_p90=float(np.percentile(life, 90)),
             tracce_ge_2s=int((life >= 30).sum()))
    # salti: residuo dopo aver tolto il moto proprio (oggetti statici: dZ = -v dt)
    res_raw, res_f, jr, jf = [], [], [], []
    for i, v in tr.items():
        for (n0, a), (n1, b) in zip(v, v[1:]):
            if n1 != n0 + 1: continue
            dt = (tm[n1] - tm[n0]) / 1000; vv = float(ego.at(tm[n1], "v_s"))
            if a["fam"] in ("paletto-palo", "barriera-cancello", "ostacolo") and a["Z"] < 25:
                res_raw.append(b["Zraw"] - a["Zraw"] + vv * dt); res_f.append(b["Z"] - a["Z"] + vv * dt)
            if a["Z"] < 25: jr.append(abs(b["Zraw"] - a["Zraw"])); jf.append(abs(b["Z"] - a["Z"]))
    S["residuo_statici_vs_encoder_m_per_frame"] = dict(n=len(res_raw), std_raw=round(float(np.std(res_raw)), 3), std_filtrato=round(float(np.std(res_f)), 3), p95_abs_raw=pct(np.abs(res_raw), 95), p95_abs_filtrato=pct(np.abs(res_f), 95))
    S["salto_frame_su_frame_Z<25"] = dict(n=len(jr), raw_mediana=pct(jr, 50), raw_p95=pct(jr, 95), raw_frac_gt_0p5m=round(float(np.mean(np.array(jr) > 0.5)), 4), filt_mediana=pct(jf, 50), filt_p95=pct(jf, 95), filt_frac_gt_0p5m=round(float(np.mean(np.array(jf) > 0.5)), 4))
    # pendenza -dZ/ds su tracce statiche >=2 s
    sl_r, sl_f = [], []
    for i, v in tr.items():
        if len(v) < 30 or v[0][1]["fam"] not in ("paletto-palo", "barriera-cancello", "ostacolo"): continue
        s = np.array([float(ego.at(tm[n], "s")) for n, _ in v])
        if s[-1] - s[0] < 3.0: continue
        sl_r.append(-np.polyfit(s, [r["Zraw"] for _, r in v], 1)[0]); sl_f.append(-np.polyfit(s, [r["Z"] for _, r in v], 1)[0])
    S["pendenza_-dZ/ds_statici"] = dict(n=len(sl_r), raw_mediana=pct(sl_r, 50), filtrato_mediana=pct(sl_f, 50), nota="attesa 1.0 (oggetto fermo, Z scende come la strada percorsa)")
    # corridoio
    k = np.array([c["k"] for c in cs]); curva = np.abs(k) > 0.03
    fa = [c["first"]["arc"] for c in cs]; fs = [c["first"]["str"] for c in cs]; za = [c["firstZ"]["arc"] for c in cs]; zs = [c["firstZ"]["str"] for c in cs]
    diff = [(a != b) for a, b in zip(fa, fs)]
    S["curvatura"] = dict(frame_k_abs_gt_0p03=int(curva.sum()), frame_k_abs_gt_0p01=int((np.abs(k) > 0.01).sum()), k_min=round(float(k.min()), 3), k_max=round(float(k.max()), 3))
    S["primo_ostacolo"] = dict(frame_con_arco=sum(x is not None for x in fa), frame_con_dritta=sum(x is not None for x in fs), frame_diversi=int(sum(diff)),
                               frame_diversi_in_curva=int(sum(d and c for d, c in zip(diff, curva))), frame_arco_libero_dritta_occupata=int(sum(a is None and b is not None for a, b in zip(fa, fs))),
                               frame_dritta_libera_arco_occupata=int(sum(a is not None and b is None for a, b in zip(fa, fs))))
    # cambi di id del primo ostacolo
    S["primo_ostacolo"]["cambi_id_arco"] = int(sum(1 for a, b in zip(fa, fa[1:]) if a != b)); S["primo_ostacolo"]["cambi_id_dritta"] = int(sum(1 for a, b in zip(fs, fs[1:]) if a != b))
    # chi era 'primo' per la banda dritta ma non e' nell'arco
    cnt_fr = Counter(); ids = defaultdict(set)
    byid = {n: {r["id"]: r for r in rows} for n, rows in enumerate(per)}
    for n, (a, b) in enumerate(zip(fa, fs)):
        if b is not None and b != a:
            r = byid[n][b]
            if not r["in_arc"]:
                key = "senza_classe(blob)" if r["src"] == "blob" else r["fam"]; cnt_fr[key] += 1; ids[key].add(b)
    S["escono_dal_ruolo_primo_per_arco"] = dict(frame=dict(cnt_fr), tracce_distinte={k_: len(v) for k_, v in ids.items()})
    cnt2 = Counter(); ids2 = defaultdict(set)
    for n, (a, b) in enumerate(zip(fa, fs)):
        if a is not None and a != b:
            r = byid[n][a]
            if not r["in_str"]:
                key = "senza_classe(blob)" if r["src"] == "blob" else r["fam"]; cnt2[key] += 1; ids2[key].add(a)
    S["entrano_come_primo_per_arco"] = dict(frame=dict(cnt2), tracce_distinte={k_: len(v) for k_, v in ids2.items()})
    # variazione di Z del primo ostacolo
    both = [(a, b) for a, b in zip(za, zs) if a is not None and b is not None]
    S["Z_primo_arco_vs_dritta_mediana_diff_m"] = None if not both else round(float(np.median([a - b for a, b in both])), 3)
    dz = [abs(b - a) for a, b in zip(za, za[1:]) if a is not None and b is not None]
    S["salti_Z_banner_primo_p95_m_per_frame"] = pct(dz, 95)
    return S


if __name__ == "__main__":
    allS = [stats(s) for s in sys.argv[1:]]
    json.dump(allS, open(os.path.join(OUT, "stats_fluido.json"), "w"), indent=1); print(json.dumps(allS, indent=1))
