#!/usr/bin/env python3
"""obstacles_v2.py — strato "ostacolo senza classe" v2 (L1.ostacoli in ombra, dopo VETO 1/3). SOLO #001, calib PROVVISORIA.
Cambi rispetto a depth_seg_001.obstacles (che resta invariata, usata dai test v1):
 1. disparity_v2: SGBM con padding a sinistra (P=160) e numDisparities=160 (Z>=1.64 m). Prima le prime 288 colonne
    (X<-0.27*Z) avevano disparita' INVALIDA per costruzione (bordo SGBM = numDisparities): lato sx cieco.
 2. piano strada a 3 parametri (vh, pendenza a, inclinazione laterale b) con fit robusto iterativo, vincolato attorno alla geometria nota
    (prima: solo vh, pendenza fissa dalla geometria, moda sulle colonne 200-1080).
 3. soglia altezza h_med >= HMED_MIN (0.25 m) sul blob e altezza di picco; cresta del blob >= 0.3 m (non un'ondulazione d'asfalto).
 4. coerenza multi-frame (in ostacoli_v2_run.py): il blob deve esserci anche nei frame +-K con Z prevista dall'odometria dell'encoder.
 5. banda: "corridoio" |X_centro|<=1.5 m (margine 0.3 m sul bordo del box, dichiarato) vs "laterale" (fuori dal conteggio).
"""
import numpy as np, cv2
import depth_seg_001 as D

P_PAD, NDISP = 160, 160
H, W, B, CAM_H, PITCH = D.H, D.W, D.B, D.CAM_H, D.PITCH
HPIX_MIN = 0.09          # soglia altezza per pixel (m) + 1.5 px di disparita' di margine
HMED_MIN = 0.25          # altezza mediana minima del blob sopra la strada (m)
W_MIN_M, H_BOX_MIN_M = 0.12, 0.30   # dimensioni reali minime del box (m)
HPEAK_MIN = 0.35         # altezza del 90 percentile
CORRIDOIO_X = 1.5        # |X| centro per il conteggio
MARGINE_X = 0.3          # il bordo del box puo' sporgere di 0.3 m
_sg = None


def disparity_v2(L, R):
    global _sg
    if _sg is None:
        _sg = cv2.StereoSGBM_create(minDisparity=0, numDisparities=NDISP, blockSize=7, P1=8 * 49, P2=32 * 49, disp12MaxDiff=1,
                                    uniquenessRatio=8, speckleWindowSize=150, speckleRange=2, preFilterCap=31,
                                    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    Lp = cv2.copyMakeBorder(L, 0, 0, P_PAD, 0, cv2.BORDER_CONSTANT, value=0)
    Rp = cv2.copyMakeBorder(R, 0, 0, P_PAD, 0, cv2.BORDER_CONSTANT, value=0)
    return (_sg.compute(Lp, Rp).astype(np.float32) / 16.0)[:, P_PAD:]


def ground_plane(disp, cx):
    """d_g(u,v) = a (v - vh) + b (u - cx). Ritorna (a, vh, b) o None. Fit robusto, vincolato attorno alla geometria nota."""
    a0 = B / (CAM_H * np.cos(PITCH))
    vs, us = np.nonzero(disp[430:, :] > 6)
    if len(vs) < 3000:
        return None
    vs = vs + 430
    d = disp[vs, us]
    vh0 = vs - d / a0
    h, e = np.histogram(vh0, bins=np.arange(-200, 700, 4))
    c = 0.5 * (e[h.argmax()] + e[h.argmax() + 1])
    a, vh, b = a0, float(np.median(vh0[np.abs(vh0 - c) < 12])), 0.0
    for _ in range(4):
        dg = a * (vs - vh) + b * (us - cx)
        inl = np.abs(d - dg) < (1.0 + 0.06 * d)
        if inl.sum() < 2000:
            break
        A = np.stack([vs[inl], np.ones(inl.sum()), us[inl] - cx], 1).astype(np.float64)
        sol, *_ = np.linalg.lstsq(A, d[inl].astype(np.float64), rcond=None)
        a_n, c_n, b_n = sol
        if not (0.85 * a0 <= a_n <= 1.15 * a0 and abs(b_n) <= 0.04):
            break
        a, vh, b = float(a_n), float(-c_n / a_n), float(b_n)
    return a, vh, b


def obstacles_v2(rc, disp, zmin=2.0, zmax=15.0, corridor=4.5):
    """Lista di dict: Z (p20), box, mask, h_med, h90, banda. 'corridor' = massima |X| cercata (4.5, i laterali sono etichettati)."""
    g = ground_plane(disp, rc.cx)
    if g is None:
        return [], None
    a, vh, b = g
    v = np.arange(H, dtype=np.float32)[:, None]; u = np.arange(W, dtype=np.float32)[None, :]
    dg = np.maximum(a * (v - vh) + b * (u - rc.cx), 0.1)
    valid = disp > 4
    Z = np.where(valid, rc.f * B / np.maximum(disp, 1e-3), 0)
    X = (u - rc.cx) * Z / rc.f
    y = CAM_H * (disp - dg) / np.maximum(disp, 1e-3)
    m = valid & (Z >= zmin) & (Z <= zmax) & (np.abs(X) <= corridor) & (y >= HPIX_MIN + 1.5 * CAM_H / np.maximum(disp, 1.0)) & (y <= 3.0)
    m = m.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for k in range(1, n):
        x0, y0, bw, bh, area = st[k]
        if area < 300:
            continue
        # dimensioni REALI (m) al posto della soglia fissa in pixel: un blob di 700 px a 2 m sono 5 cm (sasso/ciottolo)
        wm, hm_ = bw * np.median(Z[lab == k]) / rc.f, bh * np.median(Z[lab == k]) / rc.f
        if wm < W_MIN_M or hm_ < H_BOX_MIN_M:
            continue
        mk = (lab == k).astype(np.uint8)
        zz = Z[mk > 0]
        z20, z80 = np.percentile(zz, [20, 80])
        if z80 > 1.3 * z20 + 0.4:
            continue
        ys_, xs_ = np.nonzero(mk)
        base = ys_ >= np.percentile(ys_, 85)
        if float(np.median(y[ys_[base], xs_[base]])) > 0.5:
            continue
        hv = y[mk > 0]
        h_med, h90 = float(np.median(hv)), float(np.percentile(hv, 90))
        if h_med < HMED_MIN or h90 < HPEAK_MIN:
            continue
        xc = float((0.5 * (x0 + x0 + bw) - rc.cx) * z20 / rc.f)
        xl, xr = (x0 - rc.cx) * z20 / rc.f, (x0 + bw - rc.cx) * z20 / rc.f
        corr = abs(xc) <= CORRIDOIO_X and xl >= -(CORRIDOIO_X + MARGINE_X) and xr <= CORRIDOIO_X + MARGINE_X
        corr = corr or (abs(xc) <= CORRIDOIO_X)          # centro dentro 1.5 m basta (oggetti larghi a cavallo)
        out.append({"Z": float(z20), "box": [int(x0), int(y0), int(x0 + bw), int(y0 + bh)], "mask": mk, "h_med": h_med, "h90": h90,
                    "X": xc, "banda": "corridoio" if corr else "laterale"})
    return out, (a, vh, b)
