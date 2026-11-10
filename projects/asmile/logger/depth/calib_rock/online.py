#!/usr/bin/env python3
"""
online.py - correzione ONLINE della calibrazione, SENZA tabellone (profilo #001).

Parte dalla calib NOMINALE di #001 e corregge solo cio' che il software puo' vedere:
  1. roll/pitch relativi (e un po' di yaw) dallo scarto verticale dy: vincolo epipolare ESATTO sui punti SIFT
     L-R (coordinate rettificate col nominale, baseline lungo x); RANSAC lineare + raffinamento robusto.
  2. YAW/convergenza (= offset costante di disparita' d0) e SCALA fB: invisibili al dy. Si stimano dal MOTO:
     per un punto fermo la bici avanza di ds (encoder ruota, C=1.576 m): P(t0)-P(t1) e' la STESSA traslazione
     per tutti i punti, di norma ds. Si cercano yaw e scala che rendono i punti rigidi e |t|=ds.
  3. controllo piano strada: camera a ~0.825 m (altezza stimata dal piano a terra) - solo verifica/accettazione.
La correzione e' ACCETTATA solo se migliora su coppie TENUTE FUORI (dy e coerenza del moto) e il piano strada
non peggiora; altrimenti si restituisce il nominale. Esce un CANDIDATO, mai la calib di fabbrica sovrascritta.
Assunzioni dichiarate: moto ~rettilineo tra i due istanti; baseline lungo x del frame rettificato (ty,tz di pochi
mm valgono ~0.5 gradi equivalenti, non separabili da rotazione); lente = quella del nominale (errori di lente
NON si correggono qui: per quelli serve il collaudo col tabellone).
"""
import os
import sys

import cv2
import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stereo_common import Calib  # noqa: E402

W, H = 1280, 800
GROUND_W = 1.0     # peso residui piano strada (px) nel bundle
SIG_D = 0.3        # rumore atteso sulla disparita' (px) per pesare i residui del moto
ZMAX_MOTION = 15.0  # oltre, la disparita' e' <18 px e il bias 1/d del rumore pesa
GATE_ONLINE = dict(ds_min_m=0.5, min_chains=60, min_zone_inliers=12, ep_inlier_px=2.0)


def Rot(w):
    return cv2.Rodrigues(np.asarray(w, float).reshape(3, 1))[0]


# ---------------------------------------------------------------------------------------------- rettifica + SIFT
class Rect:
    def __init__(self, cal: Calib):
        self.cal = cal
        r = cal.rectify(alpha=0)
        self.r = r
        self.f = float(r["P1"][0, 0])
        self.cx, self.cy = float(r["P1"][0, 2]), float(r["P1"][1, 2])
        ones = np.full((H, W), 255, np.uint8)
        self.mask = [cv2.erode(cv2.remap(ones, r["m1x"], r["m1y"], cv2.INTER_NEAREST), np.ones((25, 25), np.uint8)),
                     cv2.erode(cv2.remap(ones, r["m2x"], r["m2y"], cv2.INTER_NEAREST), np.ones((25, 25), np.uint8))]

    def apply(self, img, cam):
        m = self.r["m1x"], self.r["m1y"]
        if cam == 2:
            m = self.r["m2x"], self.r["m2y"]
        return cv2.remap(img, m[0], m[1], cv2.INTER_LINEAR)


def features(rect, img, cam, feature_mask=None, nfeat=3000):
    sift = cv2.SIFT_create(nfeatures=nfeat, contrastThreshold=0.015)
    im = rect.apply(img, cam)
    mask = rect.mask[cam - 1].copy()
    if feature_mask is not None:
        mask = cv2.bitwise_and(mask, feature_mask)
    kp, de = sift.detectAndCompute(im, mask)
    return np.array([k.pt for k in kp], np.float32).reshape(-1, 2), de


def match(da, db, ratio=0.75):
    """Match con test del rapporto + reciproco. Ritorna (idx_a, idx_b)."""
    if da is None or db is None or len(da) < 5 or len(db) < 5:
        return np.zeros(0, int), np.zeros(0, int)
    bf = cv2.BFMatcher(cv2.NORM_L2)
    ab = bf.knnMatch(da, db, k=2)
    ba = bf.knnMatch(db, da, k=1)
    ia, ib = [], []
    for m in ab:
        if len(m) == 2 and m[0].distance < ratio * m[1].distance and ba[m[0].trainIdx][0].trainIdx == m[0].queryIdx:
            ia.append(m[0].queryIdx)
            ib.append(m[0].trainIdx)
    return np.array(ia, int), np.array(ib, int)


