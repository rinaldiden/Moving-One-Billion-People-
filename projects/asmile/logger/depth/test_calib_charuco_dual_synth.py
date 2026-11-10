#!/usr/bin/env python3
"""
test_calib_charuco_dual_synth.py — REGRESSIONE AUTOMATICA di calib_charuco_dual.py (e depth.py): da lanciare
OGNI VOLTA che si tocca il codice di calibrazione (D012). Esce con codice != 0 se UN caso non da' l'esito atteso.

Rende un tabellone ChArUco visto da una coppia stereo con distorsione NOTA (rational + thin-prism, simile a #001:
f~1150, k1~-0.37, rotazione relativa ~5 deg), lo codifica in DUE file h264 a 500 kbps con la convenzione di #001
(video_left = camera fisicamente DESTRA), lancia lo script vero e confronta con la verita' (punti 3D indipendenti).

CRITERIO FISSATO PRIMA di rilanciare (veto critico 2026-11-10, soglie D012 NON ritoccate):
  9zone su SEEDS_9ZONE (5 seed, inclusi 1,2,3 che il critico aveva trovato ROSSI): >= MIN_VERDI VERDI (4/5), e ZERO falsi
  verdi in tutti i casi (VERDE con verita' 3D fuori da dy p95<1 px o depth p95<=2%, o con modello/baseline sbagliati).
  Gate: modello e stereo scelti su un blocco DIVERSO da quello del gate (fit 50% / scelta 20% / gate 30%).

Casi (esito atteso fra parentesi):
  9zone_5seed      9 zone, 5 seed (>= 4/5 VERDE; verita': dy p95<1 px e depth p95<=2% a 1-5 m in OGNI zona se VERDE)
  stat_dy_unit     la statistica dy (media per vista) vede un errore sistematico di 1.2 px e non il solo rumore di corner
  solo_centro      viste solo al centro (ROSSO: copertura)
  file_scambiati   stessi video, --left-file/--right-file invertiti (ROSSO, T[0]>=0)  [falso verde del critico]
  tilt_auto/rational/prism  sensore sinistro INCLINATO ~0.3 deg: il gate deve CONCORDARE con la verita' 3D (rational assorbe
                   il tilt: VERDE vero; VERDE con verita' fuori soglia = falso verde = FAIL)
  camera_mossa     camera destra toccata (0.12 deg) a meta' sessione: ROSSO (dy sistematico); VERDE = falso verde
  scala_2pct       --square-len sbagliato del +2% -> |T| 2% fuori (ARANCIO: calibro + annotazione)
  scala_5pct       --square-len sbagliato del +5% -> ROSSO
  sync_3pct        3% coppie con dt 3 ms (VERDE, coppie scartate = iniettate)
  sync_20pct       20% coppie con dt 3 ms (ROSSO p95, coppie scartate = iniettate)
  export           YAML OpenCV + .maps.npz esistono, CANDIDATO nel nome, K1 coincide col JSON; --out senza CANDIDATO rifiutato
  depth_default    depth.py con default = copia bit-identica del vecchio codice; filtro confidenza (stub) opzionale

Uso: python3 test_calib_charuco_dual_synth.py --work <cartella temporanea fuori da git>
Scrive test_calib_charuco_dual_synth.esito.json e .log accanto allo script. Exit 0 solo se TUTTI i casi sono OK.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calib_charuco_dual as ccd  # noqa: E402
from stereo_common import Calib  # noqa: E402

W, H, SS = 1280, 800, 2
SEEDS_9ZONE = [20261109, 1, 2, 3, 4]    # fissati PRIMA della regressione (non scelti dopo aver visto gli esiti)
MIN_VERDI = 4                            # >= 4/5 VERDE
MAX_JOBS = 3                             # processi di calibrazione in parallelo (il Mac allena il MAESTRO)
rng = np.random.default_rng(20261109)

# ---- verità (fisicamente SINISTRA = camera 1 della calib; DESTRA = camera 2) ----
K1 = np.array([[1153.0, 0, 646.0], [0, 1151.0, 397.0], [0, 0, 1]])
K2 = np.array([[1149.0, 0, 628.0], [0, 1148.0, 409.0], [0, 0, 1]])
# rational(8) + thin prism(4): k1 k2 p1 p2 k3 k4 k5 k6 s1 s2 s3 s4
D1 = np.array([-0.37, 0.17, 0.0004, -0.0006, -0.02, 0.0, 0.0, 0.04, 0.004, -0.001, -0.003, 0.0008])
D2 = np.array([-0.39, 0.20, -0.0003, 0.0005, -0.03, 0.0, 0.0, 0.05, -0.002, 0.0006, 0.004, -0.001])
# stessa ottica ma sensore SINISTRO inclinato di ~0.3 deg (tauX, tauY in rad, 14 coefficienti OpenCV)
D1T = np.r_[D1, np.radians(0.22), np.radians(-0.20)]
D2T = np.r_[D2, 0.0, 0.0]
R_TRUE = cv2.Rodrigues(np.radians([-5.2, 2.1, 0.3]))[0]
T_TRUE = np.array([[-0.2], [0.0012], [0.0018]])


def ray_map(K, D):
    """Per ogni sotto-pixel (SSx) il raggio normalizzato; maschera dove l'inversione non converge."""
    u, v = np.meshgrid((np.arange(W * SS) + 0.5) / SS - 0.5, (np.arange(H * SS) + 0.5) / SS - 0.5)
    pts = np.stack([u.ravel(), v.ravel()], 1).reshape(-1, 1, 2)
    crit = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-10)
    n = cv2.undistortPointsIter(pts, K, D, None, None, crit).reshape(-1, 2)
    back = cv2.projectPoints(np.c_[n, np.ones(len(n))].reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K, D)[0].reshape(-1, 2)
    ok = np.linalg.norm(back - pts.reshape(-1, 2), axis=1) < 0.02
    return np.c_[n, np.ones(len(n))].reshape(H * SS, W * SS, 3), ok.reshape(H * SS, W * SS)


