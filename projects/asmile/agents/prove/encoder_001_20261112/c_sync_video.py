#!/usr/bin/env python3
"""Punto 4: encoder <-> camere nel giro 09/11 (sessione 094146). Tre misure:
 1) orologi: wall - t_ms vs clock_map; enc_t_ms - t_ms; jitter campionamento encoder
 2) frame t_ms -> riga sensori (come nel rapporto 09/11, rifatto)
 3) MISURA INDIPENDENTE: lag tra moto visivo (flusso ottico medio nel video) e velocita' encoder, per cross-correlazione."""
import numpy as np, pandas as pd, subprocess, json, cv2, os
R = "asmile-loggers/asmile-001/"
S = pd.read_csv(R + "_sensors/sensors/sensors_20261109_085334.csv", low_memory=False)
meta = json.load(open(R + "session_20261109_094146/metadata.json"))
off = meta["clock_map_start"]["wall_minus_monotonic_s"]
w = (pd.to_datetime(S.wall) - pd.Timestamp("1970-01-01")).dt.total_seconds()  # wall naive = ora locale del Pi
# wall e' ora locale? calcolo la differenza assoluta e la confronto con la sua mediana
dw = (w.values - S.t_ms.values / 1000)
print("1) wall - t_ms/1000: mediana %.3f s, ptp %.0f ms (tutto il file 3600 s) | clock_map wall-monotonic %.3f s" % (np.median(dw), np.ptp(dw) * 1000, off))
print("   (differenza fra le due costanti = fuso orario/epoca: %.0f s = %.2f h)" % (np.median(dw) - off, (np.median(dw) - off) / 3600))
e = S.dropna(subset=["enc_t_ms"]).drop_duplicates("enc_t_ms")
x = e.enc_t_ms.values - e.t_ms.values
print("2) enc_t_ms - t_ms (riga sensor_hub): mediana %.0f ms, p1 %.0f p99 %.0f, min %.0f max %.0f" % (np.median(x), *np.percentile(x, [1, 99]), x.min(), x.max()))
de = np.diff(e.enc_t_ms.values); print("   passo campioni encoder: mediana %.0f ms p99 %.0f max %.0f ms (n=%d); righe con enc ripetuto: %.1f%%" % (np.median(de), np.percentile(de, 99), de.max(), len(e), 100 * (1 - len(e) / S.enc_t_ms.notna().sum())))
fl = pd.read_csv(R + "session_20261109_094146/frames_left.csv"); fr = pd.read_csv(R + "session_20261109_094146/frames_right.csv")
print("   frame sx %d dx %d; t_ms primo %d ultimo %d (rel %.1f..%.1f s)" % (len(fl), len(fr), fl.t_ms.iloc[0], fl.t_ms.iloc[-1], fl.t_ms.iloc[0] / 1000 - S.t_ms.iloc[0] / 1000, fl.t_ms.iloc[-1] / 1000 - S.t_ms.iloc[0] / 1000))
ie = np.clip(np.searchsorted(e.enc_t_ms.values, fl.t_ms.values), 1, len(e) - 1)
dist = np.minimum(np.abs(e.enc_t_ms.values[ie] - fl.t_ms.values), np.abs(e.enc_t_ms.values[ie - 1] - fl.t_ms.values))
print("   frame -> campione encoder piu' vicino: mediana %.1f max %.0f p99 %.0f ms" % (np.median(dist), dist.max(), np.percentile(dist, 99)))
# 3) flusso ottico
W, H = 160, 100
out = "/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/1b32ebd7-24f0-43c1-a686-c4879d52bcb7/scratchpad/flow.npy"
if not os.path.exists(out):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-f", "h264", "-i", R + "session_20261109_094146_left.h264", "-vf", "scale=%d:%d" % (W, H), "-pix_fmt", "gray", "-vsync", "passthrough", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    buf = p.stdout.read(); fr_ = np.frombuffer(buf, np.uint8).reshape(-1, H, W); print("   frame decodificati", len(fr_))
    mag = np.full(len(fr_), np.nan)
    for i in range(1, len(fr_)):
        f = cv2.calcOpticalFlowFarneback(fr_[i - 1], fr_[i], None, 0.5, 2, 9, 2, 5, 1.1, 0)
        mag[i] = np.median(np.hypot(f[..., 0], f[..., 1])[40:, :])  # meta' bassa = strada
    np.save(out, mag)
mag = np.load(out); n = min(len(mag), len(fl)); mag = mag[:n]; tf = fl.t_ms.values[:n] / 1000
# velocita' encoder (SG 0.3 s) campionata ai frame
from scipy.signal import savgol_filter
tt = e.enc_t_ms.values / 1000; cc = e.enc_wheel_cum.values.astype(float) * (15.760 / 742726)
tg = np.arange(tt[0], tt[-1], 0.02); cg = np.interp(tg, tt, cc); ve = np.abs(savgol_filter(cg, 15, 2, deriv=1, delta=0.02))
ok = np.isfinite(mag)
res = []
for L in np.arange(-0.6, 0.6001, 0.0167):  # passi di 1/60 s
    v = np.interp(tf + L, tg, ve)   # velocita' encoder al tempo (frame + L)
    m = ok & (v > 0.5)
    res.append((L, np.corrcoef(mag[m], v[m])[0, 1]))
res = np.array(res); k = res[:, 1].argmax()
# parabola sui 5 punti attorno al picco
sl = slice(max(k - 3, 0), k + 4); pf = np.polyfit(res[sl, 0], res[sl, 1], 2); Lp = -pf[1] / (2 * pf[0])
print("3) flusso ottico (gray 160x100, mediana meta' bassa) vs |v| encoder, lag L (v campionata a t_frame+L):")
print("   corr a L=0: %.3f ; picco a L=%+.0f ms (corr %.3f), parabola %+.0f ms; corr a +-200 ms: %.3f / %.3f" % (
    np.interp(0, res[:, 0], res[:, 1]), res[k, 0] * 1000, res[k, 1], Lp * 1000, np.interp(-0.2, res[:, 0], res[:, 1]), np.interp(0.2, res[:, 0], res[:, 1])))
# larghezza del picco: lag con corr >= picco - 0.01
w_ = res[res[:, 1] >= res[k, 1] - 0.01, 0]; print("   intervallo lag con corr entro 0.01 dal picco: %+.0f .. %+.0f ms" % (w_.min() * 1000, w_.max() * 1000))
# stabilita' per terzi del giro
for a, b in [(0, 1/3), (1/3, 2/3), (2/3, 1)]:
    idx = np.arange(int(a * n), int(b * n)); r2 = []
    for L in np.arange(-0.4, 0.4001, 0.0167):
        v = np.interp(tf[idx] + L, tg, ve); m = ok[idx] & (v > 0.5); r2.append((L, np.corrcoef(mag[idx][m], v[m])[0, 1]))
    r2 = np.array(r2); print("   terzo %.2f-%.2f: picco a %+.0f ms (corr %.3f)" % (a, b, r2[r2[:, 1].argmax(), 0] * 1000, r2[:, 1].max()))
