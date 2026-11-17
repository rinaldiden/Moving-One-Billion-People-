#!/usr/bin/env python3
"""fit_joint_pm.py (asmile #001, 2026-11-09 pomeriggio) - rifit joint: rettifica + focale + k1,k2 PER CAMERA + dcy largo + Ty,Tz.
Punti: soste col metro (mattina 093216 + pomeriggio 153251 centro) + bordi del pomeriggio con Z dalla posa PnP della scacchiera
(quadretto SQ ricavato dalle soste centrali col metro, indipendente dalla disparita'); dy=0 su SIFT (mattina in moto + pomeriggio sfondo)
e sugli angoli della scacchiera. Split deciso PRIMA (vedi FIT_STARTS): le soste HOLD non entrano mai nel fit.
Uso: fit_joint_pm.py SCRATCH_DIR SESS(both|pm) OUT.json   (SCRATCH_DIR contiene meas3.pkl, moving.pkl, pm_sift.pkl, boards_pm.pkl)"""
import sys, json, pickle
import numpy as np, cv2
from scipy.optimize import least_squares
SP, SESS, OUT = sys.argv[1:4]
W, H, B = 1280, 800, 0.2
MFIT = [0, 1, 2, 4, 6, 8, 10]          # mattina 1-2-3-5-7-10-15 m
MHOLD = [3, 5, 7, 9]                   # mattina 4-6-8-12 m (mai nel fit)
rng = np.random.default_rng(0)
M = pickle.load(open(f'{SP}/meas3.pkl', 'rb')); MOV = pickle.load(open(f'{SP}/moving.pkl', 'rb'))
PM = pickle.load(open(f'{SP}/pm_sift.pkl', 'rb')); BR = pickle.load(open(f'{SP}/boards_pm.pkl', 'rb'))
def sub(a, b, n):
    k = rng.choice(len(a), min(n, len(a)), replace=False); return a[k], b[k]
mS1 = np.vstack([m['s1'] for m in M]); mS2 = np.vstack([m['s2'] for m in M])
mv1 = np.vstack([MOV[k][0] for k in MOV]); mv2 = np.vstack([MOV[k][1] for k in MOV])
SIFT_AM = [sub(mS1, mS2, 6000), sub(mv1, mv2, 8000)]
SIFT_PM = [sub(PM[0], PM[1], 8000)]

