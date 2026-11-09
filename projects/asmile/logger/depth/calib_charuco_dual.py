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

Uscita: <out> (formato Calib di stereo_common, T in METRI come calib_asmile-001.json) + <out>.report.json.
Non sovrascrive MAI una calib_<unità>.json: il nome deve contenere "CANDIDATO". La sostituzione la decide
asmile-calib-critico (PASSA) — non questo script.
"""
import argparse
import csv
import datetime
import json
import os
import subprocess
import sys

import cv2
import numpy as np

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
}


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


def paired_frames(args, prof):
    """Genera (idx, phys_left, phys_right). Per #001 controlla il sync coi sensor_ts dei frames_*.csv."""
    info = {}
    if prof["mode"] == "dual":
        fl = args.left_file or os.path.join(args.session, prof["phys_left_file"])
        fr = args.right_file or os.path.join(args.session, prof["phys_right_file"])
        tl = read_sensor_ts(os.path.join(args.session, prof["phys_left_csv"])) if args.session else None
        tr = read_sensor_ts(os.path.join(args.session, prof["phys_right_csv"])) if args.session else None
        info.update(phys_left_file=fl, phys_right_file=fr)
        if tl and tr:
            n = min(len(tl), len(tr))
            dt = np.abs(np.array(tl[:n]) - np.array(tr[:n])) / 1e6
            info["sync_ms_p95"] = float(np.percentile(dt, 95))
            info["sync_ms_max"] = float(dt.max())
        gL, gR = gray_frames(fl, CAM_W, CAM_H), gray_frames(fr, CAM_W, CAM_H)
        for i, (a, b) in enumerate(zip(gL, gR)):
            yield i, a, b, info
    else:
        from stereo_common import split_sbs
        info.update(sbs_file=args.sbs)
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
    views, info, n = [], {}, 0
    last_sig = None
    for i, L, R, info in paired_frames(args, prof):
        n += 1
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
    return views, info


def split_holdout(views, every):
    """Deterministico: una vista ogni `every` va in hold-out (mai usata nel fit)."""
    fit, hold = [], []
    for k, v in enumerate(views):
        (hold if k % every == every - 1 else fit).append(v)
    return fit, hold


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


def holdout_stereo(views, K1, D1, K2, D2, R, T, sq_m):
    """dy rettificato per zona (zona = posizione nel frame GREZZO sinistro) + errore di scala da triangolazione:
    distanza 3D fra corner vicini del tabellone vs lato vero -> proxy dell'errore % di depth (X=x·Z/f)."""
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, D1, K2, D2, (CAM_W, CAM_H), R, T,
                                                flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    dy_z = [[] for _ in range(9)]
    sc_z = [[] for _ in range(9)]
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
        # coppie di corner adiacenti (distanza vera = 1 lato)
        for j in range(len(obj)):
            dd = np.linalg.norm(obj - obj[j], axis=1)
            for k in np.where(np.abs(dd - sq_m) < 1e-6)[0]:
                if k <= j or not (ok[j] and ok[k]):
                    continue
                s = np.linalg.norm(X[j] - X[k]) / sq_m - 1.0
                sc_z[zs[j]].append(float(s))
    f = lambda arr, fn: (float(fn(np.array(arr))) if arr else None)
    return dict(
        dy_median=[f(a, np.median) for a in dy_z],
        dy_abs_p95=[f(np.abs(a).tolist(), lambda x: np.percentile(x, 95)) for a in dy_z],
        dy_n=[len(a) for a in dy_z],
        scale_err_pct_median=[f(a, lambda x: 100 * np.median(x)) for a in sc_z],
        scale_n=[len(a) for a in sc_z],
        z_range_m=[float(np.min(zdist)), float(np.max(zdist))] if zdist else None,
        focal_rect_px=float(P1[0, 0]),
    )


