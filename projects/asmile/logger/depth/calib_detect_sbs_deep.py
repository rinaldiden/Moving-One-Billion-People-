#!/usr/bin/env python3
"""
calib_detect_sbs_deep.py — rilevazione ChArUco "a fondo" per clip SBS (logger001, Arducam Camarray 2560x800).
Scritto 2026-11-21 (asmile-calib): con quadretti ~20-35 px + h264 a 0.5 Mbps il detector di default
(calib_charuco_dual.collect, 1x, 1 frame su 3) trova poche viste. Qui: OGNI frame, parametri ArUco larghi,
upscaling 2x poi 3x (solo se serve), coordinate riportate al pixel originale (centro-pixel corretto).
Uscita: .npz compatibile con calib_charuco_dual.load_views_npz (usa poi `calib_charuco_dual.py --views-npz`).
Lavora per CLIP (multiprocessing), nessun video scritto altrove.

Uso: calib_detect_sbs_deep.py --out views.npz --squares 11x5 --square-len 0.038 clip1.h264 clip2.h264 ...
"""
import argparse, json, os, sys
from multiprocessing import Pool
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from calib_charuco_dual import gray_frames, make_board, CAM_W, CAM_H, MIN_CORNERS  # noqa: E402

_G = {}


def _init(dict_name, sx, sy, sq, mk, keep=None):
    cv2.setNumThreads(1)
    _G["keep"] = keep
    board = make_board(dict_name, sx, sy, sq, mk)
    p = cv2.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 5
    p.cornerRefinementMaxIterations = 100
    p.cornerRefinementMinAccuracy = 0.01
    p.adaptiveThreshWinSizeMax = 63
    p.adaptiveThreshWinSizeStep = 6
    p.minMarkerPerimeterRate = 0.01
    p.errorCorrectionRate = 0.9
    p.adaptiveThreshConstant = 4          # default 7: con il lato L sfocato (Laplaciano 2x piu' basso) serve piu' sensibile
    _G["det"] = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), p)
    _G["board"] = board


def _prep(gray, scale, sharpen):
    g = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if sharpen:
        # unsharp a raggio largo (sigma 2*scale px, peso 5): il lato L del Camarray e' ~2x piu' sfocato di R
        # (Laplaciano 77 vs 168 sul tabellone) e senza questo i marker non si decodificano (0/60 -> 47/60 viste).
        g = cv2.addWeighted(g, 1 + 5.0, cv2.GaussianBlur(g, (0, 0), 2.0 * scale), -5.0, 0)
    return g


def refine_corners(gray, img):
    """Il rilevamento con unsharp trova bene id e posizione approssimata, ma sposta i corner (residuo omografia
    0.83 px contro 0.5 sul 2x senza unsharp, 24 viste R). Si raffinano quindi i corner sull'immagine ORIGINALE
    (2x bicubica, nessun filtro): cornerSubPix win 8 (=+-4 px originali), misurato 0.58 L / 0.48 R px (omografia).
    Spostamento > 2 px = raffinamento andato altrove: si tiene la stima di partenza per quel corner."""
    sc = 2
    g = cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
    p0 = ((img.astype(np.float32) + 0.5) * sc - 0.5).reshape(-1, 1, 2)
    p1 = p0.copy()
    cv2.cornerSubPix(g, p1, (8, 8), (-1, -1), (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 0.001))
    bad = np.linalg.norm((p1 - p0).reshape(-1, 2), axis=1) > 2.0 * sc
    p1[bad] = p0[bad]
    return ((p1.reshape(-1, 2) + 0.5) / sc - 0.5).astype(np.float32)


def _one(gray, scale, sharpen=True):
    det, board = _G["det"], _G["board"]
    g = _prep(gray, scale, sharpen)
    cc, ci, mc, mi = det.detectBoard(g)
    nm = 0 if mi is None else len(mi)
    if cc is None or len(cc) < 6:
        return None, nm
    obj, img = board.matchImagePoints(cc, ci)
    img = img.reshape(-1, 2) / scale + (0.5 / scale - 0.5)      # centro-pixel: x_orig = (x_up+0.5)/s-0.5
    return dict(ids=ci.ravel().astype(int), img=img.astype(np.float32)), nm


def _side(gray):
    best, nmax = None, 0
    # un solo percorso di base (2x + unsharp); 3x e 2x senza unsharp solo come ripiego se < 20 corner
    for sc, sh in ((2, True), (3, True), (2, False)):
        d, nm = _one(gray, sc, sh)
        nmax = max(nmax, nm)
        if d is not None and (best is None or len(d["ids"]) > len(best["ids"])):
            best = d
        if best is not None and len(best["ids"]) >= 20:
            break
        if nm == 0 and sc == 2:      # niente marker a 2x: inutile insistere
            break
    if best is not None:
        best["img"] = refine_corners(gray, best["img"])
    return best, nmax