# ---------------------------------------------------------------------------------------------- epipolare
def _norm(rect, p):
    return (p[:, 0] - rect.cx) / rect.f, (p[:, 1] - rect.cy) / rect.f


def epi_resid(w, x1, y1, x2, y2, ty=0.0, tz=0.0):
    """Vincolo epipolare generale: e = t^ . (r1 x v), v = Rot(w) r2, t^ = (1, ty, tz) (baseline ~ lungo x).
    Con ty=0: e = y1 v_z - v_y (coplanarita' con baseline lungo x). e*f ~ dy in px."""
    r2 = np.stack([x2, y2, np.ones_like(x2)], 0)
    v = Rot(w) @ r2
    cxx = y1 * v[2] - v[1]
    cyy = v[0] - x1 * v[2]
    czz = x1 * v[1] - y1 * v[0]
    return cxx + ty * cyy + tz * czz


def epi_ransac(rect, p1, p2, thr_px=2.0, iters=600, seed=0):
    x1, y1 = _norm(rect, p1)
    x2, y2 = _norm(rect, p2)
    rng = np.random.default_rng(seed)
    A = np.stack([1 + y1 * y2, -y1 * x2, -x2], 1)
    b = y2 - y1
    best, bestn = None, 0
    n = len(x1)
    if n < 8:
        return None, np.zeros(n, bool)
    for _ in range(iters):
        i = rng.choice(n, 3, replace=False)
        try:
            w = np.linalg.solve(A[i], b[i])
        except np.linalg.LinAlgError:
            continue
        if np.abs(w).max() > 0.5:
            continue
        inl = np.abs(epi_resid(w, x1, y1, x2, y2)) * rect.f < thr_px
        if inl.sum() > bestn:
            best, bestn = w, inl.sum()
    if best is None:
        return None, np.zeros(n, bool)
    inl = np.abs(epi_resid(best, x1, y1, x2, y2)) * rect.f < thr_px * 2
    sol = least_squares(lambda v: epi_resid(v[:3], x1[inl], y1[inl], x2[inl], y2[inl], v[3], v[4]) * rect.f,
                        np.r_[best, 0.0, 0.0], loss="soft_l1", f_scale=1.0)
    w, ty, tz = sol.x[:3], sol.x[3], sol.x[4]
    inl = np.abs(epi_resid(w, x1, y1, x2, y2, ty, tz)) * rect.f < thr_px
    return np.r_[w, ty, tz], inl


def epi_fit_fixed_yaw(rect, p1, p2, phi, g0):
    """Rifit di (wx, wz, ty') con wy=phi fissato (yaw dal moto). g0 = [wx,wy,wz,ty]."""
    x1, y1 = _norm(rect, p1)
    x2, y2 = _norm(rect, p2)
    f = lambda v: epi_resid([v[0], phi, v[1]], x1, y1, x2, y2, v[2], v[3]) * rect.f
    sol = least_squares(f, [g0[0], g0[2], g0[3], g0[4]], loss="soft_l1", f_scale=1.0)
    return np.array([sol.x[0], phi, sol.x[1], sol.x[2], sol.x[3]])


# ---------------------------------------------------------------------------------------------- triangolazione e moto
def triangulate(rect, p1, p2, g, kappa, B):
    """p1,p2 px rettificati nominali -> punti 3D nel frame rettificato sinistro. g=[wx,wy,wz,ty]: rotazione della
    camera destra e inclinazione della baseline t^=(1,ty,0); centro cam destra c = kappa B t^/|t^|.
    Triangolazione a minimi quadrati fra i raggi r1 e v (non assume piu' baseline esattamente lungo x)."""
    x1, y1 = _norm(rect, p1)
    x2, y2 = _norm(rect, p2)
    w, ty, tz = g[:3], g[3], g[4]
    v = Rot(w) @ np.stack([x2, y2, np.ones_like(x2)], 0)        # 3 x n
    r1 = np.stack([x1, y1, np.ones_like(x1)], 0)
    th = np.array([1.0, ty, tz])
    c = kappa * B * th / np.linalg.norm(th)
    a11 = (r1 * r1).sum(0)
    a12 = -(r1 * v).sum(0)
    a22 = (v * v).sum(0)
    b1 = c @ r1
    b2 = -(c @ v)
    det = a11 * a22 - a12 * a12
    with np.errstate(divide="ignore", invalid="ignore"):
        s1 = (a22 * b1 - a12 * b2) / det
        s2 = (a11 * b2 - a12 * b1) / det
    Z = np.where((s1 > 0) & (s2 > 0), s1, np.nan)
    return np.stack([Z * x1, Z * y1, Z], 1), x1 - v[0] / v[2]


