"""
seg_merge_video.py — un solo video: segmentazione SAM 3 | oggetti con distanza | lista a lato (2026-11-08).

Fonde seg_<cam>.mp4 (solo il pannello del maestro) e depth_<cam>.mp4 di seg_object_depth.py, e a destra
scrive la lista di cose viste nel frame (oggetti per distanza, prima quelli DAVANTI) + superfici in %
+ totale di quello che si è visto finora nel giro.

Uso:
  python3 training/segmentation/seg_merge_video.py asmile-loggers/_seg_sam3/<sess> [--cam left]
"""
import argparse
import csv
import os
import subprocess
from collections import defaultdict

import cv2
import numpy as np

W, H = 1280, 800
S = 0.7                                            # scala dei due pannelli video
PW = 460                                           # larghezza della lista


def put(img, txt, y, col=(230, 230, 230), sc=0.55, x=12, th=1):
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, col, th, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seg_dir")
    ap.add_argument("--cam", default="left")
    a = ap.parse_args()
    d = a.seg_dir

    objs = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(d, f"objects_depth_{a.cam}.csv"))):
        objs[int(r["frame"])].append(r)
    stuff = {}
    for r in csv.DictReader(open(os.path.join(d, f"stuff_{a.cam}.csv"))):
        stuff[int(r["frame"])] = {k[4:]: float(v) for k, v in r.items() if k.startswith("pct_")}

    cs = cv2.VideoCapture(os.path.join(d, f"seg_{a.cam}.mp4"))
    cd = cv2.VideoCapture(os.path.join(d, f"depth_{a.cam}.mp4"))
    pw, ph = int(W * S), int(H * S)
    out = os.path.join(d, f"fuso_{a.cam}.mp4")
    vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), 15, (2 * pw + PW, ph))

    cur_o, cur_s, seen, i = [], {}, defaultdict(int), 0
    while True:
        ok1, fs = cs.read()
        ok2, fd = cd.read()
        if not (ok1 and ok2):
            break
        if i in objs:
            cur_o = objs[i]
            for r in cur_o:
                seen[r["classe"]] += 1
        cur_s = stuff.get(i, cur_s)

        panel = np.full((ph, PW, 3), 28, np.uint8)
        put(panel, f"COSA VEDE  t={i / 15:5.1f}s  f={i}", 26, (255, 255, 255), 0.6, th=2)
        y = 52
        put(panel, "OGGETTI (distanza stereo)", y, (160, 200, 255), 0.55, th=2)
        y += 22
        order = sorted(cur_o, key=lambda r: (r["davanti"] != "1", float(r["Z_m"]) if r["Z_m"] else 1e9))
        for r in order[:13]:
            if r["Z_m"]:
                z = float(r["Z_m"])
                col = (80, 80, 255) if z < 4 else (0, 165, 255) if z < 8 else (90, 220, 90)
                txt = f"{r['classe']:<13s} {z:5.1f} m  X{float(r['X_m']):+.1f}"
            else:
                col, txt = (140, 140, 140), f"{r['classe']:<13s}   ?"
            if r["davanti"] == "1":
                txt += "  DAVANTI"
            put(panel, txt, y, col, 0.5, th=2 if r["davanti"] == "1" else 1)
            y += 20
        if len(order) > 13:
            put(panel, f"... altri {len(order) - 13}", y, (140, 140, 140), 0.45)
            y += 20
        if not order:
            put(panel, "nessuno", y, (140, 140, 140), 0.5)
            y += 20
        y += 10
        put(panel, "SUPERFICI (% immagine)", y, (160, 200, 255), 0.55, th=2)
        y += 22
        for k, v in sorted(cur_s.items(), key=lambda kv: -kv[1]):
            if v < 1.0:
                continue
            cv2.rectangle(panel, (150, y - 11), (150 + int(2.6 * v), y - 1), (110, 110, 110), -1)
            put(panel, f"{k:<11s} {v:4.0f}%", y, (220, 220, 220), 0.48)
            y += 19
        y = max(y + 10, ph - 22 * 6 - 10)
        put(panel, "VISTI NEL GIRO (rilevamenti)", y, (160, 200, 255), 0.55, th=2)
        y += 20
        tops = sorted(seen.items(), key=lambda kv: -kv[1])[:10]
        for j, (k, n) in enumerate(tops):
            put(panel, f"{k} {n}", y + 20 * (j // 2), (200, 200, 200), 0.45, x=12 + 225 * (j % 2))

        seg = cv2.resize(fs[:, :W], (pw, ph))      # solo il pannello del maestro SAM 3
        dep = cv2.resize(fd, (pw, ph))
        vw.write(np.hstack([seg, dep, panel]))
        i += 1
    vw.release()
    tmp = out.replace(".mp4", "_h264.mp4")
    if subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-c:v", "libx264", "-crf", "23",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]).returncode == 0:
        os.replace(tmp, out)
    print(f"{i} frame -> {out}")


if __name__ == "__main__":
    main()
