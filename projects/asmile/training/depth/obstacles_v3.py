#!/usr/bin/env python3
"""obstacles_v3.py — strato "ostacolo senza classe" v3 (L1.ostacoli in ombra, dopo VETO 2/3). SOLO #001, calib PROVVISORIA.
Cause dei mancati v2 (diag_v3.py, per stadio) e rimedi:
 1. dg troncato a 0.1 sopra l'orizzonte => h saturata a 0.82 (= cam_h) e test 'base_y<=0.5' scarta ogni blob con la parte bassa sopra
    l'orizzonte (oggetti con disparita' invalida in basso: auto scure, muri lisci). v3: altezza REALE (nessun troncamento), contatto a
    terra = 5 percentile di y <= GROUND_Y (0.8 m) e almeno 0.5 m di estensione verticale.
 2. closing 9x9 su tutta l'immagine fonde auto+muro+strada in un unico blob (Z20..Z80 su 4-14 m) => scartato da 'coerenza'. v3: SLICING in Z:
    finestre [z, 1.3 z] (passo 1.2) ; componenti per finestra, poi NMS (stesso oggetto in finestre adiacenti).
 3. conferma multiframe: v3 SOLO causale (t-3), e nessuna conferma per Z<5 m (in ostacoli_v3_run.py).
 4. banda corridoio che cresce con Z: |X_centro| <= 1.5 + 0.03 Z (formula dichiarata); 'laterale_vicino' = Z<6 e fino a |X|<=2.5.
"""
import numpy as np, cv2
import depth_seg_001 as D
from obstacles_v2 import ground_plane
P_PAD, NDISP = 160, 160
_sg = None


def disparity_v3(L, R, relaxed=True):
    """SGBM v2 (padding sx 160) con filtri meno severi (uniqueness 3, disp12 2, speckle 60): +10-15% pixel validi su auto scure/muri lisci."""
    global _sg
    if _sg is None:
        u, d12, sp = (3, 2, 60) if relaxed else (8, 1, 150)
        _sg = cv2.StereoSGBM_create(minDisparity=0, numDisparities=NDISP, blockSize=7, P1=8 * 49, P2=32 * 49, disp12MaxDiff=d12,
                                    uniquenessRatio=u, speckleWindowSize=sp, speckleRange=2, preFilterCap=31, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    Lp = cv2.copyMakeBorder(L, 0, 0, P_PAD, 0, cv2.BORDER_CONSTANT, value=0)
    Rp = cv2.copyMakeBorder(R, 0, 0, P_PAD, 0, cv2.BORDER_CONSTANT, value=0)
    return (_sg.compute(Lp, Rp).astype(np.float32) / 16.0)[:, P_PAD:]


H, W, B, CAM_H = D.H, D.W, D.B, D.CAM_H
HPIX_MIN = 0.09
HMED_MIN, HPEAK_MIN = 0.25, 0.35
W_MIN_M, H_BOX_MIN_M = 0.12, 0.30
GROUND_Y = 0.8           # il 5 percentile di altezza del blob deve scendere sotto 0.8 m (non e' un aggancio sospeso: tettoia, ramo)
VEXT_MIN = 0.0           # (v3: eliminato, tagliava i muri lisci con solo la base valida)
RATIO, STEP = 1.3, 1.2
FILL_MIN = 0.25          # frazione minima di pixel veri nel box (scarta strisce sparse)
CORR_X0, CORR_XK = 1.5, 0.03     # semi-larghezza corridoio(Z) = 1.5 + 0.03 Z
NEAR_Z, NEAR_X = 6.0, 2.5        # allarme laterale vicino


def corr_half(z): return CORR_X0 + CORR_XK * z


def obstacles_v3(rc, disp, zmin=1.8, zmax=15.0, xmax=4.5):
    g = ground_plane(disp, rc.cx)
    if g is None:
        return [], None
    a, vh, b = g
    v = np.arange(H, dtype=np.float32)[:, None]; u = np.arange(W, dtype=np.float32)[None, :]
    dg = a * (v - vh) + b * (u - rc.cx)                       # NIENTE troncamento: sopra l'orizzonte dg<0 => y > cam_h (reale)
    valid = disp > 4
    dsafe = np.maximum(disp, 1e-3)
    Z = np.where(valid, rc.f * B / dsafe, 0)
    X = (u - rc.cx) * Z / rc.f
    y = CAM_H * (disp - dg) / dsafe
    base = valid & (np.abs(X) <= xmax) & (y >= HPIX_MIN + 1.5 * CAM_H / np.maximum(disp, 1.0)) & (y <= 3.0)
    cands = []
    z = zmin
    while z < zmax:
        win = base & (Z >= z) & (Z < z * RATIO)
        m = win.astype(np.uint8)
        z *= STEP
        if m.sum() < 250:
            continue
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (11, 7)))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        for k in range(1, n):
            x0, y0, bw, bh, area = st[k]
            if area < 250:
                continue
            sel = lab[y0:y0 + bh, x0:x0 + bw] == k
            vv = sel & win[y0:y0 + bh, x0:x0 + bw]            # statistiche SOLO sui pixel veri della finestra (il closing ne aggiunge altri)
            if vv.sum() < 150 or vv.sum() < FILL_MIN * bw * bh:
                continue
            Zs, ys = Z[y0:y0 + bh, x0:x0 + bw][vv], y[y0:y0 + bh, x0:x0 + bw][vv]
            zm = float(np.median(Zs)); z20 = float(np.percentile(Zs, 20))
            wm, hm_ = bw * zm / rc.f, bh * zm / rc.f
            if wm < W_MIN_M or hm_ < H_BOX_MIN_M:
                continue
            ysel = ys[ys < 2.2]
            h_med, h90 = float(np.median(ys)), float(np.percentile(ys, 90))
            y5, y95 = float(np.percentile(ys, 5)), float(np.percentile(ys, 95))
            if h_med < HMED_MIN or h90 < HPEAK_MIN or y5 > GROUND_Y:
                continue
            xc = float((x0 + bw / 2 - rc.cx) * z20 / rc.f)
            Xs = X[y0:y0 + bh, x0:x0 + bw][vv]
            sX, sZ = float(np.std(Xs)), float(np.std(Zs))
            cands.append({"sX": sX, "sZ": sZ, "Z": z20, "box": [int(x0), int(y0), int(x0 + bw), int(y0 + bh)], "area": int(area), "h_med": h_med,
                          "h90": h90, "X": xc, "_k": (z, k), "_sel": (x0, y0, bw, bh, lab == k)})
    # NMS: stesso oggetto in finestre adiacenti
    cands.sort(key=lambda c: -c["area"]); keep = []
    for c in cands:
        dup = False
        for q in keep:
            if abs(q["Z"] - c["Z"]) > 0.3 * q["Z"] + 0.3: continue
            ix = max(0, min(q["box"][2], c["box"][2]) - max(q["box"][0], c["box"][0])); iy = max(0, min(q["box"][3], c["box"][3]) - max(q["box"][1], c["box"][1]))
            ca = (c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1])
            if ix * iy > 0.6 * ca: dup = True; break
        if not dup: keep.append(c)
    out = []
    for c in keep:
        x0, y0, bw, bh, mk = c.pop("_sel"); c.pop("_k"); c["mask"] = mk.astype(np.uint8)
        zc, xc = c["Z"], c["X"]
        if abs(xc) <= corr_half(zc): c["banda"] = "corridoio"
        elif zc < NEAR_Z and abs(xc) <= NEAR_X: c["banda"] = "laterale_vicino"
        else: c["banda"] = "laterale"
        out.append(c)
    return out, (a, vh, b)
