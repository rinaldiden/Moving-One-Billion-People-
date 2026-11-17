#!/usr/bin/env python3
"""Punto 3: accelerazione da encoder filtrata vs GPS 10 Hz vs IMU #001. Segni IMU ricavati dai dati."""
import numpy as np, pandas as pd
from scipy.signal import savgol_filter
D = "asmile-loggers/asmile-001/_sensors/sensors/sensors_20261109_085334.csv"
MPC = 15.760 / 742726
d = pd.read_csv(D, low_memory=False); t0 = d.t_ms.iloc[0] / 1000
# griglia comune 20 ms (sensor_hub 50 Hz)
tg = np.arange(0, d.t_ms.iloc[-1] / 1000 - t0, 0.02)
e = d.dropna(subset=["enc_wheel_cum"]).drop_duplicates("enc_t_ms")
c = np.interp(tg, e.enc_t_ms.values / 1000 - t0, e.enc_wheel_cum.values.astype(float)) * MPC
g = d.dropna(subset=["gps_t_ms", "gps_lat"]).drop_duplicates("gps_t_ms")
g = g[(g.gps_fix == 1) & (g.gps_hdop < 3)]
gv = np.interp(tg, g.gps_t_ms.values / 1000 - t0, g.gps_speed_ms.values)
imu = d.dropna(subset=["imu_ax_g"]).drop_duplicates("t_ms")
I = {k: np.interp(tg, imu.t_ms.values / 1000 - t0, imu["imu_a%s_g" % k].values) for k in "xyz"}
mov = (tg > 3021) & (tg < 3565)
def sg(x, win_s, deriv):  # Savitzky-Golay polinomio 2, finestra win_s, derivata deriv
    n = int(round(win_s / 0.02)) | 1
    return savgol_filter(x, n, 2, deriv=deriv, delta=0.02)
def lagcorr(a, b, m, maxlag=1.5):
    best = None
    for L in np.arange(-maxlag, maxlag + 1e-9, 0.02):
        s = int(round(L / 0.02)); bb = np.roll(b, s)
        r = np.corrcoef(a[m], bb[m])[0, 1]
        if best is None or r > best[1]: best = (L, r)
    return best
print("GPS: velocita' interpolata a 50 Hz da 10 Hz Doppler; accel GPS = SG derivata sulla stessa finestra W")
print("W(s) | lag: GPS in RITARDO di |L| s se L<0 | corr(enc,GPS) | pendenza OLS enc=a*GPS | frenata GPS<-0.5: n, rapp. mediano, corr | std enc/GPS | accel picco")
res = {}
for W in [0.5, 0.8, 1.0, 1.5, 2.0]:
    ae = sg(c, W, 2) if False else sg(c, W * 2 if False else W, 2)   # derivata seconda diretta della posizione encoder (poli 2)
    ve = sg(c, W, 1)                                                    # velocita' filtrata
    ae = sg(ve, W, 1)                                                   # accel = derivata della velocita' filtrata
    ag = sg(gv, W, 1)
    L, r = lagcorr(ae, ag, mov & (gv > 1.5))
    # allineo GPS sul lag stimato (GPS in ritardo di L: gps(t) ~ enc(t-L) -> roll indietro)
    s = int(round(L / 0.02)); agL = np.roll(ag, s)
    m = mov & (gv > 1.5) & (np.roll(gv, s) > 1.5)
    r0 = np.corrcoef(ae[m], agL[m])[0, 1]; slope = np.polyfit(agL[m], ae[m], 1)[0]
    fr = m & (agL < -0.5)
    print("%.1f | %+.2f | %.3f | %.2f | n=%d rapp %.2f corr %.2f | %.2f/%.2f | enc max %.2f min %.2f" % (
        W, L, r0, slope, fr.sum(), np.median(ae[fr] / agL[fr]), np.corrcoef(ae[fr], agL[fr])[0, 1], ae[m].std(), agL[m].std(), ae[m].max(), ae[m].min()))
    res[W] = (ae, agL, m)
print("\nLimite fisico: filtro W=1 s e' lo stesso del GPS -> le frenate brevi (<1 s) sono smussate da ENTRAMBI; rapporto 0.9 in frenata include ritardo/smussamento diversi.")
# velocita' encoder vs GPS al lag
ve = np.abs(sg(c, 0.3, 1)); L, r = lagcorr(ve, gv, mov & (gv > 1.5)); print("lag velocita' enc vs GPS (picco corr): GPS ritarda %.2f s (corr %.3f)" % (L, r))
# IMU: segno e asse avanti dai dati. accel_avanti_encoder (W=1) contro IMU smussata 1 s, rimuovendo bias su fermo
W = 1.0; ae, agL, m = res[W]
print("\nIMU: regressione accel IMU (g, smussata %.1f s) contro accel encoder (m/s2), solo moto" % W)
for k in "xyz":
    x = sg(I[k], W, 0)
    mm = m
    r = np.corrcoef(x[mm], ae[mm])[0, 1]; sl = np.polyfit(ae[mm], x[mm], 1)
    print("  imu_a%s: corr con acc_enc %+.3f  pendenza %.4f g per m/s2 (=%.2f del teorico 0.102)  intercetta %.3f g" % (k, r, sl[0], sl[0] / 0.102, sl[1]))
