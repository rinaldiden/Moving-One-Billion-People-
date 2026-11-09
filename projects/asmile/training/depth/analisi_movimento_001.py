#!/usr/bin/env python3
"""
analisi_movimento_001.py — gate L1.depth_moto su #001: coerenza della distanza stereo con l'ODOMETRIA (encoder ruota).
Oggetti FERMI (pali, cartelli, cestini, ...) seguiti nel tempo da objects_<tag>.csv di depth_seg_001.py.
Per un oggetto fermo la distanza lungo l'asse ottico cala di c*S, S = metri percorsi (encoder, 2.1219e-5 m/count,
ruota misurata col metro 15.76 m/10 giri), c = cos(pitch 7.4 deg) = 0.992.
Per traccia: Z_i = A - c*S_i, A (1 solo parametro) stimato con peso 1/Z^2 (errori relativi); errore_i = Z_i/(A - c S_i) - 1,
a fascia di Z PREDETTO. In piu' la pendenza libera k (Z = A - k S): k/c-1 = errore di SCALA, indipendente da A.
Uso: python3 training/depth/analisi_movimento_001.py out_20261109/objects_clip.csv [--out json] [--png]
"""
import argparse, csv, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
C = np.cos(np.radians(7.4))
STATIC = {"pole", "bollard", "traffic sign", "stop sign", "traffic light", "trash can", "bench", "barrier", "gate",
          "fence", "traffic cone"}
PARKED = {"car", "van", "truck"}            # fermi solo se la traccia lo conferma (pendenza)
CX = 640.0


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def load_S(t_lo, t_hi):
    import pandas as pd
    LOGS = os.path.join(os.path.dirname(__file__), "..", "..", "asmile-loggers", "asmile-001", "_sensors", "sensors")
    fs = [pd.read_csv(os.path.join(LOGS, f), usecols=["t_ms", "enc_wheel_cum"]) for f in sorted(os.listdir(LOGS))
          if f.startswith("sensors_20261109") and f.endswith(".csv")]
    d = pd.concat(fs).drop_duplicates("t_ms").sort_values("t_ms")
    d = d[(d.t_ms >= t_lo - 5000) & (d.t_ms <= t_hi + 5000)]
    t, s = d.t_ms.values.astype(float), d.enc_wheel_cum.values.astype(float) * 2.1219e-5
    return lambda x: np.interp(x, t, s)


def build_tracks(rows, Sfun, zmax=30.0):
    passes = sorted({r["frame"] for r in rows})
    by = {p: [r for r in rows if r["frame"] == p] for p in passes}
    tracks, live = [], []
    for p in passes:
        used = set()
        for tr in list(live):
            last = tr[-1]
            if p - last["frame"] > 4 * 6:                      # perso per piu' di ~4 passate
                live.remove(tr); continue
            best, bs = None, 0
            for k, r in enumerate(by[p]):
                if k in used or r["classe"] != tr[0]["classe"]:
                    continue
                zp = last["Z"] - C * (r["S"] - last["S"])
                if abs(r["Z"] - zp) > 1.0 + 0.12 * zp:        # coerenza geometrica con la marcia
                    continue
                sc = iou(last["box"], r["box"])
                if sc > bs and sc > 0.15:
                    best, bs = k, sc
            if best is not None:
                used.add(best); tr.append(by[p][best])
        for k, r in enumerate(by[p]):
            if k not in used:
                nt = [r]; tracks.append(nt); live.append(nt)
    return [t for t in tracks if len(t) >= 6]


