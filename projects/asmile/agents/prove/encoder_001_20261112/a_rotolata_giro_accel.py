#!/usr/bin/env python3
"""L0.encoder_ruota 2026-11-12 - punti 1,2,3. Solo CSV sul Mac. Uso: python3 a_rotolata_giro_accel.py"""
import numpy as np, pandas as pd, subprocess, sys
from scipy.signal import savgol_filter
D = "asmile-loggers/asmile-001/_sensors/sensors/"
F = D + "sensors_20261109_085334.csv"
CPR = 16384; MPC = 15.760 / 742726
d = pd.read_csv(F, low_memory=False)
t0 = d.t_ms.iloc[0] / 1000
e = d.dropna(subset=["enc_wheel_cum"]).drop_duplicates("enc_t_ms")
te = e.enc_t_ms.values / 1000 - t0; ce = e.enc_wheel_cum.values.astype(float)
g = d.dropna(subset=["gps_t_ms", "gps_lat"]).drop_duplicates("gps_t_ms")
print("== 1. ROTOLATA: confronto dei 3 candidati (mpc nuovo %.4e)" % MPC)
for a, b in [(1821.9, 1838.5), (2736.8, 2765.6), (3044.9, 3057.6)]:
    m = (te >= a) & (te <= b); c = ce[m]; t = te[m]
    v = np.abs(np.gradient(savgol_filter(c, 25, 2), t)) * MPC
    gg = g[(g.gps_t_ms / 1000 - t0 >= a) & (g.gps_t_ms / 1000 - t0 <= b)]
    print(" %.1f-%.1f s dur %.1f s dcount %d (%.2f m) vmax_enc %.2f m/s vmedia %.2f | GPS vmax %.2f m/s fix %.2f n=%d | retrograde %.2f%%" % (
        a, b, b - a, c[-1] - c[0], (c[-1] - c[0]) * MPC, v.max(), (c[-1] - c[0]) * MPC / (b - a),
        gg.gps_speed_ms.max() if len(gg) else np.nan, gg.gps_fix.mean() if len(gg) else np.nan, len(gg),
        100 * (np.abs(np.diff(c)).sum() - abs(c[-1] - c[0])) / np.abs(np.diff(c)).sum() / 2))
# fermo prima/dopo della spinta
for a, b in [(2730, 2737), (2765.6, 2772)]:
    m = (te >= a) & (te <= b); print("  fermo %.1f-%.1f s: ptp %d count (%.1f mm)" % (a, b, np.ptp(ce[m]), np.ptp(ce[m]) * MPC * 1000))
print("  wall inizio spinta:", d.wall.iloc[(np.abs(d.t_ms / 1000 - t0 - 2736.8)).argmin()], " fine:", d.wall.iloc[(np.abs(d.t_ms / 1000 - t0 - 2765.6)).argmin()])
# velocita' a passo (tracce): velocita' picco/profilo regolare = spinta continua a mano
m = (te >= 2736.8) & (te <= 2765.6); v = np.abs(np.gradient(savgol_filter(ce[m], 25, 2), te[m])) * MPC
print("  profilo velocita' spinta (m/s) percentili 10/50/90/max: %s  -> %.1f km/h max" % (np.round(np.percentile(v, [10, 50, 90, 100]), 2), v.max() * 3.6))

print("\n== incertezza: rapporto encoder/GPS per ogni tratto di moto (mpc nuovo) = dispersione indipendente dalla spinta")
def hav(la1, lo1, la2, lo2):
    R = 6371000.0; p1, p2 = np.radians(la1), np.radians(la2); dp, dl = p2 - p1, np.radians(lo2 - lo1)
    return 2 * R * np.arcsin(np.sqrt(np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2))
gv = g[(g.gps_fix == 1) & (g.gps_hdop < 3)]
gt = gv.gps_t_ms.values / 1000 - t0
seg = hav(gv.gps_lat.values[:-1], gv.gps_lon.values[:-1], gv.gps_lat.values[1:], gv.gps_lon.values[1:])
ok = (gv.gps_speed_ms.values[1:] > 1.5) & (np.diff(gt) < 0.5)
cI = np.interp(gt, te, ce); dE = np.abs(np.diff(cI)) * MPC
rat = []
for a, b in [(3021, 3115), (3115, 3200), (3250, 3390), (3390, 3522), (3524, 3565)]:
    mm = ok & (gt[1:] >= a) & (gt[1:] < b)
    if mm.sum() > 100:
        rat.append(dE[mm].sum() / seg[mm].sum()); print("  %d-%d s: GPS %.1f m enc %.1f m ratio %.3f" % (a, b, seg[mm].sum(), dE[mm].sum(), rat[-1]))
print("  ratio medio %.3f dev.std %.3f (n=%d)" % (np.mean(rat), np.std(rat, ddof=1), len(rat)))
print("\n== GPS qualita' (intero file, in moto >1.5 m/s)")
gm = g[g.gps_speed_ms > 1.5]
print("  righe GPS distinte %d in %.0f s => %.1f Hz; fix==1 %.1f%%; HDOP mediano %.2f p90 %.2f max %.2f; sats mediana %d min %d" % (
    len(g), g.gps_t_ms.max() / 1000 - g.gps_t_ms.min() / 1000, len(g) / ((g.gps_t_ms.max() - g.gps_t_ms.min()) / 1000),
    100 * (g.gps_fix == 1).mean(), gm.gps_hdop.median(), gm.gps_hdop.quantile(.9), gm.gps_hdop.max(), gm.gps_sats.median(), gm.gps_sats.min()))
print("  dt GPS: mediana %.0f ms p99 %.0f ms" % (np.median(np.diff(g.gps_t_ms)), np.percentile(np.diff(g.gps_t_ms), 99)))

print("\n== 2. giro con script ufficiale, --mpc %.4e" % MPC)
for f in ["sensors_20261109_085334.csv", "sensors_20261109_095334.csv"]:
    print("--", f); sys.stdout.flush()
    subprocess.run([sys.executable, "agents/rapporti/encoder_taratura_metro.py", "giro", D + f, "--mpc", "%.4e" % MPC])
print("-- confronto con mpc attivo 2.0593e-5 (0.3374)")
subprocess.run([sys.executable, "agents/rapporti/encoder_taratura_metro.py", "giro", F, "--mpc", "%.4e" % (0.3374 / CPR)])
