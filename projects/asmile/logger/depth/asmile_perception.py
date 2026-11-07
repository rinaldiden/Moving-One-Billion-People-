#!/usr/bin/env python3
"""
asmile_perception.py — schema UNICO di percezione per TUTTI i video della flotta
(bici asmile #001… e logger Camarray). Deciso con Daniele 2026-11-07.

Tre livelli, fusi frame per frame:
  1. SCENA (semantica)  Mask2Former Mapillary Vistas: strada, marciapiede, CORDOLO, scivolo,
                        strisce, segnaletica orizzontale (linea di stop inclusa), tombino, buca,
                        pista ciclabile, pali, cartelli… + "Ego Vehicle" (pezzi della bici
                        davanti alle lenti) escluso da depth e scala.
  2. OGGETTI            YOLO26-seg + tracking (id stabile) → distanza filtrata nel tempo.
  3. DEPTH + GEOMETRIA  YOLO26-depth DENSA; scala metrica dallo stereo (calib della bici) come
                        MEDIANA su finestra lunga, o fissa (scale_fixed nella calib, dal metro).
                        Piano strada stimato (RANSAC sui pixel "Road") → altezza di ogni pixel
                        sul piano → gradini/cordoli/buche misurati in cm ("cambio di piano").

Input:  --left L.h264 --right R.h264  (camere separate, #001)  |  --video sbs.h264 (logger)
Uscite in --out: frame_XXXXX.jpg (scena+oggetti | depth+cambi di piano), mosaic.jpg,
                 objects.csv, scene.csv, preview.mp4 (H.264, frame consecutivi tracciati).
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
from collections import deque

import cv2
import numpy as np

from stereo_common import Calib, split_sbs, depth_from_disparity
from depth import disparity_sgbm

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
SEM_MODEL = "facebook/mask2former-swin-large-mapillary-vistas-semantic"
CLASSI = {0: "persona", 1: "bici", 2: "auto", 3: "moto", 5: "bus", 7: "camion",
          9: "semaforo", 11: "stop", 15: "gatto", 16: "cane"}
# classi Vistas da mostrare: nome Vistas -> (etichetta, colore BGR)
SCENA = {
    "Road": ("strada", (128, 64, 128)), "Sidewalk": ("marciapiede", (232, 35, 244)),
    "Curb": ("cordolo", (0, 220, 255)), "Curb Cut": ("scivolo", (0, 255, 160)),
    "Crosswalk - Plain": ("attravers.", (255, 255, 255)),
    "Lane Marking - Crosswalk": ("strisce", (255, 255, 255)),
    "Lane Marking - General": ("segnaletica", (0, 255, 255)),
    "Manhole": ("tombino", (60, 60, 200)), "Pothole": ("buca", (0, 0, 255)),
    "Bike Lane": ("ciclabile", (0, 128, 0)), "Service Lane": ("corsia serv.", (100, 80, 128)),
    "Pedestrian Area": ("area pedonale", (180, 120, 230)), "Parking": ("parcheggio", (160, 170, 250)),
    "Terrain": ("terreno", (35, 142, 107)), "Vegetation": ("vegetazione", (35, 142, 60)),
    "Pole": ("palo", (153, 153, 153)), "Utility Pole": ("palo", (153, 153, 153)),
    "Traffic Sign (Front)": ("cartello", (0, 220, 220)), "Traffic Light": ("semaforo", (30, 170, 250)),
    "Wall": ("muro", (156, 102, 102)), "Fence": ("recinzione", (153, 153, 190)),
    "Building": ("edificio", (70, 70, 70)), "Sky": ("cielo", (180, 130, 70)),
    "Ego Vehicle": ("bici (ego)", (40, 40, 40)),
}
DMAX = 15.0
STEP_CM = 6.0                     # cambio di piano segnalato oltre questa altezza


class Source:
    """Legge coppie (left, right) grezze in grigio, qualunque sia il formato."""

    def __init__(self, a, order, flip):
        self.order, self.flip = order, flip
        files = [a.video] if a.video else [a.left, a.right]
        self.caps = [cv2.VideoCapture(self._indexed(f, a.out)) for f in files]
        self.n = min(int(c.get(cv2.CAP_PROP_FRAME_COUNT)) for c in self.caps)
        self.fps = 15.0

    @staticmethod
    def _indexed(path, out):
        """L'.h264 grezzo di rpicam non ha indice né conteggio frame → niente seek.
        Rimpacchetto in mp4 (copia del flusso, 15 fps) una volta sola."""
        if not path.endswith(".h264"):
            return path
        mp4 = os.path.join(out, os.path.basename(path)[:-5] + ".mp4")
        if not os.path.exists(mp4):
            ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
            subprocess.run([ff, "-loglevel", "error", "-y", "-r", "15", "-i", path,
                            "-c", "copy", mp4])
        return mp4

    def read(self, idx=None):
        frames = []
        for c in self.caps:
            if idx is not None:
                c.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, f = c.read()
            if not ok:
                return None
            frames.append(f)
        if len(frames) == 1:
            return split_sbs(frames[0], order=self.order, flip180=self.flip)
        a, b = (cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames)
        if self.flip:
            a, b = cv2.rotate(a, cv2.ROTATE_180), cv2.rotate(b, cv2.ROTATE_180)
        return (b, a) if self.order == "RL" else (a, b)   # RL: il file "left" è la cam destra


def ensure_model(name):
    p = os.path.join(MODELS, name)
    if not os.path.exists(p):
        os.makedirs(MODELS, exist_ok=True)
        from ultralytics import YOLO
        YOLO(name)                                        # scarica nella cwd
        shutil.move(name, p)
    return p


class Semantic:
    """Mask2Former Mapillary Vistas (Mac, MPS). Lento (~1.7s/frame): è il teacher offline."""

    def __init__(self):
        import torch
        from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation
        self.torch = torch
        self.dev = "mps" if torch.backends.mps.is_available() else "cpu"
        self.proc = AutoImageProcessor.from_pretrained(SEM_MODEL)
        self.model = Mask2FormerForUniversalSegmentation.from_pretrained(SEM_MODEL).to(self.dev).eval()
        self.id = {v: int(k) for k, v in self.model.config.id2label.items()}

    def __call__(self, bgr):
        from PIL import Image
        img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        x = {k: v.to(self.dev) for k, v in self.proc(images=img, return_tensors="pt").items()}
        with self.torch.no_grad():
            out = self.model(**x)
        return self.proc.post_process_semantic_segmentation(
            out, target_sizes=[bgr.shape[:2]])[0].cpu().numpy()

    def mask(self, seg, name):
        return seg == self.id[name] if name in self.id else np.zeros(seg.shape, bool)


def ground_heights(depth, road, f, cx, cy, step=4):
    """Piano strada (RANSAC sui pixel Road) → altezza (m) di ogni pixel sul piano, + altezza camera."""
    h, w = depth.shape
    vv, uu = np.mgrid[0:h:step, 0:w:step]
    Z = depth[::step, ::step]
    X, Y = (uu - cx) * Z / f, (vv - cy) * Z / f
    P = np.stack([X, Y, Z], -1)
    sel = road[::step, ::step] & (Z > 0.8) & (Z < 15)
    pts = P[sel]
    if len(pts) < 300:
        return None, None
    rng = np.random.default_rng(0)
    best, best_n = None, 0
    for _ in range(150):
        s = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(s[1] - s[0], s[2] - s[0])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        if abs(n[1]) < 0.8:                               # il piano strada è ~orizzontale (asse Y camera)
            continue
        d = -n @ s[0]
        k = (np.abs(pts @ n + d) < 0.04).sum()
        if k > best_n:
            best, best_n = (n, d), k
    if best is None:
        return None, None
    n, d = best
    if n[1] > 0:                                          # normale verso l'alto (Y camera punta in basso)
        n, d = -n, -d
    Zf = depth
    Xf = (np.arange(w)[None, :] - cx) * Zf / f
    Yf = (np.arange(h)[:, None] - cy) * Zf / f
    H = Xf * n[0] + Yf * n[1] + Zf * n[2] + d             # >0 sopra il piano strada
    return H, abs(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", help="side-by-side (logger)")
    ap.add_argument("--left"); ap.add_argument("--right")
    ap.add_argument("--calib", help="calib JSON della bici (senza: scala non ancorata)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--video-out", type=float, default=40, help="secondi di preview (0=no)")
    ap.add_argument("--video-start", type=float, default=None, help="default: metà clip")
    ap.add_argument("--depth-model", default="yolo26m-depth.pt")
    ap.add_argument("--seg-model", default="yolo26m-seg.pt")
    ap.add_argument("--no-semantic", action="store_true", help="salta Mask2Former (veloce)")
    a = ap.parse_args()
    assert a.video or (a.left and a.right), "serve --video oppure --left/--right"
    os.makedirs(a.out, exist_ok=True)

    meta = json.load(open(a.calib)) if a.calib else {}
    order = meta.get("order", "LR")
    flip = meta.get("flip180", bool(a.video))             # Camarray capovolta di default
    d0 = float(meta.get("d0_px", 0.0))
    scale_fixed = meta.get("scale_fixed")                 # dal fit col metro: scala costante per camera
    rect = Calib.load(a.calib).rectify() if a.calib else None
    if rect is not None:
        f, cx, cy = rect["P1"][0, 0], rect["P1"][0, 2], rect["P1"][1, 2]
    else:
        f, cx, cy = 930.0, 640.0, 400.0

    from ultralytics import YOLO
    dmodel = YOLO(ensure_model(a.depth_model))
    smodel = YOLO(ensure_model(a.seg_model))
    sem = None if a.no_semantic else Semantic()
    src = Source(a, order, flip)
    st = {"scales": deque(maxlen=40), "dist": {}}

    def scale_of(dense, L, R, valid):
        if scale_fixed:
            return float(scale_fixed), "scala fissa (metro)"
        if rect is None:
            return 1.0, "scala modello (non ancorata)"
        if d0:
            R = cv2.warpAffine(R, np.float32([[1, 0, d0], [0, 1, 0]]), (R.shape[1], R.shape[0]))
        f_st = float(meta.get("focal_fit_px", rect["focal_px"]))   # dal metro, se c'è
        sg = depth_from_disparity(disparity_sgbm(L, R, 256, wls=False), f_st, rect["baseline_m"])
        ok = valid & (sg > 0.9) & (sg < 25.0) & (dense > 0.5)   # 256 px di disparità (dopo -d0): ~1 m
        if ok.sum() > 2000:
            st["scales"].append(float(np.median(sg[ok] / dense[ok])))
        if not st["scales"]:
            return 1.0, "scala modello (in attesa stereo)"
        s = float(np.median(st["scales"]))                 # mediana su finestra lunga: niente salti
        return s, f"scala stereo x{s:.2f} (mediana {len(st['scales'])})"

    def process(L, R, t, track):
        if rect is not None:
            L = cv2.remap(L, rect["m1x"], rect["m1y"], cv2.INTER_LINEAR)
            R = cv2.remap(R, rect["m2x"], rect["m2y"], cv2.INTER_LINEAR)
        img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
        seg = sem(img) if sem else None
        ego = sem.mask(seg, "Ego Vehicle") if sem else np.zeros(L.shape, bool)
        sky = sem.mask(seg, "Sky") if sem else np.zeros(L.shape, bool)
        dense = dmodel(img, verbose=False)[0].depth.data.cpu().numpy().astype(np.float32)
        dense = cv2.resize(dense, (img.shape[1], img.shape[0]))
        s, tag = scale_of(dense, L, R, ~ego & ~sky)
        dense *= s
        dense[ego] = 0                                     # pezzi di bici davanti alle lenti: niente depth

        # --- pannello SCENA: semantica + oggetti ---
        vis = img.copy()
        scene_rows = []
        if seg is not None:
            over = vis.copy()
            for vname, (lab, col) in SCENA.items():
                m = sem.mask(seg, vname)
                if m.any():
                    over[m] = col
            vis = cv2.addWeighted(vis, 0.45, over, 0.55, 0)
        # geometria: piano strada → cambi di piano
        H = cam_h = None
        if seg is not None:
            H, cam_h = ground_heights(dense, sem.mask(seg, "Road"), f, cx, cy)
        if H is not None:
            for vname, lab in [("Curb", "cordolo"), ("Sidewalk", "marciapiede"), ("Curb Cut", "scivolo"),
                               ("Pothole", "buca"), ("Manhole", "tombino")]:
                m = sem.mask(seg, vname) & (dense > 0.5) & (dense < 15)
                if m.sum() < 150:
                    continue
                hcm = 100 * float(np.median(H[m]))
                dist = float(np.percentile(dense[m], 10))     # parte più vicina
                scene_rows.append((round(t, 2), lab, round(hcm, 1), round(dist, 2)))
                ys, xs = np.nonzero(m)
                k = np.argmax(ys)                             # punto più basso (più vicino) della zona
                txt = f"{lab} {hcm:+.0f}cm? {dist:.1f}m"   # cm PROVVISORI finché la scala non è dal metro
                cv2.putText(vis, txt, (int(xs[k]) - 40, int(ys[k]) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
                cv2.putText(vis, txt, (int(xs[k]) - 40, int(ys[k]) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        # oggetti (tracciati → distanza filtrata)
        obj_rows = []
        res = (smodel.track(img, conf=0.35, persist=True, verbose=False) if track
               else smodel(img, conf=0.35, verbose=False))[0]
        if res.masks is not None:
            masks = res.masks.data.cpu().numpy()
            for k, b in enumerate(res.boxes):
                c = int(b.cls[0])
                name = CLASSI.get(c, res.names[c])
                mk = cv2.resize(masks[k], (img.shape[1], img.shape[0])) > 0.5
                mk = cv2.erode(mk.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
                v = dense[mk & (dense > 0)]
                if v.size < 30:
                    continue
                d = float(np.median(v))
                tid = int(b.id[0]) if track and b.id is not None else None
                if tid is not None:                         # filtro temporale per oggetto
                    prev = st["dist"].get(tid)
                    d = d if prev is None else 0.6 * prev + 0.4 * d
                    st["dist"][tid] = d
                colr = (0, 0, 255) if d < 4 else (0, 165, 255) if d < 8 else (0, 255, 0)
                cnts, _ = cv2.findContours(mk.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(vis, cnts, -1, colr, 3)
                x1, y1 = int(b.xyxy[0][0]), int(b.xyxy[0][1])
                lab = f"{name}{'#' + str(tid) if tid is not None else ''} {d:.1f}m"
                cv2.putText(vis, lab, (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 5)
                cv2.putText(vis, lab, (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colr, 2)
                obj_rows.append((round(t, 2), name, tid, round(float(b.conf[0]), 2), round(d, 2)))
        cv2.putText(vis, f"t={t:.1f}s  scena+oggetti", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # --- pannello DEPTH densa + cambi di piano ---
        col = cv2.applyColorMap((255 * (1 - np.clip(dense, 0, DMAX) / DMAX)).astype(np.uint8), cv2.COLORMAP_PLASMA)
        col[dense <= 0] = (20, 20, 20)
        dvis = cv2.addWeighted(img, 0.35, col, 0.65, 0)
        if H is not None:
            step = (np.abs(H) * 100 > STEP_CM) & (dense > 0.5) & (dense < 12) & ~ego & ~sky
            if seg is not None:                             # solo dove si può camminare/guidare
                walk = np.zeros_like(step)
                for vname in ("Road", "Sidewalk", "Curb", "Curb Cut", "Crosswalk - Plain", "Manhole",
                              "Pothole", "Bike Lane", "Lane Marking - General", "Lane Marking - Crosswalk"):
                    walk |= sem.mask(seg, vname)
                step &= cv2.dilate(walk.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
            edges = cv2.Canny((step * 255).astype(np.uint8), 50, 150)
            dvis[cv2.dilate(edges, np.ones((3, 3), np.uint8)) > 0] = (0, 255, 255)
            cv2.putText(dvis, f"piano strada: camera a {cam_h:.2f}m | giallo = cambio di piano >{STEP_CM:.0f}cm",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(dvis, f"depth densa 0-{DMAX:.0f}m  {tag}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return np.hstack([vis, dvis]), obj_rows, scene_rows

    allo, alls, thumbs = [], [], []
    for idx in np.linspace(45, src.n - 15, a.samples).astype(int):
        pair = src.read(idx)
        if pair is None:
            continue
        panel, o, s = process(*pair, idx / src.fps, track=False)
        cv2.imwrite(f"{a.out}/frame_{idx:05d}.jpg", panel, [cv2.IMWRITE_JPEG_QUALITY, 88])
        thumbs.append(cv2.resize(panel, (1280, 400)))
        allo += o; alls += s
        print(f"  t={idx / src.fps:6.1f}s  oggetti={[(r[1], r[4]) for r in o]}  scena={[(r[1], r[2]) for r in s]}", flush=True)

    if thumbs:
        while len(thumbs) % 2:
            thumbs.append(np.zeros_like(thumbs[0]))
        mosaic = np.vstack([np.hstack(thumbs[i:i + 2]) for i in range(0, len(thumbs), 2)])
        cv2.imwrite(f"{a.out}/mosaic.jpg", mosaic, [cv2.IMWRITE_JPEG_QUALITY, 80])
    with open(f"{a.out}/objects.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["t_s", "classe", "track_id", "conf", "distanza_m"]); w.writerows(allo)
    with open(f"{a.out}/scene.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["t_s", "elemento", "altezza_su_strada_cm", "distanza_m"]); w.writerows(alls)

    if a.video_out > 0:                                     # frame CONSECUTIVI (~5fps) col tracking
        start = a.video_start if a.video_start is not None else max(0, src.n / src.fps / 2 - a.video_out / 2)
        tmp = tempfile.mkdtemp()
        idx0, k = int(start * src.fps), 0
        st["dist"].clear()
        for idx in range(idx0, min(src.n, idx0 + int(a.video_out * src.fps)), 3):
            pair = src.read(idx)
            if pair is None:
                break
            panel, _, _ = process(*pair, idx / src.fps, track=True)
            cv2.imwrite(f"{tmp}/{k:05d}.jpg", cv2.resize(panel, (1920, 600))); k += 1
        if k:
            ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
            subprocess.run([ff, "-loglevel", "error", "-y", "-framerate", "5", "-i", f"{tmp}/%05d.jpg",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", f"{a.out}/preview.mp4"])
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"fatto -> {a.out}")


if __name__ == "__main__":
    main()