def fit_track(tr):
    Z = np.array([r["Z"] for r in tr]); S = np.array([r["S"] for r in tr])
    w = 1 / Z ** 2
    A = float(np.sum(w * (Z + C * S)) / np.sum(w))
    pred = A - C * S
    ok = pred > 1.0
    # pendenza libera (pesi 1/Z^2): Z = A' - k S
    X = np.vstack([np.ones_like(S), -S]).T * np.sqrt(w)[:, None]
    coef, *_ = np.linalg.lstsq(X, Z * np.sqrt(w), rcond=None)
    return A, pred, ok, float(coef[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--out"); ap.add_argument("--zmax", type=float, default=30.0)
    a = ap.parse_args()
    rows = []
    for r in csv.DictReader(open(a.csv)):
        if not r["Z_m"] or float(r["conf"]) < 0.5 or int(r["n_valid"]) < 150:
            continue
        Z = float(r["Z_m"])
        if Z > a.zmax or Z < 1.5:
            continue
        rows.append(dict(frame=int(r["frame"]), t=int(r["t_ms"]), classe=r["classe"], Z=Z, u=float(r["u_c"]),
                         box=[float(r[k]) for k in ("x1", "y1", "x2", "y2")]))
    Sf = load_S(min(r["t"] for r in rows), max(r["t"] for r in rows))
    for r in rows:
        r["S"] = float(Sf(r["t"]))
    cand = [r for r in rows if r["classe"] in STATIC | PARKED]
    tracks = build_tracks(cand, Sf, a.zmax)
    res = []
    for tr in tracks:
        A, pred, ok, k = fit_track(tr)
        span = max(r["S"] for r in tr) - min(r["S"] for r in tr)
        zr = (max(r["Z"] for r in tr), min(r["Z"] for r in tr))
        if span < 3.0:                                         # bici quasi ferma: nessuna info
            continue
        e = [(r["Z"] / p - 1) * 100 for r, p in zip(tr, pred)]
        res.append(dict(classe=tr[0]["classe"], n=len(tr), frame0=tr[0]["frame"], frame1=tr[-1]["frame"],
                        Zfar=round(zr[0], 1), Znear=round(zr[1], 1), span_m=round(span, 1),
                        scala_err_pct=round((k / C - 1) * 100, 1), rms_pct=round(float(np.sqrt(np.mean(np.square(e)))), 1),
                        static=bool(abs(k / C - 1) < 0.30 and np.sqrt(np.mean(np.square(e))) < 20),
                        pts=[(r["frame"], round(r["Z"], 2), round(p, 2), round(x, 1), round(r["u"]))
                             for r, p, x in zip(tr, pred, e)]))
    stat = [t for t in res if t["classe"] in STATIC and t["static"]]
    par = [t for t in res if t["classe"] in PARKED and t["static"]]
    print(f"tracce con >=6 detections e span>=3 m: {len(res)}  (fisse da classe: {len([t for t in res if t['classe'] in STATIC])}, "
          f"ferme confermate: pali ecc {len(stat)}, auto/furgoni {len(par)})")

    def bins(trs, name):
        pts = [p for t in trs for p in t["pts"]]
        out = {}
        for lo, hi, tol in ((0, 5, 2), (5, 10, 5), (10, 20, 10), (20, 31, None)):
            e = np.array([p[3] for p in pts if lo <= p[2] < hi])
            if len(e) < 3:
                out[f"{lo}-{hi}"] = None; continue
            out[f"{lo}-{hi}"] = dict(n=int(len(e)), tracce=len({id(t) for t in trs for p in t["pts"] if lo <= p[2] < hi}),
                                     bias_pct=round(float(np.median(e)), 2), mae_pct=round(float(np.mean(np.abs(e))), 2),
                                     p90_pct=round(float(np.percentile(np.abs(e), 90)), 2), obiettivo_pct=tol)
        print(name, json.dumps(out))
        return out

    o1 = bins(stat, "FISSI(pali/cartelli/..)")
    o2 = bins(stat + par, "FISSI + auto/furgoni ferme")
    # bordi
    edge = {}
    for nm, lo, hi in (("centro |u-cx|<200", 0, 200), ("medio 200-400", 200, 400), ("bordo >400", 400, 700)):
        e = np.array([p[3] for t in stat + par for p in t["pts"] if lo <= abs(p[4] - CX) < hi])
        edge[nm] = None if len(e) < 3 else dict(n=int(len(e)), bias_pct=round(float(np.median(e)), 2),
                                                  mae_pct=round(float(np.mean(np.abs(e))), 2),
                                                  p90_pct=round(float(np.percentile(np.abs(e), 90)), 2))
    print("bordi", json.dumps(edge))
    sc = [t["scala_err_pct"] for t in stat + par]
    print("errore di scala per traccia (pendenza): mediana %.1f%%  MAE %.1f%%  n=%d" % (np.median(sc), np.mean(np.abs(sc)), len(sc)))
    if a.out:
        json.dump(dict(bins_fissi=o1, bins_fissi_e_auto=o2, bordi=edge,
                       tracce=[{k: v for k, v in t.items()} for t in res]), open(a.out, "w"), indent=1)
    for t in sorted(res, key=lambda t: -t["n"])[:25]:
        print(t["classe"], "f%d-%d" % (t["frame0"], t["frame1"]), "n", t["n"], "Z %.1f->%.1f" % (t["Zfar"], t["Znear"]),
              "S %.1f m" % t["span_m"], "scala %+.1f%%" % t["scala_err_pct"], "rms %.1f%%" % t["rms_pct"],
              "FERMO" if t["static"] else "mobile?")


if __name__ == "__main__":
    main()
