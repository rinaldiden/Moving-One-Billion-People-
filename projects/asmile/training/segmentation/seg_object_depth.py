"""
seg_object_depth.py — distanza stereo degli oggetti segmentati da SAM 3 (2026-11-08).

Prende objects_<cam>.csv di seg_teacher_student.py e, per ogni box, misura la disparità L↔R
con lo STESSO metodo dei punti col metro (calib_tape_joint: niente rettifica, d = fB/Z + d0):
  - scarto verticale L↔R stimato PER FRAME con SIFT (in movimento varia 5-12 px: sync software),
  - box (ristretto al centro) cercato nella camera destra con NCC lungo la riga, subpixel,
  - Z = fB / (d - d0), con fB e d0 dalla calib JSON (tape_points).
"Davanti alla bici": senza sterzo/IMU sul logger si assume la marcia DRITTA → corridoio
|X| <= --corridor m attorno all'asse della camera (X = (u - cx) * Z / f).
Controllo col terreno (oggetti appoggiati a terra): Z_terra = f * h_cam / (y_base - orizzonte); se lo
stereo dista più di x2.5 dal terreno la misura si scarta (match su un oggetto gemello, es. dissuasori in fila).

Uscite in <seg_dir>/: objects_depth_<cam>.csv, depth_<cam>.mp4, summary_depth_<cam>.json

Uso:
  ~/.asmile_depth_venv/bin/python training/segmentation/seg_object_depth.py \
      asmile-loggers/_work/asmile-logger/<sess> asmile-loggers/_seg_sam3/<sess> \
      --calib logger/depth/calib_asmile-logger_metro.json
"""
import argparse
import csv
import json
import os
import subprocess
from collections import defaultdict

import cv2
import numpy as np

W, H = 1280, 800
A_TERRA = {"person", "child", "car", "van", "truck", "bus", "tractor", "bollard", "trash can", "bench",
           "traffic cone", "barrier", "stroller", "bicycle", "motorcycle", "dog", "cat", "wheelchair", "pole"}


def ground_ok(Z, y2, f, horizon, cam_h, tol=2.5):
    """Lo stereo è coerente col punto dove il box tocca la strada? (base tagliata dal bordo: non si sa)"""
    if y2 >= H - 5:
        return True
    den = y2 - horizon
    if den <= 15:                                       # base sull'orizzonte: oggetto lontano
        return Z > 8.0
    zg = f * cam_h / den
    return zg / tol <= Z <= zg * tol


def frames(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE)
    while True:
        buf = p.stdout.read(W * H)
        if len(buf) < W * H:
            return
        yield np.frombuffer(buf, np.uint8).reshape(H, W)


def frame_dy(sift, L, R, prev):
    """Scarto verticale L-R del frame (mediana sui match SIFT); se pochi match tiene il precedente."""
    k1, d1 = sift.detectAndCompute(L, None)
    k2, d2 = sift.detectAndCompute(R, None)
    if d1 is None or d2 is None or len(k1) < 10 or len(k2) < 10:
        return prev
    mt = [a for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2) if a.distance < 0.7 * b.distance]
    if len(mt) < 15:
        return prev
    p1 = np.float32([k1[m.queryIdx].pt for m in mt])
    p2 = np.float32([k2[m.trainIdx].pt for m in mt])
    ok = (p1[:, 0] - p2[:, 0] > 20) & (p1[:, 0] - p2[:, 0] < 300)
    return float(np.median(p1[ok, 1] - p2[ok, 1])) if ok.sum() >= 10 else prev


