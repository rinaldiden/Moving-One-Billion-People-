#!/usr/bin/env python3
"""
decel_frenate_20261123.py - decelerazioni nelle frenate (13-23/11/2026) per tarare lo speed_limiter di #001.
Sola lettura. Fonti:
  - #001: sensors_20261113_145727.csv, velocita'/decel da encoder ruota con PARABOLA ai minimi quadrati sulla DISTANZA
    percorsa nella finestra causale di 0.3 s (stessa matematica di pi/autonomous/speed_limiter.py, classe WheelEncoder._fit).
    m/giro encoder: circ (default 0.3477 = encoder_calibration.json DEPLOYATA, metro 9/11); --circ 0.3374 per l'altra.
  - logger001: velocita' BLE CooSpo (aggiorna ~1/s, ritardo ~0.3 s) + IMU (solo conferma/picco).
Uso: python3 training/eventi/decel_frenate_20261123.py --out DIR
"""
import argparse, os
import numpy as np, pandas as pd

S1 = 'asmile-loggers/asmile-001/_sensors/sensors/sensors_%s.csv'
SL = 'asmile-loggers/asmile-logger/_sensors/sensors/sensors_%s.csv'
WIN = 0.30
HZ = 50.0
K_ENC = 16384.0


def parab_fit(t, s, win=WIN, tmin=6):
    """Per ogni campione k: parabola s(tau)=s0+v tau+0.5 a tau^2 sui campioni in (t_k-win, t_k], tau=t-t_k.
    Ritorna v, a all'istante t_k (nan se finestra corta)."""
    n = len(t); v = np.full(n, np.nan); a = np.full(n, np.nan)
    j0 = 0
    for k in range(n):
        while t[k] - t[j0] > win:
            j0 += 1
        if k - j0 + 1 < tmin or t[k] - t[j0] < 0.1:
            continue
        tau = t[j0:k + 1] - t[k]
        c = np.polyfit(tau, s[j0:k + 1], 2)
        v[k] = c[1]; a[k] = 2 * c[0]
    return v, a


def runs(mask, gap=0):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    cut = np.where(np.diff(idx) > gap + 1)[0]
    st = np.r_[0, cut + 1]; en = np.r_[cut, len(idx) - 1]
    return [(idx[a], idx[b]) for a, b in zip(st, en)]


def load001(sess, circ):
    d = pd.read_csv(S1 % sess, low_memory=False, usecols=[
        't_ms', 'wall', 'imu_ay_g', 'imu_az_g', 'imu_gx_dps', 'imu_gz_dps', 'enc_wheel_cum', 'servo_v', 'lim_zone',
        'brake_out_deg', 'gps_speed_ms'])
    d = d[d.enc_wheel_cum.notna()].reset_index(drop=True)
    d['brake_out_deg'] = pd.to_numeric(d.brake_out_deg, errors='coerce')
    cum = d.enc_wheel_cum.values.astype(float) * circ / K_ENC
    t = d.t_ms.values / 1000.0
    keep = np.r_[True, np.diff(cum) != 0]
    keep |= np.r_[True, np.diff(t) > 0] & (np.arange(len(t)) % 5 == 0)   # anche da fermo
    kt, kc = t[keep], cum[keep]
    v, a = parab_fit(kt, kc)
    # su griglia 50 Hz (tiene l'ultimo valore)
    ix = np.searchsorted(kt, t, side='right') - 1
    d['t'] = t; d['v'] = v[ix]; d['a'] = a[ix]
    d['gps_v'] = d.gps_speed_ms.ffill()
    return d


