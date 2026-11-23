"""Analisi della prova a secco: confronto con le frenate di Daniele, what-if a anello chiuso sulle finestre veloci, grafici.
Uso: python3 pi/autonomous/speed_limiter_v3/analisi_secco.py --dir DIR_con_principale.npz --png-out agents/rapporti/"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from speed_limiter_v3.controllo import carica_soglie            # noqa: E402
from speed_limiter_v3.scenari import comando_liscio, con_guasto, jerk_decel, nuovo   # noqa: E402
from speed_limiter_v3.sim import Guasti, esegui_sintetico         # noqa: E402

EV = "agents/rapporti/decel_frenate_20261113-23.csv"


def confronto_frenate(z, scatti):
    e = pd.read_csv(EV)
    e = e[e.unita == "asmile-001"].reset_index(drop=True)
    t = z["t"]
    righe = []
    for _, r in e.iterrows():
        m = (t >= r.t_s - 0.5) & (t <= r.t_s + r.dur_s + 0.5)
        if m.sum() < 10:
            continue
        a = pd.Series(z["a_enc"][m]).rolling(25, center=True, min_periods=3).mean().values
        sc = [s for s in scatti if r.t_s - 1.0 <= s[0] <= r.t_s + r.dur_s + 1.5]
        righe.append(dict(ora=r.ora, v0=r.v0_kmh, a_pic_csv=r.a_picco, a_pic_v3=float(-np.nanmin(a)),
                          dec_imu_max=float(z["dec_imu"][m].max()), d03_max=float(z["d03"][m].max()),
                          angolo_max_v3=float(z["angolo"][m].max()), impuntata_csv=bool(r.impuntata), scatti_anti=len(sc)))
    return pd.DataFrame(righe)


def finestre_veloci(z, soglia_kmh=11.0, gap=3.0):
    t, v = z["t"], z["v_enc"] * 3.6
    idx = np.where(v > soglia_kmh)[0]
    out, a, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if t[i] - t[p] > gap:
            out.append((a, p)); a = i
        p = i
    out.append((a, p))
    return [(t[a] - 4.0, min(t[b] + 3.0, t[a] + 25.0)) for a, b in out if t[b] - t[a] >= 3.0]   # max 25 s: la simulazione si allontana dal reale


def whatif(z, cfg, w, g):
    t0, t1 = w
    t, v, a = z["t"], z["v_enc"], pd.Series(z["a_enc"]).rolling(15, center=True, min_periods=1).mean().values
    m = (t >= t0) & (t <= t1)
    tw, aw = t[m], a[m]
    v0 = float(v[m][0])
    fn = lambda tt: float(np.interp(tt, tw, aw))
    cfg2, s, ctl, b = nuovo(cfg, k_dec_per_grado=g, v0_kmh=v0 * 3.6, a_nat_fn=fn, t0=t0)
    r = esegui_sintetico(ctl, s, b, t1 - t0)
    vr = v[m] * 3.6
    vs = np.array([x["v_vera"] for x in r]) * 3.6
    sl, inv = comando_liscio(r)
    return dict(t0=t0, dur=t1 - t0, v_real_max=float(vr.max()), v_sim_max=float(vs.max()),
                s15_real=float((vr > 15).sum() * 0.02), s15_sim=float((vs > 15).sum() * 0.02),
                ang_max=float(max(x["angolo"] for x in r)), slew=sl, inv=inv, jerk=sl * g,
                t_frenato=float(sum(1 for x in r if x["angolo"] > 1) * 0.02)), r, (tw, vr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--png-out", required=True)
    a = ap.parse_args()
    cfg = carica_soglie()
    z = dict(np.load(os.path.join(a.dir, "principale.npz")))
    sc = json.load(open(os.path.join(a.dir, "scatti_anti.json")))
    df = confronto_frenate(z, sc)
    print("== confronto frenate (n=%d)" % len(df))
    print("a_picco v3 / csv: mediana %.2f, corr %.2f" % (np.nanmedian(df.a_pic_v3 / df.a_pic_csv), np.corrcoef(df.a_pic_v3, df.a_pic_csv)[0, 1]))
    print("dec IMU max / a picco v3: mediana %.2f" % np.nanmedian(df.dec_imu_max / df.a_pic_v3))
    print("scatti anti per frenata:", df[["ora", "v0", "a_pic_csv", "a_pic_v3", "dec_imu_max", "d03_max", "impuntata_csv", "scatti_anti"]].round(2).query("scatti_anti>0 or impuntata_csv").to_string())
    print("frenate con v0>=12 km/h e angolo v3 > 1 (open-loop):", int(((df.v0 >= 12) & (df.angolo_max_v3 > 1)).sum()), "su", int((df.v0 >= 12).sum()))
    ws = finestre_veloci(z)
    print("== what-if finestre veloci:", len(ws))
    best = None
    for g in (0.03, 0.05, 0.12):
        rs = []
        for w in ws:
            res, r, vr = whatif(z, cfg, w, g)
            rs.append(res)
            if g == 0.05 and (best is None or res["v_real_max"] > best[0]["v_real_max"] or False):
                pass
        d = pd.DataFrame(rs)
        print("g=%.2f: v max reale %.1f -> sim %.1f | s>15 reale %.0f s -> sim %.0f s | angolo max %.0f | slew max %.0f gradi/s | inversioni max %d | jerk del COMANDO (slew x g) max %.2f m/s3 | tempo frenato %.0f s" % (
            g, d.v_real_max.max(), d.v_sim_max.max(), d.s15_real.sum(), d.s15_sim.sum(), d.ang_max.max(), d.slew.max(), d.inv.max(), d.jerk.max(), d.t_frenato.sum()))
        if g == 0.05:
            print(d.round(1).sort_values("v_real_max", ascending=False).head(6).to_string())
            ordine = d.sort_values("s15_real", ascending=False).index[:2]
            scelte = [ws[i] for i in ordine]
    # grafici
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 3, figsize=(10, 6), sharex="col")
    cols = []
    for w in scelte:
        res, r, (tw, vr) = whatif(z, cfg, w, 0.05)
        cols.append(("what-if su guida vera %.0f s (g=0.05 ipotesi)" % w[0], r, (tw - w[0], vr)))
    cfg2, s, ctl, b = nuovo(cfg, k_dec_per_grado=0.05, pendenza_ms2=0.7, v0_kmh=14.0)
    r = esegui_sintetico(ctl, s, b, 12, impuntate=(6.0,))
    cols.append(("sintetica: discesa + impuntata a t=6 s", r, None))
    for j, (tit, r, real) in enumerate(cols):
        tt = np.array([x["t"] for x in r])
        ax[0, j].plot(tt, [x["v_vera"] * 3.6 for x in r], label="v simulata")
        if real is not None:
            ax[0, j].plot(real[0], real[1], "--", color="gray", label="v reale (senza limiter)")
        ax[0, j].axhline(15, color="r", lw=0.6); ax[0, j].axhline(12, color="orange", lw=0.6)
        ax[0, j].set_title(tit, fontsize=7); ax[0, j].set_ylabel("km/h", fontsize=7)
        ax[1, j].plot(tt, [-x["a_vera"] for x in r], label="decel vera")
        ax[1, j].plot(tt, [-x["a_des"] for x in r], ":", label="decel voluta")
        ax[1, j].set_ylabel("decel m/s2", fontsize=7)
        ax[2, j].plot(tt, [x["angolo"] for x in r], color="k")
        ax[2, j].axhline(50, color="r", lw=0.6); ax[2, j].set_ylabel("angolo gradi", fontsize=7); ax[2, j].set_xlabel("s", fontsize=7)
        if real is None:
            for k in range(3):
                ax[k, j].set_xlim(4.5, 10.5)
        for k in range(3):
            ax[k, j].tick_params(labelsize=6)
    ax[0, 0].legend(fontsize=5); ax[1, 0].legend(fontsize=5)
    fig.tight_layout()
    fig.savefig(os.path.join(a.png_out, "speed_limiter_v3_secco_frenate.png"), dpi=65)
    # impuntate vere
    fig, ax = plt.subplots(3, 2, figsize=(8, 5), sharex="col")
    for j, t0 in enumerate((4000.9, 4301.43)):
        m = (z["t"] > t0 - 2) & (z["t"] < t0 + 4)
        tt = z["t"][m] - t0
        ax[0, j].plot(tt, z["v_enc"][m] * 3.6); ax[0, j].set_title("impuntata vera %s (t=%.0f s)" % (("15:03:51", "15:08:52")[j], t0), fontsize=7)
        ax[0, j].set_ylabel("km/h", fontsize=7)
        ax[1, j].plot(tt, z["dec_imu"][m], label="dec IMU (>=2.0)"); ax[1, j].plot(tt, z["d03"][m], label="muso giu' 0.3 s (>=1.5)")
        ax[1, j].axhline(2.0, color="gray", lw=0.5); ax[1, j].axhline(1.5, color="gray", lw=0.5, ls=":")
        for s_ in sc:
            if t0 - 2 < s_[0] < t0 + 4:
                ax[1, j].axvline(s_[0] - t0, color="r", lw=0.4)
        ax[1, j].legend(fontsize=5)
        ax[2, j].plot(tt, z["angolo"][m]); ax[2, j].set_ylabel("angolo v3 (anello aperto)", fontsize=6); ax[2, j].set_xlabel("s da inizio frenata", fontsize=7)
        for k in range(3):
            ax[k, j].tick_params(labelsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(a.png_out, "speed_limiter_v3_secco_impuntate.png"), dpi=65)


if __name__ == "__main__":
    main()
