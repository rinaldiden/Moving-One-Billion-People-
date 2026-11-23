#!/usr/bin/env python3
"""Depth SGBM su logger02 al buio vs crepuscolo vs giorno: % pixel validi (check L-R) nel corridoio davanti.

Calib: CANDIDATO_v3 (fatta a 1280x720). Il modo 1280x800 parte dalla riga 0 del sensore, il 720 dalla riga 40
(ov9281_1280x800.h: 0x3803 0x28 -> 0x00) => il 720 è il crop centrale e basta cy += 40 su entrambe le camere.
Le clip a 720 righe (firmware prima delle 15:07) usano la calib così com'è.
Il controllo dy (SIFT dopo la rettifica) è stampato per ogni gruppo: se la mediana |dy| > 1.5 px la calib non regge.

Uso: ~/.asmile_depth_venv/bin/python buio_depth_logger02.py <dir_logger02> <calib.json> <out_dir> <gruppo>:<clipA>@<sessB>[,...] ...
"""
import csv, glob, json, os, sys
import cv2, numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "depth"))
from stereo_depth import compute_depth, colorize  # noqa: E402

D, CAL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
PASSO = int(os.environ.get("PASSO", "16"))
c = json.load(open(CAL))
SGBM = dict(minDisparity=0, numDisparities=128, blockSize=9, P1=8 * 9 * 9, P2=32 * 9 * 9, disp12MaxDiff=1,
            uniquenessRatio=5, speckleWindowSize=200, speckleRange=2, preFilterCap=63)
_MAPS = {}


def mappe(H):
    """rettifica per altezza H (720 = calib nativa, 800 = cy + 40)"""
    if H in _MAPS: return _MAPS[H]
    K1, K2 = np.array(c["K_left"]), np.array(c["K_right"])
    K1[1, 2] += (H - 720) / 2; K2[1, 2] += (H - 720) / 2
    d1, d2 = np.array(c["dist_left"]), np.array(c["dist_right"])
    R, T = np.array(c["R"]), np.array(c["T"]).reshape(3, 1)
    SZ = (1280, H)
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, d1, K2, d2, SZ, R, T, flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    m1 = cv2.initUndistortRectifyMap(K1, d1, R1, P1, SZ, cv2.CV_32FC1)
    m2 = cv2.initUndistortRectifyMap(K2, d2, R2, P2, SZ, cv2.CV_32FC1)
    F = float(P1[0, 0]); CY = float(P1[1, 2])
    # corridoio: strada davanti, sotto l'orizzonte (cy rettificato), terzo centrale, fino a 20 px dal fondo
    roi = (int(CY) + 30, H - 20, 400, 880)
    print(f"H={H} f_rett={F:.1f} cy_rett={CY:.1f} corridoio y{roi[0]}-{roi[1]} x{roi[2]}-{roi[3]}")
    _MAPS[H] = (m1, m2, F, roi)
    return _MAPS[H]


sift = cv2.SIFT_create(800)


def frames(clip):
    return [int(r["t_a_us"]) for r in csv.DictReader(open(clip[:-5] + "_frames.csv"))]


def leggi(clip, keep):
    t = frames(clip); cap = cv2.VideoCapture(clip); out = {}; i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i < len(t) and keep(i, t[i]): out[t[i]] = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        i += 1
    return out


def dy_check(a, b):
    ka, da = sift.detectAndCompute(a, None); kb, db = sift.detectAndCompute(b, None)
    if da is None or db is None: return []
    mm = cv2.BFMatcher().knnMatch(da, db, k=2)
    return [kb[m.trainIdx].pt[1] - ka[m.queryIdx].pt[1] for m, n in (x for x in mm if len(x) == 2)
            if m.distance < 0.7 * n.distance and 0 < ka[m.queryIdx].pt[0] - kb[m.trainIdx].pt[0] < 130]


righe = []
for arg in sys.argv[4:]:
    gruppo, lst = arg.split(":", 1)
    for item in lst.split(","):
        ca, sessB = item.split("@")
        pa = f"{D}/{ca}.h264"
        if not os.path.exists(pa): print("manca", pa); continue
        A = leggi(pa, lambda i, t: i % PASSO == 0)
        t0, t1 = min(A), max(A); tA = np.array(sorted(A))
        B = {}
        for cb in sorted(glob.glob(f"{D}/clip_20261123_{sessB}_B_*.h264")):
            tb = frames(cb)
            if not tb or tb[-1] < t0 or tb[0] > t1: continue
            B.update(leggi(cb, lambda i, t: np.min(np.abs(tA - t)) < 12000))
        if not B: print("niente B per", ca); continue
        tB = np.array(sorted(B)); dys = []
        for k, t in enumerate(tA):
            j = int(np.argmin(np.abs(tB - t)))
            if abs(tB[j] - t) > 12000: continue
            m1, m2, F, (Y0, Y1, X0, X1) = mappe(A[t].shape[0])
            ra = cv2.remap(A[t], *m1, cv2.INTER_LINEAR); rb = cv2.remap(B[tB[j]], *m2, cv2.INTER_LINEAR)
            if k % 8 == 0: dys += dy_check(ra, rb)
            depth, disp = compute_depth(ra, rb, F, 200.0, SGBM, swap=False)
            roi = depth[Y0:Y1, X0:X1]; g = ra[Y0:Y1, X0:X1]
            righe.append(dict(gruppo=gruppo, clip=ca, t=t, H=A[t].shape[0], dt_ms=abs(tB[j] - t) / 1e3, luma_corr=float(g.mean()),
                              validi_corr=float((roi > 0).mean() * 100), validi_tutto=float((depth > 0).mean() * 100),
                              z_med=float(np.median(roi[roi > 0])) if (roi > 0).any() else float("nan")))
            if k in (16, 40):
                vis = np.hstack([cv2.cvtColor(ra, cv2.COLOR_GRAY2BGR), colorize(depth, 15)])
                cv2.rectangle(vis, (X0, Y0), (X1, Y1), (0, 255, 0), 2)
                cv2.imwrite(f"{OUT}/{gruppo}_{ca[-14:]}_{k}.jpg", cv2.resize(vis, (1280, 400)), [cv2.IMWRITE_JPEG_QUALITY, 80])
        dy = np.abs(np.array(dys)) if dys else np.array([np.nan])
        print(gruppo, ca, "coppie", sum(r["clip"] == ca for r in righe), "dy_med", round(float(np.median(dy)), 2),
              "dy_p95", round(float(np.percentile(dy, 95)), 2), "n_dy", len(dys), flush=True)
with open(f"{OUT}/depth.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(righe[0])); w.writeheader(); w.writerows(righe)
for g in dict.fromkeys(r["gruppo"] for r in righe):
    R_ = [r for r in righe if r["gruppo"] == g]
    print(g, "n", len(R_), "validi_corr_med", round(np.median([r["validi_corr"] for r in R_]), 1),
          "p25", round(np.percentile([r["validi_corr"] for r in R_], 25), 1),
          "validi_tutto_med", round(np.median([r["validi_tutto"] for r in R_]), 1),
          "luma_corr_med", round(np.median([r["luma_corr"] for r in R_]), 1), "dt_med", round(np.median([r["dt_ms"] for r in R_]), 1))