def build_chains(rect, seg, feature_mask=None):
    """Per un segmento (L0,R0,L1,R1 grezzi + ds): catene punto-fermo (pL0,pR0,pL1,pR1) via SIFT:
    L0-R0, L0-L1, L1-R1 composti. Ritorna dict con gli array e i conteggi."""
    L0, R0, L1, R1 = seg["L0"], seg["R0"], seg["L1"], seg["R1"]
    kL0, dL0 = features(rect, L0, 1, feature_mask)
    kR0, dR0 = features(rect, R0, 2, feature_mask)
    kL1, dL1 = features(rect, L1, 1, feature_mask)
    kR1, dR1 = features(rect, R1, 2, feature_mask)
    a0, b0 = match(dL0, dR0)
    a1, b1 = match(dL1, dR1)
    t0, t1 = match(dL0, dL1)
    mapA = dict(zip(a0.tolist(), b0.tolist()))
    mapB = dict(zip(a1.tolist(), b1.tolist()))
    ch = []
    for i0, i1 in zip(t0.tolist(), t1.tolist()):
        if i0 in mapA and i1 in mapB:
            ch.append((kL0[i0], kR0[mapA[i0]], kL1[i1], kR1[mapB[i1]]))
    out = dict(ds=seg["ds"], n_LR0=len(a0), n_LR1=len(a1), pairs0=(kL0[a0], kR0[b0]), pairs1=(kL1[a1], kR1[b1]))
    if ch:
        out["chains"] = [np.array([c[k] for c in ch], float) for k in range(4)]
    else:
        out["chains"] = [np.zeros((0, 2)) for _ in range(4)]
    return out