def rect(p):
    rx, ry, rz, fL, fR, k1L, k2L, k1R, k2R, dcx, dcy, ty, tz, dlx, dly, k3L, k3R = p
    K1 = np.array([[fL, 0, W/2+dlx], [0, fL, H/2+dly], [0, 0, 1.]]); K2 = np.array([[fR, 0, W/2+dlx+dcx], [0, fR, H/2+dly+dcy], [0, 0, 1.]])
    D1 = np.array([k1L, k2L, 0, 0, k3L]); D2 = np.array([k1R, k2R, 0, 0, k3R])
    R = cv2.Rodrigues(np.radians([rx, ry, rz]))[0]; T = np.array([[-np.sqrt(B*B-(ty/1000)**2-(tz/1000)**2)], [ty/1000], [tz/1000]])
    R1, R2, P1, P2, *_ = cv2.stereoRectify(K1, D1, K2, D2, (W, H), R, T, flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    return K1, K2, D1, D2, R, T, R1, R2, P1, P2
def proj(p, p1, p2, cache=None):
    K1, K2, D1, D2, _, _, R1, R2, P1, P2 = cache or rect(p); f = p[3]
    def one(pt, Rr, Kc, Dc):
        n = cv2.undistortPoints(pt.reshape(-1, 1, 2).astype(np.float64), Kc, Dc).reshape(-1, 2)
        v = np.hstack([n, np.ones((len(n), 1))]) @ Rr.T; return f*v[:, :2]/v[:, 2:3]
    return one(p1, R1, K1, D1), one(p2, R2, K2, D2)
def objpts(pat):
    c, r = pat; return np.array([[i % c, i//c, 0] for i in range(c*r)], np.float64)
def board_stats(p, run, cache, nf=4):
    """d mediana (px rettificati, scala f=fL), tz in quadretti (PnP IPPE sul sinistro rettificato), dy angoli"""
    fr = run['frames']; D = []; TZ = []; DY = []; TX = []
    Kc = np.array([[p[3], 0, 0], [0, p[3], 0], [0, 0, 1.]])
    for k, f in enumerate(fr):
        u1, u2 = proj(p, f['b1'], f['b2'], cache); D.append(u1[:, 0]-u2[:, 0]); DY.append(u1[:, 1]-u2[:, 1])
        if k < nf or True:
            ok, rv, tv = cv2.solvePnP(objpts(f['pat']), u1.reshape(-1, 1, 2), Kc, None, flags=cv2.SOLVEPNP_IPPE)
            if ok: TZ.append(tv[2, 0]); TX.append(tv[0, 0])
    return float(np.median(np.concatenate(D))), float(np.median(TZ)), float(np.median(np.concatenate(DY))), float(np.median(TX))
def tape_d(p, m, cache):
    u1, u2 = proj(p, m['b1'][m['ok']], m['b2'][m['ok']], cache); return float(np.median(u1[:, 0]-u2[:, 0]))

sessions_for_dy = SIFT_PM + (SIFT_AM if SESS == 'both' else [])
mfit = MFIT if SESS == 'both' else []
fitruns = [r for r in BR if r['fit']]
REPW = float(__import__('os').environ.get('REPW', '0.5'))
NAMES = 'rx ry rz fL fR k1L k2L k1R k2R dcx dcy ty tz dlx dly k3L k3R SQ z0m z0p dyoff'.split()
MW = float(__import__('os').environ.get('MW', '1'))
DYW = float(__import__('os').environ.get('DYW', '0.5'))
def resid(q):
    p = q[:17]; SQ, z0m, z0p, dyoff = q[17:21]; cache = rect(p); r = []
    for si, (S1, S2) in enumerate(sessions_for_dy):
        u1, u2 = proj(p, S1, S2, cache); z = (u1[:, 1]-u2[:, 1]-(dyoff if si == 0 else 0))/0.5; r.append(np.sign(z)*np.sqrt(2*(np.sqrt(1+z*z)-1)))
    dyb = []
    for run in fitruns:
        d, tz, dy, _ = board_stats(p, run, cache); Zs = p[3]*B/d; Zp = SQ*tz
        if run['pos'] == 'C':
            r.append(np.array([(Zs/(run['nom']+z0p)-1)*4000, (Zp/(run['nom']+z0p)-1)*2000]))
        else:
            r.append(np.array([(Zs/Zp-1)*4000]))
        dyb.append(np.array([(f_dy) for f_dy in []]))
    # reprojection PnP (sinistra e destra rettificate): vincola k1,k2,f per camera con la geometria planare della scacchiera
    Kc = np.array([[p[3], 0, 0], [0, p[3], 0], [0, 0, 1.]])
    for run in fitruns:
        for f in run['frames'][:5]:
            u1, u2 = proj(p, f['b1'], f['b2'], cache)
            for u in (u1, u2):
                o = objpts(f['pat'])
                ok, rv, tv = cv2.solvePnP(o, u.reshape(-1, 1, 2), Kc, None, flags=cv2.SOLVEPNP_IPPE)
                pr = cv2.projectPoints(o, rv, tv, Kc, None)[0].reshape(-1, 2); r.append(np.clip((pr-u).ravel()/0.4, -6, 6)*REPW)
    # dy angoli scacchiera (fit runs)
    for run in fitruns:
        for f in run['frames'][:6]:
            u1, u2 = proj(p, f['b1'], f['b2'], cache); r.append(np.clip((u1[:, 1]-u2[:, 1]-dyoff)/0.5, -8, 8)*DYW)
    for i in mfit:
        d = tape_d(p, M[i], cache); r.append(np.array([(d/(p[3]*B/(M[i]['Z']+z0m))-1)*4000*MW]))
    return np.concatenate(r)

if __name__ == '__main__':
    j = json.load(open('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json'))['fit_params']
    x0 = [*j['rx_ry_rz_deg'], j['fL'], j['fR'], j['k1_L'], j['k2'], j['k1_R'], j['k2'], j['dcx_right_px'], j['dcy_right_px'], 0, 0, 0, 0, 0, 0, 0.0292, 0, 0.04, 1.4]
    lo = [-20, -20, -20, 1090, 1090, -1, -2, -1, -2, -200, -40, -3, -1, -15, -15, -1, -1, 0.02, -0.02, -0.12, -4]
    hi = [20, 20, 20, 1220, 1220, 1, 2, 1, 2, 200, 40, 3, 1, 15, 15, 1, 1, 0.04, 0.02, 0.12, 4]
    x0 = np.clip(x0, np.array(lo)+1e-6, np.array(hi)-1e-6)
    if sys.argv[4:5] == ['before']:
        sol = x0
    else:
        sb = least_squares(resid, x0, bounds=(lo, hi), x_scale=[1, 1, 1, 50, 50, .1, .1, .1, .1, 10, 5, 1, 1, 5, 5, .3, .3, 0.002, 0.05, 0.05, 1], diff_step=1e-4, max_nfev=300, xtol=1e-12, ftol=1e-10, gtol=1e-10, verbose=1); sol = sb.x
    print(dict(zip(NAMES, np.round(sol, 5))))
    json.dump(dict(x=list(map(float, sol)), names=NAMES, sess=SESS), open(OUT, 'w'), indent=1)
