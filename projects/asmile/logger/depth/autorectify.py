#!/usr/bin/env python3
"""
autorectify.py — auto-calibrazione stereo SENZA scacchiera.

Risolve il problema #1 della depth attuale (dy=3.75px di disallineamento
verticale -> righe epipolari storte -> disparita' sbagliata -> 7.8% di errore).

Metodo (ICRA-2024 "rectifying homography online self-calibration" + flow-guided
rectification di Tesla, brevetto US 12470683):
  - le camere sono rigide sullo stesso supporto -> baseline e intrinseci sono
    stabili (l'ancora metrica), cio' che driftta e' la ROTAZIONE relativa;
  - in uno stereo rettificato PERFETTO le corrispondenze L<->R stanno sulla
    stessa riga: y_L' == y_R' (disparita' verticale = 0);
  - quindi si stima la piccola rotazione relativa (3-DoF: roll/pitch/yaw) che
    MINIMIZZA la disparita' verticale media dei match, tenendo fissi K,d,baseline.

Niente rettifica non-calibrata (Hartley): perderebbe la scala metrica.

Uso:
  python3 autorectify.py --video clip.h264 --out calib_logger.json \
      [--prior stereo_auto_sift.json] [--focal-px 902] [--frames 60]
"""
import argparse
import numpy as np
import cv2
from scipy.optimize import least_squares

from stereo_common import Calib, split_sbs, CAM_W, CAM_H, BASELINE_MM


# ---------- feature matching L<->R ----------
def match_LR(left, right, max_pts=800):
    """Corrispondenze L<->R robuste: SIFT+ratio+MAGSAC (fallback ORB)."""
    try:
        det = cv2.SIFT_create(nfeatures=max_pts * 3)
        norm = cv2.NORM_L2
    except Exception:
        det = cv2.ORB_create(nfeatures=max_pts * 4)
        norm = cv2.NORM_HAMMING
    k1, des1 = det.detectAndCompute(left, None)
    k2, des2 = det.detectAndCompute(right, None)
    if des1 is None or des2 is None or len(k1) < 8 or len(k2) < 8:
        return np.empty((0, 2)), np.empty((0, 2))
    bf = cv2.BFMatcher(norm)
    raw = bf.knnMatch(des1, des2, k=2)
    good = [m for m, n in (p for p in raw if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return np.empty((0, 2)), np.empty((0, 2))
    pL = np.float32([k1[m.queryIdx].pt for m in good])
    pR = np.float32([k2[m.trainIdx].pt for m in good])
    # outlier rejection con matrice fondamentale (MAGSAC)
    F, mask = cv2.findFundamentalMat(pL, pR, cv2.USAC_MAGSAC, 1.0, 0.999, 10000)
    if mask is not None:
        m = mask.ravel().astype(bool)
        pL, pR = pL[m], pR[m]
    return pL, pR


def collect_matches(video, size, order, flip180, n_frames):
    """Campiona n_frames dal video e accumula tutti i match L<->R."""
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // max(1, n_frames))
    allL, allR = [], []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            left, right = split_sbs(frame, order=order, flip180=flip180)
            if (left.shape[1], left.shape[0]) != size:
                left = cv2.resize(left, size); right = cv2.resize(right, size)
            pL, pR = match_LR(left, right)
            if len(pL):
                allL.append(pL); allR.append(pR)
        i += 1
    cap.release()
    if not allL:
        return np.empty((0, 2)), np.empty((0, 2))
    return np.vstack(allL), np.vstack(allR)


# ---------- ottimizzazione rotazione -> dy minimo ----------
def _rectified_y(calib, R_rel, pL, pR):
    """Rettifica i punti con R_rel e torna (yL', yR') dopo undistort+rettifica."""
    c = Calib(calib.K1, calib.d1, calib.K2, calib.d2, R_rel, calib.T,
              calib.size, calib.baseline_mm)
    R1, R2, P1, P2, _, _, _ = cv2.stereoRectify(
        c.K1, c.d1, c.K2, c.d2, c.size, c.R, c.T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    rL = cv2.undistortPoints(pL.reshape(-1, 1, 2), c.K1, c.d1, R=R1, P=P1).reshape(-1, 2)
    rR = cv2.undistortPoints(pR.reshape(-1, 1, 2), c.K2, c.d2, R=R2, P=P2).reshape(-1, 2)
    return rL[:, 1], rR[:, 1]


def refine_rotation(calib, pL, pR):
    """Trova la rotazione relativa che azzera la disparita' verticale media."""
    R0 = calib.R.copy()

    def resid(rv):
        R_rel = cv2.Rodrigues(rv)[0] @ R0
        yL, yR = _rectified_y(calib, R_rel, pL, pR)
        return yL - yR                       # residuo = disparita' verticale

    r0 = np.zeros(3)
    sol = least_squares(resid, r0, method="lm", max_nfev=200)
    R_new = cv2.Rodrigues(sol.x)[0] @ R0
    out = Calib(calib.K1, calib.d1, calib.K2, calib.d2, R_new, calib.T,
                calib.size, calib.baseline_mm)
    return out, sol


def mean_abs_dy(calib, pL, pR):
    yL, yR = _rectified_y(calib, calib.R, pL, pR)
    return float(np.mean(np.abs(yL - yR)))


# ---------- bootstrap calib per camera NUOVA (senza prior) ----------
def bootstrap_calib(focal_px, size, baseline_mm):
    """Calib iniziale: pp=centro, distorsione 0, R=I, T=[-B,0,0]. La FOCALE
    la correggi col muro-test (validate.py) - e' l'ancora metrica col metro."""
    w, h = size
    K = np.array([[focal_px, 0, w / 2.0], [0, focal_px, h / 2.0], [0, 0, 1.0]])
    d = np.zeros(5)
    return Calib(K.copy(), d.copy(), K.copy(), d.copy(),
                 np.eye(3), np.array([-baseline_mm, 0, 0]), size, baseline_mm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior", help="calib JSON/YAML di partenza (consigliato)")
    ap.add_argument("--focal-px", type=float, default=902.0,
                    help="focale px iniziale se niente prior (OV9281 ~2.7mm ~902)")
    ap.add_argument("--baseline-mm", type=float, default=BASELINE_MM)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true", help="camere NON capovolte")
    args = ap.parse_args()

    size = (CAM_W, CAM_H)
    calib = (Calib.load(args.prior) if args.prior
             else bootstrap_calib(args.focal_px, size, args.baseline_mm))

    print(f"[1] match L<->R su {args.frames} frame...")
    pL, pR = collect_matches(args.video, size, args.order, not args.no_flip, args.frames)
    print(f"    match validi: {len(pL)}")
    if len(pL) < 50:
        raise SystemExit("Troppi pochi match: servono scene con texture e varie profondita'.")

    dy0 = mean_abs_dy(calib, pL, pR)
    print(f"[2] dy verticale PRIMA: {dy0:.3f}px  (target <0.3)")
    calib2, sol = refine_rotation(calib, pL, pR)
    dy1 = mean_abs_dy(calib2, pL, pR)
    print(f"[3] dy verticale DOPO:  {dy1:.3f}px  (miglioramento {dy0 - dy1:+.3f}px)")

    calib2.save(args.out)
    print(f"[4] calib salvata -> {args.out}")
    print("    NB: ora fai il muro-test (validate.py) per fissare la FOCALE col metro.")


if __name__ == "__main__":
    main()
