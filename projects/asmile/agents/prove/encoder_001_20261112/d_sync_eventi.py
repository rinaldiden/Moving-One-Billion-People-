#!/usr/bin/env python3
"""Punto 4 bis: lag encoder<->video per avvii/arresti (dove il flusso ottico e' monotono con la velocita', v<2.5 m/s).
Segnale video = flusso ottico mediano (Farneback 160x100, meta' bassa). Cross-correlazione sui soli campioni con v<2.5 m/s
entro +-4 s da un passaggio fermo<->moto; bootstrap sugli eventi per l'incertezza."""
import numpy as np, pandas as pd, subprocess, cv2, os
R = "asmile-loggers/asmile-001/"; SC = "/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/1b32ebd7-24f0-43c1-a686-c4879d52bcb7/scratchpad/"
fl = pd.read_csv(R + "session_20261109_094146/frames_left.csv"); tf = fl.t_ms.values / 1000
S = pd.read_csv(R + "_sensors/sensors/sensors_20261109_085334.csv", usecols=["enc_t_ms", "enc_wheel_cum"]).dropna().drop_duplicates("enc_t_ms")
tt = S.enc_t_ms.values / 1000; cc = S.enc_wheel_cum.values * (15.760 / 742726)
from scipy.signal import savgol_filter
tg = np.arange(tt[0], tt[-1], 0.01); ve = np.abs(savgol_filter(np.interp(tg, tt, cc), 21, 2, deriv=1, delta=0.01))
W, H = 160, 100
f2 = SC + "flow2.npy"
if not os.path.exists(f2):
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "h264", "-i", R + "session_20261109_094146_left.h264", "-vf", "scale=%d:%d" % (W, H), "-pix_fmt", "gray", "-vsync", "passthrough", "-f", "rawvideo", "-"], capture_output=True)
    fr = np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W); mag = np.full(len(fr), np.nan)
    for i in range(1, len(fr)):
        f = cv2.calcOpticalFlowFarneback(fr[i - 1], fr[i], None, 0.5, 4, 15, 3, 5, 1.1, 0)
        mag[i] = np.median(np.hypot(f[..., 0], f[..., 1])[40:, :])
    np.save(f2, mag)
mag = np.load(f2)[:len(tf)]
vf = np.interp(tf, tg, ve)
for lo, hi in [(0.3, 1), (1, 2), (2, 3), (3, 4), (4, 5)]:
    m = (vf >= lo) & (vf < hi); print("v %.1f-%.1f m/s: flusso medio %.2f (n=%d)" % (lo, hi, np.nanmean(mag[m]), m.sum()))
# eventi: instanti in cui v attraversa 0.4 m/s (salita o discesa) con almeno 2 s di v<0.15 da un lato
vs = np.interp(tf, tg, ve); ev = []
for i in range(30, len(vs) - 30):
    if (vs[i - 1] < 0.4 <= vs[i] and vs[i - 30:i - 8].max() < 0.2) or (vs[i - 1] >= 0.4 > vs[i] and vs[i + 8:i + 30].max() < 0.2):
        ev.append(i)
print("eventi avvio/arresto trovati: %d" % len(ev))
Ls = np.arange(-0.5, 0.5001, 1 / 60)
def corr_ev(evs):
    idx = np.unique(np.concatenate([np.arange(i - 60, i + 60) for i in evs])); idx = idx[(idx > 0) & (idx < len(tf) - 1)]
    out = []
    for L in Ls:
        v = np.interp(tf[idx] + L, tg, ve); m = (v < 2.5) & np.isfinite(mag[idx])
        out.append(np.corrcoef(mag[idx][m], v[m])[0, 1])
    return np.array(out)
c = corr_ev(ev); k = np.nanargmax(c)
print("tutti gli eventi: picco lag %+.0f ms corr %.3f; corr a 0 ms %.3f; a +-200 ms %.3f/%.3f" % (Ls[k] * 1000, c[k], c[len(Ls) // 2], np.interp(-.2, Ls, c), np.interp(.2, Ls, c)))
rng = np.random.default_rng(1); pk = []
for _ in range(200):
    s = rng.choice(len(ev), len(ev)); pk.append(Ls[np.nanargmax(corr_ev([ev[i] for i in s]))] * 1000)
print("bootstrap eventi (200): lag mediano %+.0f ms, p5-p95 %+.0f..%+.0f ms" % (np.median(pk), *np.percentile(pk, [5, 95])))
# per evento singolo
pe = [Ls[np.nanargmax(corr_ev([i]))] * 1000 for i in ev]
print("per evento (n=%d): mediana %+.0f ms, p25-p75 %+.0f..%+.0f ms" % (len(pe), np.median(pe), *np.percentile(pe, [25, 75])))
print("(convenzione: v encoder campionata a t_frame+L; L>0 = il frame vede il moto DOPO l'encoder? L negativo = il video e' in anticipo)")
