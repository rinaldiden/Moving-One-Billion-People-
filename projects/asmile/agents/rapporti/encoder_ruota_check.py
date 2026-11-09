#!/usr/bin/env python3
"""Gate L0.encoder_ruota: encoder vs GPS (6-16 km/h) e accel encoder vs IMU, da limiter_*.csv.
Uso: python3 encoder_ruota_check.py <limiter.csv> [circ_attiva] [circ_target]"""
import sys, numpy as np, pandas as pd
f = sys.argv[1]
c_act = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3374
c_tgt = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3374
d = pd.read_csv(f, parse_dates=['timestamp_iso'])
t = (d.timestamp_iso - d.timestamp_iso.iloc[0]).dt.total_seconds().values
dt = np.median(np.diff(t)); print("dt mediano %.3fs n=%d" % (dt, len(d)))
gps = d.gps_speed_ms.values; enc = d.enc_speed_ms.values * c_tgt / c_act
# GPS: il log ripete l'ultimo valore; usa solo righe con fix
fix = d.fix.values == 1
# lag: correla enc(t) con gps(t+lag): GPS in ritardo => gps(t) ~ enc(t-lag)
lags = np.arange(0, 2.01, 0.1); best = None; cc = []
for L in lags:
    k = int(round(L / dt))
    a = enc[:len(enc) - k] if k else enc; b = gps[k:]
    m = fix[k:] & (gps[k:] > 1.5)
    r = np.corrcoef(a[m], b[m])[0, 1]; cc.append(r)
    if best is None or r > best[1]: best = (L, r)
print("lag GPS stimato %.1fs (corr %.3f)" % best, [round(x, 3) for x in cc[::2]])
L = best[0]; k = int(round(L / dt))
a = enc[:len(enc) - k] if k else enc; b = gps[k:]; kmh = b * 3.6
m = fix[k:] & (kmh >= 6) & (kmh <= 16)
err = np.abs(a[m] - b[m]) / b[m] * 100; sg = (a[m] - b[m]) / b[m] * 100
print("6-16 km/h n=%d (%.0fs): err abs mediana %.1f%% p90 %.1f%% | bias mediano %+.1f%%" % (m.sum(), m.sum()*dt, np.median(err), np.percentile(err, 90), np.median(sg)))
for lo, hi in [(6, 9), (9, 12), (12, 16)]:
    mm = m & (kmh >= lo) & (kmh < hi)
    print("  %d-%d km/h n=%d err med %.1f%% p90 %.1f%% bias %+.1f%%" % (lo, hi, mm.sum(), np.median(np.abs(a[mm]-b[mm])/b[mm]*100), np.percentile(np.abs(a[mm]-b[mm])/b[mm]*100, 90), np.median((a[mm]-b[mm])/b[mm]*100)))
# senza compensazione lag
m0 = fix & (gps*3.6 >= 6) & (gps*3.6 <= 16); e0 = np.abs(enc[m0]-gps[m0])/gps[m0]*100
print("senza lag: med %.1f%% p90 %.1f%%" % (np.median(e0), np.percentile(e0, 90)))
# accel: enc_accel vs IMU accel_x_g*9.81
ea = d.enc_accel_ms2.values; ia = d.accel_x_g.values * 9.80665
mv = d.enc_speed_ms.values > 1.5
def sm(x, n): return np.convolve(x, np.ones(n)/n, mode='same')
print("accel: std enc %.2f imu %.2f m/s2 (in moto)" % (ea[mv].std(), ia[mv].std()))
for n in (1, 5, 10):
    x, y = sm(ea, n)[mv], sm(ia, n)[mv]
    print("  smooth %d camp: corr %.3f" % (n, np.corrcoef(x, y)[0, 1]))
# accel da derivata GPS vs enc (riferimento debole)
ga = np.gradient(sm(enc, 5), dt)
x, y = sm(ea, 5)[mv], sm(ia - np.median(ia[~mv]), 5)[mv]
sl = np.polyfit(y, x, 1); print("  fit enc = %.2f*imu + %.2f ; offset imu fermo %.3f g" % (sl[0], sl[1], np.median(d.accel_x_g.values[~mv])))
print("  rms diff (smooth5, imu-offset) %.2f m/s2" % np.sqrt(np.mean((x-y)**2)))
for L2 in (0, 1):
    pass
print("enc_accel: n frenate (<-1.5) %d, n accel (>1.5) %d, |a|max %.1f" % ((ea < -1.5).sum(), (ea > 1.5).sum(), np.abs(ea).max()))

# ---- confronto per blocchi: GPS e' a 1 Hz (scalino); media enc su 1 s per ogni aggiornamento GPS
print("\n== per blocchi GPS (1 Hz) ==")
ch = np.flatnonzero(np.diff(gps) != 0) + 1
res = {}
for L in np.arange(0, 2.01, 0.2):
    e = []; gg = []
    for i0, i1 in zip(ch[:-1], ch[1:]):
        if i1 - i0 > 12: continue
        g = gps[i0]
        if not (6/3.6 <= g <= 16/3.6) or not fix[i0]: continue
        k0 = int(round((t[i0] - L - t[0]) / dt)); k1 = int(round((t[i1] - L - t[0]) / dt))
        if k0 < 0: continue
        e.append(enc[k0:k1].mean()); gg.append(g)
    e = np.array(e); gg = np.array(gg); er = np.abs(e-gg)/gg*100
    res[round(L, 1)] = (len(e), np.median(er), np.percentile(er, 90), np.median((e-gg)/gg*100), np.corrcoef(e, gg)[0, 1])
    print("lag %.1fs n=%d err med %.1f%% p90 %.1f%% bias %+.1f%% corr %.3f" % (L, *res[round(L, 1)]))

# ---- accel: derivata enc_speed (smussata 1 s) e derivata GPS vs IMU
print("\n== accel (parziale) ==")
sp = pd.Series(enc).rolling(10, center=True, min_periods=1).mean().values
a_d = np.gradient(sp, dt)
ia1 = pd.Series(ia).rolling(10, center=True, min_periods=1).mean().values
off = np.median(ia[d.enc_speed_ms.values < 0.05])
for sgn in (+1, -1):
    x = a_d[mv]; y = sgn*(ia1[mv]-off)
    print("segno IMU %+d: corr(d/dt enc 1s, IMU 1s) %.3f  rms diff %.2f m/s2" % (sgn, np.corrcoef(x, y)[0, 1], np.sqrt(np.mean((x-y)**2))))
print("std d/dt enc(1s) %.2f, std IMU(1s) %.2f" % (a_d[mv].std(), (ia1[mv]-off).std()))
