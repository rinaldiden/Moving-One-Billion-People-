#!/usr/bin/env python3
"""
soglie_dalle_guide.py — estrae dai log #001 (guide di Daniele) frenate, sterzate, velocita' tenute.
Solo lettura. Uso: python3 training/eventi/soglie_dalle_guide.py --circ 0.3477 --out DIR
Decisioni: tratti in moto = |v|>0.5 m/s; v e acc da Savitzky-Golay (ord.2) sul cumulativo encoder ruota
(16384 count/giro enc, circ = metri per giro ENCODER). IMU #001 avanti = -ay. Il speed_limiter (target 10 km/h)
frena col servo: gli eventi con brake_out_deg alto sono del LIMITER, non di Daniele -> separati.
"""
import argparse, json, os, pickle
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

S = 'asmile-loggers/asmile-001/_sensors/sensors/sensors_%s.csv'
SESS = ['20261108_160150', '20261109_085334']
CENTER, DEG_STEP = 6606, 0.02197
HZ = 50.0
# GUARDIA (2026-11-13): questo script legge SOLO i log grezzi di #001 (encoder ruota). Se in futuro leggera' il registro
# agents/registro_guide, deve usare registro_guide.righe_usabili(): mai righe candidata_imu / qualita bassa / segno_imu non_verificato.
MIN_AMP_DEG = 5.0
V9 = 'training/depth/out_20261112_v9/tracks_20261109_094146.pkl'
BANDS = [(0, 6.5, 5), (6.5, 9, 8), (9, 11, 10), (11, 13.5, 12), (13.5, 99, 15)]


def band(kmh):
    for lo, hi, c in BANDS:
        if lo <= kmh < hi:
            return c


def load(sess, circ):
    d = pd.read_csv(S % sess, low_memory=False,
                    usecols=['t_ms', 'wall', 'imu_ay_g', 'imu_gz_dps', 'enc_wheel_cum', 'enc_steer_raw',
                             'lim_zone', 'brake_out_deg', 'gps_speed_ms'])
    d = d[d.enc_wheel_cum.notna() & (d.enc_steer_raw >= 0)].reset_index(drop=True)
    d['brake_out_deg'] = pd.to_numeric(d.brake_out_deg, errors='coerce')
    m = circ / 16384.0
    cum = d.enc_wheel_cum.values.astype(float) * m
    d['v'] = savgol_filter(cum, 25, 2, deriv=1, delta=1 / HZ)          # 0.5 s
    d['v15'] = savgol_filter(cum, 75, 2, deriv=1, delta=1 / HZ)        # 1.5 s
    d['a'] = savgol_filter(cum, 75, 2, deriv=2, delta=1 / HZ)          # 1.5 s
    d['a_imu'] = -pd.Series(d.imu_ay_g.values * 9.81).rolling(75, center=True, min_periods=1).mean()
    d['steer_deg'] = (d.enc_steer_raw - CENTER) * DEG_STEP
    d['steer_rate'] = savgol_filter(d.steer_deg.values, 15, 2, deriv=1, delta=1 / HZ)   # 0.3 s
    still = np.abs(d.v) < 0.05
    bias = d.imu_gz_dps[still].median() if still.sum() > 500 else 0.0
    d['gz'] = savgol_filter(d.imu_gz_dps.values - bias, 25, 2)
    d['t'] = d.t_ms / 1000.0
    d['sess'] = sess
    # coerenza GPS (blocchi 1 s)
    g = d.gps_speed_ms.ffill()
    d['gps_v'] = g
    return d


def runs(mask, gap=25, minlen=1):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    cut = np.where(np.diff(idx) > gap)[0]
    st = np.r_[0, cut + 1]; en = np.r_[cut, len(idx) - 1]
    return [(idx[a], idx[b]) for a, b in zip(st, en) if idx[b] - idx[a] >= minlen]


def moto_segments(d):
    return [(i, j) for i, j in runs(np.abs(d.v.values) > 0.5, gap=500) if (j - i) / HZ > 5]


def gps_ratio(d, i, j):
    s = d.iloc[i:j]
    ok = s.gps_v > 1.0
    if ok.sum() < 50:
        return np.nan
    return float(np.median(s.v[ok].abs() / s.gps_v[ok]))


def perc_load():
    p = pickle.load(open(V9, 'rb'))
    return np.array(p['t_ms']), p['cs']


