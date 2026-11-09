#!/usr/bin/env python3
"""
calib_charuco_dual.py — calibrazione stereo ChArUco PER UNITÀ, con copertura 3x3, viste tenute fuori
e scarto verticale (dy) misurato zona per zona. (2026-11-09, HANDOFF_calib_camere_20261109 punto 1)

Perché esiste (lezioni asmile-calib 2026-11-09):
  - la calib di #001 è ottima al centro ma ai bordi sbaglia (bordo sx +4..+17% depth, dy -4 px a x<430):
    il fit aveva quasi solo punti centrali e un modello solo radiale;
  - quindi: viste in TUTTE le 9 zone, modello rational (+ thin-prism se le viste tenute fuori lo vogliono),
    verifica SOLO su viste mai usate nel fit, dy su tutta l'immagine (9 zone), non sul solo mediano.

Unità (MAI confonderle, profili fissi qui sotto):
  asmile-001        2 OV9281 Inno-Maker SEPARATE, 2 file h264 (rpicam --sync). Ordine RL:
                    file video_left (cam0) = camera fisicamente DESTRA, video_right (cam1) = fisicamente SINISTRA.
  asmile-logger001  Arducam Camarray, 1 file SBS 2560x800 (order/flip da confermare sul primo video).

Uso:
  # tabellone (stampa rigida A2 consigliata; misura col metro il lato di un quadretto e passalo a --square-len)
  python3 calib_charuco_dual.py --make-board board_A2.png
  # #001: cartella sessione con video_left.h264 / video_right.h264 (+ frames_*.csv per l'accoppiamento)
  python3 calib_charuco_dual.py --unit asmile-001 --session asmile-loggers/asmile-001/session_YYYYMMDD_HHMMSS \
      --square-len 0.0500 --out calib_asmile-001.CANDIDATO.json
  # logger001 (dopo, stesso metodo):
  python3 calib_charuco_dual.py --unit asmile-logger001 --sbs clip.h264 --square-len 0.0500 \
      --out calib_asmile-logger001.CANDIDATO.json

Uscita: <out> (formato Calib di stereo_common, T in METRI come calib_asmile-001.json) + <out>.report.json
        + <out senza .json>.yaml (OpenCV FileStorage) + <out senza .json>.maps.npz (mappe di rettifica).
        Il JSON resta la fonte; YAML e mappe sono esportazioni per strumenti esterni (solo con CANDIDATO nel nome).

D012 firmato 2026-11-09 (punto A): |T| NON viene mai riscalato (e' un CONTROLLO: 200 mm +-3%, fra +-1% e +-3%
ARANCIO "calibro + annotazione"); RMS mono<0.5 e stereo<1 px e dy (p50<0.5, p95<1) SOLO su viste tenute fuori
(blocchi di tempo contigui); dy p95<1 px in tutte le 9 zone e' PRIORITARIO; sync p95 <1 ms con scarto automatico
delle coppie oltre soglia; 3 modelli (rational, +prism, +prism+tilted) scelti sull'hold-out.
Non sovrascrive MAI una calib_<unità>.json: il nome deve contenere "CANDIDATO". La sostituzione la decide
asmile-calib-critico (PASSA) — non questo script.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stereo_common import Calib  # noqa: E402

CAM_W, CAM_H = 1280, 800
BASELINE_M = 0.200

UNITS = {
    "asmile-001": dict(mode="dual", phys_left_file="video_right.h264", phys_right_file="video_left.h264",
                       phys_left_csv="frames_right.csv", phys_right_csv="frames_left.csv",
                       order="RL", flip180=False,
                       hw="Inno-Maker CAM-MIPIOV9281V2, 2 moduli separati, rpicam --sync"),
    "asmile-logger001": dict(mode="sbs", order="LR", flip180=False,
                             hw="Arducam Camarray OV9281 SBS 2560x800, 1 CSI"),
}

# tabellone di default: A2 (594x420 mm) -> 11x8 quadretti da 50 mm. Se stampi diverso, passa i parametri.
DEF_DICT = "DICT_5X5_1000"
DEF_SX, DEF_SY = 11, 8
DEF_SQ, DEF_MK = 0.050, 0.037

MODELS = {
    "rational": cv2.CALIB_RATIONAL_MODEL,
    "rational+prism": cv2.CALIB_RATIONAL_MODEL | cv2.CALIB_THIN_PRISM_MODEL,
    "rational+prism+tilted": cv2.CALIB_RATIONAL_MODEL | cv2.CALIB_THIN_PRISM_MODEL | cv2.CALIB_TILTED_MODEL,
}
# fisheye (cv2.fisheye) solo con FOV MISURATO > 100 deg: #001 e' ~58 deg -> NON usato (D012/consigli di Daniele).


# ---------------------------------------------------------------------------- board
def make_board(dict_name, sx, sy, sq, mk):
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    b = cv2.aruco.CharucoBoard((sx, sy), sq, mk, d)
    b.setLegacyPattern(False)
    return b


def detect(det, board, gray):
    cc, ci, _, _ = det.detectBoard(gray)
    if cc is None or len(cc) < 6:
        return None
    obj, img = board.matchImagePoints(cc, ci)
    return dict(ids=ci.ravel().astype(int), obj=obj.reshape(-1, 3).astype(np.float32),
                img=img.reshape(-1, 2).astype(np.float32))


# ---------------------------------------------------------------------------- video
def gray_frames(path, w, h):
    p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-i", path, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w)
    p.wait()


def read_sensor_ts(path):
    if not path or not os.path.exists(path):
        return None
    with open(path) as f:
        return [int(r["sensor_ts_ns"]) for r in csv.DictReader(f)]


def sync_stats(tl, tr, max_ms):
    """Delta t per coppia (riga i del csv sinistro vs riga i del destro), in ms."""
    n = min(len(tl), len(tr))
    dt = np.abs(np.array(tl[:n], float) - np.array(tr[:n], float)) / 1e6
    return dt, dict(n_pairs=int(n), dt_ms_p50=float(np.percentile(dt, 50)), dt_ms_p95=float(np.percentile(dt, 95)),
                    dt_ms_max=float(dt.max()), max_ms=max_ms, pairs_over=int((dt > max_ms).sum()),
                    rows_left=len(tl), rows_right=len(tr))


def paired_frames(args, prof):
    """Genera (idx, phys_left, phys_right, info). Per #001 calcola il delta t per coppia dai sensor_ts dei
    frames_*.csv e segna le coppie oltre soglia (info['bad_idx']): vengono SCARTATE da collect()."""
    info = {}
    if prof["mode"] == "dual":
        fl = args.left_file or os.path.join(args.session, prof["phys_left_file"])
        fr = args.right_file or os.path.join(args.session, prof["phys_right_file"])
        tl = read_sensor_ts(os.path.join(args.session, prof["phys_left_csv"])) if args.session else None
        tr = read_sensor_ts(os.path.join(args.session, prof["phys_right_csv"])) if args.session else None
        info.update(phys_left_file=fl, phys_right_file=fr, bad_idx=set(), sync=None)
        if tl and tr:
            dt, st = sync_stats(tl, tr, args.max_sync_ms)
            info["sync"] = st
            info["bad_idx"] = set(int(i) for i in np.where(dt > args.max_sync_ms)[0])
        gL, gR = gray_frames(fl, CAM_W, CAM_H), gray_frames(fr, CAM_W, CAM_H)
        for i, (a, b) in enumerate(zip(gL, gR)):
            yield i, a, b, info
    else:
        from stereo_common import split_sbs
        # SBS: un solo sensore, un solo frame per coppia -> Delta t L/R non esiste (n/d), non e' un controllo saltato
        info.update(sbs_file=args.sbs, bad_idx=set(), sync=None)
        for i, f in enumerate(gray_frames(args.sbs, 2 * CAM_W, CAM_H)):
            a, b = split_sbs(f, order=prof["order"], flip180=prof["flip180"])
            yield i, a, b, info


# ---------------------------------------------------------------------------- zone 3x3
def zone_of(xy, w=CAM_W, h=CAM_H):
    zx = np.clip((xy[:, 0] * 3 // w).astype(int), 0, 2)
    zy = np.clip((xy[:, 1] * 3 // h).astype(int), 0, 2)
    return zy * 3 + zx


ZNAME = ["alto-sx", "alto-centro", "alto-dx", "mezzo-sx", "centro", "mezzo-dx", "basso-sx", "basso-centro", "basso-dx"]


def coverage(views, key):
    c = np.zeros(9, int)
    v = np.zeros(9, int)
    for vw in views:
        d = vw[key]
        if d is None:
            continue
        z = zone_of(d["img"])
        c += np.bincount(z, minlength=9)
        v += (np.bincount(z, minlength=9) >= 4).astype(int)
    return c, v


# ---------------------------------------------------------------------------- selezione viste
def collect(args, prof, board):
    det = cv2.aruco.CharucoDetector(board)
    views, info, n, skipped = [], {}, 0, 0
    last_sig = None
    for i, L, R, info in paired_frames(args, prof):
        n += 1
        if i in info["bad_idx"]:      # coppia con delta t oltre soglia: scartata automaticamente
            skipped += 1
            continue
        if i % args.step:
            continue
        dL, dR = detect(det, board, L), detect(det, board, R)
        if dL is None and dR is None:
            continue
        # scarta viste quasi identiche alla precedente tenuta (tabellone fermo): firma = centroidi + n corner
        sig = np.array([*(dL["img"].mean(0) if dL else (-1, -1)), *(dR["img"].mean(0) if dR else (-1, -1)),
                        len(dL["ids"]) if dL else 0, len(dR["ids"]) if dR else 0], float)
        if last_sig is not None and np.abs(sig - last_sig).max() < args.min_move_px:
            continue
        last_sig = sig
        views.append(dict(frame=i, L=dL, R=dR))
    info["frames_decoded"] = n
    info["pairs_discarded_sync"] = skipped
    info = {k: v for k, v in info.items() if k != "bad_idx"}
    return views, info


def split_holdout(views, n_blocks, guard):
    """Hold-out a BLOCCHI DI TEMPO CONTIGUI (D012/critico #6): le viste (ordinate per frame) sono divise in
    `n_blocks` blocchi; si tengono fuori il blocco n_blocks//2-1 e l'ultimo (~20%, lontani fra loro). Le `guard`
    viste adiacenti a un blocco tenuto fuori NON entrano nel fit (quasi-duplicati temporali)."""
    n = len(views)
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    hold_blocks = {n_blocks // 2 - 1, n_blocks - 1}
    hold_idx = set()
    for b in hold_blocks:
        hold_idx.update(range(edges[b], edges[b + 1]))
    near = set()
    for i in hold_idx:
        for g in range(1, guard + 1):
            near.update((i - g, i + g))
    fit = [v for k, v in enumerate(views) if k not in hold_idx and k not in near]
    hold = [v for k, v in enumerate(views) if k in hold_idx]
    return fit, hold, dict(n_blocks=n_blocks, hold_blocks=sorted(hold_blocks), guard=guard,
                           hold_view_ranges=[[int(edges[b]), int(edges[b + 1] - 1)] for b in sorted(hold_blocks)],
                           guard_excluded=len(near - hold_idx & set(range(n))))


def cap_views(views, key, max_views):
    """Se troppe viste, tiene quelle che bilanciano le zone (greedy sulla zona meno coperta)."""
    vv = [v for v in views if v[key] is not None]
    if len(vv) <= max_views:
        return vv
    cnt = np.zeros(9)
    chosen, rest = [], list(vv)
    while len(chosen) < max_views and rest:
        best, bs = None, -1
        for j, v in enumerate(rest):
            h = np.bincount(zone_of(v[key]["img"]), minlength=9)
            s = float(np.sum(h / (1.0 + cnt)))
            if s > bs:
                best, bs = j, s
        v = rest.pop(best)
        cnt += np.bincount(zone_of(v[key]["img"]), minlength=9)
        chosen.append(v)
    return sorted(chosen, key=lambda v: v["frame"])


# ---------------------------------------------------------------------------- fit mono + verifica hold-out
def calib_mono(views, key, flags):
    obj = [v[key]["obj"] for v in views]
    img = [v[key]["img"] for v in views]
    crit = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 200, 1e-9)
    rms, K, D, rv, tv = cv2.calibrateCamera(obj, img, (CAM_W, CAM_H), None, None, flags=flags, criteria=crit)
    return float(rms), K, D.ravel()


def holdout_reproj(views, key, K, D):
    """Per ogni vista tenuta fuori: solvePnP (6 dof) con gli intrinseci del fit -> residui per zona."""
    per_zone = [[] for _ in range(9)]
    tilts = []
    for v in views:
        d = v[key]
        if d is None or len(d["ids"]) < 8:
            continue
        ok, rv, tv = cv2.solvePnP(d["obj"], d["img"], K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue
        pr, _ = cv2.projectPoints(d["obj"], rv, tv, K, D)
        e = np.linalg.norm(pr.reshape(-1, 2) - d["img"], axis=1)
        for z, ee in zip(zone_of(d["img"]), e):
            per_zone[z].append(ee)
        n = cv2.Rodrigues(rv)[0][:, 2]
        tilts.append(float(np.degrees(np.arccos(abs(n[2])))))
    all_e = np.concatenate([np.array(p) for p in per_zone if p]) if any(per_zone) else np.array([np.nan])
    return dict(rms=float(np.sqrt(np.mean(all_e ** 2))),
                zone_rms=[float(np.sqrt(np.mean(np.square(p)))) if p else None for p in per_zone],
                zone_n=[len(p) for p in per_zone]), tilts


# ---------------------------------------------------------------------------- stereo
def common_pts(v):
    a, b = v["L"], v["R"]
    if a is None or b is None:
        return None
    com, ia, ib = np.intersect1d(a["ids"], b["ids"], return_indices=True)
    if len(com) < 6:
        return None
    return a["obj"][ia], a["img"][ia], b["img"][ib]


def stereo_fit(views, K1, D1, K2, D2, flags_model, joint):
    obj, iL, iR = [], [], []
    for v in views:
        c = common_pts(v)
        if c is not None:
            obj.append(c[0]); iL.append(c[1]); iR.append(c[2])
    if len(obj) < 6:
        raise SystemExit(f"Poche viste stereo con corner comuni ({len(obj)}): servono >= 6 (meglio 20+).")
    flags = flags_model | (cv2.CALIB_USE_INTRINSIC_GUESS if joint else cv2.CALIB_FIX_INTRINSIC)
    crit = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 300, 1e-10)
    rms, K1, D1, K2, D2, R, T, _, _ = cv2.stereoCalibrate(obj, iL, iR, K1.copy(), D1.copy(), K2.copy(), D2.copy(),
                                                         (CAM_W, CAM_H), flags=flags, criteria=crit)
    return float(rms), K1, D1.ravel(), K2, D2.ravel(), R, T.reshape(3, 1), len(obj)


def rect_points(K, D, R, P, pts):
    return cv2.undistortPoints(pts.reshape(-1, 1, 2).astype(np.float64), K, D, R=R, P=P).reshape(-1, 2)


def stereo_pose_rms(views, K1, D1, K2, D2, R, T):
    """RMS stereo sulle viste TENUTE FUORI: per ogni vista la posa del tabellone e' stimata con i due sensori
    insieme (LM sui residui L+R, intrinseci/estrinseci del fit fissi); residuo = distanza 2D per corner."""
    T = np.asarray(T, float).ravel()
    eL, eR = [], []
    for v in views:
        c = common_pts(v)
        if c is None or len(c[0]) < 8:
            continue
        obj, a, b = c
        obj = obj.astype(np.float64)
        ok, rv, tv = cv2.solvePnP(obj, a.astype(np.float64), K1, D1, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue

        def res(x):
            pL = cv2.projectPoints(obj, x[:3], x[3:], K1, D1)[0].reshape(-1, 2)
            Rb = cv2.Rodrigues(x[:3])[0]
            pR = cv2.projectPoints(obj, cv2.Rodrigues(R @ Rb)[0], R @ x[3:] + T, K2, D2)[0].reshape(-1, 2)
            return np.r_[(pL - a).ravel(), (pR - b).ravel()]
        sol = least_squares(res, np.r_[rv.ravel(), tv.ravel()], method="lm")
        r = sol.fun.reshape(2, -1, 2)
        eL += list(np.linalg.norm(r[0], axis=1))
        eR += list(np.linalg.norm(r[1], axis=1))
    allr = np.array(eL + eR)
    if not len(allr):
        return dict(rms=None, rms_L=None, rms_R=None, n_points=0)
    return dict(rms=float(np.sqrt(np.mean(allr ** 2))), rms_L=float(np.sqrt(np.mean(np.square(eL)))),
                rms_R=float(np.sqrt(np.mean(np.square(eR)))), n_points=int(len(eL)))


def holdout_stereo(views, K1, D1, K2, D2, R, T, sq_m):
    """dy rettificato per zona (zona = posizione nel frame GREZZO sinistro, p50 e p95 di |dy|) + proxy di scala
    (distanza 3D fra corner vicini triangolati vs lato MISURATO) + bias di disparita' per zona rispetto alla
    posa del tabellone da PnP sul solo sinistro, estrapolato a 1 m e 10 m (A8: INFORMATIVO, non nel gate)."""
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, D1, K2, D2, (CAM_W, CAM_H), R, T,
                                                flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    fB = float(P1[0, 0]) * float(np.linalg.norm(T))
    dy_z = [[] for _ in range(9)]
    sc_z = [[] for _ in range(9)]
    dd_z = [[] for _ in range(9)]
    zdist = []
    for v in views:
        c = common_pts(v)
        if c is None:
            continue
        obj, a, b = c
        ra, rb = rect_points(K1, D1, R1, P1, a), rect_points(K2, D2, R2, P2, b)
        zs = zone_of(a)
        for z, dy in zip(zs, ra[:, 1] - rb[:, 1]):
            dy_z[z].append(float(dy))
        disp = ra[:, 0] - rb[:, 0]
        ok = disp > 0.5
        X = cv2.perspectiveTransform(np.c_[ra, disp].reshape(-1, 1, 3), Q).reshape(-1, 3)
        zdist += list(X[ok, 2])
        okp, rv, tv = cv2.solvePnP(obj.astype(np.float64), a.astype(np.float64), K1, D1, flags=cv2.SOLVEPNP_ITERATIVE)
        if okp:
            Xl = (cv2.Rodrigues(rv)[0] @ obj.astype(np.float64).T).T + tv.ravel()
            Zexp = (R1 @ Xl.T)[2]
            for z, dd in zip(zs, disp - fB / Zexp):
                dd_z[z].append(float(dd))
        # coppie di corner adiacenti (distanza vera = 1 lato)
        for j in range(len(obj)):
            dd = np.linalg.norm(obj - obj[j], axis=1)
            for k in np.where(np.abs(dd - sq_m) < 1e-6)[0]:
                if k <= j or not (ok[j] and ok[k]):
                    continue
                s = np.linalg.norm(X[j] - X[k]) / sq_m - 1.0
                sc_z[zs[j]].append(float(s))
    f = lambda arr, fn: (float(fn(np.array(arr))) if arr else None)
    bias = [f(a, np.median) for a in dd_z]
    edge = lambda Z: [None if b is None else float(100 * (1 / (1 + Z * b / fB) - 1)) for b in bias]
    return dict(
        dy_median=[f(a, np.median) for a in dy_z],
        dy_abs_p50=[f(np.abs(a).tolist(), np.median) for a in dy_z],
        dy_abs_p95=[f(np.abs(a).tolist(), lambda x: np.percentile(x, 95)) for a in dy_z],
        dy_n=[len(a) for a in dy_z],
        scale_err_pct_median=[f(a, lambda x: 100 * np.median(x)) for a in sc_z],
        scale_n=[len(a) for a in sc_z],
        disp_bias_px_median=bias,
        depth_edge_informativo=dict(
            nota=("INFORMATIVO, non nel gate: bias di disparita' per zona vs posa PnP del tabellone (viste a ~0.65-1.6 m), "
                  "estrapolato a Z fissa come bias costante in disparita'. NON e' una misura col metro."),
            err_pct_1m=edge(1.0), err_pct_10m=edge(10.0)),
        z_range_m=[float(np.min(zdist)), float(np.max(zdist))] if zdist else None,
        focal_rect_px=float(P1[0, 0]),
    )


# ---------------------------------------------------------------------------- gate
def gate(rep, a):
    """Ritorna (rossi, arancio). ROSSO = non usare. ARANCIO = usabile solo con 'calibro + annotazione'."""
    red, orange = [], []
    covL, covR = rep["coverage_fit"]["L_corners"], rep["coverage_fit"]["R_corners"]
    for name, cov in (("L", covL), ("R", covR)):
        bad = [ZNAME[z] for z in range(9) if cov[z] < a.min_zone_corners]
        if bad:
            red.append(f"copertura {name} insufficiente (<{a.min_zone_corners} corner) in: {', '.join(bad)}")
    st = rep["stereo_holdout"]
    for z in range(9):
        n, ns = st["dy_n"][z], st["scale_n"][z]
        if n == 0 or st["dy_abs_p95"][z] is None:
            red.append(f"hold-out stereo: zona {ZNAME[z]} VUOTA (dy non misurabile) -> non verificata")
        elif n < a.min_zone_holdout:
            red.append(f"hold-out stereo: zona {ZNAME[z]} con {n} punti (<{a.min_zone_holdout}) -> non verificata")
        else:
            if st["dy_abs_p50"][z] >= a.max_dy_p50_px:
                red.append(f"dy zona {ZNAME[z]}: p50 |dy| {st['dy_abs_p50'][z]:.2f} px (>= {a.max_dy_p50_px})")
            if st["dy_abs_p95"][z] >= a.max_dy_p95_px:
                red.append(f"dy zona {ZNAME[z]}: p95 |dy| {st['dy_abs_p95'][z]:.2f} px (>= {a.max_dy_p95_px}) [PRIORITARIO]")
        se = st["scale_err_pct_median"][z]
        if ns == 0 or se is None:
            red.append(f"scala zona {ZNAME[z]} VUOTA (nessuna coppia di corner triangolabile) -> non verificata")
        elif ns < a.min_zone_holdout // 2:
            red.append(f"scala zona {ZNAME[z]} con {ns} coppie (<{a.min_zone_holdout // 2}) -> non verificata")
        elif abs(se) > a.max_scale_pct:
            red.append(f"scala/depth zona {ZNAME[z]} {se:+.2f}% (> {a.max_scale_pct}%)")
    if rep["n_holdout_stereo"] < 4:
        red.append(f"solo {rep['n_holdout_stereo']} viste stereo in hold-out (servono >= 4)")
    # RMS SOLO sulle viste tenute fuori
    rm = rep["rms_mono_holdout"]
    for nm, val in zip(("L", "R"), rm):
        if val is None or not np.isfinite(val):
            red.append(f"RMS mono {nm} su viste tenute fuori non misurabile")
        elif val >= a.max_rms_mono:
            red.append(f"RMS mono {nm} (tenute fuori) {val:.3f} px (>= {a.max_rms_mono})")
    rs = rep["rms_stereo_holdout"]["rms"]
    if rs is None:
        red.append("RMS stereo su viste tenute fuori non misurabile")
    elif rs >= a.max_rms_stereo:
        red.append(f"RMS stereo (tenute fuori) {rs:.3f} px (>= {a.max_rms_stereo})")
    # geometria: segno della baseline (cam1 = sinistra: T[0] deve essere < 0) e |T| CONTROLLO, mai forzato
    T = rep["T_m"]
    if T[0] >= 0:
        red.append(f"T[0] = {T[0]*1000:+.1f} mm >= 0: camere scambiate (file L/R invertiti?) o ordine sbagliato")
    dev = 100 * (rep["T_from_board_mm"] / (BASELINE_M * 1000) - 1)
    rep["baseline_dev_pct"] = dev
    if abs(dev) > a.baseline_tol_red:
        red.append(f"|T| dal tabellone {rep['T_from_board_mm']:.1f} mm = {dev:+.2f}% da 200 mm (> +-{a.baseline_tol_red}%): "
                   "misura col calibro la baseline e controlla --square-len (T NON viene riscalata)")
    elif abs(dev) > a.baseline_tol_orange:
        orange.append(f"|T| dal tabellone {rep['T_from_board_mm']:.1f} mm = {dev:+.2f}% da 200 mm (fra +-{a.baseline_tol_orange}% "
                      f"e +-{a.baseline_tol_red}%): calibro + annotazione")
    # sync (solo #001: due sensori)
    sy = rep["input"].get("sync")
    if rep["input"].get("sbs_file"):
        pass  # SBS: un solo sensore, delta t n/d
    elif sy is None:
        red.append("sync L/R non verificabile (mancano i frames_*.csv con sensor_ts_ns)")
    else:
        if sy["dt_ms_p95"] >= a.max_sync_ms:
            red.append(f"sync: p95 delta t coppie {sy['dt_ms_p95']:.3f} ms (>= {a.max_sync_ms}); "
                       f"{sy['pairs_over']}/{sy['n_pairs']} coppie scartate")
        if sy["rows_left"] != sy["rows_right"]:
            red.append(f"csv L/R con righe diverse ({sy['rows_left']} vs {sy['rows_right']}): accoppiamento per indice inaffidabile")
    tilts = rep.get("tilt_deg_fit_L", [])
    if tilts and np.percentile(tilts, 75) < 15:
        red.append("tabellone quasi sempre frontale (tilt p75 < 15 deg): inclinalo 20-40 deg")
    return red, orange


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def export_yaml_maps(base, cal, rep, files):
    """A4: YAML OpenCV FileStorage + mappe di rettifica .npz. `base` contiene 'CANDIDATO' (controllato in main).
    T in METRI come il JSON (che resta la fonte)."""
    rc = cal.rectify()
    fs = cv2.FileStorage(base + ".yaml", cv2.FILE_STORAGE_WRITE)
    fs.write("unit", rep["unit"])
    fs.write("model", rep["model"])
    fs.write("date", datetime.datetime.now().isoformat(timespec="seconds"))
    fs.write("image_width", CAM_W); fs.write("image_height", CAM_H)
    for k, v in (("K1", cal.K1), ("D1", cal.d1.reshape(-1, 1)), ("K2", cal.K2), ("D2", cal.d2.reshape(-1, 1)),
                 ("R", cal.R), ("T", cal.T), ("R1", rc["R1"]), ("R2", rc["R2"]), ("P1", rc["P1"]), ("P2", rc["P2"]),
                 ("Q", rc["Q"])):
        fs.write(k, np.asarray(v, float))
    fs.write("T_units", "metres")
    fs.write("rms_mono_holdout_L", float(rep["rms_mono_holdout"][0])); fs.write("rms_mono_holdout_R", float(rep["rms_mono_holdout"][1]))
    fs.write("rms_stereo_holdout", float(rep["rms_stereo_holdout"]["rms"] or -1))
    fs.write("gate", rep["gate"])
    fs.startWriteStruct("video_sha256", cv2.FILE_NODE_MAP)
    for k, h in files.items():
        fs.write(k, h)
    fs.endWriteStruct()
    fs.release()
    np.savez_compressed(base + ".maps.npz", m1x=rc["m1x"], m1y=rc["m1y"], m2x=rc["m2x"], m2y=rc["m2y"],
                        P1=rc["P1"], P2=rc["P2"], Q=rc["Q"])
    return base + ".yaml", base + ".maps.npz"


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--make-board", metavar="PNG")
    ap.add_argument("--unit", choices=sorted(UNITS))
    ap.add_argument("--session", help="#001: cartella sessione (video_left/right.h264 + frames_*.csv)")
    ap.add_argument("--left-file", help="#001: file della camera FISICAMENTE sinistra (override)")
    ap.add_argument("--right-file", help="#001: file della camera FISICAMENTE destra (override)")
    ap.add_argument("--sbs", help="logger001: clip side-by-side 2560x800")
    ap.add_argument("--out")
    ap.add_argument("--dict", default=DEF_DICT)
    ap.add_argument("--squares", default=f"{DEF_SX}x{DEF_SY}")
    ap.add_argument("--square-len", type=float, default=DEF_SQ, help="lato quadretto MISURATO col metro, in m")
    ap.add_argument("--marker-len", type=float, default=None, help="default = 0.74 * square-len")
    ap.add_argument("--step", type=int, default=3, help="analizza 1 frame ogni N")
    ap.add_argument("--min-move-px", type=float, default=12.0)
    ap.add_argument("--holdout-blocks", type=int, default=10, help="blocchi di tempo contigui; ne tiene fuori 2 (~20%%)")
    ap.add_argument("--holdout-guard", type=int, default=1, help="viste adiacenti al blocco tenuto fuori escluse dal fit")
    ap.add_argument("--max-views", type=int, default=90)
    ap.add_argument("--min-zone-corners", type=int, default=150)
    ap.add_argument("--min-zone-holdout", type=int, default=20)
    ap.add_argument("--max-dy-p50-px", type=float, default=0.5)
    ap.add_argument("--max-dy-p95-px", type=float, default=1.0)
    ap.add_argument("--max-scale-pct", type=float, default=2.0)
    ap.add_argument("--max-rms-mono", type=float, default=0.5)
    ap.add_argument("--max-rms-stereo", type=float, default=1.0)
    ap.add_argument("--max-sync-ms", type=float, default=1.0)
    ap.add_argument("--baseline-tol-orange", type=float, default=1.0)
    ap.add_argument("--baseline-tol-red", type=float, default=3.0)
    ap.add_argument("--models", default="rational,rational+prism,rational+prism+tilted")
    a = ap.parse_args()

    sx, sy = map(int, a.squares.lower().split("x"))
    mk = a.marker_len or round(0.74 * a.square_len, 5)
    board = make_board(a.dict, sx, sy, a.square_len, mk)

    if a.make_board:
        ppsq = 400
        img = board.generateImage((sx * ppsq, sy * ppsq), marginSize=ppsq // 2, borderBits=1)
        cv2.imwrite(a.make_board, img)
        print(f"[board] {sx}x{sy} quadretti, {a.dict}, marker/quadretto 0.74 -> {a.make_board} {img.shape[1]}x{img.shape[0]} px")
        print(f"        stampa a scala reale: quadretto {a.square_len*1000:.0f} mm; poi MISURA col metro 10 quadretti e passa --square-len")
        return

    if not a.unit or not a.out:
        ap.error("servono --unit e --out")
    if "CANDIDATO" not in os.path.basename(a.out):
        ap.error("il file di uscita deve contenere 'CANDIDATO' (la calib vera la sostituisce solo il PASSA del critico)")
    prof = UNITS[a.unit]
    if prof["mode"] == "dual" and not (a.session or (a.left_file and a.right_file)):
        ap.error(f"{a.unit}: servono --session (o --left-file e --right-file)")
    if prof["mode"] == "sbs" and not a.sbs:
        ap.error(f"{a.unit}: serve --sbs")

    print(f"[1] unità {a.unit} ({prof['hw']}): detect ChArUco 1 frame ogni {a.step}...")
    views, info = collect(a, prof, board)
    fit, hold, hinfo = split_holdout(views, a.holdout_blocks, a.holdout_guard)
    fitL, fitR = cap_views(fit, "L", a.max_views), cap_views(fit, "R", a.max_views)
    sy = info.get("sync")
    print(f"    frame {info.get('frames_decoded')}, viste diverse {len(views)} -> fit L {len(fitL)} R {len(fitR)}, "
          f"hold-out {len(hold)} (blocchi {hinfo['hold_view_ranges']}, guard {hinfo['guard']})"
          + (f"\n    sync dt p50 {sy['dt_ms_p50']:.3f} p95 {sy['dt_ms_p95']:.3f} max {sy['dt_ms_max']:.3f} ms, "
             f"coppie scartate (>{a.max_sync_ms} ms): {sy['pairs_over']}/{sy['n_pairs']}" if sy else
             "\n    sync dt: n/d (SBS, un solo sensore)" if prof["mode"] == "sbs" else "\n    sync dt: NON verificabile (nessun csv)"))
    if len(fitL) < 10 or len(fitR) < 10:
        raise SystemExit("troppe poche viste per camera (servono >= 10, meglio 40-60)")

    print("[2] intrinseche per modello, scelta sulle viste TENUTE FUORI...")
    cand = {}
    for name in a.models.split(","):
        fl = MODELS[name]
        rL, KL, DL = calib_mono(fitL, "L", fl)
        rR, KR, DR = calib_mono(fitR, "R", fl)
        hL, tiltL = holdout_reproj(hold, "L", KL, DL)
        hR, _ = holdout_reproj(hold, "R", KR, DR)
        cand[name] = dict(flags=fl, KL=KL, DL=DL, KR=KR, DR=DR, rms_fit=(rL, rR), hold=(hL, hR), tiltL=tiltL)
        print(f"    {name:22s} fit rms L {rL:.3f} R {rR:.3f} | hold-out L {hL['rms']:.3f} R {hR['rms']:.3f} px  fx L {KL[0,0]:.1f} R {KR[0,0]:.1f}")
    names = list(cand)
    best = names[0]
    for nm in names[1:]:   # modello più ricco solo se migliora l'hold-out di almeno il 5%
        s_b = sum(h["rms"] for h in cand[best]["hold"])
        s_n = sum(h["rms"] for h in cand[nm]["hold"])
        if s_n < 0.95 * s_b:
            best = nm
    c = cand[best]
    print(f"    scelto: {best}")

    print("[3] stereo (prima intrinseci fissi, poi rifinitura congiunta) e verifica sulle viste tenute fuori...")
    stereo_views = [v for v in fit if common_pts(v) is not None]
    res = {}
    for joint in (False, True):
        r = stereo_fit(stereo_views, c["KL"], c["DL"], c["KR"], c["DR"], c["flags"], joint)
        rms, K1, D1, K2, D2, R, T, nv = r
        # T NON riscalata (D012): |T| dal tabellone e' un controllo contro 200 mm +-3%
        hs = holdout_stereo(hold, K1, D1, K2, D2, R, T, a.square_len)
        srms = stereo_pose_rms(hold, K1, D1, K2, D2, R, T)
        wp95 = max(d for d in hs["dy_abs_p95"] if d is not None) if any(d is not None for d in hs["dy_abs_p95"]) else 1e9
        res[joint] = dict(rms=rms, K1=K1, D1=D1, K2=K2, D2=D2, R=R, T=T, T_raw_m=float(np.linalg.norm(T)),
                          n=nv, hold=hs, worst_dy_p95=wp95, srms=srms)
        print(f"    {'congiunta' if joint else 'intr. fissi':11s} rms fit {rms:.3f} px, viste {nv}, |T| {np.linalg.norm(T)*1000:.1f} mm, "
              f"hold-out: dy p95 peggior zona {wp95:.2f} px, RMS stereo {srms['rms']}")
    s = res[True] if res[True]["worst_dy_p95"] <= res[False]["worst_dy_p95"] else res[False]

    covL, vL = coverage(fitL, "L")
    covR, vR = coverage(fitR, "R")
    rep = dict(
        unit=a.unit, model=best, stereo_mode="congiunta" if s is res[True] else "intrinseci fissi",
        input=info, n_views=len(views), n_fit=dict(L=len(fitL), R=len(fitR), stereo=s["n"]),
        n_holdout=len(hold), n_holdout_stereo=sum(common_pts(v) is not None for v in hold),
        holdout=hinfo, holdout_frames=[v["frame"] for v in hold],
        coverage_fit=dict(L_corners=covL.tolist(), R_corners=covR.tolist(), L_views=vL.tolist(), R_views=vR.tolist()),
        models={nm: dict(rms_fit=cand[nm]["rms_fit"], holdout_rms=(cand[nm]["hold"][0]["rms"], cand[nm]["hold"][1]["rms"]),
                         holdout_zone_rms_L=cand[nm]["hold"][0]["zone_rms"], holdout_zone_rms_R=cand[nm]["hold"][1]["zone_rms"])
                for nm in cand},
        rms_mono_holdout=[cand[best]["hold"][0]["rms"], cand[best]["hold"][1]["rms"]],
        rms_stereo_holdout=s["srms"],
        tilt_deg_fit_L=[round(t, 1) for t in c["tiltL"]],
        stereo_rms_fit=s["rms"], T_from_board_mm=s["T_raw_m"] * 1000, T_m=[float(x) for x in s["T"].ravel()],
        stereo_holdout=s["hold"], zone_names=ZNAME,
    )
    red, orange = gate(rep, a)
    rep["gate_problemi"] = red
    rep["gate_avvisi"] = orange
    rep["gate"] = "ROSSO" if red else ("ARANCIO" if orange else "VERDE")

    cal = Calib(s["K1"], s["D1"], s["K2"], s["D2"], s["R"], s["T"], size=(CAM_W, CAM_H), baseline_mm=s["T_raw_m"] * 1000)
    cal.save(a.out)
    blob = json.load(open(a.out))
    blob.update({
        "order": prof["order"], "flip180": prof["flip180"], "d0_px": 0.0,
        "focal_rect_px": s["hold"]["focal_rect_px"],
        "method": f"calib_charuco_dual.py: ChArUco {sx}x{sy} {a.dict} lato {a.square_len*1000:.1f} mm, modello {best}, "
                  f"stereo {rep['stereo_mode']}, T NON riscalata (|T| dal tabellone = {s['T_raw_m']*1000:.1f} mm, controllo 200+-3%); "
                  f"verifica su {len(hold)} viste tenute fuori (blocchi di tempo)",
        "valid_for": f"SOLO {a.unit} con QUESTO set di camere come montate al momento della sessione. Mai fallback su altre unità.",
        "camera_hw": prof["hw"],
        "stato": "CANDIDATO — non in uso finché asmile-calib-critico non dà PASSA",
        "gate_script": rep["gate"],
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    json.dump(blob, open(a.out, "w"), indent=2)
    if prof["mode"] == "dual":
        hashes = {"video_phys_left": sha256_file(info["phys_left_file"]), "video_phys_right": sha256_file(info["phys_right_file"])}
    else:
        hashes = {"video_sbs": sha256_file(info["sbs_file"])}
    base = a.out[:-5] if a.out.endswith(".json") else a.out
    ypath, mpath = export_yaml_maps(base, cal, rep, hashes)
    rep["export"] = dict(yaml=ypath, maps=mpath, video_sha256=hashes)
    json.dump(rep, open(a.out + ".report.json", "w"), indent=1, default=float)

    st = s["hold"]
    print("[4] dy hold-out per zona (p50|p95 di |dy|, px) / scala % / depth ai bordi (INFORMATIVO, 1 m | 10 m):")
    e1, e10 = st["depth_edge_informativo"]["err_pct_1m"], st["depth_edge_informativo"]["err_pct_10m"]
    for z in range(9):
        if st["dy_abs_p95"][z] is None:
            print(f"    {ZNAME[z]:12s} (vuota)")
            continue
        sc = st["scale_err_pct_median"][z]
        print(f"    {ZNAME[z]:12s} dy {st['dy_abs_p50'][z]:.2f}|{st['dy_abs_p95'][z]:.2f}  scala {('%+.2f%%' % sc) if sc is not None else 'n/d'}"
              f"  depth 1m {('%+.2f%%' % e1[z]) if e1[z] is not None else 'n/d'} | 10m {('%+.2f%%' % e10[z]) if e10[z] is not None else 'n/d'}")
    print(f"    RMS hold-out: mono L {rep['rms_mono_holdout'][0]:.3f} R {rep['rms_mono_holdout'][1]:.3f} px, stereo {rep['rms_stereo_holdout']['rms']}")
    print(f"    |T| {rep['T_from_board_mm']:.1f} mm ({rep.get('baseline_dev_pct', float('nan')):+.2f}% da 200), T[0] {rep['T_m'][0]*1000:+.1f} mm")
    print(f"[5] GATE {rep['gate']}" + "".join("\n    - " + m for m in red) + "".join("\n    ~ AVVISO: " + m for m in orange))
    print(f"    -> {a.out}  (+ .report.json, {os.path.basename(ypath)}, {os.path.basename(mpath)})")


if __name__ == "__main__":
    main()
