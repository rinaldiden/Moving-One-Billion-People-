#!/usr/bin/env python3
"""
impuntate_20261113.py — misura beccheggio (gx), velocita' di beccheggio e az in ogni frenata di #001 del 13/11,
e valuta soglie anti-impuntata. IMU #001: beccheggio = gx, bias -2.67 dps a bici ferma (misurato qui da fermo), avanti = -ay.
Beccheggio = integrale di (gx-bias) con passa-alto (tau 4 s, causale). Segno in avanti: da determinare (colonna 'segno').
"""
import sys, os
import numpy as np, pandas as pd
from scipy.signal import savgol_filter, butter, sosfilt
sys.path.insert(0, os.path.dirname(__file__))
import soglie_dalle_guide as G
G.CENTER = 4112
HZ = 50.0


def carica():
    d = G.load('20261113_145727', 0.3374)
    raw = pd.read_csv(G.S % '20261113_145727', low_memory=False, usecols=['t_ms', 'imu_ax_g', 'imu_az_g', 'imu_gx_dps', 'imu_gy_dps'])
    raw = raw.set_index('t_ms')
    for c in ['imu_ax_g', 'imu_az_g', 'imu_gx_dps', 'imu_gy_dps']:
        d[c] = raw.loc[d.t_ms.values, c].values
    still = np.abs(d.v) < 0.02
    d.attrs['bias_gx'] = float(d.imu_gx_dps[still].median())
    gx = d.imu_gx_dps.values - d.attrs['bias_gx']
    # passa-alto causale tau 4 s sull'angolo: angolo = integrale; hp(angle) = angle - lowpass(angle)
    ang = np.cumsum(gx) / HZ
    a = 1 - np.exp(-1 / (HZ * 4.0)); lp = np.zeros_like(ang); s = 0.0
    for k, x in enumerate(ang):
        s += a * (x - s); lp[k] = s
    d['pitch'] = ang - lp                          # gradi, segno = segno di gx (da confermare)
    d['gxs'] = savgol_filter(gx, 9, 2)              # 0.18 s, dps
    d['azs'] = pd.Series(d.imu_az_g.values).rolling(9, center=True, min_periods=1).mean().values
    return d

if __name__ == '__main__':
    d = carica()
    print('bias gx', d.attrs['bias_gx'], 'n', len(d))
    mv = d.v.values > 1.0
    print('rumore in moto (non frenata) |gxs| p50/p99/p99.9', np.percentile(np.abs(d.gxs[mv]), [50, 99, 99.9]), 'pitch p99', np.percentile(np.abs(d.pitch[mv]), [50, 99, 99.9]))
    d.to_pickle(os.environ.get('OUT', '/tmp/d13.pkl'))
