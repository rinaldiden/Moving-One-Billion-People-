#!/usr/bin/env python3
"""
test_calib_charuco_dual_synth.py — test sintetico di calib_charuco_dual.py PRIMA di chiamare Daniele.
(HANDOFF_calib_camere_20261109, condizione 3 dello scettico)

Rende un tabellone ChArUco visto da una coppia stereo con distorsione NOTA (rational + thin-prism, valori
simili a #001: f~1150, k1~-0.37, rotazione relativa ~5 deg), lo codifica in DUE file h264 a 500 kbps con la
stessa convenzione di #001 (video_left = camera fisicamente DESTRA), lancia lo script vero e confronta con la verità:
  B) dy su punti 3D casuali a 1-5 m in tutta l'immagine (proiettati con la verità, rettificati con la stima)
  C) errore % di depth a 1-5 m per zona (Z = f·B/disparità con la stima vs Z vero)
  D) controllo negativo: viste SOLO al centro -> lo script deve dire GATE ROSSO (copertura).

Uso: python3 test_calib_charuco_dual_synth.py --work <cartella temporanea fuori da git>
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calib_charuco_dual as ccd  # noqa: E402
from stereo_common import Calib  # noqa: E402

W, H, SS = 1280, 800, 2
rng = np.random.default_rng(20261109)

# ---- verità (fisicamente SINISTRA = camera 1 della calib; DESTRA = camera 2) ----
K1 = np.array([[1153.0, 0, 646.0], [0, 1151.0, 397.0], [0, 0, 1]])
K2 = np.array([[1149.0, 0, 628.0], [0, 1148.0, 409.0], [0, 0, 1]])
# rational(8) + thin prism(4): k1 k2 p1 p2 k3 k4 k5 k6 s1 s2 s3 s4
D1 = np.array([-0.37, 0.17, 0.0004, -0.0006, -0.02, 0.0, 0.0, 0.04, 0.004, -0.001, -0.003, 0.0008])
D2 = np.array([-0.39, 0.20, -0.0003, 0.0005, -0.03, 0.0, 0.0, 0.05, -0.002, 0.0006, 0.004, -0.001])
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


def make_session(work, name, center_only, nviews, board, sx, sy, sq):
    d = os.path.join(work, name)
    os.makedirs(d, exist_ok=True)
    ppsq = 120
    tex = board.generateImage((sx * ppsq, sy * ppsq), marginSize=0, borderBits=1).astype(np.float32)
    tex = 40 + tex * (200 / 255.0)  # contrasto realistico (non 0/255)
    ppm = ppsq / sq
    rl, okl = ray_map(K1, D1)
    rr, okr = ray_map(K2, D2)
    frames = {"L": [], "R": []}
    for Rb, tb in poses(nviews, center_only, (sx * sq, sy * sq)):
        bg = rng.uniform(90, 160)
        a = render(rl, okl, tex, ppm, Rb, tb, bg)
        b = render(rr, okr, tex, ppm, R_TRUE @ Rb, R_TRUE @ tb + T_TRUE, bg)
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


def compare(cal_path):
    est = Calib.load(cal_path)
    re, rt = est.rectify(), Calib(K1, D1, K2, D2, R_TRUE, T_TRUE).rectify()
    fE, fT = re["focal_px"], rt["focal_px"]
    # B,C) punti 3D casuali visibili in entrambe a 1-5 m
    N = 40000
    uu, vv = rng.uniform(0, W, N), rng.uniform(0, H, N)
    Z = rng.uniform(1.0, 5.0, N)
    n = cv2.undistortPoints(np.stack([uu, vv], 1).reshape(-1, 1, 2), K1, D1).reshape(-1, 2)
    P = np.c_[n * Z[:, None], Z]
    pl = cv2.projectPoints(P.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K1, D1)[0].reshape(-1, 2)
    Pr = (R_TRUE @ P.T + T_TRUE).T
    pr = cv2.projectPoints(Pr.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K2, D2)[0].reshape(-1, 2)
    vis = (pr[:, 0] > 2) & (pr[:, 0] < W - 2) & (pr[:, 1] > 2) & (pr[:, 1] < H - 2) & (Pr[:, 2] > 0)
    a = cv2.undistortPoints(pl[vis].reshape(-1, 1, 2), est.K1, est.d1, R=re["R1"], P=re["P1"]).reshape(-1, 2)
    b = cv2.undistortPoints(pr[vis].reshape(-1, 1, 2), est.K2, est.d2, R=re["R2"], P=re["P2"]).reshape(-1, 2)
    dy = a[:, 1] - b[:, 1]
    disp = a[:, 0] - b[:, 0]
    Zest = fE * 0.2 / disp
    # Z vero nel frame rettificato sinistro = componente lungo l'asse ottico rettificato
    Zr = (re["R1"] @ P[vis].T).T[:, 2]
    errC = 100 * (Zest / Zr - 1)
    zB = ccd.zone_of(pl[vis])
    out = dict(zone=ccd.ZNAME, B_dy_abs_p95=[], B_dy_median=[], C_depth_pct_p95=[], C_depth_pct_median=[])
    for z in range(9):
        mb = zB == z
        out["B_dy_abs_p95"].append(round(float(np.percentile(np.abs(dy[mb]), 95)), 3))
        out["B_dy_median"].append(round(float(np.median(dy[mb])), 3))
        out["C_depth_pct_p95"].append(round(float(np.percentile(np.abs(errC[mb]), 95)), 3))
        out["C_depth_pct_median"].append(round(float(np.median(errC[mb])), 3))
    out["focal_rect_est_true"] = [fE, fT]
    out["baseline_dir_ok"] = bool(est.T[0, 0] < 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--views", type=int, default=72)
    a = ap.parse_args()
    sx, sy, sq = ccd.DEF_SX, ccd.DEF_SY, ccd.DEF_SQ
    board = ccd.make_board(ccd.DEF_DICT, sx, sy, sq, round(0.74 * sq, 5))
    res = {}
    for name, center in (("synth_9zone", False), ("synth_solo_centro", True)):
        d = make_session(a.work, name, center, a.views, board, sx, sy, sq)
        out = os.path.join(a.work, f"calib_{name}.CANDIDATO.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "calib_charuco_dual.py"), "--unit", "asmile-001",
                            "--session", d, "--square-len", str(sq), "--step", "1", "--out", out],
                           capture_output=True, text=True)
        print(f"===== {name} =====\n{r.stdout}{r.stderr}")
        if r.returncode:
            res[name] = dict(errore=r.returncode)
            continue
        rep = json.load(open(out + ".report.json"))
        res[name] = dict(gate_script=rep["gate"], gate_problemi=rep["gate_problemi"], verita=compare(out))
    v = res.get("synth_9zone", {}).get("verita")
    ok = (v is not None and res["synth_9zone"]["gate_script"] == "VERDE"
          and max(v["B_dy_abs_p95"]) < 1.0 and max(v["C_depth_pct_p95"]) <= 2.0 and v["baseline_dir_ok"]
          and res.get("synth_solo_centro", {}).get("gate_script") == "ROSSO")
    res["TEST"] = "VERDE" if ok else "ROSSO"
    res["criteri"] = ("obiettivo HANDOFF in OGNI zona 3x3 (punti 1-5 m): dy |p95| < 1 px e depth |p95| <= 2%; gate script "
                      "VERDE; baseline col segno giusto; controllo negativo solo-centro -> gate script ROSSO")
    if v is not None:
        res["margine_interno_0.5px_1pct"] = [ccd.ZNAME[z] + " NO" for z in range(9)
                                             if v["B_dy_abs_p95"][z] >= 0.5 or v["C_depth_pct_p95"][z] >= 1.0] or "tutte OK"
    p = os.path.join(a.work, "esito_test_sintetico.json")
    json.dump(res, open(p, "w"), indent=1)
    print(json.dumps(res, indent=1))
    print(f"TEST {res['TEST']} -> {p}")


if __name__ == "__main__":
    main()
