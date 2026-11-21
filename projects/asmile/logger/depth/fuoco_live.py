#!/usr/bin/env python3
"""fuoco_live.py — nitidezza dal vivo delle due camere del logger001 (Camarray SBS) per la messa a fuoco (21/11/2026).
Legge lo streaming MJPEG (stream_logger.py a risoluzione piena: W=2560 H=800) e stampa ogni secondo la nitidezza
(varianza del Laplaciano) di sinistra e destra nella stessa zona centrale, il rapporto e un consiglio,
più quanti marker del tabellone riesce a leggere per lato (per sapere dal vivo se a quella distanza la posa è buona).
Il tabellone deve stare fermo al centro, intero in tutte e due le camere: si confronta la stessa scena.
Uso: fuoco_live.py [http://100.83.200.55:8080/stream] [--roi 0.5]
"""
import sys, time, urllib.request, argparse
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("url", nargs="?", default="http://100.83.200.55:8080/stream")
ap.add_argument("--roi", type=float, default=0.5, help="lato della zona centrale (frazione della mezza immagine)")
a = ap.parse_args()


def nitidezza(img, roi):
    h, w = img.shape
    y0, y1 = int(h * (0.5 - roi / 2)), int(h * (0.5 + roi / 2))
    x0, x1 = int(w * (0.5 - roi / 2)), int(w * (0.5 + roi / 2))
    return float(cv2.Laplacian(img[y0:y1, x0:x1], cv2.CV_64F).var())


import calib_detect_sbs_deep as CD            # stesso rilevatore della calibrazione (2x + unsharp, parametri per il lato sfocato)
CD._init("DICT_5X5_1000", 11, 8, 0.050, 0.037)


def marker(img):
    """angoli del tabellone letti (come li conta la calibrazione: buona posa = almeno 12)"""
    d, _ = CD._side(img)
    return 0 if d is None else len(d["ids"])


s = urllib.request.urlopen(a.url, timeout=10)
buf, storia, t0, best = b"", [], time.time(), 0.0
while True:
    buf += s.read(65536)
    i, j = buf.find(b"\xff\xd8"), buf.find(b"\xff\xd9")
    if i < 0 or j < i:
        continue
    jpg, buf = buf[i:j + 2], buf[j + 2:]
    im = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        continue
    w = im.shape[1] // 2
    storia.append((nitidezza(im[:, :w], a.roi), nitidezza(im[:, w:], a.roi)))
    if time.time() - t0 < 1.0:
        continue
    l, r = np.median(np.array(storia), axis=0)
    ml, mr = marker(im[:, :w]), marker(im[:, w:])
    storia, t0 = [], time.time()
    best = max(best, l)
    rap = l / r if r > 0 else 0
    if rap >= 0.9:
        cons = "OK: sinistra a fuoco come destra"
    elif l >= best * 0.97:
        cons = "continua nello stesso verso"
    else:
        cons = "peggiora: torna indietro"
    print(f"{time.strftime('%H:%M:%S')}  SX {l:7.1f}   DX {r:7.1f}   SX/DX {rap:4.2f}   migliore SX {best:7.1f}   angoli letti SX {ml:2d} DX {mr:2d}   -> {cons}", flush=True)
