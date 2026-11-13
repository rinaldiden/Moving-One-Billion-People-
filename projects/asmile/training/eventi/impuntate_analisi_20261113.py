#!/usr/bin/env python3
"""impuntate_analisi_20261113.py — frenate #001 del 13/11: beccheggio (gx), velocita' di beccheggio, az, decel IMU; simulazione causale delle regole
anti-impuntata. Segno: gx>0 = muso giu' (posteriore su), CONFERMATO dal video (corr dy~gx -0.77 lag 0 in 2 giri; phaseCorrelate dy>0=contenuto giu')
e dalla regola della mano destra (X=sinistra). Uso: python3 impuntate_analisi_20261113.py  (richiede out_guide_20261113/frenate.csv)."""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import impuntate_20261113 as I
HZ = 50.0
OUT = 'training/eventi/out_guide_20261113'


def ema(x, n):
    a = 2.0 / (n + 1); y = np.zeros(len(x)); s = x[0]
    for k, v in enumerate(x):
        s += a * (v - s); y[k] = s
    return y


def episodi(m, gap=50):
    idx = np.where(m)[0]
    return [] if len(idx) == 0 else [int(idx[0])] + [int(idx[i]) for i in range(1, len(idx)) if idx[i] - idx[i - 1] > gap]


def main():
    d = I.carica(); T = d.t_ms.values
    still = d.v.abs() < 0.02
    ay = (d.imu_ay_g.values - d.imu_ay_g[still].median()) * 9.81            # + = frenata (avanti = -ay)
    dec = ema(ay, 7)                                                         # causale ~0.14 s
    gx = d.imu_gx_dps.values - d.attrs['bias_gx']
    rate = ema(gx, 5)                                                        # causale ~0.1 s
    cs = np.cumsum(gx) / HZ
    d03 = np.r_[np.zeros(15), cs[15:] - cs[:-15]]                           # variazione beccheggio in 0.3 s (gradi, + = muso giu')
    pitchHP = d.pitch.values                                                 # passa-alto tau 4 s (la regola attuale)
    RULES = {
        'attuale (rate>15 o beccheggio_HP>2)': (rate > 15) | (pitchHP > 2.0),
        'P1 dec>=2.0 e d0.3s>=1.5': (dec >= 2.0) & (d03 >= 1.5),
        'P2 dec>=2.5 e d0.3s>=1.5': (dec >= 2.5) & (d03 >= 1.5),
        'P3 dec>=2.0 e d0.3s>=2.0': (dec >= 2.0) & (d03 >= 2.0),
        'P4 d0.3s>=3.0 (senza decel)': d03 >= 3.0,
        'cap dec>=3.0': dec >= 3.0, 'cap dec>=3.5': dec >= 3.5,
    }
    b = pd.read_csv(f'{OUT}/frenate.csv')
    rows = []
    for _, e in b.iterrows():
        i = int(np.searchsorted(T, e.t_ms0)); j = min(len(d) - 1, i + int(e.dur_s * HZ)); s = slice(i - 25, j + 25)
        pk = i - 25 + int(np.argmax(pitchHP[s]))
        r = dict(wall=e.wall, classe=e.classe, pulita=bool(e.pulita), v0_kmh=round(e.v0_kmh, 1), v1_kmh=round(e.v1_kmh, 1),
                 dec_imu_picco=round(float(dec[s].max()), 2), dec_ruota_picco=round(float(e.a_peak), 2),
                 pitch_picco_deg=round(float(pitchHP[pk]), 2), d03_max_deg=round(float(d03[s].max()), 2),
                 rate_picco_dps=round(float(rate[s].max()), 1), az_min_g=round(float(d.imu_az_g.values[s].min()), 2),
                 az_max_g=round(float(d.imu_az_g.values[s].max()), 2), v_al_picco_kmh=round(float(d.v.values[pk] * 3.6), 1),
                 servo_max_deg=e.brake_out_max)
        for nome, m in RULES.items():
            hit = np.where(m[i - 25:j + 1])[0]
            r['scatta:' + nome] = bool(len(hit))
        rows.append(r)
    R = pd.DataFrame(rows)
    R['impuntata'] = (R.dec_imu_picco >= 3.5) & (R.d03_max_deg >= 3.0)          # criterio: decel forte + muso giu' >=3 gradi in 0.3 s
    R.to_csv(f'{OUT}/impuntate_per_frenata.csv', index=False)
    # soglie sulle due impuntate note: anticipo rispetto al picco di beccheggio
    lead = {}
    for nome_ev, (a0, a1) in {'15:03:51': (19050, 19300), '15:08:52': (34200, 34400)}.items():
        k = a0 + int(np.argmax(pitchHP[a0:a1])); lead[nome_ev] = {}
        for nome, m in RULES.items():
            w = np.where(m[k - 80:k])[0]
            lead[nome_ev][nome] = None if len(w) == 0 else dict(anticipo_s=round((80 - w[0]) / HZ, 2), v_kmh=round(float(d.v.values[k - 80 + w[0]] * 3.6), 1))
    # falsi allarmi in moto (v>1 km/h), episodi/min
    mv = d.v.values > 1 / 3.6; mins = mv.sum() / HZ / 60
    fa = {}
    for nome, m in RULES.items():
        st = episodi(mv & m)
        fa[nome] = dict(episodi=len(st), ogni_min=round(len(st) / mins, 2),
                        quando=[(d.wall[s][11:19], round(float(d.v.values[s] * 3.6), 1)) for s in st][:40])
    rum = dict(minuti_in_moto=round(mins, 2), rate_p99=float(np.percentile(rate[mv], 99)), rate_p999=float(np.percentile(rate[mv], 99.9)),
               d03_p99=float(np.percentile(d03[mv], 99)), d03_p999=float(np.percentile(d03[mv], 99.9)),
               pitchHP_p99=float(np.percentile(pitchHP[mv], 99)), dec_p99=float(np.percentile(dec[mv], 99)), bias_gx=d.attrs['bias_gx'])
    json.dump(dict(anticipo=lead, falsi_allarmi=fa, rumore=rum), open(f'{OUT}/impuntate_soglie.json', 'w'), indent=1)
    pd.set_option('display.width', 250)
    print(R[R.impuntata | R['scatta:attuale (rate>15 o beccheggio_HP>2)'] | R['scatta:P1 dec>=2.0 e d0.3s>=1.5']].T.to_string())
    print(json.dumps(lead, indent=1)); print(json.dumps({k: (v['episodi'], v['ogni_min']) for k, v in fa.items()}, indent=1)); print(rum)
    cnt = {n: int(R['scatta:' + n].sum()) for n in RULES}; print('frenate su', len(R), 'con scatto', cnt)
    print('impuntata (criterio):', R[R.impuntata][['wall', 'classe', 'v0_kmh', 'dec_imu_picco', 'pitch_picco_deg', 'd03_max_deg']].to_string())

main()
