#!/usr/bin/env python3
"""
Asmile Perception Priority Scheduler — percezione CPU-only multi-rate per il Pi 5.

Ispirato allo schema CPU-only di Affan Khan (object detection+tracking, drivable-area,
image-space motion, Perception Priority Map) e adattato ad Asmile per NON sovraccaricare
il Raspberry Pi: il modulo pesante (detector) gira di rado, un tracker leggero propaga i
box ad alto rate, e la depth stereo (costosa) si calcola SOLO sulle ROI prioritarie.

Design doc: docs/perception_priority_scheduler.md

SHADOW/DRY: questo scaffold OSSERVA e LOGGA. Non pilota attuatori, non tocca GPIO.
L'integrazione con speed_limiter v2 (owner unico GPIO) è un passo successivo e firmato.

Uso:
  # Benchmark (GATE G0): misura Hz e costo per stadio su un video di logging
  python3 perception_scheduler.py --benchmark --video /path/session/left.mp4

  # Dry-run su video: stampa priority map frame per frame, nessun attuatore
  python3 perception_scheduler.py --video /path/session/left.mp4

  # Come modulo
  from perception_scheduler import PerceptionScheduler
  sched = PerceptionScheduler(detect_every=6)
  for frame in frames:
      state = sched.step(frame)   # dict: tracks, priority, drivable, timing
"""

import os
import sys
import time
import argparse
from collections import deque

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────────────
# Config rate (punto di partenza — da tarare col benchmark G0)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_DETECT_EVERY = 6      # 1 detection ogni N frame (~2-4 Hz se input 15 FPS)
DEFAULT_DRIVABLE_EVERY = 15   # drivable-area ~1 Hz
DEFAULT_TOPK_DEPTH = 3        # quante ROI prioritarie pagano la depth densa (SGBM)
DETECT_INPUT_PX = 320         # lato lungo per l'inferenza detector (ridurre = più veloce)


# ─────────────────────────────────────────────────────────────────────────────
# Priority Map — score relativo di scena (NON attention umana, NON collision pred.)
# ─────────────────────────────────────────────────────────────────────────────
# Peso per classe: persone > veicoli > statico. Allineare ai pattern P1-P9.
CLASS_WEIGHT = {
    "person": 1.0, "bicycle": 0.8, "motorcycle": 0.8,
    "car": 0.7, "truck": 0.75, "bus": 0.75, "dog": 0.6, "cat": 0.4,
}
DEFAULT_CLASS_WEIGHT = 0.3  # oggetto sconosciuto ma presente


def priority_score(track, frame_w, frame_h, in_drivable):
    """Score di priorità in [0,1]-ish da classe, posizione, moto, corridoio, confidenza.

    track: dict con bbox=(x,y,w,h), cls, conf, velocity=(vx,vy) in px/frame.
    """
    x, y, w, h = track["bbox"]
    cx = x + w / 2.0
    cy = y + h / 2.0

    w_cls = CLASS_WEIGHT.get(track.get("cls"), DEFAULT_CLASS_WEIGHT)

    # posizione: più al centro orizzontale = più importante (sulla nostra traiettoria)
    center_term = 1.0 - min(1.0, abs(cx - frame_w / 2.0) / (frame_w / 2.0))

    # vicinanza grezza in image-space: box più in basso/più grande = più vicino
    size_term = min(1.0, (h / float(frame_h)) * 2.0)

    # moto: che si avvicina (vy>0, scende nell'immagine) o taglia il centro
    vx, vy = track.get("velocity", (0.0, 0.0))
    motion_term = min(1.0, (max(0.0, vy) + abs(vx)) / 10.0)

    drivable_term = 1.0 if in_drivable else 0.3
    conf = track.get("conf", 0.5)

    score = (
        0.30 * w_cls +
        0.20 * center_term +
        0.20 * size_term +
        0.15 * motion_term +
        0.15 * drivable_term
    ) * (0.5 + 0.5 * conf)
    return float(score)


