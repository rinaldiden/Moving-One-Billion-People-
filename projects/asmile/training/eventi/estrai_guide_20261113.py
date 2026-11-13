#!/usr/bin/env python3
"""
estrai_guide_20261113.py — frenate e sterzate di #001 dal log del 13/11/2026 (sensors_20261113_145727, 2 giri).
Riusa training/eventi/soglie_dalle_guide.py (stessi filtri/classi) con: centro sterzo 4112 (calib 13/11 dopo rimontaggio),
circ encoder 0.3374 m/giro, GPS quasi assente (1940 campioni) -> niente filtro coerenza GPS: dichiarato nel rapporto.
Uso: nice -n 10 python3 training/eventi/estrai_guide_20261113.py --out training/eventi/out_guide_20261113
"""
import argparse, os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import soglie_dalle_guide as G

SESS = '20261113_145727'
G.CENTER = 4112


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--circ', type=float, default=0.3374)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    d = G.load(SESS, a.circ)
    B, ST, SEGS = [], [], []
    for i, j in G.moto_segments(d):
        sg = dict(sess=SESS, t0=float(d.t.values[i]), t1=float(d.t.values[j]), wall=d.wall[i][11:19], wall_fine=d.wall[j][11:19],
                  dist_m=float(d.v.values[i:j].clip(min=0).sum() / G.HZ), vmax_kmh=float(d.v.values[i:j].max() * 3.6),
                  gps_ratio=G.gps_ratio(d, i, j))
        SEGS.append(sg)
        B += G.brake_events(d, [(i, j)], None, None)
        ST += G.steer_events(d, [(i, j)], None, None)
    for e in B:
        bm = e['brake_out_max'] if np.isfinite(e['brake_out_max']) else 0.0
        e['pulita'] = bool(bm < 1.0 and e['lim_frac'] < 0.2)
    pd.DataFrame(B).to_csv(f'{a.out}/frenate.csv', index=False)
    pd.DataFrame(ST).to_csv(f'{a.out}/sterzate.csv', index=False)
    json.dump(SEGS, open(f'{a.out}/segmenti.json', 'w'), indent=1)
    b = pd.DataFrame(B)
    print('segmenti', len(SEGS), 'metri', round(sum(s['dist_m'] for s in SEGS)), 'frenate', len(B), 'sterzate', len(ST))
    print(b.classe.value_counts().to_dict(), 'pulite', int(b.pulita.sum()))

if __name__ == '__main__':
    main()