def render(rays, ok, tex, ppm, Rb, tb, bg):
    nrm = Rb[:, 2]
    den = rays @ nrm
    s = (nrm @ tb) / np.where(np.abs(den) < 1e-9, 1e-9, den)
    X = rays * s[..., None] - tb.ravel()
    Xb = X @ Rb  # R^T (X - t)
    mx, my = (Xb[..., 0] * ppm).astype(np.float32), (Xb[..., 1] * ppm).astype(np.float32)
    bad = (~ok) | (s <= 0)
    mx[bad] = -1e5
    img = cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=-1)
    img = np.where(img < 0, bg, img)
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    img = cv2.GaussianBlur(img, (0, 0), 0.7)
    img = img + rng.normal(0, 2.0, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def poses(n, center_only, board_wh):
    out = []
    for k in range(n):
        if center_only:
            zx, zy = 1, 1
        else:
            zx, zy = k % 3, (k // 3) % 3
        u = (zx + rng.uniform(0.25, 0.75)) * W / 3
        v = (zy + rng.uniform(0.25, 0.75)) * H / 3
        Z = rng.uniform(0.65, 1.6)
        # viste pari: angolo mirato sulla camera SINISTRA; dispari: sulla DESTRA (le due camere sono ruotate:
        # coprire gli angoli di una non copre quelli dell'altra -> stesso consiglio dato a Daniele)
        if center_only or (k // 9) % 2 == 0:
            ray = np.linalg.solve(K1, [u, v, 1.0]); c = ray / ray[2] * Z
        else:
            ray = np.linalg.solve(K2, [u, v, 1.0]); cr = ray / ray[2] * Z
            c = R_TRUE.T @ (cr - T_TRUE.ravel())
        tilt = np.radians(rng.uniform(20, 40))
        ax = rng.uniform(0, 2 * np.pi)
        Rt = cv2.Rodrigues(np.array([np.cos(ax), np.sin(ax), 0]) * tilt)[0]
        Rz = cv2.Rodrigues(np.array([0, 0, np.radians(rng.uniform(-25, 25))]))[0]
        Rb = Rt @ Rz
        tb = (c - Rb @ np.array([board_wh[0] / 2, board_wh[1] / 2, 0])).reshape(3, 1)
        out.append((Rb, tb))
    return out


def make_session(work, name, center_only, nviews, board, sx, sy, sq, d1=D1, d2=D2, bump_deg=0.0):
    d = os.path.join(work, name)
    os.makedirs(d, exist_ok=True)
    ppsq = 120
    tex = board.generateImage((sx * ppsq, sy * ppsq), marginSize=0, borderBits=1).astype(np.float32)
    tex = 40 + tex * (200 / 255.0)  # contrasto realistico (non 0/255)
    ppm = ppsq / sq
    rl, okl = ray_map(K1, d1)
    rr, okr = ray_map(K2, d2)
    frames = {"L": [], "R": []}
    Rbump = cv2.Rodrigues(np.radians([bump_deg, 0.0, 0.0]))[0] @ R_TRUE      # camera destra 'toccata' a meta' sessione
    for idx, (Rb, tb) in enumerate(poses(nviews, center_only, (sx * sq, sy * sq))):
        Ruse = Rbump if (bump_deg and idx >= nviews // 2) else R_TRUE
        bg = rng.uniform(90, 160)
        a = render(rl, okl, tex, ppm, Rb, tb, bg)
        b = render(rr, okr, tex, ppm, Ruse @ Rb, Ruse @ tb + T_TRUE, bg)
        for _ in range(2):
            frames["L"].append(a); frames["R"].append(b)
    # convenzione #001: video_left.h264 = camera fisicamente DESTRA, video_right.h264 = fisicamente SINISTRA
    for key, fn in (("R", "video_left.h264"), ("L", "video_right.h264")):
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                              "-r", "15", "-i", "-", "-c:v", "libx264", "-profile:v", "baseline", "-b:v", "500k",
                              "-pix_fmt", "yuv420p", os.path.join(d, fn)], stdin=subprocess.PIPE)
        for f in frames[key]:
            p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()
    for fn in ("frames_left.csv", "frames_right.csv"):
        with open(os.path.join(d, fn), "w") as f:
            f.write("frame,t_ms,sensor_ts_ns,exposure_us,rx_minus_sensor_ms\n")
            for i in range(len(frames["L"])):
                f.write(f"{i},{i*66},{i*66666666},900,480\n")
    return d


def _truth_points(N, zlo, zhi, d1, d2):
    uu, vv = rng.uniform(0, W, N), rng.uniform(0, H, N)
    Z = rng.uniform(zlo, zhi, N)
    n = cv2.undistortPoints(np.stack([uu, vv], 1).reshape(-1, 1, 2), K1, d1).reshape(-1, 2)
    P = np.c_[n * Z[:, None], Z]
    pl = cv2.projectPoints(P.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K1, d1)[0].reshape(-1, 2)
    Pr = (R_TRUE @ P.T + T_TRUE).T
    pr = cv2.projectPoints(Pr.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K2, d2)[0].reshape(-1, 2)
    vis = (pr[:, 0] > 2) & (pr[:, 0] < W - 2) & (pr[:, 1] > 2) & (pr[:, 1] < H - 2) & (Pr[:, 2] > 0) \
        & (pl[:, 0] > 2) & (pl[:, 0] < W - 2) & (pl[:, 1] > 2) & (pl[:, 1] < H - 2)
    return P[vis], pl[vis], pr[vis]


def _err(est, re, P, pl, pr):
    a = cv2.undistortPoints(pl.reshape(-1, 1, 2), est.K1, est.d1, R=re["R1"], P=re["P1"]).reshape(-1, 2)
    b = cv2.undistortPoints(pr.reshape(-1, 1, 2), est.K2, est.d2, R=re["R2"], P=re["P2"]).reshape(-1, 2)
    dy = a[:, 1] - b[:, 1]
    Bm = float(np.linalg.norm(est.T))            # baseline STIMATA (non quella vera): include l'errore di scala
    Zest = re["focal_px"] * Bm / (a[:, 0] - b[:, 0])
    Zr = (re["R1"] @ P.T).T[:, 2]
    return dy, 100 * (Zest / Zr - 1), ccd.zone_of(pl)


def compare(cal_path, d1, d2):
    est = Calib.load(cal_path)
    re = est.rectify()
    out = dict(zone=ccd.ZNAME)
    # B,C) GATE: punti 3D casuali a 1-5 m, mai usati nel fit (verita' indipendente)
    P, pl, pr = _truth_points(40000, 1.0, 5.0, d1, d2)
    dy, e, zB = _err(est, re, P, pl, pr)
    for key, fn in (("B_dy_abs_p95", lambda m: np.percentile(np.abs(dy[m]), 95)), ("B_dy_median", lambda m: np.median(dy[m])),
                    ("C_depth_pct_p95", lambda m: np.percentile(np.abs(e[m]), 95)), ("C_depth_pct_median", lambda m: np.median(e[m]))):
        out[key] = [round(float(fn(zB == z)), 3) for z in range(9)]
    # A8) INFORMATIVO: depth ai bordi a 1 m e a 10 m (verita'), non nel criterio
    for lab, lo, hi in (("1m", 0.9, 1.1), ("10m", 9.0, 11.0)):
        P2, pl2, pr2 = _truth_points(60000, lo, hi, d1, d2)
        _, e2, z2 = _err(est, re, P2, pl2, pr2)
        out[f"info_depth_pct_p95_{lab}"] = [round(float(np.percentile(np.abs(e2[z2 == z]), 95)), 3) if (z2 == z).sum() > 20 else None
                                           for z in range(9)]
    Rt = Calib(K1, d1, K2, d2, R_TRUE, T_TRUE).rectify()
    out["focal_rect_est_true"] = [re["focal_px"], Rt["focal_px"]]
    out["baseline_dir_ok"] = bool(est.T[0, 0] < 0)
    out["baseline_est_mm"] = round(float(np.linalg.norm(est.T)) * 1000, 2)
    out["baseline_true_mm"] = round(float(np.linalg.norm(T_TRUE)) * 1000, 2)
    return out


class Tee:
    def __init__(self, path):
        self.f = open(path, "w")
        self.o = sys.stdout

    def write(self, x):
        self.o.write(x); self.f.write(x)

    def flush(self):
        self.o.flush(); self.f.flush()


def run_script(session, out, extra=(), unit="asmile-001", sq=ccd.DEF_SQ):
    t0 = time.time()
    cmd = [sys.executable, os.path.join(HERE, "calib_charuco_dual.py"), "--unit", unit, "--session", session,
           "--square-len", str(sq), "--step", "1", "--out", out, *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"----- {os.path.basename(out)}  (rc {r.returncode}, {time.time()-t0:.0f}s)\n{r.stdout}{r.stderr[-1500:]}")
    rep = json.load(open(out + ".report.json")) if r.returncode == 0 and os.path.exists(out + ".report.json") else None
    return rep, r


def sync_session(src, dst, frac, seed):
    """Stessi video, csv con una frazione di coppie con dt = 3 ms (right in ritardo)."""
    os.makedirs(dst, exist_ok=True)
    for fn in ("video_left.h264", "video_right.h264"):
        if os.path.lexists(os.path.join(dst, fn)):
            os.remove(os.path.join(dst, fn))
        os.symlink(os.path.join(src, fn), os.path.join(dst, fn))
    n = sum(1 for _ in open(os.path.join(src, "frames_left.csv"))) - 1
    bad = set(np.random.default_rng(seed).choice(n, int(round(frac * n)), replace=False).tolist())
    for fn in ("frames_left.csv", "frames_right.csv"):
        with open(os.path.join(dst, fn), "w") as f:
            f.write("frame,t_ms,sensor_ts_ns,exposure_us,rx_minus_sensor_ms\n")
            for i in range(n):
                extra = 3_000_000 if (fn == "frames_right.csv" and i in bad) else 0
                f.write(f"{i},{i*66},{i*66666666 + extra},900,480\n")
    return dst, len(bad)


def depth_checks(work_session):
    import depth as dp
    out = {}
    L = next(iter(ccd.gray_frames(os.path.join(work_session, "video_left.h264"), W, H)))[:, :640][:400]
    Rr = next(iter(ccd.gray_frames(os.path.join(work_session, "video_right.h264"), W, H)))[:, :640][:400]
    L, Rr = np.ascontiguousarray(L), np.ascontiguousarray(Rr)

    def legacy(left, right, num_disp=192, block=7, wls=True):          # COPIA del disparity_sgbm prima della modifica
        sgbm = dp.make_sgbm(num_disp, block)
        dl = sgbm.compute(left, right).astype(np.float32) / 16.0
        if wls and dp.HAS_WLS:
            right_m = dp.ximgproc.createRightMatcher(sgbm)
            dr = right_m.compute(right, left).astype(np.float32) / 16.0
            wf = dp.ximgproc.createDisparityWLSFilter(sgbm)
            wf.setLambda(8000.0)
            wf.setSigmaColor(1.5)
            return wf.filter((dl * 16).astype(np.int16), left, None, (dr * 16).astype(np.int16)).astype(np.float32) / 16.0
        return dl
    a, b = dp.disparity_sgbm(L, Rr), legacy(L, Rr)
    out["default_bit_identico"] = bool(a.dtype == b.dtype and np.array_equal(a, b))
    out["HAS_WLS_reale"] = bool(dp.HAS_WLS)

    # glue del filtro confidenza con uno STUB di ximgproc (opencv-contrib non installato su questo Mac):
    # verifica SOLO la logica di mascheratura, NON la qualita' del WLS vero
    class _F:
        def setLambda(self, *_): pass
        def setSigmaColor(self, *_): pass
        def filter(self, dl16, left, _none, dr16): self.shape = dl16.shape; return dl16
        def getConfidenceMap(self):
            m = np.zeros(self.shape, np.float32); m[:, self.shape[1] // 2:] = 255.0
            return m

    class _RM:
        def compute(self, right, left): return np.zeros(left.shape, np.int16)

    class _X:
        createRightMatcher = staticmethod(lambda s: _RM())
        createDisparityWLSFilter = staticmethod(lambda s: _F())
    old = (dp.HAS_WLS, getattr(dp, "ximgproc", None))
    dp.HAS_WLS, dp.ximgproc = True, _X
    try:
        base = dp.disparity_sgbm(L, Rr)
        filt = dp.disparity_sgbm(L, Rr, conf_min=128)
        half = base.shape[1] // 2
        out["conf_stub_default_invariato"] = bool(np.array_equal(base, dp.disparity_sgbm(L, Rr, conf_min=None)))
        out["conf_stub_scarta_sotto_soglia"] = bool(np.all(filt[:, :half] == -1) and np.array_equal(filt[:, half:], base[:, half:]))
    finally:
        dp.HAS_WLS = old[0]
        if old[1] is None:
            del dp.ximgproc
        else:
            dp.ximgproc = old[1]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--views", type=int, default=200)
    ap.add_argument("--reuse", action="store_true", help="riusa sessioni e report gia' calcolati in --work (stesso codice calib): "
                    "ricalcola solo verita', criteri e i job mancanti")
    ap.add_argument("--extra-seeds", default="", help="seed 9zone ulteriori, solo informativi (non nel criterio)")
    ap.add_argument("--esito", default=os.path.join(HERE, "test_calib_charuco_dual_synth.esito.json"))
    ap.add_argument("--log", default=os.path.join(HERE, "test_calib_charuco_dual_synth.log"))
    a = ap.parse_args()
    sys.stdout = Tee(a.log)
    os.makedirs(a.work, exist_ok=True)
    sx, sy, sq = ccd.DEF_SX, ccd.DEF_SY, ccd.DEF_SQ
    board = ccd.make_board(ccd.DEF_DICT, sx, sy, sq, round(0.74 * sq, 5))
    cases = {}

    def case(name, expected, rep, checks, truth=None, extra=None):
        ok = all(c[1] for c in checks)
        cases[name] = dict(atteso=expected, gate_script=(rep or {}).get("gate"), modello=(rep or {}).get("model"),
                           problemi=(rep or {}).get("gate_problemi"), avvisi=(rep or {}).get("gate_avvisi"),
                           checks={c[0]: bool(c[1]) for c in checks}, OK=ok, verita=truth)
        if extra:
            cases[name].update(extra)
        print(f"\n>>>> CASO {name}: atteso {expected} -> script {cases[name]['gate_script']} | {'OK' if ok else 'FALLITO'}"
              + ("" if ok else "  checks KO: " + ", ".join(k for k, v in cases[name]['checks'].items() if not v)))

    def truth_ok(v):
        return [("verita_dy_p95<1_in_9_zone", max(v["B_dy_abs_p95"]) < 1.0),
                ("verita_depth_p95<=2%_in_9_zone", max(v["C_depth_pct_p95"]) <= 2.0), ("T[0]<0", v["baseline_dir_ok"])]

    # ---------- sessioni (generate in sequenza: rng globale), poi le calibrazioni in parallelo (max MAX_JOBS)
    global rng
    _ms = globals()["make_session"]

    def make_session(work, name, *args, **kw):          # noqa: F811 (con --reuse non rigenera una sessione gia' fatta)
        dd_ = os.path.join(work, name)
        if a.reuse and os.path.exists(os.path.join(dd_, "video_right.h264")):
            return dd_
        return _ms(work, name, *args, **kw)
    P = lambda n: os.path.join(a.work, f"calib_{n}.CANDIDATO.json")
    d9 = make_session(a.work, f"synth_9zone_s{SEEDS_9ZONE[0]}", False, a.views, board, sx, sy, sq)
    dc = make_session(a.work, "synth_solo_centro", True, a.views, board, sx, sy, sq)
    dt = make_session(a.work, "synth_tilt", False, int(a.views * 1.5), board, sx, sy, sq, D1T, D2T)
    extra_seeds = [int(x) for x in a.extra_seeds.split(",") if x.strip()]
    seed_dirs = {SEEDS_9ZONE[0]: d9}
    for sd in SEEDS_9ZONE[1:] + extra_seeds:
        rng = np.random.default_rng(sd)
        seed_dirs[sd] = make_session(a.work, f"synth_9zone_s{sd}", False, a.views, board, sx, sy, sq)
    sd3, ninj3 = sync_session(d9, os.path.join(a.work, "synth_sync_3pct"), 0.03, 7)
    sd20, ninj20 = sync_session(d9, os.path.join(a.work, "synth_sync_20pct"), 0.20, 7)
    rng = np.random.default_rng(4242)
    dm = make_session(a.work, "synth_camera_mossa", False, a.views, board, sx, sy, sq, bump_deg=0.12)
    jobs = {}
    for sd, dd in seed_dirs.items():
        jobs[f"9zone_s{sd}"] = (dd, [], sq)
    jobs["camera_mossa"] = (dm, [], sq)
    jobs["solo_centro"] = (dc, [], sq)
    jobs["scambiati"] = (d9, ["--left-file", os.path.join(d9, "video_left.h264"), "--right-file", os.path.join(d9, "video_right.h264")], sq)
    jobs["tilt_auto"] = (dt, [], sq)
    jobs["tilt_rational"] = (dt, ["--models", "rational"], sq)
    jobs["tilt_prism"] = (dt, ["--models", "rational+prism"], sq)
    jobs["scala_2pct"] = (d9, [], round(sq * 1.02, 6))
    jobs["scala_5pct"] = (d9, [], round(sq * 1.05, 6))
    jobs["sync_3pct"] = (sd3, [], sq)
    jobs["sync_20pct"] = (sd20, [], sq)
    from concurrent.futures import ThreadPoolExecutor
    def run_or_reuse(k, v):
        if a.reuse and os.path.exists(P(k) + ".report.json"):
            class _R:
                returncode = 0
            return json.load(open(P(k) + ".report.json")), _R()
        return run_script(v[0], P(k), v[1], "asmile-001", v[2])
    with ThreadPoolExecutor(max_workers=MAX_JOBS) as ex:
        futs = {k: ex.submit(run_or_reuse, k, v) for k, v in jobs.items()}
        res_run = {k: f.result() for k, f in futs.items()}

    def truth(k, d1, d2):
        rep_ = res_run[k][0]
        if not rep_:
            return None
        globals()["rng"] = np.random.default_rng(777)     # punti di verita' riproducibili
        return compare(P(k), d1, d2)

    # 0) statistica dy: errore sistematico visto, rumore di corner no (unit test sul codice del gate)
    r0 = np.random.default_rng(0)
    mk = lambda off, sig: [{i: list(off + r0.normal(0, sig, 25)) for i in range(12)} for _ in range(9)]
    st_a, st_b, st_c = ccd.dy_zone_stats(mk(0.0, 0.44)), ccd.dy_zone_stats(mk(1.2, 0.44)), ccd.dy_zone_stats(mk(0.6, 0.44))
    case("stat_dy_unit", "rumore 0.44 px: media-per-vista <1 ma p95 grezzo ~0.9; offset 1.2 px: >=1; offset 0.6: <1", None,
         [("solo rumore -> p95 media-per-vista < 0.5", max(st_a["dy_patch_abs_p95"]) < 0.5),
          ("solo rumore -> p95 grezzo >= 0.8 (pavimento di rumore)", max(st_a["dy_abs_p95"]) >= 0.8),
          ("offset sistematico 1.2 px -> media-per-vista >= 1.0 (gate ROSSO)", min(st_b["dy_patch_abs_p95"]) >= 1.0),
          ("offset 0.6 px -> media-per-vista < 1.0", max(st_c["dy_patch_abs_p95"]) < 1.0)],
         extra=dict(valori=dict(rumore=max(st_a["dy_patch_abs_p95"]), off12=min(st_b["dy_patch_abs_p95"]), off06=max(st_c["dy_patch_abs_p95"]))))

    # 1) 9 zone x 5 seed (criterio fissato prima)
    tab = []
    for sd in SEEDS_9ZONE + extra_seeds:
        k = f"9zone_s{sd}"
        rep, r = res_run[k]
        v = truth(k, D1, D2)
        gtruth = bool(v) and all(c[1] for c in truth_ok(v))
        verde = bool(rep) and rep["gate"] == "VERDE"
        hs_ = (rep or {}).get("stereo_holdout", {})
        tab.append(dict(seed=sd, in_criterio=sd in SEEDS_9ZONE, gate=(rep or {}).get("gate"), verde=verde,
                        falso_verde=verde and not gtruth, verita_ok=gtruth, modello=(rep or {}).get("model"),
                        dy_n_min=min(hs_["dy_n"]) if hs_ else None, patch_n_min=min(hs_["dy_patch_n"]) if hs_ else None,
                        dy_patch_p95_peggiore=max([x for x in hs_.get("dy_patch_abs_p95", []) if x is not None] or [None]) if hs_ else None,
                        dy_p95_grezzo_peggiore=max([x for x in hs_.get("dy_abs_p95", []) if x is not None] or [None]) if hs_ else None,
                        rumore_corner_sigma_px=float(np.nanmedian([x for x in hs_.get("dy_noise_sigma_px", []) if x is not None] or [np.nan])) if hs_ else None,
                        rms_mono_gate=(rep or {}).get("rms_mono_holdout"), rms_stereo_gate=((rep or {}).get("rms_stereo_holdout") or {}).get("rms"),
                        baseline_dev_pct=(rep or {}).get("baseline_dev_pct"),
                        verita_dy_p95_peggiore=max(v["B_dy_abs_p95"]) if v else None,
                        verita_depth_p95_peggiore=max(v["C_depth_pct_p95"]) if v else None,
                        problemi=(rep or {}).get("gate_problemi"), avvisi_margine=(rep or {}).get("avvisi_margine"),
                        n_viste=(rep or {}).get("holdout", {}).get("n_views")))
    crit_t = [t_ for t_ in tab if t_["in_criterio"]]
    n_verdi = sum(t_["verde"] for t_ in crit_t)
    case("9zone_5seed", f">= {MIN_VERDI}/5 VERDE, 0 falsi verdi", None,
         [(f"VERDE su {n_verdi}/5 (>= {MIN_VERDI})", n_verdi >= MIN_VERDI),
          ("zero falsi verdi (verita' 3D)", not any(t_["falso_verde"] for t_ in tab)),
          ("ogni ROSSO ha un motivo", all(t_["verde"] or t_["problemi"] for t_ in tab))],
         extra=dict(seed_tabella=tab, n_verdi=n_verdi))
    rep9, r9 = res_run[f"9zone_s{SEEDS_9ZONE[0]}"]
    # 2) solo centro
    rep, r = res_run["solo_centro"]
    case("solo_centro", "ROSSO", rep, [("rc0", r.returncode == 0), ("gate ROSSO", bool(rep) and rep["gate"] == "ROSSO"),
                                       ("motivo copertura", bool(rep) and any("copertura" in m for m in rep["gate_problemi"]))])
    # 3) file scambiati (falso verde del critico)
    rep, r = res_run["scambiati"]
    case("file_scambiati", "ROSSO (T[0]>=0)", rep, [("rc0", r.returncode == 0), ("gate ROSSO", bool(rep) and rep["gate"] == "ROSSO"),
                                                   ("motivo T[0]>=0", bool(rep) and any("T[0]" in m for m in rep["gate_problemi"]))])
    # 4) sensore inclinato ~0.3 deg. Con la statistica corretta (media per vista) il gate non e' piu' deciso dal rumore dei
    # corner: il modello rational ASSORBE un tilt di 0.3 deg (verita' dy p95<0.5 px) e il VERDE e' VERO. Quindi il criterio
    # non e' "ROSSO" ma "il gate concorda con la verita' 3D": VERDE con verita' fuori soglia = FALSO VERDE = FAIL; ROSSO con
    # verita' buona = falso rosso, riportato (non fallisce: e' prudenza).
    for nm, v_nm in (("tilt_auto", None), ("tilt_rational", None), ("tilt_prism", None)):
        rep, r = res_run[nm]
        v = truth(nm, D1T, D2T)
        verde = bool(rep) and rep["gate"] == "VERDE"
        truth_good = bool(v) and all(c[1] for c in truth_ok(v))
        stato = "FALSO VERDE" if (verde and not truth_good) else ("VERDE VERO" if verde else
                ("ROSSO prudente (verita' buona: falso rosso)" if truth_good else "ROSSO giusto (verita' cattiva)"))
        case(nm, "gate concorda con la verita' 3D (VERDE solo se verita' ok; falso VERDE = FAIL)", rep,
             [("rc0", r.returncode == 0), ("falso VERDE = FAIL", not (verde and not truth_good)),
              ("ROSSO sempre motivato", verde or bool(rep and rep["gate_problemi"]))], v,
             extra=dict(tilt_stato=stato, holdout_rms_modelli=(rep or {}).get("models"), modello_scelto=(rep or {}).get("model")))
    # 4b) camera destra TOCCATA a meta' sessione (0.12 deg su x -> dy ~2.4 px): il gate vede dy sistematico nei blocchi
    # dopo il colpo, la verita' (R originale) e' cattiva -> deve essere ROSSO; VERDE qui = FALSO VERDE.
    rep, r = res_run["camera_mossa"]
    v = truth("camera_mossa", D1, D2)
    truth_good = bool(v) and all(c[1] for c in truth_ok(v))
    verde = bool(rep) and rep["gate"] == "VERDE"
    case("camera_mossa", "ROSSO (dy sistematico dopo il colpo); VERDE = falso verde", rep,
         [("rc0", r.returncode == 0), ("gate ROSSO", bool(rep) and rep["gate"] == "ROSSO"), ("falso VERDE = FAIL", not (verde and not truth_good)),
          ("motivo: dy", bool(rep) and any(m.startswith("dy zona") for m in rep["gate_problemi"]))], v,
         extra=dict(verita_cattiva=not truth_good))
    # 5) scala del tabellone sbagliata (|T| fuori dal 200 mm)
    for nm, k_, exp in (("scala_2pct", 1.02, "ARANCIO"), ("scala_5pct", 1.05, "ROSSO")):
        rep, r = res_run[nm]
        case(nm, exp, rep, [("rc0", r.returncode == 0), (f"gate {exp}", bool(rep) and rep["gate"] == exp),
                            ("|T| NON riscalata (dev ~ +%d%%)" % round((k_ - 1) * 100),
                             bool(rep) and abs(rep["baseline_dev_pct"] - (k_ - 1) * 100) < 0.7)],
             extra=dict(baseline_dev_pct=(rep or {}).get("baseline_dev_pct")))
    # 6) sync
    for nm, ninj, exp in (("sync_3pct", ninj3, "VERDE"), ("sync_20pct", ninj20, "ROSSO")):
        rep, r = res_run[nm]
        sy_ = (rep or {}).get("input", {}).get("sync") or {}
        case(nm, exp, rep, [("rc0", r.returncode == 0), (f"gate {exp}", bool(rep) and rep["gate"] == exp),
                            ("coppie scartate = iniettate", sy_.get("pairs_over") == ninj),
                            ("frame scartati in collect = iniettati", (rep or {}).get("input", {}).get("pairs_discarded_sync") == ninj)],
             extra=dict(iniettate=ninj, sync=sy_))
    # 7) export + rifiuto nome senza CANDIDATO
    K9 = f"9zone_s{SEEDS_9ZONE[0]}"
    y, m = P(K9)[:-5] + ".yaml", P(K9)[:-5] + ".maps.npz"
    chk = [("yaml esiste", os.path.exists(y)), ("maps esiste", os.path.exists(m)),
           ("CANDIDATO nel nome", "CANDIDATO" in y and "CANDIDATO" in m)]
    if os.path.exists(y) and os.path.exists(m):
        fs = cv2.FileStorage(y, cv2.FILE_STORAGE_READ)
        cal = Calib.load(P(K9))
        keys = ["K1", "D1", "K2", "D2", "R", "T", "R1", "R2", "P1", "P2", "Q"]
        chk += [("chiavi " + ",".join(keys), all(not fs.getNode(k).empty() for k in keys)),
                ("K1 yaml == JSON", np.allclose(fs.getNode("K1").mat(), cal.K1)),
                ("T yaml == JSON", np.allclose(fs.getNode("T").mat(), cal.T)),
                ("modello+hash", bool(fs.getNode("model").string()) and not fs.getNode("video_sha256").empty())]
        mp = np.load(m)
        chk += [("mappe 800x1280", mp["m1x"].shape == (H, W) and mp["m2y"].shape == (H, W))]
        fs.release()
    rr_ = subprocess.run([sys.executable, os.path.join(HERE, "calib_charuco_dual.py"), "--unit", "asmile-001", "--session", d9,
                          "--out", os.path.join(a.work, "calib_senza_marca.json")], capture_output=True, text=True)
    chk += [("--out senza CANDIDATO rifiutato", rr_.returncode != 0 and not os.path.exists(os.path.join(a.work, "calib_senza_marca.json")))]
    case("export", "file creati e coerenti", None, chk)
    # 8) depth.py
    dc_ = depth_checks(d9)
    case("depth_default", "default bit-identico, conf opzionale", None,
         [("default bit-identico al vecchio codice", dc_["default_bit_identico"]),
          ("(stub) conf_min=None invariato", dc_["conf_stub_default_invariato"]),
          ("(stub) conf_min scarta sotto soglia", dc_["conf_stub_scarta_sotto_soglia"])],
         extra=dict(HAS_WLS_reale=dc_["HAS_WLS_reale"],
                    NON_VERIFICATO="getConfidenceMap del WLS vero: opencv-contrib (ximgproc) assente su questo Mac, provato solo con stub"))

    ok = all(c["OK"] for c in cases.values())
    res = dict(TEST="VERDE" if ok else "ROSSO", casi=cases, casi_falliti=[k for k, c in cases.items() if not c["OK"]],
               quando=time.strftime("%Y-%m-%dT%H:%M:%S"),
               criteri=("ogni caso ha esito atteso dichiarato; nessuna soglia modificata per far passare; verita' = punti 3D "
                        "indipendenti 1-5 m (dy p95<1 px e depth p95<=2% in OGNI zona 3x3); exit code != 0 se un caso fallisce"))
    json.dump(res, open(a.esito, "w"), indent=1, default=float)
    print("\n===== RIEPILOGO =====")
    for k, c in cases.items():
        print(f"  {k:16s} atteso {c['atteso']:42s} script {str(c['gate_script']):8s} {'OK' if c['OK'] else 'FALLITO'}")
    print(f"TEST {res['TEST']} -> {a.esito}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