# ─────────────────────────────────────────────────────────────────────────────
# Tracker leggero — propaga i box fra una detection e l'altra (alto rate, OpenCV)
# ─────────────────────────────────────────────────────────────────────────────
class LightTracker:
    """IOU + centroide per ri-associare le detection e stimare la velocità image-space.

    Nota: lo scaffold usa un re-detect ogni N frame + propagazione per IOU/centroide.
    In sviluppo si può sostituire con cv2.legacy.TrackerCSRT per il lock fra i frame.
    0% stale: un track senza detection fresca entro `max_age` frame viene marcato stale
    e scartato dalla priority map (non resta a mentire).
    """

    def __init__(self, max_age=12, iou_min=0.3):
        self.max_age = max_age
        self.iou_min = iou_min
        self.tracks = {}
        self._next_id = 0

    @staticmethod
    def _iou(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def update(self, detections, frame_idx):
        """detections: list di dict bbox/cls/conf (vuota nei frame senza detection)."""
        # età +1 a tutti
        for t in self.tracks.values():
            t["age"] += 1

        for det in detections:
            best_id, best_iou = None, self.iou_min
            for tid, t in self.tracks.items():
                i = self._iou(det["bbox"], t["bbox"])
                if i >= best_iou:
                    best_id, best_iou = tid, i
            if best_id is not None:
                t = self.tracks[best_id]
                ox, oy, ow, oh = t["bbox"]
                nx, ny, nw, nh = det["bbox"]
                t["velocity"] = ((nx + nw / 2) - (ox + ow / 2),
                                 (ny + nh / 2) - (oy + oh / 2))
                t.update(bbox=det["bbox"], cls=det.get("cls"),
                         conf=det.get("conf", 0.5), age=0)
            else:
                self.tracks[self._next_id] = dict(
                    bbox=det["bbox"], cls=det.get("cls"),
                    conf=det.get("conf", 0.5), velocity=(0.0, 0.0), age=0)
                self._next_id += 1

        # scarta gli stale (0% stale tracking)
        dead = [tid for tid, t in self.tracks.items() if t["age"] > self.max_age]
        for tid in dead:
            del self.tracks[tid]
        return list(self.tracks.values())


# ─────────────────────────────────────────────────────────────────────────────
# Detector — pesante, gira di rado. Pluggabile: ONNX (cv2.dnn/ORT) o ultralytics.
# ─────────────────────────────────────────────────────────────────────────────
class Detector:
    """Wrapper del detector. Default: no-op (lo scaffold gira ovunque).

    In produzione: YOLOv8n esportato ONNX INT8, caricato con cv2.dnn o onnxruntime,
    input DETECT_INPUT_PX. Molto più leggero di yolov8m-seg (usato oggi offline).
    """

    def __init__(self, backend="none", model_path=None):
        self.backend = backend
        self.model_path = model_path
        self._net = None

    def _lazy(self):
        if self._net is not None or self.backend == "none":
            return
        if self.backend == "ultralytics":
            from ultralytics import YOLO
            self._net = YOLO(self.model_path or "yolov8n.pt")
        elif self.backend == "onnx-cv2":
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        # onnxruntime / tflite: aggiungere qui quando benchmarkati

    def detect(self, frame):
        """Ritorna list di dict bbox=(x,y,w,h)/cls/conf. Vuota se backend=none."""
        self._lazy()
        if self.backend == "none" or self._net is None:
            return []
        if self.backend == "ultralytics":
            res = self._net.predict(frame, imgsz=DETECT_INPUT_PX, verbose=False)[0]
            out = []
            for b in res.boxes:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                out.append(dict(bbox=(x1, y1, x2 - x1, y2 - y1),
                                cls=res.names[int(b.cls)], conf=float(b.conf)))
            return out
        # onnx-cv2: decodifica specifica del modello → da implementare al passo 2
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Drivable-area — CV leggera (bordi strada + ground plane), ~1 Hz
# ─────────────────────────────────────────────────────────────────────────────
def drivable_corridor(gray):
    """Stima grezza del corridoio guidabile: metà inferiore, bordi via Canny.

    Ritorna (x_left, x_right) del corridoio a mezza altezza inferiore. Placeholder
    coerente con lo stile di vision_safety.py — da raffinare al passo 4.
    """
    h, w = gray.shape[:2]
    roi = gray[int(h * 0.5):, :]
    edges = cv2.Canny(roi, 50, 150) if cv2 is not None else None
    # default: corridoio centrale largo 60% se non si ricava altro
    return (int(w * 0.2), int(w * 0.8)), edges


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler multi-rate — il cuore anti-sovraccarico
# ─────────────────────────────────────────────────────────────────────────────
class PerceptionScheduler:
    def __init__(self, detect_every=DEFAULT_DETECT_EVERY,
                 drivable_every=DEFAULT_DRIVABLE_EVERY,
                 topk_depth=DEFAULT_TOPK_DEPTH,
                 detector=None):
        self.detect_every = detect_every
        self.drivable_every = drivable_every
        self.topk_depth = topk_depth
        self.tracker = LightTracker()
        self.detector = detector or Detector(backend="none")
        self.frame_idx = 0
        self._corridor = None
        self.timing = {k: deque(maxlen=60) for k in
                       ("detect", "track", "drivable", "depth", "total")}

    def _timed(self, key, fn, *a, **k):
        t0 = time.time()
        r = fn(*a, **k)
        self.timing[key].append(time.time() - t0)
        return r

    def step(self, frame_left):
        """Un frame LEFT (grigio o BGR). Ritorna lo stato di percezione (dict)."""
        t_total = time.time()
        gray = frame_left
        if cv2 is not None and frame_left.ndim == 3:
            gray = cv2.cvtColor(frame_left, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # DETECTOR — solo ogni N frame
        detections = []
        if self.frame_idx % self.detect_every == 0:
            detections = self._timed("detect", self.detector.detect, frame_left)

        # TRACKER — ogni frame
        tracks = self._timed("track", self.tracker.update, detections, self.frame_idx)

        # DRIVABLE — ~1 Hz
        if self.frame_idx % self.drivable_every == 0 and cv2 is not None:
            self._corridor, _ = self._timed("drivable", drivable_corridor, gray)
        corridor = self._corridor or (int(w * 0.2), int(w * 0.8))

        # PRIORITY MAP
        for t in tracks:
            cx = t["bbox"][0] + t["bbox"][2] / 2
            in_drivable = corridor[0] <= cx <= corridor[1]
            t["priority"] = priority_score(t, w, h, in_drivable)
        tracks.sort(key=lambda t: t.get("priority", 0), reverse=True)

        # DEPTH on-demand — solo top-K ROI (qui marcate; il calcolo vero al passo 5)
        for t in tracks[: self.topk_depth]:
            t["depth_requested"] = True

        self.timing["total"].append(time.time() - t_total)
        self.frame_idx += 1
        return dict(tracks=tracks, corridor=corridor, frame_idx=self.frame_idx)

    def report_hz(self):
        def avg(k):
            v = self.timing[k]
            return (sum(v) / len(v)) if v else 0.0
        out = {}
        for k in self.timing:
            ms = avg(k) * 1000
            out[k] = dict(ms=round(ms, 1), hz=round(1000 / ms, 1) if ms > 0 else None)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# CLI — benchmark (G0) e dry-run
# ─────────────────────────────────────────────────────────────────────────────
def _iter_frames(video_path):
    if cv2 is None:
        raise RuntimeError("OpenCV non disponibile")
    cap = cv2.VideoCapture(video_path)
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        yield fr
    cap.release()


def main():
    ap = argparse.ArgumentParser(description="Asmile Perception Priority Scheduler")
    ap.add_argument("--video", help="video di logging (camera LEFT o stereo)")
    ap.add_argument("--benchmark", action="store_true", help="GATE G0: misura Hz/costo")
    ap.add_argument("--detect-every", type=int, default=DEFAULT_DETECT_EVERY)
    ap.add_argument("--backend", default="none",
                    choices=["none", "ultralytics", "onnx-cv2"])
    ap.add_argument("--model", help="path modello detector (ONNX o .pt)")
    ap.add_argument("--max-frames", type=int, default=300)
    args = ap.parse_args()

    detector = Detector(backend=args.backend, model_path=args.model)
    sched = PerceptionScheduler(detect_every=args.detect_every, detector=detector)

    if not args.video:
        print("Nessun --video: scaffold caricato. Vedi docs/perception_priority_scheduler.md")
        return

    n = 0
    t0 = time.time()
    for fr in _iter_frames(args.video):
        st = sched.step(fr)
        n += 1
        if not args.benchmark and n % 15 == 0:
            top = st["tracks"][:3]
            print(f"[f{st['frame_idx']}] tracks={len(st['tracks'])} "
                  + " ".join(f"{t.get('cls','?')}:{t.get('priority',0):.2f}" for t in top))
        if n >= args.max_frames:
            break

    dt = time.time() - t0
    print(f"\n== {n} frame in {dt:.1f}s → pipeline {n/dt:.1f} FPS reali ==")
    if args.benchmark:
        for stage, m in sched.report_hz().items():
            print(f"  {stage:9s}: {m['ms']:6.1f} ms/call  (~{m['hz']} Hz)")
        print("\nGATE G0: detector deve reggere ≥2 Hz sul Pi. Se no → MobileNet-SSD "
              "o --detect-every più alto. Vedi docs/perception_priority_scheduler.md §6")


if __name__ == "__main__":
    main()
