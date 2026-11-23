#!/usr/bin/env python3
"""Frenate dal logger001 con velocita' BLE CooSpo (1 Hz, ritardo ~0.3 s): qualita' BASSA per costruzione.
Evento = serie di aggiornamenti consecutivi con v in calo, dv totale >= 1.0 m/s, v0 >= 1.5 m/s.
a_media = dv/dt fra primo e ultimo aggiornamento (+-0.5 s di incertezza sul tempo). Il picco non e' misurabile a 1 Hz."""
import sys, numpy as np, pandas as pd
P = 'asmile-loggers/asmile-logger/_sensors/sensors/sensors_%s.csv'
FILES = ['20261113_125003', '20261118_105244', '20261119_154708', '20261119_171140', '20261121_143034', '20261121_152154']
rows = []
for s in FILES:
    d = pd.read_csv(P % s, usecols=['t_ms', 'wall', 'imu_ax_g', 'imu_ay_g', 'imu_az_g', 'imu_gz_dps', 'ble_wheel_evt', 'ble_speed_ms'])
    b = d[d.ble_wheel_evt.notna()]
    u = b[b.ble_wheel_evt.diff() != 0]
    t = u.t_ms.values / 1000.0; v = u.ble_speed_ms.values; w = u.wall.values
    tt = d.t_ms.values / 1000.0
    i = 0
    while i < len(v) - 1:
        if v[i] >= 1.5 and v[i + 1] < v[i] - 0.1 and t[i + 1] - t[i] < 2.5:
            j = i
            while j + 1 < len(v) and v[j + 1] < v[j] + 0.05 and t[j + 1] - t[j] < 2.5:
                j += 1
            dv = v[i] - v[j]
            if dv >= 1.0 and t[j] > t[i]:
                sel = (tt >= t[i] - 0.3) & (tt <= t[j] + 0.3)
                ax = d.imu_ax_g.values[sel]; ay = d.imu_ay_g.values[sel]
                rows.append(dict(unita='logger001', sess=s, ora=w[i][11:19], t_s=round(t[i], 1), fonte_v='BLE_1Hz', v0_kmh=v[i] * 3.6, v1_kmh=v[j] * 3.6,
                                 dur_s=t[j] - t[i], dv_ms=dv, a_media=dv / (t[j] - t[i]), a_picco=np.nan, jerk_max_ms3=np.nan,
                                 dist_m=float(np.trapezoid(v[i:j + 1], t[i:j + 1])), n_upd=j - i + 1,
                                 ax_media_g=float(ax.mean()), ay_media_g=float(ay.mean()), gz_max_dps=float(np.abs(d.imu_gz_dps.values[sel]).max()), qualita='bassa'))
            i = j + 1
        else:
            i += 1
df = pd.DataFrame(rows)
df.to_csv(sys.argv[1], index=False)
print(len(df)); print(df.groupby('sess').size())
print(df[['ora','v0_kmh','v1_kmh','dur_s','a_media','ax_media_g','ay_media_g','gz_max_dps']].round(2).to_string())
print('corr a_media vs ax', np.corrcoef(df.a_media, df.ax_media_g)[0,1], 'vs ay', np.corrcoef(df.a_media, df.ay_media_g)[0,1])
