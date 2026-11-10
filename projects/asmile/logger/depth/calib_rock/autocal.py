#!/usr/bin/env python3
"""
autocal.py - calibrazione automatica di un set NUOVO di camere (profilo #001).

(a) CON tabellone (collaudo a campione): rendi/leggi coppie L/R del ChArUco, scegli il modello di lente sulle
    viste TENUTE FUORI (mai col RMS del fit), stereo con intrinseci fissi, |T| dal lato misurato del tabellone
    (200 mm +-3% e' un CONTROLLO, mai forzata).
(b) SENZA tabellone: vedi online.py (nominale #001 + correzione online roll/pitch dal dy, yaw/scala dal moto+encoder).

Esce sempre un CANDIDATO (mai sovrascrive la calib di fabbrica) + un verdetto VERDE/ROSSO con i motivi.
"""
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from stereo_common import Calib  # noqa: E402
import twin  # noqa: E402
import render  # noqa: E402
import calib_charuco_dual as ccd  # noqa: E402  (riuso: calib_mono, holdout_reproj, stereo_fit, stereo_pose_rms, zone_of)

W, H = twin.W, twin.H
GATE_BOARD = dict(mono_rms_px=0.5, stereo_rms_px=1.0, baseline_tol=0.03, min_corners_zone=40, min_views_zone=4,
                  min_holdout_zone=12, dy_holdout_p95_px=0.8, rim_px=40, rim_min=3)

# pixel QUADRATI (OV9281 1280x800): fx = fy, quindi CALIB_FIX_ASPECT_RATIO (con guess fx=fy). Toglie un grado di liberta'
# che nel tabellone piano si confonde con focale, centro ottico e distorsione.
_SQ = cv2.CALIB_FIX_ASPECT_RATIO
MODEL_FLAGS = {   # candidati semplici (5-8 parametri) scelti sulle viste tenute fuori
    "k1k2": _SQ | cv2.CALIB_ZERO_TANGENT_DIST | cv2.CALIB_FIX_K3,
    "k1k2k3": _SQ | cv2.CALIB_ZERO_TANGENT_DIST,
    "k1k2+tang": _SQ | cv2.CALIB_FIX_K3,
    "rational": _SQ | cv2.CALIB_RATIONAL_MODEL | cv2.CALIB_ZERO_TANGENT_DIST,
    "rational+tang": _SQ | cv2.CALIB_RATIONAL_MODEL,
}


# ---------------------------------------------------------------------------------------------- viste del tabellone
def make_detector(board):
    """Detector ChArUco vero con parametri adatti a marker piccoli (limite osservato sul gemello:
    A2 50 mm ~3 m, A3 38 mm ~1.5 m a 1280x800 con M12: oltre serve un tabellone piu' grande)."""
    dp = cv2.aruco.DetectorParameters()
    dp.minMarkerPerimeterRate = 0.005
    dp.perspectiveRemovePixelPerCell = 4
    dp.adaptiveThreshWinSizeMin, dp.adaptiveThreshWinSizeMax, dp.adaptiveThreshWinSizeStep = 3, 33, 6
    dp.polygonalApproxAccuracyRate = 0.05
    dp.minCornerDistanceRate = 0.02
    dp.errorCorrectionRate = 0.8
    dp.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), dp)


