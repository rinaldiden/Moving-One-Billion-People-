#!/usr/bin/env python3
"""fit_verify.py (asmile #001, 2026-11-09) — fit rettifica+focale SOLO sulle soste di FIT, verifica sulle soste mai usate.
Input: meas3.pkl (da m0/m1/m3) con, per sosta: Z metro, coppie board (b1,b2, mask ok) e match SIFT sfondo (s1,s2).
Modello: params (rx,ry,rz,f,k1) -> stereoRectify (T=[-B,0,0], d0=0 per costruzione).
Residui: dy=0 su match SIFT di TUTTA l'immagine + (d_rect(board) - f_rect*B/Z) sulle sole soste di FIT.
Uso: fit_verify.py MEAS.pkl OUT.json [--fit 0,1,2,4,6,8,10] [--k1]"""
import sys, json, pickle, argparse
import numpy as np, cv2
from scipy.optimize import least_squares
W, H, B = 1280, 800, 0.2
ap = argparse.ArgumentParser(); ap.add_argument('meas'); ap.add_argument('out')
ap.add_argument('--fit', default='0,1,2,4,6,8,10'); ap.add_argument('--k1', action='store_true'); ap.add_argument('--simple', action='store_true'); ap.add_argument('--k2', action='store_true'); ap.add_argument('--dcy', type=float, default=20.0); ap.add_argument('--pl', type=float, default=1e-9, help='limite scarto punto principale SINISTRA (px)'); ap.add_argument('--k3', type=float, default=0.0, help='limite |k3| (0=fisso a 0)'); ap.add_argument('--ty', type=float, default=0.0, help='limite |Ty|,|Tz| mm (0=fissi a 0)'); ap.add_argument('--extra', help='pkl m4 con match in movimento da AGGIUNGERE al dy (solo sessione --extra-sid)'); ap.add_argument('--extra-sid', default='094146')
a = ap.parse_args()
M = pickle.load(open(a.meas, 'rb')); fit = [int(x) for x in a.fit.split(',')]; ver = [i for i in range(len(M)) if i not in fit]
rng = np.random.default_rng(0)

