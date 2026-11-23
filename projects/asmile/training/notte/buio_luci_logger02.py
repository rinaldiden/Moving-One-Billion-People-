#!/usr/bin/env python3
"""Luci al buio su logger02: (1) macchie sature (lampioni, fari, semafori) — quante, quanto grandi, quanto strisciate;
(2) semafori trovati dal detector: ritagli a frequenza piena (16,7 fps) e serie della luminosità per lampada alto/medio/basso
(sfarfallio LED, lampeggio, quale lampada è accesa).

Uso:
  macchie: python buio_luci_logger02.py macchie <dir_logger02> <out.csv> <gruppo>:<clip>[,<clip>] ...
  semafori: python buio_luci_logger02.py semafori <dir_logger02> <det.csv> <out_dir> [conf_min=0.35]
"""
import csv, os, sys, collections
import cv2, numpy as np


def leggi(path, keep):
    cap = cv2.VideoCapture(path); i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if keep(i): yield i, cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        i += 1


def macchie(D, out, args):
    w = csv.writer(open(out, "w", newline=""))
    w.writerow(["gruppo", "clip", "frame_i", "n", "area", "w", "h", "allung", "alone200", "cx", "cy"])
    for arg in args:
        g, lst = arg.split(":", 1)
        for c in lst.split(","):
            p = f"{D}/{c}.h264"
            if not os.path.exists(p): continue
            for i, im in leggi(p, lambda i: i % 8 == 0):
                sat = (im >= 250).astype(np.uint8)
                al = (im >= 200).astype(np.uint8)
                n, lab, st, cen = cv2.connectedComponentsWithStats(sat, 8)
                nA, labA, stA, _ = cv2.connectedComponentsWithStats(al, 8)
                for k in range(1, n):
                    x, y, ww, hh, a = st[k]
                    if a < 4: continue
                    m = cv2.moments((lab[y:y + hh, x:x + ww] == k).astype(np.uint8), True)
                    mu20, mu02, mu11 = m["mu20"] / a, m["mu02"] / a, m["mu11"] / a
                    d = np.sqrt(((mu20 - mu02) / 2) ** 2 + mu11 ** 2)
                    l1, l2 = (mu20 + mu02) / 2 + d, max((mu20 + mu02) / 2 - d, 1e-3)
                    ka = labA[int(cen[k][1]), int(cen[k][0])]
                    w.writerow([g, c, i, n - 1, a, ww, hh, round(float(np.sqrt(l1 / l2)), 2),
                                int(stA[ka][4]) if ka else a, int(cen[k][0]), int(cen[k][1])])
            print(g, c, flush=True)


def semafori(D, det, out, conf_min=0.35):
    """per ogni semaforo (gruppi di detection consecutive nella stessa clip), ritaglio ogni fotogramma tra la prima e
    l'ultima detection e misuro la luminosità di 3 fasce verticali (alto/medio/basso) del box."""
    os.makedirs(out, exist_ok=True)
    R = [r for r in csv.DictReader(open(det)) if r["classe"] == "semaforo" and float(r["conf"]) >= conf_min]
    perclip = collections.defaultdict(list)
    for r in R: perclip[r["clip"]].append(r)
    serie = csv.writer(open(f"{out}/serie.csv", "w", newline=""))
    serie.writerow(["id", "gruppo", "clip", "frame_i", "x1", "y1", "x2", "y2", "alto", "medio", "basso", "max", "sat_px"])
    tid = 0
    for clip, L in perclip.items():
        L.sort(key=lambda r: int(r["frame_i"]))
        tracce, cur = [], [L[0]]
        for r in L[1:]:
            p = cur[-1]
            cx, px = (int(r["x1"]) + int(r["x2"])) / 2, (int(p["x1"]) + int(p["x2"])) / 2
            if int(r["frame_i"]) - int(p["frame_i"]) <= 12 and abs(cx - px) < 80: cur.append(r)
            else: tracce.append(cur); cur = [r]
        tracce.append(cur)
        tracce = [t for t in tracce if len(t) >= 2]
        if not tracce: continue
        rng = {}
        for t in tracce:
            tid += 1
            fs = [int(r["frame_i"]) for r in t]
            for f in range(min(fs), max(fs) + 1):
                # box interpolato dalla detection più vicina, allargato del 30%
                r = min(t, key=lambda r: abs(int(r["frame_i"]) - f))
                x1, y1, x2, y2 = map(int, (r["x1"], r["y1"], r["x2"], r["y2"]))
                rng.setdefault(f, []).append((tid, t[0]["gruppo"], x1, y1, x2, y2))
        for i, im in leggi(f"{D}/{clip}.h264", lambda i: i in rng):
            for (k, g, x1, y1, x2, y2) in rng[i]:
                h = y2 - y1; mw = int((x2 - x1) * 0.3); mh = int(h * 0.3)
                box = im[y1:y2, x1:x2].astype(np.float32)
                if box.size == 0: continue
                b3 = [float(box[j * h // 3:(j + 1) * h // 3].mean()) if h >= 3 else float("nan") for j in range(3)]
                serie.writerow([k, g, clip, i, x1, y1, x2, y2, *[round(v, 1) for v in b3], int(box.max()), int((box >= 250).sum())])
                crop = im[max(0, y1 - mh):y2 + mh, max(0, x1 - mw):x2 + mw]
                if crop.size: cv2.imwrite(f"{out}/t{k:03d}_{g}_{clip[14:]}_{i:04d}.png", crop)
        print(clip, len(tracce), "tracce", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "macchie": macchie(sys.argv[2], sys.argv[3], sys.argv[4:])
    else: semafori(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]) if len(sys.argv) > 5 else 0.35)
