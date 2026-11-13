#!/usr/bin/env python3
"""logger_guide.py — velocità visiva (stereo+KLT) e modulo comune per le guide di asmile-logger001.
SOLO logger (Camarray SBS 2560x800, calib_asmile-logger_metro.json): mai per #001.
Velocità = mediana su punti statici tracciati (KLT, sx) di (Z_t - Z_t+dt)/dt con Z=f*B/(d-d0) da SGBM sx/dx
(f 902.8, B 0.2, d0 26.336 dal fit col metro). Qualità BASSA: nessuna verità a terra (BLE ruota nel 2026-11-09 solo
in un test a banco con IMU piatta, non in guida). Mapping clip->tempo: mtime fine clip (mai indice cumulato).
"""
import os, glob, datetime, json, sys
import numpy as np, cv2
L = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "asmile-loggers", "asmile-logger") + os.sep
FPS = 15.0
F_FIT, B, D0 = 902.8, 0.2, 26.336
cv2.setNumThreads(1)


def clip_list(prefix):
    return sorted((os.path.getmtime(f), f) for f in glob.glob(L + f"clip_{prefix}_*.h264"))


def sgbm():
    return cv2.StereoSGBM_create(minDisparity=0, numDisparities=256, blockSize=7, P1=8*49, P2=32*49,
                                 uniquenessRatio=8, speckleWindowSize=100, speckleRange=2, mode=cv2.STEREO_SGBM_MODE_SGBM)


def clip_frames(path, mtime):
    """(wall_epoch, grigio SBS) per ogni frame; wall = mtime fine clip - (N-1-k)/FPS."""
    cap = cv2.VideoCapture(path); fr = []
    while True:
        ok, im = cap.read()
        if not ok: break
        fr.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im)
    n = len(fr)
    return [(mtime - (n - 1 - k) / FPS, f) for k, f in enumerate(fr)]


def zmap(g):
    l, r = g[:, :1280], g[:, 1280:]
    # mezza risoluzione per CPU: disparita /2
    ls = cv2.resize(l, (640, 400)); rs = cv2.resize(r, (640, 400))
    d = sgbm().compute(ls, rs).astype(np.float32) / 16.0 * 2.0
    return d


def vspeed(g0, g1, dt, d0map, d1map):
    """velocità (m/s) fra due frame: mediana su punti tracciati. None se pochi punti."""
    l0, l1 = g0[:, :1280], g1[:, :1280]
    roi = np.zeros(l0.shape, np.uint8); roi[330:760, 60:1220] = 255   # sotto l'orizzonte, no cielo
    p0 = cv2.goodFeaturesToTrack(l0, 400, 0.01, 12, mask=roi)
    if p0 is None: return None, 0
    p1, st, _ = cv2.calcOpticalFlowPyrLK(l0, l1, p0, None, winSize=(31, 31), maxLevel=3)
    ok = st.ravel() == 1
    p0, p1 = p0[ok, 0], p1[ok, 0]
    def z_at(dm, p):
        x = np.clip((p[:, 0] / 2).astype(int), 0, 639); y = np.clip((p[:, 1] / 2).astype(int), 0, 399)
        d = dm[y, x]; z = np.where(d > D0 + 8, F_FIT * B / np.maximum(d - D0, 1e-3), np.nan); return z
    z0, z1 = z_at(d0map, p0), z_at(d1map, p1)
    m = np.isfinite(z0) & np.isfinite(z1) & (z0 > 2.0) & (z0 < 14) & (z1 > 1.5)
    if m.sum() < 15: return None, int(m.sum())
    v = (z0[m] - z1[m]) / dt
    return float(np.median(v)), int(m.sum())


H_CAM, YH = 0.71, 400.0     # altezza camera nominale (calib logger) e riga orizzonte (fit stereo 390-445): incertezza scala ~±20%


def ground_speed(g0, g1, dt, h=H_CAM, yh=YH):
    """v (m/s) dal flusso sul piano strada: Z=f*h/(y-yh). Nessuna stereo (troppo sparsa). None se pochi punti.
    Il beccheggio (sassi/pavé) sposta tutta l'immagine in y e finisce in v: lo tolgo col flusso verticale mediano dei
    punti LONTANI (riga 150-420, solo rotazione) e lo sottraggo ai punti strada (giro 2: giro 1 senza questo = v rumorosa)."""
    l0, l1 = g0[:, :1280], g1[:, :1280]
    def track(y0, y1, n):
        roi = np.zeros(l0.shape, np.uint8); roi[y0:y1, 150:1130] = 255
        p0 = cv2.goodFeaturesToTrack(l0, n, 0.005, 10, mask=roi)
        if p0 is None: return None, None
        p1, st, _ = cv2.calcOpticalFlowPyrLK(l0, l1, p0, None, winSize=(25, 25), maxLevel=3)
        ok = (st.ravel() == 1)
        return p0[ok, 0], p1[ok, 0]
    p0, p1 = track(500, 790, 300)
    q0, q1 = track(150, 420, 200)
    if p0 is None or len(p0) < 20: return None, 0
    pitch = float(np.median(q1[:, 1] - q0[:, 1])) if (q0 is not None and len(q0) >= 15) else 0.0
    if abs(pitch) > 6.0: return None, 0          # urto/buca: beccheggio troppo forte per compensarlo
    dy = p1[:, 1] - p0[:, 1] - pitch
    m = (p0[:, 1] - yh > 60) & (p1[:, 1] - pitch - yh > 60) & (dy > 0.3)
    if m.sum() < 15: return 0.0 if (np.abs(dy).max() < 1.0) else None, int(m.sum())
    z0 = F_FIT * h / (p0[m, 1] - yh); z1 = F_FIT * h / (p1[m, 1] - pitch - yh)
    return float(np.median((z0 - z1) / dt)), int(m.sum())


def speed_series(prefix, w0, w1, step=3, gap=10):
    """serie (wall_epoch, v m/s, n_punti) fra due istanti wall (epoch)."""
    out = []
    for m, f in clip_list(prefix):
        if m < w0 or m - 32 > w1: continue
        fr = clip_frames(f, m)
        for k in range(0, len(fr) - gap, step):
            tw = (fr[k][0] + fr[k + gap][0]) / 2
            if tw < w0 or tw > w1: continue
            v, n = ground_speed(fr[k][1], fr[k + gap][1], fr[k + gap][0] - fr[k][0])
            out.append((tw, v, n))
    return out


def road_flow_series(prefix, w0, w1):
    """Flusso ottico (Farneback, 320x120 sulla zona strada righe 300-780 della sx, mediana px/frame righe basse) per ogni
    frame fra due istanti wall. Gate bici FERMA = flusso < 0.25 (stesso metodo dello scettico, 2026-11-13). Indipendente dalla stereo."""
    out = []
    for m, f in clip_list(prefix):
        if m < w0 or m - 32 > w1: continue
        fr = clip_frames(f, m)
        prev = None
        for tw, g in fr:
            s = cv2.resize(g[:, :1280][300:780], (320, 120))
            if prev is not None and w0 <= tw <= w1:
                fl = cv2.calcOpticalFlowFarneback(prev, s, None, 0.5, 2, 15, 2, 5, 1.1, 0)
                out.append((tw, float(np.median(np.hypot(fl[..., 0], fl[..., 1])[40:, :]))))
            prev = s
    return out