# ---------------------------------------------------------------------------- gate
def gate(rep, a):
    msgs = []
    covL, covR = rep["coverage_fit"]["L_corners"], rep["coverage_fit"]["R_corners"]
    for name, cov in (("L", covL), ("R", covR)):
        bad = [ZNAME[z] for z in range(9) if cov[z] < a.min_zone_corners]
        if bad:
            msgs.append(f"copertura {name} insufficiente (<{a.min_zone_corners} corner) in: {', '.join(bad)}")
    st = rep["stereo_holdout"]
    for z in range(9):
        if st["dy_n"][z] < a.min_zone_holdout:
            msgs.append(f"hold-out stereo: zona {ZNAME[z]} con {st['dy_n'][z]} punti (<{a.min_zone_holdout}) -> non verificata")
        elif abs(st["dy_median"][z]) >= a.max_dy_px:
            msgs.append(f"dy zona {ZNAME[z]} = {st['dy_median'][z]:+.2f} px (>= {a.max_dy_px})")
        se = st["scale_err_pct_median"][z]
        if se is not None and st["scale_n"][z] >= a.min_zone_holdout // 2 and abs(se) > a.max_scale_pct:
            msgs.append(f"scala/depth zona {ZNAME[z]} {se:+.2f}% (> {a.max_scale_pct}%)")
    if rep["n_holdout_stereo"] < 4:
        msgs.append(f"solo {rep['n_holdout_stereo']} viste stereo in hold-out (servono >= 4)")
    tilts = rep.get("tilt_deg_fit_L", [])
    if tilts and np.percentile(tilts, 75) < 15:
        msgs.append("tabellone quasi sempre frontale (tilt p75 < 15 deg): inclinalo 20-40 deg")
    return msgs


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
    ap.add_argument("--holdout-every", type=int, default=5)
    ap.add_argument("--max-views", type=int, default=90)
    ap.add_argument("--min-zone-corners", type=int, default=150)
    ap.add_argument("--min-zone-holdout", type=int, default=20)
    ap.add_argument("--max-dy-px", type=float, default=1.0)
    ap.add_argument("--max-scale-pct", type=float, default=2.0)
    ap.add_argument("--models", default="rational,rational+prism")
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
    fit, hold = split_holdout(views, a.holdout_every)
    fitL, fitR = cap_views(fit, "L", a.max_views), cap_views(fit, "R", a.max_views)
    print(f"    frame {info.get('frames_decoded')}, viste diverse {len(views)} -> fit L {len(fitL)} R {len(fitR)}, hold-out {len(hold)}"
          + (f", sync p95 {info['sync_ms_p95']:.3f} ms" if "sync_ms_p95" in info else ""))
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
        print(f"    {name:15s} fit rms L {rL:.3f} R {rR:.3f} | hold-out L {hL['rms']:.3f} R {hR['rms']:.3f} px  fx L {KL[0,0]:.1f} R {KR[0,0]:.1f}")
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
        sq_scale = BASELINE_M / float(np.linalg.norm(T))
        Ts = T * sq_scale
        hs = holdout_stereo(hold, K1, D1, K2, D2, R, Ts, a.square_len * sq_scale)
        # errore di scala vero: lato triangolato (con T riscalata a 200 mm) vs lato MISURATO col metro
        hs_m = holdout_stereo(hold, K1, D1, K2, D2, R, Ts, a.square_len)
        hs["scale_err_pct_median"] = hs_m["scale_err_pct_median"]
        hs["scale_n"] = hs_m["scale_n"]
        worst = max(abs(d) for d in hs["dy_median"] if d is not None)
        res[joint] = dict(rms=rms, K1=K1, D1=D1, K2=K2, D2=D2, R=R, T=Ts, T_raw_m=float(np.linalg.norm(T)),
                          n=nv, hold=hs, worst_dy=worst)
        print(f"    {'congiunta' if joint else 'intr. fissi':11s} rms {rms:.3f} px, viste {nv}, |T| dal tabellone "
              f"{np.linalg.norm(T)*1000:.1f} mm (atteso ~200 se --square-len giusto), dy hold-out peggior zona {worst:.2f} px")
    s = res[True] if res[True]["worst_dy"] <= res[False]["worst_dy"] else res[False]

    covL, vL = coverage(fitL, "L")
    covR, vR = coverage(fitR, "R")
    rep = dict(
        unit=a.unit, model=best, stereo_mode="congiunta" if s is res[True] else "intrinseci fissi",
        input=info, n_views=len(views), n_fit=dict(L=len(fitL), R=len(fitR), stereo=s["n"]),
        n_holdout=len(hold), n_holdout_stereo=sum(common_pts(v) is not None for v in hold),
        holdout_frames=[v["frame"] for v in hold],
        coverage_fit=dict(L_corners=covL.tolist(), R_corners=covR.tolist(), L_views=vL.tolist(), R_views=vR.tolist()),
        models={nm: dict(rms_fit=cand[nm]["rms_fit"], holdout_rms=(cand[nm]["hold"][0]["rms"], cand[nm]["hold"][1]["rms"]),
                         holdout_zone_rms_L=cand[nm]["hold"][0]["zone_rms"], holdout_zone_rms_R=cand[nm]["hold"][1]["zone_rms"])
                for nm in cand},
        tilt_deg_fit_L=[round(t, 1) for t in c["tiltL"]],
        stereo_rms_fit=s["rms"], T_from_board_mm=s["T_raw_m"] * 1000,
        stereo_holdout=s["hold"], zone_names=ZNAME,
    )
    rep["gate_problemi"] = gate(rep, a)
    rep["gate"] = "VERDE" if not rep["gate_problemi"] else "ROSSO"

    cal = Calib(s["K1"], s["D1"], s["K2"], s["D2"], s["R"], s["T"], size=(CAM_W, CAM_H), baseline_mm=BASELINE_M * 1000)
    cal.save(a.out)
    blob = json.load(open(a.out))
    blob.update({
        "order": prof["order"], "flip180": prof["flip180"], "d0_px": 0.0,
        "focal_rect_px": s["hold"]["focal_rect_px"],
        "method": f"calib_charuco_dual.py: ChArUco {sx}x{sy} {a.dict} lato {a.square_len*1000:.1f} mm, modello {best}, "
                  f"stereo {rep['stereo_mode']}, T riscalata a baseline 200 mm; verifica su {len(hold)} viste tenute fuori",
        "valid_for": f"SOLO {a.unit} con QUESTO set di camere come montate al momento della sessione. Mai fallback su altre unità.",
        "camera_hw": prof["hw"],
        "stato": "CANDIDATO — non in uso finché asmile-calib-critico non dà PASSA",
        "gate_script": rep["gate"],
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    json.dump(blob, open(a.out, "w"), indent=2)
    json.dump(rep, open(a.out + ".report.json", "w"), indent=1, default=float)

    print("[4] dy hold-out per zona (mediana px) / errore scala % (lato triangolato vs metro):")
    st = s["hold"]
    for r0 in range(3):
        print("    " + " | ".join(
            f"{ZNAME[r0*3+k]:12s} dy {st['dy_median'][r0*3+k]:+.2f} sc {st['scale_err_pct_median'][r0*3+k]:+.2f}%"
            if st["dy_median"][r0 * 3 + k] is not None and st["scale_err_pct_median"][r0 * 3 + k] is not None
            else f"{ZNAME[r0*3+k]:12s} (vuota)" for k in range(3)))
    print(f"[5] GATE {rep['gate']}" + ("" if not rep["gate_problemi"] else ":\n    - " + "\n    - ".join(rep["gate_problemi"])))
    print(f"    -> {a.out}  (+ .report.json)")


if __name__ == "__main__":
    main()
