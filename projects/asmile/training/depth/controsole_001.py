#!/usr/bin/env python3
"""controsole_001.py — misura di sbiancamento per fotogramma (1 Hz) sui giri di #001: media luma, % pixel saturi (>=250) e % pixel quasi neri (<=8) sul terzo alto e sull'intera
immagine (camera sinistra fisica = file *_right, 1280x800 non rettificata). Scrive controsole_<sid>.csv in out_20261113_giri. Uso: controsole_001.py SESSIONE"""
import os, sys, subprocess, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sess = "session_" + sys.argv[1].replace("session_", "")
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-001")
t_ms = [int(r["t_ms"]) for r in csv.DictReader(open(os.path.join(LOGS, sess, "frames_right.csv")))]
p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", os.path.join(LOGS, sess + "_right.h264"), "-fps_mode", "passthrough", "-vf", "select='not(mod(n\\,15))',scale=320:200", "-vsync", "0",
                      "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
rows = []; n = 0
while True:
    b = p.stdout.read(320 * 200)
    if len(b) < 320 * 200: break
    g = np.frombuffer(b, np.uint8).reshape(200, 320); fr = n * 15
    rows.append(dict(frame=fr, t_ms=t_ms[min(fr, len(t_ms) - 1)], luma=round(float(g.mean()), 1), sat_pct=round(100 * float((g >= 250).mean()), 2), sat_alto_pct=round(100 * float((g[:70] >= 250).mean()), 2),
                     buio_pct=round(100 * float((g <= 8).mean()), 2), std=round(float(g.std()), 1)))
    n += 1
out = os.path.join(HERE, "out_20261113_giri", f"controsole_{sess[8:]}.csv")
w = csv.DictWriter(open(out, "w"), fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows); print(out, n)
