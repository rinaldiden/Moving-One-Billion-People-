#!/usr/bin/env python3
"""video_shift_20261113.py — spostamento verticale/orizzontale globale tra frame consecutivi (phase correlation, meta' alta
dell'immagine = scena lontana, 320x200) per capire il SEGNO del beccheggio. Uso: video_shift_20261113.py SESSIONE OUT.csv"""
import sys, cv2, numpy as np, pandas as pd
cv2.setNumThreads(1)
S = sys.argv[1]; base = 'asmile-loggers/asmile-001/'
fr = pd.read_csv(f'{base}session_{S}/frames_left.csv')
cap = cv2.VideoCapture(f'{base}session_{S}_left.h264')
prev = None; rows = []; k = 0
win = cv2.createHanningWindow((320, 100), cv2.CV_32F)
while True:
    ok, f = cap.read()
    if not ok: break
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f.ndim == 3 else f
    g = cv2.resize(g, (320, 200), interpolation=cv2.INTER_AREA).astype(np.float32)[10:110]   # fascia alta (orizzonte/scena lontana)
    if prev is not None:
        (dx, dy), r = cv2.phaseCorrelate(prev, g, win)
        rows.append((k, dx, dy, r))
    else:
        rows.append((k, 0, 0, 0))
    prev = g; k += 1
df = pd.DataFrame(rows, columns=['frame', 'dx', 'dy', 'resp'])
df['t_ms'] = fr.t_ms.values[:len(df)]
df.to_csv(sys.argv[2], index=False); print(S, len(df), len(fr))