def rect(p):
    """p = rx,ry,rz (deg), fL, k1L, dcx, fR, k1R, dcy, k2 (k2 comune).  dcx/dcy = scarto punto principale camera DESTRA (px).
    Con --simple: fR=fL, k1R=k1L, dcy=0, k2=0."""
    rx, ry, rz, fL, k1L, dcx, fR, k1R, dcy, k2, ty, tz, dlx, dly, k3 = p     # ty,tz = componenti verticale/profondita' di T (mm), |T|=B
    K1 = np.array([[fL, 0, W/2 + dlx], [0, fL, H/2 + dly], [0, 0, 1.]]); K2 = np.array([[fR, 0, W/2 + dlx + dcx], [0, fR, H/2 + dly + dcy], [0, 0, 1.]])
    D1 = np.array([k1L, k2, 0, 0, k3]); D2 = np.array([k1R, k2, 0, 0, k3])
    R = cv2.Rodrigues(np.radians([rx, ry, rz]))[0]; T = np.array([[-np.sqrt(B*B - (ty/1000)**2 - (tz/1000)**2)], [ty/1000], [tz/1000]])
    R1, R2, P1, P2, *_ = cv2.stereoRectify(K1, D1, K2, D2, (W, H), R, T, flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    return K1, K2, D1, D2, R, T, R1, R2, P1, P2

def proj(p, p1, p2):
    """rotazioni di rettifica da stereoRectify, proiezione con f=fL (niente zoom): d_atteso = fL*B/Z esatto."""
    K1, K2, D1, D2, _, _, R1, R2, P1, P2 = rect(p); f = p[3]
    def one(pt, Rr, Kc, Dc):
        n = cv2.undistortPoints(pt.reshape(-1, 1, 2).astype(np.float64), Kc, Dc).reshape(-1, 2)
        v = np.hstack([n, np.ones((len(n), 1))]) @ Rr.T
        return f * v[:, :2] / v[:, 2:3]
    return one(p1, R1, K1, D1), one(p2, R2, K2, D2), f

S1 = np.vstack([m['s1'] for m in M]); S2 = np.vstack([m['s2'] for m in M])
if a.extra:   # match in movimento (solo dy): coprono tutta l'immagine, bordi compresi
    E = pickle.load(open(a.extra, 'rb'))[a.extra_sid]; S1 = np.vstack([S1, E[0]]); S2 = np.vstack([S2, E[1]])
sel = rng.choice(len(S1), min(25000, len(S1)), replace=False); S1, S2 = S1[sel], S2[sel]
T1 = {i: M[i]['b1'][M[i]['ok']] for i in range(len(M))}; T2 = {i: M[i]['b2'][M[i]['ok']] for i in range(len(M))}

def tape_d(p, i):
    u1, u2, fr = proj(p, T1[i], T2[i]); return float(np.median(u1[:, 0] - u2[:, 0])), fr

def expand(q):
    q = list(q)
    if a.simple:   # rx,ry,rz,f,k1,dcx
        return [q[0], q[1], q[2], q[3], q[4], q[5], q[3], q[4], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    return q

def resid_q(q): return resid(expand(q))

def resid(p):
    u1, u2, fr = proj(p, S1, S2); z = (u1[:, 1] - u2[:, 1]) / 0.5; r = [np.sign(z) * np.sqrt(2 * (np.sqrt(1 + z * z) - 1))]   # soft-L1 a mano sul solo dy
    for i in fit:
        d, fr = tape_d(p, i); r.append(np.array([(d / (fr * B / M[i]['Z']) - 1.0) / 0.01 * 40.0]))   # errore RELATIVO (come l'errore % di profondita')   # peso x3: poche misure, molto precise
    return np.concatenate(r)

best = None; DCY = a.dcy; TY = a.ty; PL = a.pl; K3 = a.k3 if a.k3 > 0 else 1e-9
if a.simple:
    lo = [-20, -20, -20, 500, -0.6 if a.k1 else -1e-9, -80]; hi = [20, 20, 20, 2500, 0.6 if a.k1 else 1e-9, 80]; x0 = [-5.8, 0.0, 0.2, 1140., 0.0, -40.]
else:
    lo = [-20, -20, -20, 500, -0.8, -150, 500, -0.8, -DCY, -1.0 if a.k2 else -1e-9, -TY if (a.ty > 0) else -1e-9, -TY if (a.ty > 0) else -1e-9, -PL, -PL, -K3]; hi = [20, 20, 20, 2500, 0.8, 150, 2500, 0.8, DCY, 1.0 if a.k2 else 1e-9, TY if (a.ty > 0) else 1e-9, TY if (a.ty > 0) else 1e-9, PL, PL, K3]
    x0 = [-5.8, 0.0, 0.2, 1140., -0.2, -40., 1140., -0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
best = least_squares(resid_q, x0, bounds=(lo, hi), loss='linear')
p = np.array(expand(best.x)); K, K2, D, D2, R, T, R1, R2, P1, P2 = rect(p); fr = p[3]
print('rx/ry/rz=%.3f/%.3f/%.3f deg  fL=%.1f fR=%.1f  k1L=%+.4f k1R=%+.4f k2=%+.4f  dcx_destra=%+.2f dcy_destra=%+.2f px  Ty=%+.1f Tz=%+.1f mm  pp_sinistra=%+.1f,%+.1f k3=%+.4f' % (p[0], p[1], p[2], p[3], p[6], p[4], p[7], p[9], p[5], p[8], p[10], p[11], p[12], p[13], p[14]))
rows = []
for i in range(len(M)):
    d, fr_ = tape_d(p, i); Zs = fr_ * B / d
    rows.append(dict(Z_m=M[i]['Z'], disp_rect_px=round(d, 3), Z_stereo_m=round(Zs, 3), err_pct=round(100 * (Zs - M[i]['Z']) / M[i]['Z'], 2),
                     role='fit' if i in fit else 'verifica', n_frames=int(M[i]['ok'].sum())))
    print(f"{M[i]['Z']:5.1f} m  {rows[-1]['role']:9s} d={d:7.2f}  Z={Zs:7.3f}  err {rows[-1]['err_pct']:+6.2f}%")
u1, u2, _ = proj(p, S1, S2); dy = u1[:, 1] - u2[:, 1]
print('dy SIFT sfondo (fit set) mediana|dy|=%.3f p95=%.3f' % (np.median(abs(dy)), np.percentile(abs(dy), 95)))
json.dump(dict(params=p.tolist(), K=K.tolist(),  K_right=K2.tolist(), D=D.tolist(), D_right=D2.tolist(), R=R.tolist(), T=T.ravel().tolist(), f_rect=float(fr), rows=rows), open(a.out, 'w'), indent=1)
