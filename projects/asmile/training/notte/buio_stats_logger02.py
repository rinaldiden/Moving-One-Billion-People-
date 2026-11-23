#!/usr/bin/env python3
"""Qualità immagine notte su logger02 (23/11): per clip (~1 min) luma, saturati, neri, mosso; A vs B accoppiati sul t_a_us.

Uso: ~/.asmile_depth_venv/bin/python buio_stats_logger02.py <dir_logger02> <out.csv> [giorno=20261123]
Legge solo i .h264 completi (con _frames.csv, niente .part). Non scrive nulla in asmile-loggers.
"""
import csv, glob, os, sys, datetime as dt
import numpy as np, cv2

D = sys.argv[1]; OUT = sys.argv[2]; GIORNO = sys.argv[3] if len(sys.argv) > 3 else "20261123"
PASSO = 8          # 1 fotogramma ogni 8 (~2 al secondo)


def orologio(sess):
    """offset (s) da t_a_us a ora vera, dal registro salute della sessione."""
    offs = []
    for f in sorted(glob.glob(f"{D}/salute_{GIORNO}_{sess}_*.csv"))[:3]:
        for r in csv.DictReader(open(f)):
            t = dt.datetime.fromisoformat(r["ora"])
            offs.append(t.timestamp() - int(r["t_a_us"]) / 1e6)
    return float(np.median(offs)) if offs else None


def sec(hhmmss):
    return int(hhmmss[:2]) * 3600 + int(hhmmss[2:4]) * 60 + int(hhmmss[4:6])


def frames_csv(clip):
    return [(int(r["frame"]), int(r["t_a_us"])) for r in csv.DictReader(open(clip[:-5] + "_frames.csv"))]


def vibrazione(sess, t0, t1):
    """std del modulo accelerazione IMU nella finestra (g): ~0.01 fermo, >0.05 in marcia su strada"""
    v = []
    for f in sorted(glob.glob(f"{D}/sensors_{GIORNO}_{sess}_*.csv")):
        for r in csv.DictReader(open(f)):
            t = int(r["t_us"])
            if t0 <= t <= t1 and r["imu_ax_g"]:
                v.append((float(r["imu_ax_g"]) ** 2 + float(r["imu_ay_g"]) ** 2 + float(r["imu_az_g"]) ** 2) ** 0.5)
    return round(float(np.std(v)), 3) if len(v) > 50 else float("nan")


def metriche(g):
    lap = cv2.Laplacian(g, cv2.CV_32F)
    h = g.shape[0]
    return dict(luma=float(g.mean()), sat=float((g >= 250).mean() * 100), nero=float((g <= 10).mean() * 100),
                lapvar=float(lap.var()), luma_alto=float(g[: h // 3].mean()), luma_basso=float(g[h // 2:].mean()),
                # mosso solo nella metà bassa (strada), escludendo pixel saturi che gonfiano il laplaciano
                lapvar_basso=float(lap[h // 2:][g[h // 2:] < 240].var()))


def leggi(clip, bersagli=None):
    """dict t_a_us -> gray: ogni PASSO fotogrammi, oppure (B) solo quelli entro 35 ms da un t della A"""
    fr = frames_csv(clip)
    tb = np.array(sorted(bersagli)) if bersagli else None
    cap = cv2.VideoCapture(clip); out = {}; i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i >= len(fr): pass
        elif tb is not None:
            j = int(np.searchsorted(tb, fr[i][1])); vic = [tb[k] for k in (j - 1, j) if 0 <= k < len(tb)]
            if vic and min(abs(v - fr[i][1]) for v in vic) < 35000:
                out[fr[i][1]] = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        elif i % PASSO == 0:
            out[fr[i][1]] = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        i += 1
    return out, len(fr), i


def main():
    righe = []
    clipsA = sorted(c for c in glob.glob(f"{D}/clip_{GIORNO}_*_A_*.h264") if os.path.exists(c[:-5] + "_frames.csv"))
    clipsB = sorted(c for c in glob.glob(f"{D}/clip_{GIORNO}_*_B_*.h264") if os.path.exists(c[:-5] + "_frames.csv"))
    # indice B: (inizio, fine, clip) su t_a_us
    idxB = []
    for c in clipsB:
        fr = frames_csv(c)
        if fr: idxB.append((fr[0][1], fr[-1][1], c, sec(os.path.basename(c).split("_")[2])))
    for ca in clipsA:
        sess = os.path.basename(ca).split("_")[2]
        off = orologio(sess)
        A, nA, decA = leggi(ca)
        if not A: continue
        t0, t1 = min(A), max(A)
        # stessa sessione: B parte entro 5 s dalla A (t_a_us riparte a ogni avvio, non basta l'intervallo)
        cb = [c for (s, e, c, sb) in idxB if s < t1 and e > t0 and abs(sb - sec(sess)) <= 5]
        B = {}
        for c in cb: B.update(leggi(c, list(A))[0])
        tb = np.array(sorted(B)) if B else None
        mA, mB, d_ms = [], [], []
        for t, g in A.items():
            mA.append(metriche(g))
            if tb is not None:
                j = int(np.argmin(np.abs(tb - t)))
                if abs(tb[j] - t) < 40000:
                    mB.append(metriche(B[tb[j]])); d_ms.append(abs(tb[j] - t) / 1e3)
        def med(L, k): return float(np.median([m[k] for m in L])) if L else float("nan")
        def p95(L, k): return float(np.percentile([m[k] for m in L], 95)) if L else float("nan")
        ora = dt.datetime.fromtimestamp(off + t0 / 1e6).strftime("%H:%M:%S") if off else ""
        r = dict(clip=os.path.basename(ca), ora=ora, n=len(mA), n_ab=len(mB), dt_ab_ms=float(np.median(d_ms)) if d_ms else float("nan"),
                 vib_g=vibrazione(sess, t0, t1), clipB=";".join(os.path.basename(c) for c in cb))
        for k in ("luma", "sat", "nero", "lapvar", "lapvar_basso", "luma_alto", "luma_basso"):
            r[f"A_{k}"] = round(med(mA, k), 2); r[f"B_{k}"] = round(med(mB, k), 2)
        r["A_sat_p95"] = round(p95(mA, "sat"), 2)
        r["frac_luma_sotto_95"] = round(float(np.mean([m["luma"] < 95 for m in mA])), 2)
        righe.append(r); print(r["ora"], r["clip"], r["A_luma"], r["B_luma"], r["A_sat"], r["A_nero"], r["A_lapvar_basso"], flush=True)
    righe.sort(key=lambda r: r["ora"])
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys())); w.writeheader(); w.writerows(righe)


if __name__ == "__main__":
    main()