def box_disparity(L, R, box, dy, dmin, dmax, shrink=0.2):
    """Disparità del box: NCC del centro del box nella camera destra lungo la riga (±3 px in y)."""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    x1, x2 = int(x1 + shrink * bw), int(x2 - shrink * bw)
    y1, y2 = int(y1 + shrink * bh), int(y2 - shrink * bh)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None, 0.0
    tpl = L[y1:y2, x1:x2]
    if tpl.std() < 4:                                   # senza tessitura: niente misura
        return None, 0.0
    ry1, ry2 = int(round(y1 - dy)) - 3, int(round(y2 - dy)) + 3
    rx1, rx2 = x1 - int(dmax), x2 - int(dmin)
    if ry1 < 0 or ry2 > H or rx2 > W or rx2 - rx1 <= x2 - x1:
        return None, 0.0
    rx1 = max(0, rx1)
    if rx2 - rx1 <= x2 - x1:                            # box al bordo sinistro: niente spazio di ricerca
        return None, 0.0
    res = cv2.matchTemplate(R[ry1:ry2, rx1:rx2], tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (mx, my) = cv2.minMaxLoc(res)
    if mx <= 1 or mx >= res.shape[1] - 2:               # massimo sul limite della ricerca: match spurio
        return None, 0.0
    sup = res.copy()                                    # unicità: il 2° picco (fuori ±4 px) deve stare sotto
    sup[:, max(0, mx - 4):mx + 5] = -1
    if sup.max() > score - 0.05:
        return None, 0.0
    xr, yr = rx1 + mx, ry1 + my                         # andata e ritorno: dal match in R si deve tornare al box
    lx1, lx2 = xr + int(dmin), min(W, xr + (x2 - x1) + int(dmax))
    ly1, ly2 = int(round(yr + dy)) - 3, int(round(yr + dy)) + (y2 - y1) + 3
    if ly1 < 0 or ly2 > H or lx2 - lx1 <= x2 - x1:
        return None, 0.0
    back = cv2.matchTemplate(L[ly1:ly2, lx1:lx2], R[yr:yr + (y2 - y1), xr:xr + (x2 - x1)], cv2.TM_CCOEFF_NORMED)
    if abs(lx1 + cv2.minMaxLoc(back)[3][0] - x1) > 2:
        return None, 0.0
    sub = 0.0
    if 0 < mx < res.shape[1] - 1:                       # parabola subpixel
        a, b, c = res[my, mx - 1], res[my, mx], res[my, mx + 1]
        den = a - 2 * b + c
        sub = 0.5 * (a - c) / den if den != 0 else 0.0
    return x1 - (rx1 + mx + sub), float(score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", help="cartella con <sess>_left.h264 e <sess>_right.h264")
    ap.add_argument("seg_dir", help="cartella uscite di seg_teacher_student.py")
    ap.add_argument("--calib", required=True)
    ap.add_argument("--cam", default="left")
    ap.add_argument("--corridor", type=float, default=1.0, help="mezza larghezza corridoio davanti (m)")
    ap.add_argument("--zmax", type=float, default=25.0)
    ap.add_argument("--min-score", type=float, default=0.6)
    ap.add_argument("--cam-h", type=float, default=0.71, help="altezza camera da terra (m), logger 0.71")
    ap.add_argument("--horizon", type=float, default=330.0,
                    help="riga dell'orizzonte (px); 330 = mediana sul rientro logger 2026-11-08 (p10-p90 260-363)")
    a = ap.parse_args()

    cal = json.load(open(a.calib))
    d0 = float(cal["d0_px"])
    fB = float(cal["focal_fit_px"]) * cal["baseline_mm"] / 1000.0
    f, cx = float(cal["K_left"][0][0]), float(cal["K_left"][0][2])
    dmin, dmax = d0 + fB / a.zmax, d0 + fB / 0.7

    boxes = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(a.seg_dir, f"objects_{a.cam}.csv"))):
        boxes[int(r["frame"])].append(r)

    sess = os.path.basename(a.session.rstrip("/"))
    vL = os.path.join(a.session, f"{sess}_left.h264")
    vR = os.path.join(a.session, f"{sess}_right.h264")
    out_csv = os.path.join(a.seg_dir, f"objects_depth_{a.cam}.csv")
    fo = csv.writer(open(out_csv, "w", newline=""))
    fo.writerow(["frame", "t_ms", "track_id", "classe", "conf", "x1", "y1", "x2", "y2",
                 "disp_px", "ncc", "dy_px", "Z_m", "X_m", "davanti"])
    vw = cv2.VideoWriter(os.path.join(a.seg_dir, f"depth_{a.cam}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 15, (W, H))

    sift = cv2.SIFT_create(3000)
    dy, last, n_ok, n_tot = 0.0, [], 0, 0
    nearest = defaultdict(lambda: 1e9)                  # per track: distanza minima davanti
    for i, (L, R) in enumerate(zip(frames(vL), frames(vR))):
        if i in boxes:
            dy = frame_dy(sift, L, R, dy)
            last = []
            for r in boxes[i]:
                b = [int(r[k]) for k in ("x1", "y1", "x2", "y2")]
                n_tot += 1
                d, sc = box_disparity(L, R, b, dy, dmin, dmax)
                Z = X = None
                if d is not None and sc >= a.min_score and d - d0 > 0 and (
                        r["classe"] not in A_TERRA or ground_ok(fB / (float(d) - d0), b[3], f, a.horizon, a.cam_h)):
                    d = float(d)
                    Z = fB / (d - d0)
                    X = ((b[0] + b[2]) / 2 - cx) * Z / f
                    n_ok += 1
                front = Z is not None and abs(X) <= a.corridor
                if front:
                    key = (r["classe"], r["track_id"] or f"f{i}")
                    nearest[key] = min(nearest[key], Z)
                fo.writerow([i, r["t_ms"], r["track_id"], r["classe"], r["conf"], *b,
                             None if d is None else round(d, 2), round(sc, 3), round(dy, 2),
                             None if Z is None else round(Z, 2), None if X is None else round(X, 2), int(front)])
                last.append((b, r["classe"], Z, front))
        img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
        for z in (3, 8):                                # bordi del corridoio a 3 e 8 m
            for s in (-1, 1):
                u = int(cx + s * a.corridor * f / z)
                cv2.line(img, (u, 0), (u, H), (80, 80, 80), 1)
        for b, cls, Z, front in last:
            col = (90, 90, 90) if Z is None else (0, 0, 255) if Z < 4 else (0, 165, 255) if Z < 8 else (0, 220, 0)
            cv2.rectangle(img, tuple(b[:2]), tuple(b[2:]), col, 3 if front else 1)
            lab = f"{cls} {'?' if Z is None else f'{Z:.1f}m'}{' DAVANTI' if front else ''}"
            cv2.putText(img, lab, (b[0], max(18, b[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(img, lab, (b[0], max(18, b[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        cv2.putText(img, f"f={i}  dy={dy:+.1f}px  stereo d={fB:.1f}/Z+{d0:.1f}", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        vw.write(img)
    vw.release()

    src = os.path.join(a.seg_dir, f"depth_{a.cam}.mp4")
    h264 = src.replace(".mp4", "_h264.mp4")
    if subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "libx264", "-crf", "23",
                       "-pix_fmt", "yuv420p", h264]).returncode == 0:
        os.replace(h264, src)
    summary = {"calib": a.calib, "fB": fB, "d0_px": d0, "corridor_m": a.corridor,
               "box_misurati": n_ok, "box_totali": n_tot,
               "davanti_piu_vicini": sorted(([c, t, round(z, 2)] for (c, t), z in nearest.items()),
                                            key=lambda x: x[2])[:40]}
    json.dump(summary, open(os.path.join(a.seg_dir, f"summary_depth_{a.cam}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "davanti_piu_vicini"}))
    for c, t, z in summary["davanti_piu_vicini"][:15]:
        print(f"  {c:12s} track {t:>6s}  min {z:5.2f} m")


if __name__ == "__main__":
    main()
