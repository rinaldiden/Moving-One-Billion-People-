#!/usr/bin/env python3
"""
calib_charuco.py — calibrazione stereo con tabellone ChArUco MOSTRATO A MONITOR.

Alternativa a autorectify.py (auto-calib senza target). La via consigliata da
Daniele: in ~mezz'ora calibri le DUE camere + la stereo in un colpo solo.
Niente scacchiera stampata: mostri il tabellone ChArUco sullo schermo del PC e
lo "fai vedere" alle due OV9281 muovendolo a varie distanze/angoli.

Perche' ChArUco e non scacchiera classica:
  - ogni quadretto porta un marker ArUco -> ID univoci -> funziona anche se il
    tabellone e' PARZIALMENTE visibile o tagliato dal bordo (sullo schermo
    capita sempre). La scacchiera liscia invece la perdi appena esce un angolo.
  - sub-pixel sugli angoli della scacchiera interna -> focale precisa.

Scala metrica: il tabellone a monitor ha una dimensione fisica INCERTA (pixel
dello schermo). Ma a noi la scala la da' la BASELINE NOTA (200mm, ancora del
progetto): calibriamo R,T con ChArUco e poi RISCALIAMO T a |T|=200mm. Gli
intrinseci in px NON dipendono dalla taglia del tabellone, quindi restano buoni.
(Vedi README_calibrazione.md — "la scala la tiene la baseline, non il target".)

Flusso:
  # 1) genera il tabellone e mettilo a schermo intero sul monitor
  python3 calib_charuco.py --make-board board_charuco.png
  # 2) registra ~30s di clip stereo muovendo il monitor davanti alle 2 cam
  #    (vicino/lontano, inclinato, in tutti gli angoli del campo)
  # 3) calibra -> stessa calib JSON di autorectify (drop-in per depth/validate)
  python3 calib_charuco.py --video clip_charuco.h264 --out calib_charuco.json
  # 4) poi come sempre: validate.py (muro-test col metro) e depth.py

Output: JSON nel formato Calib (stereo_common.py) -> drop-in in tutta la pipeline.
"""
import argparse
import datetime
import numpy as np
import cv2

from stereo_common import Calib, split_sbs, CAM_W, CAM_H, BASELINE_MM

# --- parametri tabellone (default sensati per un monitor ~24") ---------------
# DICT 5x5: marker piccoli -> ci stanno piu' quadretti a schermo, robusti.
DEF_DICT = "DICT_5X5_1000"
DEF_SQUARES_X = 7          # colonne di quadretti
DEF_SQUARES_Y = 5          # righe di quadretti
DEF_SQUARE_LEN = 0.030     # lato quadretto in METRI (valore nominale: la scala
                           # vera la impone la baseline; vedi nota in testa)
DEF_MARKER_LEN = 0.022     # lato marker ArUco in metri (< square)


def _dict(name):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def make_board(dict_name, sx, sy, square_len, marker_len):
    """Costruisce il CharucoBoard (API OpenCV >= 4.7)."""
    d = _dict(dict_name)
    try:
        board = cv2.aruco.CharucoBoard((sx, sy), square_len, marker_len, d)
    except Exception:                      # API vecchia (< 4.7)
        board = cv2.aruco.CharucoBoard_create(sx, sy, square_len, marker_len, d)
    return board, d


def _detector(board, d):
    """CharucoDetector (4.7+) con fallback alla detect procedurale vecchia."""
    try:
        return cv2.aruco.CharucoDetector(board), None
    except Exception:
        params = cv2.aruco.DetectorParameters()
        return None, params


def detect_charuco(gray, board, d, detector, params):
    """Ritorna (charuco_corners Nx1x2, charuco_ids Nx1) o (None, None)."""
    if detector is not None:               # API nuova
        cc, ci, _, _ = detector.detectBoard(gray)
        if cc is None or len(cc) < 4:
            return None, None
        return cc, ci
    # API vecchia
    corners, ids, _ = cv2.aruco.detectMarkers(gray, d, parameters=params)
    if ids is None or len(ids) < 4:
        return None, None
    _, cc, ci = cv2.aruco.interpolateCornersCharuco(corners, ids, gray, board)
    if cc is None or len(cc) < 4:
        return None, None
    return cc, ci


def save_board_png(path, board, sx, sy, square_len, marker_len, px_per_square=200):
    """Esporta il tabellone come PNG da mettere a schermo intero."""
    w = sx * px_per_square
    h = sy * px_per_square
    try:
        img = board.generateImage((w, h), marginSize=0, borderBits=1)
    except Exception:
        img = board.draw((w, h), marginSize=0, borderBits=1)
    cv2.imwrite(path, img)
    return (w, h)


