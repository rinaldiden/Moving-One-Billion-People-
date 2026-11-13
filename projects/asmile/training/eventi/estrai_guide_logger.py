#!/usr/bin/env python3
"""estrai_guide_logger.py — frenate e sterzate del PILOTA dai giri di asmile-logger001 (IMU HW-123 + velocita visiva).
Stesso formato di out_guide_*/frenate.csv e sterzate.csv (#001); colonne non misurabili = vuote.
segno_imu: mapping_0911 = mapping assi del 09-11 (agents/rapporti/logger001_imu_assi_PROPOSTA_20261109.json, chip ruotato 180 gradi su Z, frenata = imu_ax POSITIVO,
3 eventi puliti) APPLICATO ma NON verificato con la ruota BLE (nei 2 tratti BLE del 09-11 il logger era fermo: IMU piatta, flusso 0).
Convenzioni logger (agents/lezioni/daniele.md 2026-11-09, verificate sui dati): avanti = -ax (frenata -> ax POSITIVO),
scala g 0.83 (|g| 1.20), bias gz +0.90 dps, gz>0 = sinistra (verificato col flusso ottico lontano, corr -0.78 a lag 0.25 s).
a_imu_mean e' in convenzione #001: accelerazione AVANTI (negativa = frenata).
Uso: python3 estrai_guide_logger.py <vis_r1.csv> <vis_r2.csv> <outdir>
"""
import sys, os, csv, json, datetime
import numpy as np, pandas as pd
from scipy.signal import savgol_filter, medfilt
HZ = 50.0
SENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "asmile-loggers", "asmile-logger", "_sensors", "sensors", "sensors_%s.csv")
RIDES = {"20261109_ride1050": ("2026-11-09T10:50:10", "2026-11-09T10:55:15", "vis1"),
         "20261109_ride1109": ("2026-11-09T11:09:05", "2026-11-09T11:14:40", "vis2")}
BANDS = [(0, 6.5, 5), (6.5, 9, 8), (9, 11, 10), (11, 13.5, 12), (13.5, 99, 15)]
G_SCALE, GZ_BIAS = 0.83, 0.90
E = lambda s: datetime.datetime.fromisoformat(s).timestamp()


def band(k):
    for lo, hi, c in BANDS:
        if lo <= k < hi: return c


def runs(mask, gap=25, minlen=1):
    idx = np.where(mask)[0]
    if len(idx) == 0: return []
    cut = np.where(np.diff(idx) > gap)[0]
    st = np.r_[0, cut + 1]; en = np.r_[cut, len(idx) - 1]
    return [(idx[a], idx[b]) for a, b in zip(st, en) if idx[b] - idx[a] >= minlen]


def load_imu():
    ds = []
    for s in ("20261109_101007", "20261109_111007"):
        d = pd.read_csv(SENS % s, usecols=["t_ms", "wall", "imu_ax_g", "imu_gz_dps"])
        ds.append(d)
    d = pd.concat(ds, ignore_index=True)
    d["ep"] = [datetime.datetime.fromisoformat(w).timestamp() for w in d.wall]
    return d


def build(d, vis, a, b):
    w0, w1 = E(a), E(b)
    r = d[(d.ep >= w0) & (d.ep <= w1)].reset_index(drop=True)
    v = pd.read_csv(vis)
    x = v.set_index("wall").v.interpolate(limit=12).bfill().ffill()
    x = pd.Series(medfilt(x.values, 9), index=x.index)               # ~1.2 s mediana: toglie spike del KLT
    r["v_raw"] = np.interp(r.ep, x.index, x.values)
    r["v"] = savgol_filter(r.v_raw, 25, 2).clip(min=0)
    r["v15"] = savgol_filter(r.v_raw, 75, 2).clip(min=0)
    r["a"] = savgol_filter(r.v_raw, 75, 2, deriv=2, delta=1 / HZ) if False else savgol_filter(r.v_raw, 75, 2, deriv=1, delta=1 / HZ)
    # accel avanti IMU: -ax, via componente lenta (pitch/rollio/appoggio, finestra 15 s), media 1.5 s come #001
    ax = r.imu_ax_g.values
    slow = pd.Series(ax).rolling(750, center=True, min_periods=100).median().values
    r["a_imu"] = pd.Series(-(ax - slow) * 9.81 * G_SCALE).rolling(75, center=True, min_periods=1).mean()
    still = r.v < 0.1
    r["gz"] = savgol_filter(r.imu_gz_dps.values - GZ_BIAS, 25, 2)       # gz>0 = sinistra
    r["t"] = r.t_ms / 1000.0
    return r


def load_flow(out, sess):
    f = pd.read_csv(os.path.join(out, "flusso_strada_ride%s.csv" % sess[-4:]))
    return f.wall.values, f.flow.values


scartati = []


