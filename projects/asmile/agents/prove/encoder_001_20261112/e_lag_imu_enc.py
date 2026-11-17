#!/usr/bin/env python3
"""Lag encoder<->IMU (stesso sensor_hub, stesso t_ms delle camere) su accel ad alta banda, con bootstrap a blocchi."""
import numpy as np, pandas as pd
from scipy.signal import savgol_filter
d = pd.read_csv("asmile-loggers/asmile-001/_sensors/sensors/sensors_20261109_085334.csv", low_memory=False); t0 = d.t_ms.iloc[0] / 1000
tg = np.arange(3021, 3565, 0.01)
e = d.dropna(subset=["enc_wheel_cum"]).drop_duplicates("enc_t_ms")
c = np.interp(tg, e.enc_t_ms.values / 1000 - t0, e.enc_wheel_cum.values * (15.760 / 742726))
im = d.dropna(subset=["imu_ay_g"]).drop_duplicates("t_ms"); ay = np.interp(tg, im.t_ms.values / 1000 - t0, im.imu_ay_g.values)
for W in [0.3, 0.5, 1.0]:
    n = int(W / 0.01) | 1
    a_e = savgol_filter(savgol_filter(c, n, 2, deriv=1, delta=0.01), n, 2, deriv=1, delta=0.01)
    a_i = -savgol_filter(ay, n, 2) * 9.81
    mv = savgol_filter(c, 51, 2, deriv=1, delta=0.01) > 1.5
    Ls = np.arange(-0.4, 0.4001, 0.01)
    def cur(m):
        out = []
        for L in Ls:
            s = int(round(L / 0.01)); out.append(np.corrcoef(a_e[m & np.roll(mv, s)], np.roll(a_i, s)[m & np.roll(mv, s)])[0, 1])
        return np.array(out)
    cu = cur(mv); k = cu.argmax()
    blocks = np.array_split(np.arange(len(tg)), 27); rng = np.random.default_rng(0); pk = []
    for _ in range(100):
        sel = np.concatenate([blocks[i] for i in rng.choice(27, 27)]); m = np.zeros(len(tg), bool); m[sel] = True
        pk.append(Ls[cur(m & mv).argmax()] * 1000)
    print("W=%.1f s: picco %+.0f ms (corr %.3f; a 0 ms %.3f; a +-100 ms %.3f/%.3f)  bootstrap a blocchi 20 s: mediana %+.0f p5-p95 %+.0f..%+.0f ms" % (
        W, Ls[k] * 1000, cu[k], cu[40], cu[30], cu[50], np.median(pk), *np.percentile(pk, [5, 95])))
print("(L>0: l'IMU e' in ANTICIPO sull'encoder di L ms; L<0 in ritardo)")