# --- raccolta osservazioni dal video -----------------------------------------
def collect_observations(video, board, d, size, order, flip180, n_frames,
                         min_corners=6):
    """
    Campiona il video e per ogni frame tenta la detect ChArUco su L e R.
    Accumula per-camera (per calibrare le intrinseche) e le viste condivise
    (ID comuni L&R, per la stereo).
    """
    detector, params = _detector(board, d)
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // max(1, n_frames))

    monoL = []   # (corners, ids) validi a sinistra
    monoR = []
    stereo = []  # (ccL, ciL, ccR, ciR) con ID in comune
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            left, right = split_sbs(frame, order=order, flip180=flip180)
            if (left.shape[1], left.shape[0]) != size:
                left = cv2.resize(left, size); right = cv2.resize(right, size)
            ccL, ciL = detect_charuco(left, board, d, detector, params)
            ccR, ciR = detect_charuco(right, board, d, detector, params)
            if ccL is not None and len(ccL) >= min_corners:
                monoL.append((ccL, ciL))
            if ccR is not None and len(ccR) >= min_corners:
                monoR.append((ccR, ciR))
            if (ccL is not None and ccR is not None
                    and len(ccL) >= min_corners and len(ccR) >= min_corners):
                common = np.intersect1d(ciL.ravel(), ciR.ravel())
                if len(common) >= min_corners:
                    stereo.append((ccL, ciL, ccR, ciR))
        i += 1
    cap.release()
    return monoL, monoR, stereo


def calibrate_mono(observations, board, size):
    """calibrateCameraCharuco -> (K, dist, rms)."""
    all_c = [o[0] for o in observations]
    all_i = [o[1] for o in observations]
    flags = cv2.CALIB_RATIONAL_MODEL
    rms, K, dist, _, _ = cv2.aruco.calibrateCameraCharuco(
        all_c, all_i, board, size, None, None, flags=flags)
    return K, dist, float(rms)


def _obj_img_points(board, cc, ci):
    """Da angoli ChArUco (corners+ids) ai punti 3D del tabellone e 2D immagine."""
    try:                                   # API nuova
        obj, img = board.matchImagePoints(cc, ci)
        return obj.reshape(-1, 3), img.reshape(-1, 2)
    except Exception:                      # fallback
        chess = board.getChessboardCorners()
        ids = ci.ravel().astype(int)
        obj = chess[ids].astype(np.float32)
        img = cc.reshape(-1, 2).astype(np.float32)
        return obj, img


def stereo_from_charuco(stereo, board, K1, d1, K2, d2, size):
    """
    stereoCalibrate sugli angoli ChArUco con ID COMUNI L&R (intrinseci fissi).
    Ritorna R, T (T in unita' del tabellone: verra' poi riscalato alla baseline).
    """
    objp, imgpL, imgpR = [], [], []
    for ccL, ciL, ccR, ciR in stereo:
        oL, iL = _obj_img_points(board, ccL, ciL)
        oR, iR = _obj_img_points(board, ccR, ciR)
        idL = ciL.ravel().astype(int); idR = ciR.ravel().astype(int)
        common = np.intersect1d(idL, idR)
        if len(common) < 6:
            continue
        mapL = {cid: k for k, cid in enumerate(idL)}
        mapR = {cid: k for k, cid in enumerate(idR)}
        sel_o = np.array([oL[mapL[c]] for c in common], np.float32)
        sel_iL = np.array([iL[mapL[c]] for c in common], np.float32)
        sel_iR = np.array([iR[mapR[c]] for c in common], np.float32)
        objp.append(sel_o); imgpL.append(sel_iL); imgpR.append(sel_iR)
    if len(objp) < 4:
        raise SystemExit("Poche viste stereo con ID comuni L&R: muovi il tabellone "
                         "piu' lentamente e tienilo intero in entrambe le camere.")
    flags = cv2.CALIB_FIX_INTRINSIC
    rms, *_ , R, T, _, _ = cv2.stereoCalibrate(
        objp, imgpL, imgpR, K1, d1, K2, d2, size,
        flags=flags,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6))
    return R, T.reshape(3, 1), float(rms), len(objp)