def events_from(t, v, a, vmin=1.0, amin=0.4, minlen=1.0, dvmin=0.7, fs=HZ):
    """episodi di decelerazione: a_smooth(0.5 s) < -amin, estesi finche' < -0.1."""
    k = int(fs * 0.5)
    a_s = pd.Series(a).rolling(k, center=True, min_periods=3).mean().values
    ev = []
    for i, j in runs(np.nan_to_num(a_s, nan=0) < -amin, gap=int(0.5 * fs)):
        while i > 0 and a_s[i - 1] < -0.1: i -= 1
        while j < len(a_s) - 1 and a_s[j + 1] < -0.1: j += 1
        dur = t[j] - t[i]
        w = int(0.15 * fs)
        def vm(lo, hi):
            x = v[max(0, lo):hi + 1]; x = x[np.isfinite(x)]
            return float(np.mean(x)) if len(x) else np.nan
        v0 = vm(i - w, i + w); v1 = vm(j - w, j + w)
        if not (np.isfinite(v0) and np.isfinite(v1)):
            continue
        if dur < minlen or v0 - v1 < dvmin or v0 < vmin:
            continue
        if ev and ev[-1][0] == i:
            continue
        if ev and i <= ev[-1][1]:      # sovrapposto al precedente: unisci
            pi_, pj, pv0, _, _ = ev[-1]
            ev[-1] = (pi_, j, pv0, v1, a_s)
            continue
        ev.append((i, j, v0, v1, a_s))
    return ev


def ev001(d, circ):
    t = d.t.values; v = d.v.values; a = d.a.values
    out = []
    # tratti in moto: v>0.5
    ev = events_from(t, v, a)
    a_s = pd.Series(a).rolling(25, center=True, min_periods=3).mean().values
    jerk = np.gradient(a_s, 1 / HZ)
    ay = pd.Series((d.imu_ay_g.values - np.nanmedian(d.imu_ay_g.values[np.abs(v) < 0.05])) * 9.81).ewm(span=7).mean().values
    gzs = pd.Series(d.imu_gz_dps.values - np.nanmedian(d.imu_gz_dps.values[np.abs(v) < 0.05])).rolling(13, center=True, min_periods=1).mean().values
    for i, j, v0, v1, _ in ev:
        dur = t[j] - t[i]
        seg = slice(i, j + 1)
        bo = d.brake_out_deg.values[max(0, i - 50):j + 1]
        bm = float(np.nanmax(bo)) if np.isfinite(bo).any() else 0.0
        zf = float(d.lim_zone.iloc[i:j + 1].isin(['OVER', 'RELEASE', 'HYST']).mean())
        nogood = np.isnan(a[seg]).mean()
        # jerk di salita della decel: dal primo punto fino al picco
        ip = i + int(np.nanargmin(a_s[seg]))
        out.append(dict(
            unita='asmile-001', sess='20261113_145727', t_s=round(t[i], 2), ora=d.wall[i][11:19], t_ms0=int(d.t_ms.values[i]),
            fonte_v='encoder_ruota_parabola0.3s', circ=circ,
            v0_kmh=v0 * 3.6, v1_kmh=v1 * 3.6, dur_s=dur, dv_ms=v0 - v1, a_media=(v0 - v1) / dur,
            a_picco=float(-np.nanmin(a_s[seg])), a_picco_grezza=float(-np.nanmin(a[seg])),
            jerk_max_ms3=float(-np.nanmin(jerk[i:ip + 1])) if ip > i else np.nan,
            dist_m=float(np.nansum(np.clip(v[seg], 0, None)) / HZ),
            a_imu_picco=float(np.nanmax(ay[seg])),
            gz_max_dps=float(np.abs(gzs[max(0, i - 25):j + 26]).max()),
            servo_max_deg=bm, lim_frac=zf, gps_v_med_ms=float(np.nanmedian(d.gps_v.values[seg])) if np.isfinite(d.gps_v.values[seg]).any() else np.nan,
            qualita='alta' if nogood < 0.1 else 'bassa'))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--circ', type=float, default=0.3477)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    d = load001('20261113_145727', a.circ)
    E = ev001(d, a.circ)
    df = pd.DataFrame(E)
    df['classe_freno'] = np.where(df.servo_max_deg >= 5, 'servo', np.where(df.lim_frac > 0.2, 'limiter_attivo', 'umano'))
    df.to_csv(f'{a.out}/001_eventi_raw.csv', index=False)
    print(len(df), df.classe_freno.value_counts().to_dict())
    print(df[['ora', 'v0_kmh', 'v1_kmh', 'dur_s', 'a_media', 'a_picco', 'a_imu_picco', 'jerk_max_ms3', 'servo_max_deg', 'classe_freno']].round(2).to_string())


if __name__ == '__main__':
    main()
