#!/usr/bin/env python3
"""bordi_stuff_001.py — giro 10 (12/11/2026), SOLO #001: maestro di sfondo Mask2Former Swin-L Mapillary (StuffTeacher di seg_teacher_student.py)
sui fotogrammi rettificati (camera sinistra = file *_right), 1 fotogramma ogni STEP (default 3 = 5 Hz). Salva etichette STUFF a 320x200 (nearest) in out/stuff_<sid>.npz ('f<frame>').
Uso: ~/.asmile_depth_venv/bin/python bordi_stuff_001.py SESSIONE [STEP]"""
import os, sys, time, pickle, json
import numpy as np, cv2, torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "segmentation"))
import depth_seg_001 as D
from seg_teacher_student import StuffTeacher, STUFF
sess = "session_" + sys.argv[1].replace("session_", ""); step = int(sys.argv[2]) if len(sys.argv) > 2 else 3
OUT_A = os.path.join(D.HERE, "out_20261112_v6"); OUT = os.path.join(D.HERE, "out_20261112_v10")
frames = pickle.load(open(os.path.join(OUT_A, sess + "_A", "frames.pkl"), "rb")); fl = [f["frame"] for f in frames]; want = set(fl[::step]); f0, f1 = fl[0], fl[-1]
dev = "mps" if torch.backends.mps.is_available() else "cpu"; torch.set_num_threads(3)
tt = StuffTeacher(dev); rc = D.Rect(); res = {}; t0 = time.time(); n = 0
for i, Lr in enumerate(D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264"))):
    if i > f1: break
    if i not in want: continue
    L = cv2.remap(Lr, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR); img = cv2.convertScaleAbs(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), alpha=1.15, beta=8)
    lab = tt(img); res[f"f{i}"] = cv2.resize(lab, (320, 200), interpolation=cv2.INTER_NEAREST); n += 1
    if n % 50 == 0: print(n, len(want), round(time.time() - t0, 1), "s", flush=True)
np.savez_compressed(os.path.join(OUT, f"stuff_{sess[8:]}.npz"), **res)
json.dump(dict(frames=n, secondi=round(time.time() - t0, 1), s_per_frame=round((time.time() - t0) / max(n, 1), 3), step=step, device=dev, classi=list(STUFF.keys())), open(os.path.join(OUT, f"stuff_{sess[8:]}.json"), "w"))
print("fatto", n, time.time() - t0)