def perc_at(tms, pt, cs, t_ms0):
    k = int(np.argmin(np.abs(pt - t_ms0)))
    if abs(pt[k] - t_ms0) > 150:
        return None
    z = cs[k]['firstZ']['arc']
    return dict(Z_arc=z, Z_str=cs[k]['firstZ']['str'])


def brake_events(d, seg, pt, cs):
    ev = []
    for i0, j0 in seg:
        a = d.a.values[i0:j0]
        off = i0
        for i, j in runs(a < -0.3, gap=25):
            i += off; j += off
            while i > i0 and d.a.values[i - 1] < -0.1: i -= 1
            while j < j0 - 1 and d.a.values[j + 1] < -0.1: j += 1
            dur = (j - i) / HZ
            v0 = float(d.v15.values[i]); v1 = float(d.v15.values[j])
            if dur < 1.0 or v0 - v1 < 0.5 or v0 < 0.7:
                continue
            if v1 * 3.6 < -1.0:      # giro 3: encoder all indietro (v finale < -1 km/h) = dato non valido, scartato (negativi piccoli = overshoot smoothing)
                continue
            bo = d.brake_out_deg.values[max(0, i - 25):j + 1]
            lim = bool(np.nanmax(bo) > 5 or np.nanmean(bo) > 2) if np.isfinite(bo).any() else False
            limsrc = d.lim_zone.iloc[i:j + 1].isin(['OVER', 'RELEASE', 'HYST']).mean() if 'lim_zone' in d else 0
            e = dict(sess=d.sess[i], t0=float(d.t.values[i]), t_ms0=int(d.t_ms.values[i]), wall=d.wall[i][11:19],
                     v0_kmh=v0 * 3.6, v1_kmh=v1 * 3.6, dur_s=dur, dv=v0 - v1,
                     a_mean=(v0 - v1) / dur, a_peak=float(-d.a.values[i:j + 1].min()),
                     a_imu_mean=float(d.a_imu.values[i:j + 1].mean()),
                     sp_m=float(d.v.values[i:j + 1].clip(min=0).sum() / HZ),
                     brake_out_max=float(np.nanmax(bo)) if np.isfinite(bo).any() else np.nan,
                     limiter=lim, lim_attivo=limsrc > 0.5, lim_frac=float(limsrc))
            e['fascia'] = band(e['v0_kmh'])
            # classe: sotto ACTIVATE_KMH (8) il limiter rilascia e non puo' fermare la bici -> stop = umano;
            # senza servo (<5 deg) = umano; altrimenti freno del LIMITER (servo) -> non e' una guida
            bmx = e['brake_out_max']
            # giro 2 (scettico): "frenata di Daniele" = stop con servo <1 grado E frazione di lim_zone attiva <0.2.
            # stop con servo/limiter attivo = 'stop_limiter' (contaminato, escluso dal fit)
            bm = 0.0 if not np.isfinite(bmx) else bmx
            if e['v1_kmh'] < 2.0:
                e['classe'] = 'stop_umano' if (bm < 1.0 and e['lim_frac'] < 0.2) else 'stop_limiter'
            else:
                e['classe'] = 'umano' if not (bm >= 5) else 'limiter'
            if ev and ev[-1]['t_ms0'] == e['t_ms0'] and ev[-1]['sess'] == e['sess']:
                continue
            if pt is not None and d.sess[i] == '20261109_085334':
                pr = perc_at(None, pt, cs, e['t_ms0'])
                if pr and pr['Z_arc'] is not None:
                    e.update(Z_arc=float(pr['Z_arc']), ttc=float(pr['Z_arc']) / max(v0, 0.1))
                if pr and pr['Z_str'] is not None:
                    e['Z_str'] = float(pr['Z_str'])
            ev.append(e)
    return ev