def rectified_dy(calib):
    """dy verticale residua sui punti-test: stima rapida della bonta' rettifica.
    Qui non abbiamo match grezzi, quindi e' informativo: la stereoCalibrate RMS
    e' il numero di riferimento. Lasciato 0 se non calcolabile."""
    try:
        _ = calib.rectify()
        return None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Calibrazione stereo ChArUco (monitor).")
    ap.add_argument("--make-board", metavar="PNG",
                    help="genera il tabellone PNG da mettere a schermo e esce")
    ap.add_argument("--video", help="clip stereo SBS col tabellone a monitor")
    ap.add_argument("--out", help="calib JSON di uscita (drop-in depth/validate)")
    ap.add_argument("--dict", default=DEF_DICT)
    ap.add_argument("--squares-x", type=int, default=DEF_SQUARES_X)
    ap.add_argument("--squares-y", type=int, default=DEF_SQUARES_Y)
    ap.add_argument("--square-len", type=float, default=DEF_SQUARE_LEN,
                    help="lato quadretto in m (nominale; la scala la da' la baseline)")
    ap.add_argument("--marker-len", type=float, default=DEF_MARKER_LEN)
    ap.add_argument("--baseline-mm", type=float, default=BASELINE_MM,
                    help="baseline NOTA a cui riscalare T (ancora metrica)")
    ap.add_argument("--frames", type=int, default=120,
                    help="quanti frame campionare dal clip")
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true", help="camere NON capovolte")
    args = ap.parse_args()

    board, d = make_board(args.dict, args.squares_x, args.squares_y,
                          args.square_len, args.marker_len)

    if args.make_board:
        wh = save_board_png(args.make_board, board, args.squares_x, args.squares_y,
                            args.square_len, args.marker_len)
        print(f"[board] tabellone {args.squares_x}x{args.squares_y} ({args.dict}) "
              f"-> {args.make_board}  ({wh[0]}x{wh[1]}px)")
        print("        mettilo a SCHERMO INTERO e mostralo alle 2 cam da varie "
              "distanze/angoli, tenendolo INTERO in entrambe.")
        print("        (cross-check opz.: misura col metro il lato di un quadretto "
              "a monitor e passalo con --square-len <m>)")
        return

    if not args.video or not args.out:
        ap.error("servono --video e --out (oppure --make-board).")

    size = (CAM_W, CAM_H)
    flip = not args.no_flip
    print(f"[1] detect ChArUco su ~{args.frames} frame del clip...")
    monoL, monoR, stereo = collect_observations(
        args.video, board, d, size, args.order, flip, args.frames)
    print(f"    viste valide:  L={len(monoL)}  R={len(monoR)}  stereo(common)={len(stereo)}")
    if len(monoL) < 8 or len(monoR) < 8:
        raise SystemExit("Troppe poche viste: registra piu' a lungo, tabellone "
                         "ben illuminato e INTERO in entrambe le camere.")

    print("[2] intrinseche per camera (calibrateCameraCharuco)...")
    K1, d1, rms1 = calibrate_mono(monoL, board, size)
    K2, d2, rms2 = calibrate_mono(monoR, board, size)
    print(f"    RMS reproj  L={rms1:.3f}px  R={rms2:.3f}px")
    print(f"    focale      fx_L={K1[0,0]:.1f}  fx_R={K2[0,0]:.1f}px")

    print("[3] stereo (R,T) con intrinseci fissi...")
    R, T, rms_st, n_views = stereo_from_charuco(stereo, board, K1, d1, K2, d2, size)
    scale = args.baseline_mm / float(np.linalg.norm(T))
    T_scaled = T * scale
    print(f"    RMS stereo  {rms_st:.3f}px  su {n_views} viste")
    print(f"    |T| grezzo  {np.linalg.norm(T):.4f} (unita' tabellone) -> "
          f"riscalato a {args.baseline_mm:.1f}mm (scala x{scale:.1f})")

    calib = Calib(K1, d1, K2, d2, R, T_scaled, size=size,
                  baseline_mm=args.baseline_mm)
    # salvataggio + metadati nel JSON (additivi: Calib.load ignora le chiavi extra)
    calib.save(args.out)
    import json
    with open(args.out) as f:
        blob = json.load(f)
    blob.update({
        "method": "ChArUco monitor + stereoCalibrate",
        "charuco": {"dict": args.dict, "squares": [args.squares_x, args.squares_y],
                     "square_len_m": args.square_len, "marker_len_m": args.marker_len},
        "rms_reproj_px": {"left": rms1, "right": rms2, "stereo": rms_st},
        "stereo_views": n_views,
        "scale_to_baseline": scale,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    with open(args.out, "w") as f:
        json.dump(blob, f, indent=2)
    print(f"[4] calib salvata -> {args.out}")
    print("    NB: ora conferma col MURO-TEST -> python3 validate.py --calib "
          f"{args.out} --targets targets.json")


if __name__ == "__main__":
    main()
