#!/usr/bin/env python3
"""Detector COCO pronto (YOLOv8m-seg, MPS) su clip di logger02: giorno vs crepuscolo vs buio.

Uso: ~/.asmile_depth_venv/bin/python buio_detect_logger02.py <dir_logger02> <out.csv> <pesi.pt> <gruppo>:<clip_prefix>[,<clip_prefix>...] ...
  es. giorno:clip_20261123_134617_A_00010,clip_20261123_134617_A_00011 buio:clip_20261123_175114_A_00010
Un fotogramma ogni PASSO. Scrive una riga per detection (classi utili alla guida + semafori/stop) e una riga
'__frame__' per fotogramma (luma) così si contano anche i fotogrammi vuoti.
"""
import csv, sys, os
import cv2, numpy as np
from ultralytics import YOLO

D, OUT, PESI = sys.argv[1], sys.argv[2], sys.argv[3]
PASSO = 4
CLASSI = {0: "persona", 1: "bici", 2: "auto", 3: "moto", 5: "bus", 7: "camion", 9: "semaforo", 11: "stop"}

m = YOLO(PESI)
w = csv.writer(open(OUT, "w", newline=""))
w.writerow(["gruppo", "clip", "frame_i", "classe", "conf", "x1", "y1", "x2", "y2", "luma"])
for arg in sys.argv[4:]:
    gruppo, clips = arg.split(":", 1)
    for c in clips.split(","):
        path = f"{D}/{c}.h264"
        if not os.path.exists(path):
            print("manca", path); continue
        cap = cv2.VideoCapture(path); i = 0; batch = []
        def flush():
            if not batch: return
            res = m.predict([b[1] for b in batch], conf=0.25, device="mps", verbose=False, imgsz=1280, classes=list(CLASSI))
            for (fi, img), r in zip(batch, res):
                w.writerow([gruppo, c, fi, "__frame__", "", "", "", "", "", round(float(img.mean()), 1)])
                for b in r.boxes:
                    k = int(b.cls); x1, y1, x2, y2 = [round(float(v)) for v in b.xyxy[0]]
                    w.writerow([gruppo, c, fi, CLASSI[k], round(float(b.conf), 3), x1, y1, x2, y2, ""])
            batch.clear()
        while True:
            ok, f = cap.read()
            if not ok: break
            if i % PASSO == 0:
                batch.append((i, f))
                if len(batch) == 16: flush()
            i += 1
        flush()
        print(gruppo, c, i, flush=True)