# correlazione mappata sul lag per ay (asse avanti presunto)
ay = sg(I["y"], W, 0); ax = sg(I["x"], W, 0)
L, r = lagcorr(-ay, ae, m); print("  -ay vs enc: lag ottimo %.2f s corr %.3f" % (L, r))
L2, r2 = lagcorr(-ax, ae, m); print("  -ax vs enc: lag ottimo %.2f s corr %.3f" % (L2, r2))
# frenata
fr = m & (agL < -0.5)
print("  in frenata (GPS<-0.5, n=%d): media ay %.3f g | media ay resto-moto %.3f g | differenza %.3f g = %.2f m/s2 (con encoder: media acc_enc in frenata %.2f m/s2)" % (
    fr.sum(), ay[fr].mean(), ay[m & ~fr].mean(), ay[fr].mean() - ay[m & ~fr].mean(), (ay[fr].mean() - ay[m & ~fr].mean()) * 9.81, ae[fr].mean()))
# accel avanti IMU a regime: IMU contro GPS
ia = -(ay - np.median(ay[(tg > 3000) & (tg < 3015)]))*9.81  # bias dal fermo 3009-3015 s
mr = m & (agL != 0)
print("  accel IMU(-ay, bias da fermo, x9.81) vs GPS: corr %.3f pendenza %.2f ; vs encoder: corr %.3f pendenza %.2f" % (
    np.corrcoef(ia[mr], agL[mr])[0, 1], np.polyfit(agL[mr], ia[mr], 1)[0], np.corrcoef(ia[mr], ae[mr])[0, 1], np.polyfit(ae[mr], ia[mr], 1)[0]))
# nota: IMU senza correzione di pitch: salita/discesa entra nell'asse avanti
print("  (IMU non corretta per pendenza della strada/pitch: entra come bias lento; il filtro passa-alto non e' applicato)")

# --- eventi di frenata: Delta-v per evento (non risente dello smussamento ne' della selezione sul rumore)
print("\nEVENTI di frenata: intervalli con accel GPS(W=1.5, allineata) < -0.4 m/s2 per >= 1.5 s; Delta-v su estremi dell'evento (v smussata 0.3 s)")
ve = sg(c, 0.3, 1); gvL = np.roll(gv, int(round(-0.16 / 0.02)))  # allineo GPS (in ritardo 0.16 s) all'encoder
aG = sg(gvL, 1.5, 1); sel = mov & (aG < -0.4)
ev = []; i = 0
while i < len(sel):
    if sel[i]:
        j = i
        while j < len(sel) and sel[j]: j += 1
        if (j - i) * 0.02 >= 1.5: ev.append((i, j))
        i = j
    else: i += 1
rows = []
for i, j in ev:
    dvE = ve[j] - ve[i]; dvG = gvL[j] - gvL[i]; T = (j - i) * 0.02
    ayE = -(ay[i:j].mean() - ay[max(0, i - 150):i].mean()) * 9.81
    rows.append((tg[i], T, dvG, dvE, dvG / T, dvE / T, ayE))
rows = np.array(rows)
print("  n eventi %d | durata mediana %.1f s" % (len(rows), np.median(rows[:, 1])))
print("  somma Delta-v: GPS %.1f m/s, encoder %.1f m/s -> rapporto %.3f ; mediana rapporto per evento %.2f" % (rows[:, 2].sum(), rows[:, 3].sum(), rows[:, 3].sum() / rows[:, 2].sum(), np.median(rows[:, 3] / rows[:, 2])))
print("  decel media per evento m/s2: GPS %.2f enc %.2f ; IMU(-ay, vs 3 s prima) %.2f" % (-rows[:, 4].mean(), -rows[:, 5].mean(), rows[:, 6].mean()))
print("  evento piu' forte: GPS %.2f, enc %.2f, IMU %.2f m/s2 (media sull'evento)" % (-rows[:, 4].min(), -rows[rows[:, 4].argmin(), 5], rows[rows[:, 4].argmin(), 6]))
print("  picco |accel| nel file: GPS(W=0.5) min %.2f ; enc(W=0.5) min %.2f ; IMU x9.81 max(-ay-bias) %.2f" % (sg(gv,0.5,1)[mov].min(), sg(sg(c,0.5,1),0.5,1)[mov].min(), ia[mov].min()))