def brake_events(r, sess, flow):
    """Frenate IMU-first (la velocita visiva ha scala instabile: mediana 4.2 vs 2.3 km/h cambiando solo la base 0.27->0.67 s,
    e NON correla con l'IMU: non e' usata per v0/v1/a). Detector come #001 ma su a_imu: a_imu<-0.3 m/s2 (media 1.5 s), >=1 s,
    esteso finche' < -0.1, in moto (flusso>0.3 m/s). classe: stop_umano se il video mostra bici ferma (v<0.3 m/s per >=1 s)
    entro 2 s dalla fine; altrimenti 'candidata_imu' (frenata NON confermata dal video, fuori dai fit di soglia)."""
    ev = []
    ai = r.a_imu.values; vv = r.v15.values
    seg = [(i, j) for i, j in runs(vv > 0.3, gap=250) if (j - i) / HZ > 5]
    for i0, j0 in seg:
        for i, j in runs(ai[i0:j0] < -0.3, gap=25):
            i += i0; j += i0
            while i > i0 and ai[i - 1] < -0.1: i -= 1
            while j < j0 - 1 and ai[j + 1] < -0.1: j += 1
            dur = (j - i) / HZ
            if dur < 1.0: continue
            # giro 2 (VETO scettico): gate col FLUSSO OTTICO sulla strada (Farneback, px/frame), non con la v stereo/visiva.
            # (a) in moto durante l'evento (da 1 s prima all'ultimo istante): flusso medio > 0.5, altrimenti e' IMU a bici gia' ferma -> scartato;
            # (b) ferma dopo: flusso < 0.25 per >= 10 frame consecutivi entro 2 s dalla fine (criterio dello scettico).
            fw, ff = flow
            ep0, ep1 = float(r.ep.values[i]), float(r.ep.values[j])
            pre = (fw >= ep0 - 1.0) & (fw < ep1)
            if pre.sum() < 10 or np.mean(ff[pre]) <= 0.5:
                scartati.append(r.wall[i][11:19]); continue
            post = (fw >= ep1) & (fw < ep1 + 2.0)
            ferma = bool(post.sum() >= 10 and pd.Series(ff[post] < 0.25).rolling(10).sum().max() >= 10)
            e = dict(sess=sess, t0=float(r.t.values[i]), t_ms0=int(r.t_ms.values[i]), wall=r.wall[i][11:19], dur_s=dur,
                     a_peak=float(-ai[i:j + 1].min()), a_imu_mean=float(ai[i:j + 1].mean()),
                     classe="stop_umano" if ferma else "candidata_imu", segno_imu="mapping_0911")
            if ev and ev[-1]["t_ms0"] == e["t_ms0"]: continue
            ev.append(e)
    return ev


def steer_events(r, sess, thr=22.0):
    ev = []
    m = (np.abs(r.gz.values) > thr) & (r.v15.values > 0.3)
    for i, j in runs(m, gap=25):
        if (j - i) / HZ < 0.5: continue
        s = r.iloc[i:j + 1]
        e = dict(sess=sess, t0=float(r.t.values[i]), t_ms0=int(r.t_ms.values[i]), dur_s=(j - i) / HZ,
                 gz_peak=float(np.abs(s.gz).max()),
                 verso="sx" if s.gz.values[np.argmax(np.abs(s.gz.values))] > 0 else "dx",
                 segno_imu="gz_verificato_flusso")
        ev.append(e)
    return ev


if __name__ == "__main__":
    vis = {"vis1": sys.argv[1], "vis2": sys.argv[2]}; out = sys.argv[3]
    os.makedirs(out, exist_ok=True)
    d = load_imu(); F, S, SEG, VT = [], [], [], {}
    for sess, (a, b, k) in RIDES.items():
        r = build(d, vis[k], a, b)
        r.to_pickle(os.path.join(out, f"_serie_{sess}.pkl"))
        F += brake_events(r, sess, load_flow(out, sess)); S += steer_events(r, sess)
        mov = r.v > 0.5
        SEG.append(dict(sess=sess, usato=True, dist_m=0.0, dist_visiva_m_NONAFFIDABILE=float(r.v.sum() / HZ), t_mov_s=float(mov.sum() / HZ), v_media_kmh_NONAFFIDABILE=float(r.v[mov].mean() * 3.6),
                        v_max_kmh=float(r.v.max() * 3.6), wall0=a, wall1=b))
    cols_f = ["sess", "t0", "t_ms0", "wall", "v0_kmh", "v1_kmh", "dur_s", "dv", "a_mean", "a_peak", "a_imu_mean", "sp_m", "brake_out_max", "limiter", "lim_attivo", "lim_frac", "fascia", "classe", "Z_arc", "ttc", "Z_str", "segno_imu"]
    cols_s = ["sess", "t0", "t_ms0", "dur_s", "v_kmh", "gz_peak", "k_med", "amp_deg", "rate_peak", "anticipo_s", "fascia", "Z_arc_inizio", "verso", "segno_imu"]
    for nome, cols, ev in (("frenate", cols_f, F), ("sterzate", cols_s, S)):
        with open(os.path.join(out, nome + ".csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, restval=""); w.writeheader(); w.writerows(ev)
    json.dump(SEG, open(os.path.join(out, "segmenti.json"), "w"), indent=1)
    print(len(F), "frenate", len(S), "sterzate", "scartate a bici ferma:", scartati); print(json.dumps(SEG, indent=1))