def steer_events(d, seg, pt, cs):
    ev = []
    for i0, j0 in seg:
        m = np.zeros(len(d), bool)
        m[i0:j0] = (np.abs(d.gz.values[i0:j0]) > 22) & (d.v.values[i0:j0] > 1.0)
        for i, j in runs(m, gap=25):
            if (j - i) / HZ < 0.5:
                continue
            s = d.iloc[i:j + 1]
            # inizio sterzata: risalgo finche' |steer_rate|>5 deg/s
            k = i
            while k > i0 and abs(d.steer_rate.values[k]) > 5 and i - k < 150: k -= 1
            base = d.steer_deg.values[k]
            pk = int(np.argmax(np.abs(s.gz.values)))
            e = dict(sess=d.sess[i], t0=float(d.t.values[i]), t_ms0=int(d.t_ms.values[i]), dur_s=(j - i) / HZ,
                     v_kmh=float(s.v.mean() * 3.6), gz_peak=float(np.abs(s.gz).max()),
                     k_med=float(np.median(np.abs(s.gz) * np.pi / 180 / s.v.clip(lower=0.5))),
                     amp_deg=float(np.abs(s.steer_deg - base).max()), rate_peak=float(np.abs(s.steer_rate).max()),
                     anticipo_s=float((i - k) / HZ), fascia=band(s.v.mean() * 3.6))
            if pt is not None and d.sess[i] == '20261109_085334':
                pr = perc_at(None, pt, cs, int(d.t_ms.values[k]))
                if pr and pr['Z_arc'] is not None:
                    e['Z_arc_inizio'] = float(pr['Z_arc'])
            if e['amp_deg'] < MIN_AMP_DEG:      # giro 2: sotto 5 gradi di manubrio non e' una sterzata (deriva/rumore)
                continue
            ev.append(e)
    return ev


def pct(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) == 0: return (np.nan,) * 3
    return tuple(np.percentile(x, [25, 50, 75]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--circ', type=float, default=0.3477)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pt, cs = perc_load()
    B, ST, VT, SEGS = [], [], [], []
    for sess in SESS:
        d = load(sess, a.circ)
        for i, j in moto_segments(d):
            gr = gps_ratio(d, i, j)
            sg = dict(sess=sess, t0=float(d.t.values[i]), t1=float(d.t.values[j]), wall=d.wall[i][11:19],
                      dist_m=float(d.v.values[i:j].clip(min=0).sum() / HZ), vmax_kmh=float(d.v.values[i:j].max() * 3.6),
                      gps_ratio=gr, limiter=bool(d.brake_out_deg.values[i:j].astype(float)[np.isfinite(d.brake_out_deg.values[i:j].astype(float))].size > 0),
                      brake_out_n=int(np.isfinite(d.brake_out_deg.values[i:j].astype(float)).sum()))
            # tratto scartato se encoder incoerente col GPS (>30%) o breve
            sg['usato'] = bool(np.isfinite(gr) and 0.7 < gr < 1.3)
            sg['motivo'] = '' if sg['usato'] else ('gps_incoerente' if np.isfinite(gr) else 'gps_assente')
            SEGS.append(sg)
            if not sg['usato']:
                continue
            B += brake_events(d, [(i, j)], pt, cs)
            ST += steer_events(d, [(i, j)], pt, cs)
            # velocita' per contesto (1 Hz)
            for k in range(i, j, 50):
                v = d.v.values[k]
                if v < 0.5: continue
                ctx = 'curva' if abs(d.gz.values[k]) > 22 else ('rettilineo' if abs(d.gz.values[k]) < 8 and abs(d.steer_deg.values[k]) < 5 else 'altro')
                r = dict(sess=sess, t_ms=int(d.t_ms.values[k]), v_kmh=float(v * 3.6), ctx=ctx,
                         lim=str(d.lim_zone.iloc[k]) if isinstance(d.lim_zone.iloc[k], str) else 'off',
                         steer_rate=float(abs(d.steer_rate.values[k])), steer_deg=float(abs(d.steer_deg.values[k])),
                         k=float(abs(d.gz.values[k]) * np.pi / 180 / max(v, .5)))
                if sess == '20261109_085334':
                    pr = perc_at(None, pt, cs, r['t_ms'])
                    if pr: r['Z_arc'] = pr['Z_arc']
                VT.append(r)
    pd.DataFrame(B).to_csv(f'{a.out}/frenate.csv', index=False)
    pd.DataFrame(ST).to_csv(f'{a.out}/sterzate.csv', index=False)
    pd.DataFrame(VT).to_csv(f'{a.out}/velocita_1hz.csv', index=False)
    json.dump(SEGS, open(f'{a.out}/segmenti.json', 'w'), indent=1)
    print('circ', a.circ, 'segmenti', len(SEGS), 'usati', sum(s['usato'] for s in SEGS), 'frenate', len(B), 'sterzate', len(ST), 'vel1hz', len(VT))


if __name__ == '__main__':
    main()