def work(path):
    out = []
    keep = _G.get("keep")
    for i, f in enumerate(gray_frames(path, 2 * CAM_W, CAM_H)):
        if keep is not None and (os.path.basename(path), i) not in keep:
            out.append((i, None, None, 0, 0))
            continue
        L, nl = _side(f[:, :CAM_W])
        R, nr = _side(f[:, CAM_W:])
        out.append((i, L, R, nl, nr))
    return path, out


def _refine_clip(path, frames):
    cv2.setNumThreads(1)
    out = {}
    for i, f in enumerate(gray_frames(path, 2 * CAM_W, CAM_H)):
        if i in frames:
            L, R = frames[i]
            if L is not None:
                L = dict(L, img=refine_corners(f[:, :CAM_W], L["img"]))
            if R is not None:
                R = dict(R, img=refine_corners(f[:, CAM_W:], R["img"]))
            out[i] = (L, R)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dict", default="DICT_5X5_1000")
    ap.add_argument("--squares", default="11x5")
    ap.add_argument("--square-len", type=float, required=True)
    ap.add_argument("--marker-len", type=float, default=None)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--prefilter-pkl", help="pkl di un primo passaggio leggero: si rielaborano a fondo (unsharp, 3x) solo i "
                                            "frame con >= --prefilter-markers marker su un lato (tempo /10, il passaggio "
                                            "leggero e' gia' a 2x con soglie larghe)")
    ap.add_argument("--prefilter-markers", type=int, default=2)
    ap.add_argument("--refine-pkl", help="rapido: riparte da un pkl gia' rilevato (stesso insieme di clip) e RAFFINA solo i corner "
                                         "sull'originale (refine_corners), senza rilevare di nuovo")
    a = ap.parse_args()
    sx, sy = map(int, a.squares.lower().split("x"))
    mk = a.marker_len or round(0.74 * a.square_len, 5)
    clips = sorted(a.clips, key=lambda p: os.path.basename(p))
    if a.refine_pkl:
        import pickle as _pk
        z0 = _pk.load(open(a.refine_pkl, "rb"))
        todo = {}
        for (fr, L, R, nl, nr, clip, i) in z0["rows"]:
            if L is not None or R is not None:
                todo.setdefault(clip, {})[i] = (L, R)
        base = os.path.dirname(os.path.abspath(a.clips[0]))
        with Pool(a.jobs) as pool:
            out = pool.starmap(_refine_clip, [(os.path.join(base, c), t) for c, t in todo.items()])
        new = {c: r for c, r in zip(todo, out)}
        rows = []
        for (fr, L, R, nl, nr, clip, i) in z0["rows"]:
            if clip in new and i in new[clip]:
                L, R = new[clip][i]
            rows.append((fr, L, R, nl, nr, clip, i))
        _pk.dump(dict(rows=rows, meta=dict(z0["meta"], refined=True)), open(a.out[:-4] + ".pkl", "wb"))
        print(f"raffinati corner di {sum(len(t) for t in todo.values())} frame -> {a.out[:-4]}.pkl")
        return
    keep = None
    if a.prefilter_pkl:
        import pickle as _pk
        z0 = _pk.load(open(a.prefilter_pkl, "rb"))
        keep = {(r[5], r[6]) for r in z0["rows"] if max(r[3], r[4]) >= a.prefilter_markers}
        print(f"prefiltro: {len(keep)} frame su {len(z0['rows'])} da rielaborare a fondo", flush=True)
    with Pool(a.jobs, initializer=_init, initargs=(a.dict, sx, sy, a.square_len, mk, keep)) as pool:
        res = dict(pool.imap_unordered(work, clips))
    frames, rows, off = [], [], 0
    for p in clips:
        r = res[p]
        for (i, L, R, nl, nr) in r:
            rows.append((off + i, L, R, nl, nr, os.path.basename(p), i))
        off += len(r)
    # npz: tutte le rilevazioni (>=6 corner) per frame globale; NIENTE dedupe qui
    import pickle
    pk = a.out[:-4] + ".pkl"
    pickle.dump(dict(rows=rows, meta=dict(dict=a.dict, sx=sx, sy=sy, square_len=a.square_len, marker_len=mk,
                                         clips=[os.path.basename(c) for c in clips],
                                         clip_frames=[len(res[c]) for c in clips])), open(pk, "wb"))
    nL = sum(1 for r in rows if r[1] is not None and len(r[1]["ids"]) >= MIN_CORNERS)
    nR = sum(1 for r in rows if r[2] is not None and len(r[2]["ids"]) >= MIN_CORNERS)
    print(f"frame {len(rows)}  L>={MIN_CORNERS}: {nL}  R>={MIN_CORNERS}: {nR}  -> {pk}")


if __name__ == "__main__":
    main()