_EDGE = [(0.03, 0.22), (0.4, 0.6), (0.78, 0.97)]     # centro del tabellone: vicino al bordo per le zone esterne
ZONE_BOX = [(_EDGE[i % 3][0], _EDGE[i % 3][1], _EDGE[i // 3][0], _EDGE[i // 3][1]) for i in range(9)]


def sample_poses_zoned(rng, n, board_name, z_range=(0.9, 2.8), zones=range(9), inst=None):
    """Come sample_poses ma a giro sulle zone 3x3 (il collaudatore deve riempire TUTTE le zone, bordi inclusi)."""
    zones = list(zones)
    if zones == list(range(9)):      # le zone basse perdono metà tabellone fuori quadro: ne servono di più
        zones = [0, 1, 2, 3, 4, 5, 6, 6, 7, 7, 8, 8]
    out = []
    for k in range(n):
        zb = ZONE_BOX[zones[k % len(zones)]]
        zr = z_range if zones[k % len(zones)] == 4 else (z_range[0] * 0.85, min(z_range[1], 1.9))
        # l'operatore guarda le anteprime di ENTRAMBE le camere: meta' delle viste puntano una zona della cam2
        cam = 2 if (inst is not None and (k // len(zones)) % 2 == 1) else 1
        out += sample_poses(rng, 1, board_name, region=zb, z_range=zr, inst=inst, cam=cam)
    return out


def sample_poses(rng, n, board_name, region=(0.05, 0.95, 0.05, 0.95), z_range=(0.9, 2.8), f=1154.0, inst=None, cam=1):
    """Pose del tabellone (rvec,tvec nel frame cam1): centro del tabellone puntato su un pixel della regione
    (frazioni di W,H), distanza log-uniforme, inclinazione fino a 45 gradi, rotazione nel piano +-25."""
    d, sx, sy, sq, mk = render.BOARDS[board_name]
    cen = np.array([sx * sq / 2, sy * sq / 2, 0.0])
    out = []
    for _ in range(n):
        Z = float(np.exp(rng.uniform(np.log(z_range[0]), np.log(z_range[1]))))
        u = rng.uniform(region[0], region[1]) * W
        v = rng.uniform(region[2], region[3]) * H
        X = np.array([(u - W / 2) / f * Z, (v - H / 2) / f * Z, Z])
        if cam == 2 and inst is not None:      # il punto che la cam2 vede in (u,v), espresso nel frame cam1
            X2 = inst.cam2.rays(np.array([u]), np.array([v]))[0] * Z
            X = inst.R.T @ (X2 - inst.T.ravel())
        ax = rng.normal(size=3)
        ax[2] = 0
        ax = ax / (np.linalg.norm(ax) + 1e-9) * np.radians(rng.uniform(12, 38))
        R = cv2.Rodrigues(ax)[0] @ cv2.Rodrigues(np.array([0, 0, np.radians(rng.uniform(-25, 25))]))[0]
        t = X - R @ cen
        out.append((cv2.Rodrigues(R)[0].ravel(), t))
    return out


def collect_rendered(inst, board_name, poses, rng, board_sq_scale=1.0, swap_files=False):
    """Rende le coppie e usa il DETECTOR vero. board_sq_scale!=1: il tabellone fisico ha il lato diverso da quello
    DICHIARATO a chi calibra (caso negativo: lato misurato male). swap_files: file L/R scambiati (video_left=DESTRA)."""
    board = render.make_board(board_name)
    det = make_detector(board)
    views = []
    for k, (rv, tv) in enumerate(poses):
        pl = render.board_plane(board_name, rv, tv)
        if board_sq_scale != 1.0:      # il tabellone FISICO ha il lato k volte quello dichiarato a chi calibra
            k = board_sq_scale
            Rb = cv2.Rodrigues(np.asarray(rv, float).reshape(3, 1))[0]
            pl.w, pl.h, pl.res = pl.w * k, pl.h * k, pl.res * k
            pl.p0 = Rb @ np.array([-render.MARGIN_M * k, -render.MARGIN_M * k, 0.0]) + np.asarray(tv, float)
        e = rng.uniform(0.75, 1.15)
        a = render.render(inst, 1, [pl], rng, exposure=e)
        b = render.render(inst, 2, [pl], rng, exposure=e)
        if swap_files:
            a, b = inst.to_files(a, b)
        views.append(dict(frame=k, L=_detect(det, board, a), R=_detect(det, board, b)))
    return views


def collect_adaptive(inst, board_name, rng, n0=100, rounds=5, add=14, z_range=(0.9, 2.8), render_kw=None):
    """Come l'operatore con l'app: dopo il primo giro si guarda quali zone (per camera) sono povere di corner e si
    aggiungono viste MIRATE su quelle. Soglie piu' alte di quelle del gate (il 25% va in hold-out)."""
    poses = sample_poses_zoned(rng, n0, board_name, z_range=z_range, inst=inst)
    render_kw = render_kw or {}
    views = collect_rendered(inst, board_name, poses, rng, **render_kw)
    for _ in range(rounds):
        need = []   # (zona, camera)
        both = [v for v in views if v["L"] is not None and v["R"] is not None]    # conta solo le viste STEREO
        for ci, key in ((1, "L"), (2, "R")):
            c, nv = zone_stats(both, key)
            need += [(z, ci) for z in range(9) if c[z] < 3 * GATE_BOARD["min_corners_zone"] or nv[z] < 2 * GATE_BOARD["min_views_zone"] + 2]
        if not need:
            break
        new = []
        for k in range(add):
            z, ci = need[k % len(need)]
            zb = ZONE_BOX[z]
            zr = z_range if z == 4 else (z_range[0] * 0.85, min(z_range[1], 1.9))
            new += sample_poses(rng, 1, board_name, region=zb, z_range=zr, inst=inst, cam=ci)
        views += collect_rendered(inst, board_name, new, rng, **render_kw)
    return views


def calibrate_with_retry(inst, board_name, rng, profile, n0=100, max_retry=2, seed=0, render_kw=None):
    """Il ciclo dell'operatore con l'app: se la calibrazione e' ROSSO per copertura o dy di zona, si aggiungono viste
    MIRATE alle zone deboli (per camera) e si riprova, al massimo max_retry volte. Ritorna (calib, rep, views, n_retry)."""
    render_kw = render_kw or {}
    views = collect_adaptive(inst, board_name, rng, n0=n0, render_kw=render_kw)
    for k in range(max_retry + 1):
        cand, rep = board_calibrate(views, profile, board_name, seed=seed + k)
        weak = rep.get("zone_deboli") or []
        if rep["verdetto_interno"] == "VERDE" or not weak or k == max_retry:
            return cand, rep, views, k
        new = []
        for j in range(24):
            z, ci = weak[j % len(weak)]
            zr = (0.9 * 0.85, 1.9) if z != 4 else (0.9, 2.8)
            new += sample_poses(rng, 1, board_name, region=ZONE_BOX[z], z_range=zr, inst=inst, cam=ci)
        views += collect_rendered(inst, board_name, new, rng, **render_kw)
    return cand, rep, views, max_retry


def _detect(det, board, gray):
    cc, ci, _, _ = det.detectBoard(gray)
    if cc is None or len(cc) < 6:
        return None
    obj, img = board.matchImagePoints(cc, ci)
    return dict(ids=ci.ravel().astype(int), obj=obj.reshape(-1, 3).astype(np.float32),
                img=img.reshape(-1, 2).astype(np.float32))


# ---------------------------------------------------------------------------------------------- calibrazione
def zone_stats(views, key):
    corners = np.zeros(9, int)
    nviews = np.zeros(9, int)
    for v in views:
        d = v.get(key)
        if d is None:
            continue
        z = ccd.zone_of(d["img"])
        bc = np.bincount(z, minlength=9)
        corners += bc
        nviews += (bc >= 4).astype(int)
    return corners, nviews


def radial_monotone(K, D, margin=1.08):
    """La distorsione radiale deve essere MONOTONA fino al bordo (angolo dell'immagine x margine): un modello
    razionale libero puo' avere un fit perfetto sul tabellone e impazzire negli angoli, dove non ci sono corner."""
    D = np.asarray(D, float)
    d = np.zeros(8)
    d[:min(len(D), 8)] = D[:8]
    k1, k2, k3, k4, k5, k6 = d[0], d[1], d[4], d[5], d[6], d[7]
    rmax = np.hypot(max(K[0, 2], W - K[0, 2]) / K[0, 0], max(K[1, 2], H - K[1, 2]) / K[1, 1]) * margin
    r = np.linspace(1e-3, rmax, 400)
    rd = r * (1 + k1 * r ** 2 + k2 * r ** 4 + k3 * r ** 6) / (1 + k4 * r ** 2 + k5 * r ** 4 + k6 * r ** 6)
    return bool(np.all(np.diff(rd) > 0) and np.all(np.isfinite(rd)))


SELECT_MODE = "edge"      # "all": hold-out su tutti i corner; "edge": metrica sul bordo (corner oltre EDGE_R del raggio massimo)
EDGE_R = 0.55             # frazione del raggio-angolo oltre la quale un corner di hold-out conta come "bordo"
DISAGREE_PX = None  # (PROVATO e SPENTO: non separa, vedi README) # un modello flessibile e' eleggibile solo se NON si discosta dal modello semplice di riferimento (primo eleggibile
                    # in MODEL_FLAGS) di piu' di tanti pixel in NESSUN punto dell'immagine, angoli inclusi: l'hold-out non vede gli angoli
                    # (nessun corner entro ~40 px), li' un modello flessibile estrapola (dy 3-8 px visti sul gemello). None = spento.
TOL_ABS, TOL_REL = 0.0, 0.0   # "il piu' semplice entro" la tolleranza dal migliore (sul punteggio di scelta)
EDGE_W = 1.0              # peso del bordo nella metrica di scelta: sqrt((rms_all^2 + W*rms_bordo^2)/(1+W))


def holdout_edge_rms(hold, key, K, D, edge_r=None):
    """Come ccd.holdout_reproj ma restituisce anche l'RMS dei soli corner di BORDO (raggio dal centro ottico stimato >
    edge_r x raggio-angolo): e' li' che i modelli semplici si separano (estrapolazione) e il RMS globale non li vede."""
    edge_r = EDGE_R if edge_r is None else edge_r
    rmax = np.hypot(max(K[0, 2], W - K[0, 2]), max(K[1, 2], H - K[1, 2]))
    e_all, e_edge = [], []
    for v in hold:
        d = v[key]
        if d is None or len(d["ids"]) < 8:
            continue
        ok, rv, tv = cv2.solvePnP(d["obj"], d["img"], K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue
        pr, _ = cv2.projectPoints(d["obj"], rv, tv, K, D)
        e = np.linalg.norm(pr.reshape(-1, 2) - d["img"], axis=1)
        r = np.hypot(d["img"][:, 0] - K[0, 2], d["img"][:, 1] - K[1, 2]) / rmax
        e_all += list(e)
        e_edge += list(e[r > edge_r])
    if not e_all:
        return float("nan"), float("nan"), 0
    ra = float(np.sqrt(np.mean(np.square(e_all))))
    re_ = float(np.sqrt(np.mean(np.square(e_edge)))) if len(e_edge) >= 15 else ra
    return ra, re_, len(e_edge)


def model_disagreement_px(K1, D1, K2, D2, n=(33, 21)):
    """Scarto massimo (px, nel piano immagine con K1) fra due modelli di lente, su una griglia che include i 4 angoli."""
    xs = np.linspace(0, W - 1, n[0])
    ys = np.linspace(0, H - 1, n[1])
    P = np.array([[x, y] for y in ys for x in xs], np.float64).reshape(-1, 1, 2)
    a = cv2.undistortPoints(P, K1, D1, P=K1).reshape(-1, 2)
    b = cv2.undistortPoints(P, K2, D2, P=K1).reshape(-1, 2)
    return float(np.max(np.linalg.norm(a - b, axis=1)))


def _k0(profile):
    f = W / 2 / np.tan(np.radians(profile["hfov_deg"] / 2))
    return np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])


def _mono(views, key, flags, K0):
    obj = [v[key]["obj"] for v in views]
    img = [v[key]["img"] for v in views]
    crit = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 300, 1e-10)
    rms, K, D, rv, tv = cv2.calibrateCamera(obj, img, (W, H), K0.copy(), None,
                                            flags=flags | cv2.CALIB_USE_INTRINSIC_GUESS, criteria=crit)
    return float(rms), K, D.ravel()


def homography_outliers(views, key, max_px=12.0):
    """Scarta viste con corner mal identificati: residuo omografico (piano->immagine, ammette la distorsione) alto."""
    keep = []
    for v in views:
        d = v[key]
        H_, _ = cv2.findHomography(d["obj"][:, :2], d["img"], cv2.RANSAC, 6.0)
        if H_ is None:
            continue
        p = cv2.perspectiveTransform(d["obj"][:, :2].reshape(-1, 1, 2).astype(np.float64), H_).reshape(-1, 2)
        e = np.linalg.norm(p - d["img"], axis=1)
        if np.percentile(e, 80) < max_px / 4 and e.max() < 60:
            keep.append(v)
    return keep


def clean_views(views):
    """Vista tenuta solo se passa il controllo omografico in ENTRAMBE le camere dove presenti."""
    badL = {id(v) for v in views if v["L"] is not None and v not in homography_outliers([v], "L")}
    badR = {id(v) for v in views if v["R"] is not None and v not in homography_outliers([v], "R")}
    out = []
    for v in views:
        w = dict(v)
        if id(v) in badL:
            w["L"] = None
        if id(v) in badR:
            w["R"] = None
        out.append(w)
    return out


def board_calibrate(views, profile, board_name, sq_declared=None, seed=0, holdout_frac=0.25, check_coverage=True):
    """Pipeline con tabellone. views = lista di dict(frame, L, R). Ritorna (Calib candidato | None, report)."""
    rep = dict(verdetto="VERDE", verdetto_interno="VERDE", motivi=[], gate=GATE_BOARD)
    # verdetto_interno = i controlli sui dati del tabellone; verdetto = interno + bordo verificabile (vedi rim_coverage)
    red = lambda m: (rep["motivi"].append(m), rep.__setitem__("verdetto", "ROSSO"), rep.__setitem__("verdetto_interno", "ROSSO"))
    rng = np.random.default_rng(seed)
    n_before = sum((v["L"] is not None) + (v["R"] is not None) for v in views)
    views = clean_views(views)
    rep["viste_scartate_omografia"] = n_before - sum((v["L"] is not None) + (v["R"] is not None) for v in views)
    both = [v for v in views if v["L"] is not None and v["R"] is not None]
    rep["viste_totali"], rep["viste_stereo"] = len(views), len(both)
    if len(both) < 14:
        red(f"poche viste stereo ({len(both)} < 14)")
        return None, rep
    idx = rng.permutation(len(both))
    nh = max(4, int(len(both) * holdout_frac))
    hold = [both[i] for i in idx[:nh]]
    train = [both[i] for i in idx[nh:]]
    # copertura sulle 9 zone, entrambe le camere, sul TRAIN
    cov = {}
    for key in ("L", "R"):
        c, nv = zone_stats(train, key)
        cov[key] = dict(corners=c.tolist(), views=nv.tolist())
        bad = [ccd.ZNAME[i] for i in range(9) if c[i] < GATE_BOARD["min_corners_zone"] or nv[i] < GATE_BOARD["min_views_zone"]]
        if bad:
            red(f"copertura insufficiente cam {key}: zone {bad}")
            rep.setdefault("zone_deboli", []).extend([(ccd.ZNAME.index(b), 1 if key == "L" else 2) for b in bad])
    rep["copertura_train"] = cov
    if rep["verdetto"] == "ROSSO" and check_coverage:
        return None, rep
    K0 = _k0(profile)
    best = {}
    table = {}
    for key in ("L", "R"):
        res = {}
        for name, fl in MODEL_FLAGS.items():
            try:
                rms, K, D = _mono(train, key, fl, K0)
                hr, _ = ccd.holdout_reproj(hold, key, K, D)
            except cv2.error:
                continue
            if not radial_monotone(K, D):
                table.setdefault(key + "_scartati", []).append(name)     # non monotono fino al bordo: non eleggibile
                continue
            ra, re_, ne = holdout_edge_rms(hold, key, K, D)
            score = hr["rms"] if SELECT_MODE == "all" else float(np.sqrt((ra ** 2 + EDGE_W * re_ ** 2) / (1 + EDGE_W)))
            res[name] = dict(rms_fit=rms, rms_holdout=hr["rms"], rms_bordo=re_, n_bordo=ne, score=score, K=K, D=D)
        table[key] = {n: dict(rms_fit=r["rms_fit"], rms_holdout=r["rms_holdout"], rms_bordo=r["rms_bordo"], score=r["score"]) for n, r in res.items()}
        if not res:
            red(f"nessun modello di lente eleggibile per la cam {key}")
            return None, rep
        order = list(MODEL_FLAGS)
        if DISAGREE_PX is not None and res:
            ref = next(n for n in order if n in res)
            for n_, r_ in res.items():
                r_["disaccordo_px"] = 0.0 if n_ == ref else model_disagreement_px(res[ref]["K"], res[ref]["D"], r_["K"], r_["D"])
            table.setdefault(key + "_disaccordo_px", {n_: round(r_["disaccordo_px"], 2) for n_, r_ in res.items()})
            res = {n_: r_ for n_, r_ in res.items() if r_["disaccordo_px"] <= DISAGREE_PX}
        # sceglie sul HOLD-OUT; a parita' (entro 3%) il piu' semplice
        bestn = min(res, key=lambda n: res[n]["score"])
        # il piu' semplice entro +0.03 px (o 5%) dal migliore: sotto il rumore del detector la complessita' extra e' overfit
        tol = max(TOL_ABS, TOL_REL * res[bestn]["score"])
        for n in order:
            if n in res and res[n]["score"] <= res[bestn]["score"] + tol:
                bestn = n
                break
        best[key] = (bestn, res[bestn])
    rep["modelli_mono"] = table
    rep["modello_scelto"] = {k: best[k][0] for k in best}
    K1, D1, K2, D2 = best["L"][1]["K"], best["L"][1]["D"], best["R"][1]["K"], best["R"][1]["D"]
    # stereoCalibrate usa il modello di distorsione indicato dai FLAG, non dalla lunghezza del vettore:
    # se una delle due e' razionale, entrambe vanno portate a 8 coefficienti col flag RATIONAL.
    stereo_flags = cv2.CALIB_FIX_INTRINSIC
    if len(D1) >= 8 or len(D2) >= 8:
        D1, D2 = [np.pad(d[:8], (0, max(0, 8 - len(d)))) for d in (D1, D2)]
        stereo_flags |= cv2.CALIB_RATIONAL_MODEL
    for key in ("L", "R"):
        h = best[key][1]["rms_holdout"]
        rep[f"mono_holdout_rms_{key}"] = h
        if not h < GATE_BOARD["mono_rms_px"]:
            red(f"RMS mono hold-out {key} = {h:.2f} px >= {GATE_BOARD['mono_rms_px']}")
    # stereo: intrinseci fissi, T dal tabellone. Guess robusto = mediana delle pose relative per vista
    # (le viste quasi frontali hanno l'ambiguita' di posa del PnP planare: la mediana le ignora), poi si
    # scartano le viste con errore stereo anomalo e si rifitta.
    def _stereo(vs):
        obj, iL, iR = [], [], []
        for v in vs:
            c = ccd.common_pts(v)
            if c is not None:
                obj.append(c[0]); iL.append(c[1]); iR.append(c[2])
        Rs, Ts = [], []
        keep = [k for k in range(len(obj)) if len(obj[k]) >= 10]       # viste con almeno 10 corner comuni
        obj, iL, iR = [obj[k] for k in keep], [iL[k] for k in keep], [iR[k] for k in keep]
        for o, a, b in zip(obj, iL, iR):
            ok1, r1, t1 = cv2.solvePnP(o, a, K1, D1, flags=cv2.SOLVEPNP_IPPE)
            ok2, r2, t2 = cv2.solvePnP(o, b, K2, D2, flags=cv2.SOLVEPNP_IPPE)
            if ok1 and ok2:
                Ra, Rb = cv2.Rodrigues(r1)[0], cv2.Rodrigues(r2)[0]
                Ri = Rb @ Ra.T
                Rs.append(cv2.Rodrigues(Ri)[0].ravel())
                Ts.append((t2 - Ri @ t1).ravel())
        if len(Rs) < 4:
            return None, vs, obj
        R0 = cv2.Rodrigues(np.median(Rs, 0).reshape(3, 1))[0]
        T0 = np.median(Ts, 0).reshape(3, 1)
        crit = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 300, 1e-10)
        out = None
        for guess in (True, False):     # se con la stima iniziale non converge, riprova senza
            fl = stereo_flags | (cv2.CALIB_USE_EXTRINSIC_GUESS if guess else 0)
            o = cv2.stereoCalibrateExtended(obj, iL, iR, K1.copy(), D1.copy(), K2.copy(), D2.copy(), (W, H),
                                            R0 if guess else None, T0 if guess else None, flags=fl, criteria=crit)
            rep.setdefault("stereo_tentativi", []).append(dict(guess=guess, rms=float(o[0]), n_viste=len(obj)))
            if np.isfinite(o[0]) and o[0] < 5.0:
                out = o
                break
        return out, vs, obj
    out, vs_used, objs = _stereo(train)
    if out is None:
        red("stereo: la calibrazione non converge (viste insufficienti o inconsistenti)")
        return None, rep
    (rms_fit, _, _, _, _, R, T, _, _, _, _, pve) = out
    pve = np.asarray(pve).reshape(len(objs), 2)
    ev = np.sqrt((pve ** 2).mean(1))
    keepv = [v for v, e in zip([v for v in train if ccd.common_pts(v) is not None], ev) if e < max(1.0, 3 * np.median(ev))]
    rep["viste_stereo_scartate"] = len(objs) - len(keepv)
    if len(keepv) < len(objs) and len(keepv) >= 8:
        out2, _, _ = _stereo(keepv)
        if out2 is not None:
            (rms_fit, _, _, _, _, R, T, _, _, _, _, pve) = out2
    T = T.reshape(3, 1)
    sp = ccd.stereo_pose_rms(hold, K1, D1, K2, D2, R, T)
    rep["stereo_rms_fit"] = float(rms_fit)
    # raffinamento CONGIUNTO (intrinseci liberi, stesso modello): i corner comuni vincolano focale e centro delle due
    # camere fra loro (un errore di focale L/R relativo da' un errore di disparita' che cresce con x: +a sinistra,
    # - a destra). Si adotta solo se migliora l'RMS stereo sulle viste TENUTE FUORI e resta monotono.
    try:
        obj, iL, iR = [], [], []
        for v in train:
            c = ccd.common_pts(v)
            if c is not None and len(c[0]) >= 10:
                obj.append(c[0]); iL.append(c[1]); iR.append(c[2])
        mflag = MODEL_FLAGS[best["L"][0]] | (MODEL_FLAGS[best["R"][0]] & cv2.CALIB_RATIONAL_MODEL)
        o = cv2.stereoCalibrateExtended(obj, iL, iR, K1.copy(), D1.copy(), K2.copy(), D2.copy(), (W, H), R.copy(), T.copy(),
                                        flags=mflag | cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_USE_EXTRINSIC_GUESS,
                                        criteria=(cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 200, 1e-9))
        K1j, D1j, K2j, D2j, Rj, Tj = o[1], o[2].ravel(), o[3], o[4].ravel(), o[5], o[6].reshape(3, 1)
        spj = ccd.stereo_pose_rms(hold, K1j, D1j, K2j, D2j, Rj, Tj)
        rep["stereo_holdout_congiunto"] = spj
        if (spj["rms"] is not None and sp["rms"] is not None and spj["rms"] < 0.9 * sp["rms"]
                and radial_monotone(K1j, D1j) and radial_monotone(K2j, D2j) and abs(np.linalg.norm(Tj) / np.linalg.norm(T) - 1) < 0.05):
            K1, D1, K2, D2, R, T, sp = K1j, D1j, K2j, D2j, Rj, Tj, spj
            rep["raffinamento_congiunto"] = "adottato"
        else:
            rep["raffinamento_congiunto"] = "scartato (non migliora sulle viste tenute fuori o non monotono)"
    except cv2.error as e:
        rep["raffinamento_congiunto"] = f"errore {e}"
    rep["stereo_holdout"] = sp
    # dy rettificato PER ZONA sulle viste tenute fuori (lo stesso numero del giudice, ma misurato sui corner veri):
    # una calib con RMS buono puo' avere dy alto nelle zone di bordo dove i corner di fit sono pochi.
    R1_, R2_, P1_, P2_, _, _, _ = cv2.stereoRectify(K1, D1, K2, D2, (W, H), R, T, flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    dyz = [[] for _ in range(9)]
    for v in hold:
        c = ccd.common_pts(v)
        if c is None:
            continue
        ra, rb = ccd.rect_points(K1, D1, R1_, P1_, c[1]), ccd.rect_points(K2, D2, R2_, P2_, c[2])
        for z, d in zip(ccd.zone_of(c[1]), np.abs(ra[:, 1] - rb[:, 1])):
            dyz[z].append(float(d))
    rep["dy_holdout_zona_p95"] = [None if len(x) < GATE_BOARD["min_holdout_zone"] else float(np.percentile(x, 95)) for x in dyz]
    rep["dy_holdout_zona_n"] = [len(x) for x in dyz]
    rep["zone_deboli"] = []
    for z in range(9):
        p = rep["dy_holdout_zona_p95"][z]
        if p is None:
            red(f"zona {ccd.ZNAME[z]}: meno di {GATE_BOARD['min_holdout_zone']} corner di VERIFICA (non verificabile)")
            rep["zone_deboli"] += [(z, 1), (z, 2)]
        elif p > GATE_BOARD["dy_holdout_p95_px"]:
            red(f"zona {ccd.ZNAME[z]}: dy p95 sulle viste tenute fuori = {p:.2f} px > {GATE_BOARD['dy_holdout_p95_px']}")
            rep["zone_deboli"] += [(z, 1), (z, 2)]
    if sp["rms"] is None or not sp["rms"] < GATE_BOARD["stereo_rms_px"]:
        red(f"RMS stereo hold-out = {sp['rms']} px >= {GATE_BOARD['stereo_rms_px']}")
    B = float(np.linalg.norm(T))
    rep["baseline_mm_tabellone"] = B * 1000
    ref = profile["baseline_mm"]
    rep["baseline_vs_200"] = B * 1000 / ref - 1
    if abs(B * 1000 / ref - 1) > GATE_BOARD["baseline_tol"]:
        red(f"baseline dal tabellone {B*1000:.1f} mm fuori {ref:.0f} +-{GATE_BOARD['baseline_tol']*100:.0f}% "
            f"(lato del tabellone misurato male? mai riscalata)")
    if T[0, 0] >= 0 or abs(T[0, 0]) < 0.8 * B:
        red(f"orientamento: T_x = {T[0,0]*1000:.1f} mm (atteso negativo ~ -{ref:.0f}): file L/R scambiati o camere invertite")
    cal = Calib(K1, D1, K2, D2, R, T, size=(W, H), baseline_mm=B * 1000)
    # BORDO: il tabellone non da' corner negli ultimi ~40 px (il detector vuole marker interi) e li' il modello di lente
    # semplice e' solo ESTRAPOLATO. Misurato sul gemello: il dy sui corner tenuti fuori, la copertura per cella, un
    # disaccordo fra famiglie di modelli, il dy su scene SIFT, il peso per area: NESSUNO separa le calibrazioni che poi
    # sbagliano al bordo da quelle buone (10 falsi VERDE su 103, vedi README). Quindi il bordo NON si certifica col tabellone.
    rim = rim_coverage(views)
    rep["bordo"] = rim
    if not rim["ok"]:
        rep["motivi"].append("bordo (ultimi %d px) NON verificabile col tabellone: %s -> la calibrazione e' un CANDIDATO, "
                             "il VERDE lo da' solo la verifica indipendente sul reale (banco fisso + dy in movimento)"
                             % (GATE_BOARD["rim_px"], rim["segmenti_scoperti"]))
        rep["verdetto"] = "ROSSO"
    return cal, rep


def rim_coverage(views, rim_px=None, min_corners=None):
    """Corner (train+hold, entrambe le camere) entro rim_px dal bordo, per segmento di lato (5 sui lati lunghi, 3 sui corti)."""
    rim_px = rim_px or GATE_BOARD["rim_px"]
    min_corners = min_corners or GATE_BOARD["rim_min"]
    scoperti = []
    for key in "LR":
        P = [v[key]["img"] for v in views if v[key] is not None]
        P = np.vstack(P) if P else np.zeros((0, 2))
        for side, name in enumerate(("alto", "basso", "sinistra", "destra")):
            if side < 2:
                m = (P[:, 1] < rim_px) if side == 0 else (P[:, 1] > H - rim_px)
                c, n, Ls = P[m, 0], 5, W
            else:
                m = (P[:, 0] < rim_px) if side == 2 else (P[:, 0] > W - rim_px)
                c, n, Ls = P[m, 1], 3, H
            h = np.histogram(c, bins=n, range=(0, Ls))[0]
            scoperti += [f"{key}-{name}#{i}" for i in range(n) if h[i] < min_corners]
    return dict(rim_px=rim_px, min_corners=min_corners, segmenti_scoperti=scoperti, ok=not scoperti)




def save_candidate(cal, rep, path, unit="asmile-001", note=""):
    """File CANDIDATO (mai sovrascrive la calib di fabbrica): calib_<unita>.CANDIDATO_<tag>.json."""
    cal.save(path)
    d = json.load(open(path))
    d.update(order="RL", flip180=False, d0_px=0.0, stato="CANDIDATO", valid_for=f"SOLO {unit}", note=note,
             verdetto=rep.get("verdetto"), verdetto_interno=rep.get("verdetto_interno"), motivi=rep.get("motivi"))
    json.dump(d, open(path, "w"), indent=1)
    return path
