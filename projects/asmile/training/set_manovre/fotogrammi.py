#!/usr/bin/env python3
"""fotogrammi.py — estrae fotogrammi scelti da un video h264 grezzo (decodifica sequenziale UNA volta) e compone strisce.
Usato per: lettura visiva delle frenate, fotogrammi dei casi dubbi, ritagli del registro cose nuove.
Funzioni:
  grab(video, indici, w=None, h=None, meta=None) -> {indice: img BGR}  (meta='sx' tiene la meta' sinistra: logger side-by-side)
  striscia(imgs, etichette, larg=384) -> img orizzontale con didascalie
"""
import subprocess
import numpy as np, cv2


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip().split(",")
    return int(out[0]), int(out[1])


def grab(video, indici, meta=None):
    want = sorted(set(int(i) for i in indici if i >= 0))
    if not want: return {}
    w, h = probe(video)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", video, "-fps_mode", "passthrough", "-f", "rawvideo",
                          "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    out, i, k = {}, 0, 0
    while k < len(want):
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3: break
        if i == want[k]:
            img = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
            if meta == "sx": img = np.ascontiguousarray(img[:, : w // 2])
            out[i] = img; k += 1
        i += 1
    p.kill()
    return out


def striscia(imgs, etichette, larg=384):
    tiles = []
    for im, et in zip(imgs, etichette):
        if im is None:
            t = np.zeros((int(larg * 0.625), larg, 3), np.uint8)
        else:
            t = cv2.resize(im, (larg, int(larg * im.shape[0] / im.shape[1])))
        cv2.putText(t, et, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
        cv2.putText(t, et, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        tiles.append(t)
    hh = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, hh - t.shape[0], 0, 2, cv2.BORDER_CONSTANT) for t in tiles]
    return np.hstack(tiles)
