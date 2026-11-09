#!/usr/bin/env python3
"""make_json.py MEAS.pkl FIT.json MOVING.pkl OUT.json — scrive calib_asmile-001.json (contratto stereo_common.Calib + metadati)
e RICONTROLLA gli errori % passando dal codice vero (Calib.rectify), non dal modello del fit."""
import sys, os, json, pickle, numpy as np, cv2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from stereo_common import Calib
meas, fitj, mov, out = sys.argv[1:5]
j = json.load(open(fitj)); M = pickle.load(open(meas, 'rb'))
roles = {r['Z_m']: r['role'] for r in j['rows']}
cal = dict(K_left=j['K'], dist_left=j['D'], K_right=j['K_right'], dist_right=j['D_right'], R=j['R'], T=j['T'], size=[1280, 800], baseline_mm=200.0)
json.dump(cal, open('/tmp/_c.json', 'w')); c = Calib.load('/tmp/_c.json'); r = c.rectify(); B = 0.2; fr = r['focal_px']
rp = lambda p, K, D, R, P: cv2.undistortPoints(p.reshape(-1, 1, 2).astype(np.float64), K, D, R=R, P=P).reshape(-1, 2)
pts = []
for m in M:
    p1 = m['b1'][m['ok']]; p2 = m['b2'][m['ok']]
    u1 = rp(p1, c.K1, c.d1, r['R1'], r['P1']); u2 = rp(p2, c.K2, c.d2, r['R2'], r['P2'])
    d = float(np.median(u1[:, 0] - u2[:, 0])); Zs = fr * B / d
    pts.append(dict(Z_m=m['Z'], role=roles[m['Z']], n_frames=int(m['ok'].sum()), disp_rect_px=round(d, 3), Z_stereo_m=round(Zs, 3), err_pct=round(100 * (Zs - m['Z']) / m['Z'], 2)))
    print(f"{m['Z']:5.1f} m {pts[-1]['role']:9s} Z_stereo={Zs:7.3f}  err {pts[-1]['err_pct']:+.2f}%")
p = j['params']
meta = dict(cal)
meta.update({
    'order': 'RL', 'flip180': False, 'd0_px': 0.0, 'focal_rect_px': round(fr, 2), 'focal_fit_px': round(p[3], 1),
    'method': 'calib_001_20261109/fit_verify.py: R,f,k1,k2,pp-destra da dy=0 (SIFT sfondo 7 soste + giro 094146) + 7 soste col metro (1-2-3-5-7-10-15 m) con errore RELATIVO; 4-6-8-12 m SOLO verifica; d0=0 (assorbito da dcx destra).',
    'fit_params': dict(rx_ry_rz_deg=p[:3], fL=p[3], k1_L=p[4], dcx_right_px=p[5], fR=p[6], k1_R=p[7], dcy_right_px=p[8], k2=p[9]),
    'tape_points': pts,
    'source': 'session_20261109_093216 (A1 soste 1-2-3-4-5-6-7-8-10-12-15 m, bersaglio = persona che regge un foglio con scacchiera 7x10 quadretti da 29 mm, NON il cartone da 80 cm del protocollo); dy verifica: 093909 (spinta) + 094146 (giro)',
    'valid_for': 'SOLO asmile #001 (asmile-tirano, hostname asmile / Tailscale asmile-001) con QUESTO set di 2 camere OV9281 come montate il 2026-11-09 (order=RL: cam0=file *_left=fisicamente DESTRA). NON vale per asmile2, asmile-logger o altre unità; se si smonta/sposta una camera va rifatta.',
    'camera_hw': {'model': 'Inno-Maker CAM-MIPIOV9281V2, 2 moduli separati', 'sensor': 'OV9281 mono global shutter 1280x800'},
    'cam_height_m': 0.825, 'baseline_tape_mm': 200.0,
})
json.dump(meta, open(out, 'w'), indent=2); print('scritto', out, 'focal_rect', round(fr, 1))