def zone_counts(pts):
    zx = np.clip((pts[:, 0] * 3 // W).astype(int), 0, 2)
    zy = np.clip((pts[:, 1] * 3 // H).astype(int), 0, 2)
    return np.bincount(zy * 3 + zx, minlength=9)


def ground_candidates(rect, pairs, g, B, h_ref, kappa=1.0):
    """Punti L-R che stanno sul piano strada: righe basse, Z 2-12 m, RANSAC con normale quasi lungo y."""
    p1 = np.concatenate([p[0] for p in pairs]); p2 = np.concatenate([p[1] for p in pairs])
    P, _ = triangulate(rect, p1, p2, g, kappa, B)
    low = (p1[:, 1] > rect.cy + 40) & np.isfinite(P).all(1)
    low &= (P[:, 2] > 2.0) & (P[:, 2] < 12.0)
    p1, p2, P = p1[low], p2[low], P[low]
    if len(P) < 40:
        return None
    rng = np.random.default_rng(2)
    best, bn = None, 0
    for _ in range(500):
        i = rng.choice(len(P), 3, replace=False)
        n = np.cross(P[i[1]] - P[i[0]], P[i[2]] - P[i[0]])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        if n[1] < 0:
            n = -n
        if n[1] < 0.9 or abs(n[0]) > 0.06 or not -0.02 < n[2] < 0.3:   # strada: bici ~dritta, pitch 0-17 gradi nel frame rettificato
            continue
        h = n @ P[i[0]]
        if not 0.5 * h_ref < h < 2.0 * h_ref + 0.5:
            continue
        inl = np.abs(P @ n - h) < 0.05 + 0.015 * P[:, 2]
        if inl.sum() > bn:
            best, bn = inl, inl.sum()
    if best is None or bn < 30:
        return None
    return p1[best], p2[best]


def _pred_right(rect, P, c, w):
    """Pixel rettificato-nominale (normalizzato) della cam destra per punti P (3xn o nx3) dati rotazione w e centro c."""
    v = (P - c).T                                    # 3 x n
    r2 = Rot(w).T @ v
    return r2[0] / r2[2], r2[1] / r2[2]


def bundle_fit(rect, segs, g0, B, ground, h_ref=0.825, p_nom=0.13):
    """STIMATORE PRINCIPALE: bundle adjustment ridotto in spazio-misura (nessun bias da 1/d: la profondita' di ogni
    punto e' una variabile LATENTE). Parametri globali: w (3), ty', tz' (baseline), kappa (scala fB), direzione di
    marcia per segmento (norma = ds dall'encoder), piano strada (pitch, roll; altezza = h_ref).
      catena: ray sinistro t0 fisso; residui = pixel destro t0, sinistro t1, destro t1 (6 px)
      terra:  profondita' dal piano a h_ref; residuo = pixel destro misurato - previsto (2 px)
    Ritorna (g[5], kappa, info)."""
    # init grossolano dell'yaw (l'epipolare lo vede male): scansione +-0.6 gradi sulla coerenza del moto (kappa=1)
    def _spread(gg):
        tot, cnt = 0.0, 0
        for sg in segs:
            if len(sg["inl"][0]) < 10:
                continue
            p1a, p2a, p1b, p2b = sg["inl"]
            P0, _ = triangulate(rect, p1a, p2a, gg, 1.0, B)
            P1, _ = triangulate(rect, p1b, p2b, gg, 1.0, B)
            v = P0 - P1
            ok = np.isfinite(v).all(1) & (P0[:, 2] > 1.5) & (P0[:, 2] < 15) & (P1[:, 2] > 0.5)
            if ok.sum() < 10:
                continue
            tm = np.median(v[ok], 0)
            e = np.linalg.norm(v[ok] - tm, axis=1) / P0[ok, 2] ** 2
            tot += float(np.median(e)); cnt += 1
        return tot / cnt if cnt else np.inf
    cands = [np.r_[g0[0], g0[1] + np.radians(d), g0[2:]] for d in np.linspace(-0.6, 0.6, 25)]
    g0 = min(cands, key=_spread)
    seg_id, A, Bp, C, D, ds_k, s0, tmeds = [], [], [], [], [], [], [], []
    k = 0
    for sg in segs:
        if len(sg["inl"][0]) < 10:
            continue
        p1a, p2a, p1b, p2b = sg["inl"]
        P0, _ = triangulate(rect, p1a, p2a, g0, 1.0, B)
        P1, _ = triangulate(rect, p1b, p2b, g0, 1.0, B)
        v = P0 - P1
        ok = np.isfinite(v).all(1) & (P0[:, 2] > 1.5) & (P0[:, 2] < 40) & (P1[:, 2] > 0.5)
        if ok.sum() < 10:
            continue
        t = np.median(v[ok], 0)
        tmeds.append(t)
        ok &= np.linalg.norm(v - t, axis=1) < 8 * SIG_D / (rect.f * B) * np.maximum(P0[:, 2], 0.1) ** 2 * 1.41 + 0.05
        if ok.sum() < 10:
            tmeds.pop()
            continue
        n = int(ok.sum())
        seg_id += [k] * n
        A.append(p1a[ok]); Bp.append(p2a[ok]); C.append(p1b[ok]); D.append(p2b[ok])
        s0.append(P0[ok, 2])
        ds_k.append(sg["ds"])
        k += 1
    nseg = k
    if nseg < 2:
        return None
    seg_id = np.array(seg_id)
    A, Bp, C, D, s0 = [np.concatenate(q) for q in (A, Bp, C, D, s0)]
    n = len(A)
    xa, ya = _norm(rect, A); x2a, y2a = _norm(rect, Bp); xb, yb = _norm(rect, C); x2b, y2b = _norm(rect, D)
    r1a = np.stack([xa, ya, np.ones(n)], 1)
    ds_arr = np.array(ds_k)[seg_id]
    ng = len(ground[0]) if ground is not None else 0
    if ng:
        gx1, gy1 = _norm(rect, ground[0]); gx2, gy2 = _norm(rect, ground[1])
        r1g = np.stack([gx1, gy1, np.ones(ng)], 1)
    NG = 6 + 2 * nseg + 2          # parametri globali
    f = rect.f

    def unpack(th):
        w = th[0:3]
        ty, tz, kap = th[3], th[4], th[5]
        dirs = th[6:6 + 2 * nseg].reshape(nseg, 2)
        pp, rr = th[6 + 2 * nseg], th[7 + 2 * nseg]
        lat = th[NG:]
        return w, ty, tz, kap, dirs, pp, rr, lat

    def res(th):
        w, ty, tz, kap, dirs, pp, rr, lat = unpack(th)
        tt = np.array([1.0, ty, tz])
        c = kap * B * tt / np.linalg.norm(tt)
        P0 = lat[:, None] * r1a
        a_, b_ = dirs[seg_id, 0], dirs[seg_id, 1]
        t = ds_arr[:, None] * np.stack([np.cos(b_) * np.sin(a_), np.sin(b_), np.cos(b_) * np.cos(a_)], 1)
        P1 = P0 - t
        z1 = np.maximum(P1[:, 2], 0.05)
        e1 = (P1[:, 0] / z1 - xb) * f
        e2 = (P1[:, 1] / z1 - yb) * f
        px, py = _pred_right(rect, P0, c, w)
        e3, e4 = (px - x2a) * f, (py - y2a) * f
        px, py = _pred_right(rect, P1, c, w)
        e5, e6 = (px - x2b) * f, (py - y2b) * f
        out = [np.stack([e1, e2, e3, e4, e5, e6], 1).ravel()]
        if ng:
            nvec = np.array([np.sin(rr), np.cos(rr) * np.cos(pp), np.cos(rr) * np.sin(pp)])
            den = r1g @ nvec
            s = h_ref / np.where(np.abs(den) > 1e-3, den, 1e-3)
            Pg = s[:, None] * r1g
            px, py = _pred_right(rect, Pg, c, w)
            out.append(np.stack([(px - gx2) * f, (py - gy2) * f], 1).ravel() * GROUND_W)
        return np.concatenate(out)

    # init dai dati: direzione di marcia = traslazione mediana, scala = ds / |t|
    dirs0, kap0 = [], []
    for t, dsk in zip(tmeds, ds_k):
        nt = np.linalg.norm(t)
        dirs0 += [float(np.arctan2(t[0], t[2])), float(np.arcsin(np.clip(t[1] / max(nt, 1e-6), -1, 1)))]
        kap0.append(dsk / max(nt, 1e-6))
    kap_init = float(np.clip(np.median(kap0), 0.9, 1.1))
    pp0, rr0 = np.radians(7.4), 0.0
    if ng:       # init del piano strada dai punti a terra triangolati (il frame rettificato non e' quello camera: pitch diverso)
        Pg0, _ = triangulate(rect, ground[0], ground[1], g0, kap_init, B)
        Pg0 = Pg0[np.isfinite(Pg0).all(1)]
        if len(Pg0) > 20:
            vv = np.linalg.svd(np.c_[Pg0, -np.ones(len(Pg0))], full_matrices=False)[2][-1]
            nn = vv[:3] / np.linalg.norm(vv[:3])
            nn = nn if nn[1] > 0 else -nn
            pp0, rr0 = float(np.arctan2(nn[2], nn[1])), float(np.arcsin(np.clip(nn[0], -1, 1)))
    th0 = np.r_[g0[:3], g0[3], g0[4], kap_init, dirs0, pp0, rr0, s0]
    from scipy.sparse import lil_matrix
    nres = 6 * n + 2 * ng
    sp = lil_matrix((nres, len(th0)), dtype=int)
    sp[:, :NG] = 1
    for i in range(n):
        sp[6 * i:6 * i + 6, NG + i] = 1
    spc = sp.tocsr()
    sol = None
    # fino a 3 tentativi (x_scale diversi) a partire dal migliore: il primo puo' fermarsi presto
    xs_manual = np.r_[[1e-3] * 3, 1e-3, 1e-3, 1e-2, [1e-2] * (2 * nseg), 1e-2, 1e-2, np.full(n, 0.2)]
    for xs, fs in ((xs_manual, 1.0), ("jac", 1.0), (xs_manual, 2.0), (1.0, 1.0)):
        x0 = th0 if sol is None else sol.x
        cand = least_squares(res, x0, loss="cauchy", f_scale=fs, jac_sparsity=spc, max_nfev=250, x_scale=xs,
                             ftol=1e-12, xtol=1e-12, gtol=1e-12)
        if sol is None or cand.cost < sol.cost:
            sol = cand
        if np.sqrt(np.median(sol.fun ** 2)) < 0.16:      # rumore SIFT ~0.13 px: sotto questa soglia e' a regime
            break
    th = sol.x
    r = sol.fun
    info = dict(plane_pitch_roll=[float(th[6 + 2 * nseg]), float(th[7 + 2 * nseg])], cost=float(sol.cost), status=int(sol.status), n_chain=n, n_ground=ng, nfev=int(sol.nfev),
                rms_px=float(np.sqrt(np.median(r ** 2))), dirs=th[6:6 + 2 * nseg].tolist())
    info["_res"], info["_th"] = res, th   # solo per debug; online_correct li scarta
    return np.r_[th[0:3], th[3], th[4]], float(th[5]), info


def motion_score(rect, segs, w, kappa, B):
    """Coerenza del moto su segmenti: scarto relativo mediano dei punti rispetto alla traslazione mediana
    + errore sulla norma rispetto a ds. (basso = meglio). Non usa parametri liberi sulla norma."""
    sc, ne = [], []
    for s in segs:
        p1a, p2a, p1b, p2b = s["inl"]
        if len(p1a) < 10:
            continue
        P0, _ = triangulate(rect, p1a, p2a, w, kappa, B)
        P1, _ = triangulate(rect, p1b, p2b, w, kappa, B)
        v = P0 - P1
        ok = np.isfinite(v).all(1) & (P0[:, 2] > 0.5) & (P1[:, 2] > 0.5)
        v, Z0 = v[ok], P0[ok, 2]
        if len(v) < 10:
            continue
        t = np.median(v, 0)
        sc.append(float(np.median(np.linalg.norm(v - t, axis=1) / Z0)))
        ne.append(abs(float(np.linalg.norm(t)) - s["ds"]) / s["ds"])
    if not sc:
        return None
    return dict(spread=float(np.mean(sc)), norm_err=float(np.mean(ne)))


def road_plane(rect, segs, w, kappa, B, h_ref=0.825):
    """Altezza camera dal piano a terra (punti nelle righe basse, Z 2-9 m) e pitch del piano. RANSAC con normale quasi
    lungo y e altezza plausibile (0.5-1.6 x h_ref): niente piani spuri vicini alla camera."""
    pts = []
    for s in segs:
        p1, p2 = s["pairs1"]
        P, d = triangulate(rect, p1, p2, w, kappa, B)
        low = (p1[:, 1] > rect.cy + 40) & np.isfinite(P).all(1) & (P[:, 2] > 2.0) & (P[:, 2] < 9)
        pts.append(P[low])
    P = np.concatenate(pts) if pts else np.zeros((0, 3))
    if len(P) < 30:
        return None
    rng = np.random.default_rng(1)
    best, bn = None, 0
    for _ in range(600):
        i = rng.choice(len(P), 3, replace=False)
        n = np.cross(P[i[1]] - P[i[0]], P[i[2]] - P[i[0]])
        if np.linalg.norm(n) < 1e-9:
            continue
        n = n / np.linalg.norm(n)
        if n[1] < 0:
            n = -n
        if n[1] < 0.9:          # il piano strada ha la normale quasi lungo y camera (pitch ~7 gradi): niente muri
            continue
        h = n @ P[i[0]]
        if not 0.5 * h_ref < h < 1.6 * h_ref:
            continue
        inl = np.abs(P @ n - h) < 0.03 + 0.008 * P[:, 2]
        if inl.sum() > bn:
            best, bn = inl, inl.sum()
    if best is None or bn < 20:
        return None
    A = np.c_[P[best], -np.ones(best.sum())]
    v = np.linalg.svd(A, full_matrices=False)[2][-1]
    nn = v[:3] / np.linalg.norm(v[:3])
    hh = v[3] / np.linalg.norm(v[:3])
    if nn[1] < 0:
        nn, hh = -nn, -hh
    return dict(h_m=float(hh), pitch_deg=float(np.degrees(np.arcsin(np.clip(nn[2], -1, 1)))), n_inl=int(best.sum()))


# ---------------------------------------------------------------------------------------------- candidato
def apply_correction(nominal: Calib, g, kappa):
    """Calib CANDIDATA. g=[wx,wy,wz,ty',tz']. R2' = Rot(w) R2 (rettifica del nominale); R_new = R2'^T R1;
    T_new = -kappa B R2'^T t^/|t^| (t^ = (1,ty',0)): il centro della cam destra nel frame rettificato sinistro."""
    r = nominal.rectify(alpha=0)
    R2p = Rot(g[:3]) @ r["R2"]
    B = nominal.baseline_mm / 1000.0
    th = np.array([1.0, g[3], g[4]])
    th = th / np.linalg.norm(th)
    Rn = R2p.T @ r["R1"]
    Tn = (-kappa * B * (R2p.T @ th)).reshape(3, 1)
    return Calib(nominal.K1, nominal.d1, nominal.K2, nominal.d2, Rn, Tn, size=nominal.size,
                 baseline_mm=float(np.linalg.norm(Tn)) * 1000)


# ---------------------------------------------------------------------------------------------- pipeline
def prepare(rect, segs, feature_mask=None):
    out = []
    for s in segs:
        c = build_chains(rect, s, feature_mask)
        out.append(c)
    return out


def online_correct(nominal: Calib, train_segs, hold_segs, profile, feature_mask=None, verbose=False, sabotage=None):
    """train_segs/hold_segs: liste di dict(L0,R0,L1,R1 immagini grezze gray uint8 + ds m da encoder).
    Ritorna dict(verdetto, motivi, accettata, candidato (Calib), metriche prima/dopo, ...)."""
    rep = dict(verdetto="VERDE", motivi=[], accettata=False, gate=GATE_ONLINE)
    red = lambda m: (rep["motivi"].append(m), rep.__setitem__("verdetto", "ROSSO"))
    B = nominal.baseline_mm / 1000.0
    rect = Rect(nominal)
    # 0) moto sufficiente (bici ferma = yaw e scala non osservabili -> rifiuto)
    moving = [s for s in train_segs if abs(s["ds"]) >= GATE_ONLINE["ds_min_m"]]
    rep["segmenti_con_moto"] = len(moving)
    if len(moving) < 2:
        red(f"moto insufficiente: {len(moving)} segmenti con ds >= {GATE_ONLINE['ds_min_m']} m (bici ferma?): "
            f"yaw/d0 e scala non osservabili dal solo dy. Nessuna correzione.")
        return dict(rep, candidato=nominal)
    tr = prepare(rect, moving, feature_mask)
    # 1) epipolare L-R sui punti di tutti i segmenti (t0 e t1)
    P1 = np.concatenate([np.concatenate([c["pairs0"][0], c["pairs1"][0]]) for c in tr])
    P2 = np.concatenate([np.concatenate([c["pairs0"][1], c["pairs1"][1]]) for c in tr])
    if len(P1) < 40:
        red(f"poche corrispondenze L-R ({len(P1)})")
        return dict(rep, candidato=nominal)
    w0, inl = epi_ransac(rect, P1, P2, GATE_ONLINE["ep_inlier_px"])
    if w0 is None or inl.sum() < 40:
        red("epipolare: nessun modello coerente (L/R scambiati? scena senza struttura?)")
        return dict(rep, candidato=nominal)
    zc = zone_counts(P1[inl])
    rep["copertura_inlier_zone"] = zc.tolist()
    if (zc < GATE_ONLINE["min_zone_inliers"]).any():
        bad = [i for i in range(9) if zc[i] < GATE_ONLINE["min_zone_inliers"]]
        red(f"copertura insufficiente: zone {bad} con < {GATE_ONLINE['min_zone_inliers']} corrispondenze (solo-centro?)")
        return dict(rep, candidato=nominal)
    rep["w0_epipolare_deg"] = np.degrees(w0[:3]).tolist() + [float(w0[3]), float(w0[4])]
    # inlier per segmento (per le catene)
    for c in tr:
        p1a, p2a, p1b, p2b = c["chains"]
        ok = np.ones(len(p1a), bool)
        if len(p1a):
            x1, y1 = _norm(rect, p1a); x2, y2 = _norm(rect, p2a)
            ok &= np.abs(epi_resid(w0[:3], x1, y1, x2, y2, w0[3], w0[4])) * rect.f < 3 * GATE_ONLINE["ep_inlier_px"]
            x1, y1 = _norm(rect, p1b); x2, y2 = _norm(rect, p2b)
            ok &= np.abs(epi_resid(w0[:3], x1, y1, x2, y2, w0[3], w0[4])) * rect.f < 3 * GATE_ONLINE["ep_inlier_px"]
        c["inl"] = [q[ok] for q in c["chains"]]
        # pairs per piano strada
    nch = sum(len(c["inl"][0]) for c in tr)
    rep["catene_punto_fermo"] = nch
    if nch < GATE_ONLINE["min_chains"]:
        red(f"poche catene punto-fermo ({nch} < {GATE_ONLINE['min_chains']})")
        return dict(rep, candidato=nominal)
    # orientamento: andando avanti la disparita' CRESCE; se cala i file L/R sono scambiati
    dd = []
    for c in tr:
        p1a, p2a, p1b, p2b = c["inl"]
        x1a, _ = _norm(rect, p1a); x2a, _ = _norm(rect, p2a)
        x1b, _ = _norm(rect, p1b); x2b, _ = _norm(rect, p2b)
        dd += list((x1b - x2b) - (x1a - x2a))
    rep["delta_disparita_mediana_norm"] = float(np.median(dd))
    if np.median(dd) <= 0:
        red("orientamento: in avanti la disparita' non cresce -> file L/R scambiati o camere invertite")
        return dict(rep, candidato=nominal)
    # 2) moto: yaw (phi) + scala (kappa); 3) epipolare con yaw fisso; ripeti
    w = w0.copy()
    h_ref = profile["cam_height_m"]
    pairs_all = [c["pairs0"] for c in tr] + [c["pairs1"] for c in tr]
    kappa = 1.0
    for it in range(2):
        gnd = ground_candidates(rect, pairs_all, w, B, h_ref)
        out = bundle_fit(rect, tr, w, B, gnd, h_ref=h_ref)
        if out is None:
            red("bundle: pochi segmenti/catene utilizzabili")
            return dict(rep, candidato=nominal)
        w, kappa, sol = out
        sol = {k: v for k, v in sol.items() if not k.startswith('_')}
        w = np.asarray(w)
    if sabotage:      # SOLO test negativi: inietta yaw (d0) / scala sbagliati nella stima; l'accettazione deve rifiutare
        w = w.copy()
        w[1] += np.radians(sabotage.get("dyaw_deg", 0.0))
        kappa = kappa * (1 + sabotage.get("dkappa", 0.0))
        rep["sabotaggio"] = dict(sabotage)
    rep["stima"] = dict(w_deg=np.degrees(w[:3]).tolist(), ty=float(w[3]), tz=float(w[4]), kappa=kappa, bundle=sol,
                        punti_terra=None if gnd is None else int(len(gnd[0])))
    if not (0.9 < kappa < 1.1) or np.abs(np.degrees(w[:3])).max() > 20:
        red(f"stima fuori limiti fisici (kappa={kappa:.3f}, w={np.degrees(w[:3]).round(2).tolist()})")
        return dict(rep, candidato=nominal)
    cand = apply_correction(nominal, w, kappa)
    # 4) accettazione su coppie TENUTE FUORI + piano strada
    hs = prepare(rect, hold_segs, feature_mask)
    for c in hs:
        p1a, p2a, p1b, p2b = c["chains"]
        c["inl"] = c["chains"]
    w_id = np.zeros(5)
    ms_b = motion_score(rect, hs, w_id, 1.0, B)
    ms_a = motion_score(rect, hs, w, kappa, B)

    def ep_p95(wv):
        e = []
        for c in hs:
            for (a, b) in (c["pairs0"], c["pairs1"]):
                x1, y1 = _norm(rect, a); x2, y2 = _norm(rect, b)
                r = np.abs(epi_resid(wv[:3], x1, y1, x2, y2, wv[3], wv[4])) * rect.f
                e += list(r[r < 20])
        return float(np.percentile(e, 95)) if e else None
    ep_b, ep_a = ep_p95(w_id), ep_p95(w)
    # piano strada sulle viste TENUTE FUORI: punti a terra (RANSAC con prior di altezza), con la normale (pitch/roll)
    # stimata sul train; altezza = mediana(n.P). Deve restare entro 35% di h_ref (controllo grossolano: pitch e altezza del piano non si separano bene).
    pp, rr = sol["plane_pitch_roll"]
    nvec = np.array([np.sin(rr), np.cos(rr) * np.cos(pp), np.cos(rr) * np.sin(pp)])
    gh = ground_candidates(rect, [c["pairs0"] for c in hs] + [c["pairs1"] for c in hs], w, B, h_ref, kappa)
    h_hold = None
    if gh is not None:
        Pg, _ = triangulate(rect, gh[0], gh[1], w, kappa, B)
        hh = Pg @ nvec
        hh = hh[np.isfinite(hh) & (hh > 0.4 * h_ref) & (hh < 1.8 * h_ref)]     # mediana robusta ai punti non-strada
        h_hold = float(np.median(hh)) if len(hh) >= 20 else None
    rp_a = dict(h_m=h_hold, pitch_deg=float(np.degrees(pp)), roll_deg=float(np.degrees(rr)),
                n_punti=None if gh is None else int(len(gh[0])))
    rp_b = None
    h_ref = profile["cam_height_m"]
    rep["tenute_fuori"] = dict(epi_p95_prima=ep_b, epi_p95_dopo=ep_a, moto_prima=ms_b, moto_dopo=ms_a,
                               piano_dopo=rp_a, h_ref=h_ref)
    ok_ep = ep_a is not None and (ep_b is None or ep_a < 0.8 * ep_b or ep_a < 0.5) and ep_a < 1.5
    ok_mot = ms_a is not None and (ms_b is None or (ms_a["spread"] <= ms_b["spread"] and
                                                    ms_a["norm_err"] <= ms_b["norm_err"] + 0.01)) and ms_a["norm_err"] < 0.05
    ok_pl = h_hold is not None and abs(h_hold / h_ref - 1) < 0.35   # controllo GROSSOLANO: n e h non sono separabili con precisione
    rep["accettazione"] = dict(ep=bool(ok_ep), moto=bool(ok_mot), piano=bool(ok_pl))
    if ok_ep and ok_mot and ok_pl:
        rep["accettata"] = True
        return dict(rep, candidato=cand)
    rep["motivi"].append("correzione NON accettata (non migliora su viste tenute fuori / piano strada): restituito il nominale")
    rep["verdetto"] = "ROSSO"
    return dict(rep, candidato=nominal)
