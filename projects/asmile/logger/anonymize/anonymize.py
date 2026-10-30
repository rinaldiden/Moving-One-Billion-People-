#!/usr/bin/env python3
"""
anonymize.py — oscuramento irreversibile di facce (persone) e targhe (veicoli)
nei log video di Asmile, per il logging GDPR-safe.

Tre stadi, in un unico modulo (gli agenti .claude/agents/asmile-anon-* mappano 1:1):
  [1] DETECTOR  — trova le regioni PII in ogni frame (facce + targhe)
  [2] REDACTOR  — oscura le regioni in modo IRREVERSIBILE, con smoothing temporale
  [3] AUDITOR   — campiona l'output, stima il recall, scrive un referto di conformità

Principio (vincolo prima della raccolta): si oscura ALLA SORGENTE. Il dato grezzo
con PII non deve sopravvivere al logging. Over-blur è sicuro; under-blur è il rischio.
Perciò di default: margine generoso, finestra temporale, blur forte (non reversibile).

Backend di detection PLUGGABILI (dal più robusto al fallback offline):
  --backend yolo    ultralytics YOLO (persona+veicolo) + modello targhe dedicato  [consigliato produzione]
  --backend deface  CenterFace ONNX (solo facce, qualità alta, offline dopo install)
  --backend haar    OpenCV Haar cascades BUNDLED in models/  [solo smoke-test, zero download]

NON richiede rete a runtime col backend 'haar' (cascade già in models/).
I video d'uscita restano LOCALI. Vedi README.md e docs/gdpr_logging_anonimizzazione.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    sys.exit("Serve OpenCV: python3 -m pip install --break-system-packages opencv-python-headless")

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models"
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".h264", ".m4v"}


# ───────────────────────────── strutture dati ─────────────────────────────
@dataclass
class Box:
    """Regione PII in coordinate pixel. cls ∈ {face, plate}."""
    x1: int
    y1: int
    x2: int
    y2: int
    cls: str
    conf: float = 1.0

    def expand(self, margin: float, w: int, h: int) -> "Box":
        """Allarga di `margin` (frazione del lato) e satura ai bordi. Over-blur = sicuro."""
        bw, bh = self.x2 - self.x1, self.y2 - self.y1
        mx, my = int(bw * margin), int(bh * margin)
        return Box(
            max(0, self.x1 - mx), max(0, self.y1 - my),
            min(w, self.x2 + mx), min(h, self.y2 + my),
            self.cls, self.conf,
        )


@dataclass
class AuditManifest:
    """Referto di conformità. Contiene SOLO conteggi/parametri, MAI la PII in chiaro."""
    source_name: str
    source_sha256_12: str          # fingerprint del grezzo (non il contenuto)
    created_utc: str
    backend: str
    redaction: str
    params: dict
    frames_total: int = 0
    frames_with_pii: int = 0
    det_faces: int = 0
    det_plates: int = 0
    seconds_elapsed: float = 0.0
    audit_sampled_frames: int = 0
    audit_residual_faces: int = 0      # PII trovata NELL'OUTPUT dall'auditor → deve essere 0
    audit_residual_plates: int = 0
    verdict: str = "PENDING"           # PASS / FAIL / PENDING — la FIRMA resta a Daniele
    notes: list = field(default_factory=list)


# ───────────────────────────── [1] DETECTOR ─────────────────────────────
class Detector:
    """Interfaccia comune: detect(frame_bgr) -> list[Box]."""
    def detect(self, frame) -> list[Box]:  # pragma: no cover
        raise NotImplementedError


class HaarDetector(Detector):
    """Fallback OFFLINE: Haar cascades bundled in models/. Smoke-test, non produzione.
    Recall basso su targhe/facce di profilo → compensato da smoothing+margine, ma
    in produzione usare 'yolo' o 'deface'."""
    def __init__(self, faces=True, plates=True):
        self.cascs = []
        if faces:
            for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
                p = MODELS / name
                if p.exists():
                    self.cascs.append(("face", cv2.CascadeClassifier(str(p))))
        if plates:
            p = MODELS / "haarcascade_russian_plate_number.xml"
            if p.exists():
                self.cascs.append(("plate", cv2.CascadeClassifier(str(p))))
        if not self.cascs:
            raise RuntimeError(f"Nessun cascade in {MODELS}. Scaricali (vedi README).")

    def detect(self, frame) -> list[Box]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        out: list[Box] = []
        for cls, casc in self.cascs:
            # minSize piccolo per prendere facce/targhe lontane (tipico dashcam/bici)
            rects = casc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(16, 16))
            for (x, y, w, h) in rects:
                out.append(Box(int(x), int(y), int(x + w), int(y + h), cls, 0.5))
        return out


class DefaceDetector(Detector):
    """Facce via CenterFace (pacchetto 'deface'). Qualità alta, offline dopo l'install.
    Solo facce — accoppialo a un detector targhe se servono anche quelle."""
    def __init__(self, threshold=0.2):
        try:
            from deface.centerface import CenterFace
        except ImportError:
            raise RuntimeError("Backend 'deface' non installato: pip install deface")
        self.cf = CenterFace()
        self.threshold = threshold

    def detect(self, frame) -> list[Box]:
        h, w = frame.shape[:2]
        dets, _ = self.cf(frame, threshold=self.threshold)
        out = []
        for (x1, y1, x2, y2, score) in dets:
            out.append(Box(int(x1), int(y1), int(x2), int(y2), "face", float(score)))
        return out


class YoloDetector(Detector):
    """Produzione: ultralytics YOLO. Un modello persona/veicolo (COCO) + un modello
    targhe dedicato. Per le PERSONE si oscura la testa (terzo superiore del box),
    non l'intero corpo — basta all'anonimizzazione e preserva il segnale di guida."""
    PERSON = {0}
    VEHICLE = {2, 3, 5, 7}  # car, motorcycle, bus, truck (COCO)

    def __init__(self, person_model="yolo11n.pt", plate_model=None, conf=0.25, head_only=True):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise RuntimeError("Backend 'yolo' non installato: pip install ultralytics")
        self.m = YOLO(person_model)
        self.plate = YOLO(plate_model) if plate_model else None
        self.conf = conf
        self.head_only = head_only

    def detect(self, frame) -> list[Box]:
        out: list[Box] = []
        r = self.m(frame, conf=self.conf, verbose=False)[0]
        for b in r.boxes:
            cls_id = int(b.cls[0]); x1, y1, x2, y2 = (int(v) for v in b.xyxy[0]); c = float(b.conf[0])
            if cls_id in self.PERSON:
                if self.head_only:  # testa ≈ terzo superiore del box persona
                    y2 = y1 + int((y2 - y1) * 0.35)
                out.append(Box(x1, y1, x2, y2, "face", c))
        if self.plate is not None:
            rp = self.plate(frame, conf=self.conf, verbose=False)[0]
            for b in rp.boxes:
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                out.append(Box(x1, y1, x2, y2, "plate", float(b.conf[0])))
        return out


def make_detector(backend: str, do_faces: bool, do_plates: bool, **kw) -> Detector:
    if backend == "haar":
        return HaarDetector(faces=do_faces, plates=do_plates)
    if backend == "deface":
        return DefaceDetector()
    if backend == "yolo":
        return YoloDetector(plate_model=kw.get("plate_model"))
    raise ValueError(f"backend sconosciuto: {backend}")


# ───────────────────────────── [2] REDACTOR ─────────────────────────────
def redact(frame, boxes: Iterable[Box], style: str, blur_strength: int):
    """Oscura IRREVERSIBILMENTE le regioni. blur/pixelate distruggono l'informazione
    (non ricostruibile); 'box' è un rettangolo pieno. Default: blur forte."""
    h, w = frame.shape[:2]
    for b in boxes:
        x1, y1, x2, y2 = b.x1, b.y1, b.x2, b.y2
        if x2 <= x1 or y2 <= y1:
            continue
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        if style == "box":
            frame[y1:y2, x1:x2] = 0
        elif style == "pixelate":
            rh, rw = roi.shape[:2]
            step = max(1, min(rh, rw) // 8)
            small = cv2.resize(roi, (max(1, rw // step), max(1, rh // step)), interpolation=cv2.INTER_LINEAR)
            frame[y1:y2, x1:x2] = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
        else:  # gaussian (default) — kernel proporzionale alla regione, mai reversibile
            k = max(blur_strength, (min(x2 - x1, y2 - y1) // 2) * 2 + 1)
            k = k + 1 if k % 2 == 0 else k
            frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
    return frame


class TemporalSmoother:
    """Finestra temporale: ogni frame è oscurato anche con le box dei ±window frame
    vicini. Copre flicker e mancate detection isolate (recall > precisione, per GDPR)."""
    def __init__(self, window: int):
        self.window = window
        self.buf: list[list[Box]] = []

    def feed(self, boxes: list[Box]) -> None:
        self.buf.append(boxes)
        if len(self.buf) > 2 * self.window + 1:
            self.buf.pop(0)

    def current(self) -> list[Box]:
        return [b for frame_boxes in self.buf for b in frame_boxes]


# ───────────────────────────── IO video ─────────────────────────────
def _ensure_decodable(path: Path) -> tuple[Path, bool]:
    """I .h264 grezzi (elementary stream) spesso non si aprono in OpenCV → remux a mp4
    temporaneo con ffmpeg (copy, nessuna ri-codifica). Ritorna (path, is_temp)."""
    if path.suffix.lower() != ".h264":
        return path, False
    tmp = Path(tempfile.mkdtemp(prefix="anon_")) / (path.stem + ".mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-r", "15", "-i", str(path), "-c", "copy", str(tmp)],
        check=True,
    )
    return tmp, True


def _sha256_12(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


# ───────────────────────── pipeline su un singolo video ─────────────────────────
def process_video(src: Path, dst: Path, backend: str, do_faces: bool, do_plates: bool,
                  style: str, blur_strength: int, margin: float, window: int,
                  audit_stride: int, plate_model: str | None, now_utc: str) -> AuditManifest:
    det = make_detector(backend, do_faces, do_plates, plate_model=plate_model)
    decodable, is_temp = _ensure_decodable(src)
    cap = cv2.VideoCapture(str(decodable))
    if not cap.isOpened():
        raise RuntimeError(f"Non riesco ad aprire {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    man = AuditManifest(
        source_name=src.name, source_sha256_12=_sha256_12(src), created_utc=now_utc,
        backend=backend, redaction=style,
        params=dict(margin=margin, window=window, blur_strength=blur_strength,
                    faces=do_faces, plates=do_plates, fps=fps, resolution=f"{w}x{h}"),
    )
    smoother = TemporalSmoother(window)
    # pre-detect su tutta la clip così lo smoothing vede anche i frame FUTURI
    t0 = time.time()
    frames = []
    per_frame_boxes: list[list[Box]] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
        boxes = det.detect(frame)
        for b in boxes:
            if b.cls == "face":
                man.det_faces += 1
            else:
                man.det_plates += 1
        per_frame_boxes.append(boxes)
    cap.release()
    man.frames_total = len(frames)

    for i, frame in enumerate(frames):
        lo, hi = max(0, i - window), min(len(frames), i + window + 1)
        nearby = [b for j in range(lo, hi) for b in per_frame_boxes[j]]
        if nearby:
            man.frames_with_pii += 1
        expanded = [b.expand(margin, w, h) for b in nearby]
        writer.write(redact(frame, expanded, style, blur_strength))
    writer.release()
    man.seconds_elapsed = round(time.time() - t0, 2)

    # [3] AUDITOR — ricontrolla l'OUTPUT: la PII residua deve essere 0.
    _audit_output(dst, det, man, audit_stride)

    if is_temp:
        try:
            decodable.unlink(); decodable.parent.rmdir()
        except OSError:
            pass
    return man


def _audit_output(dst: Path, det: Detector, man: AuditManifest, stride: int) -> None:
    """Rigira il detector sul video ANONIMIZZATO. Se trova ancora facce/targhe,
    l'oscuramento ha fallito → FAIL. Campiona 1 frame ogni `stride`."""
    cap = cv2.VideoCapture(str(dst))
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % stride == 0:
            man.audit_sampled_frames += 1
            for b in det.detect(frame):
                if b.cls == "face":
                    man.audit_residual_faces += 1
                else:
                    man.audit_residual_plates += 1
        i += 1
    cap.release()
    residual = man.audit_residual_faces + man.audit_residual_plates
    if residual == 0:
        man.verdict = "PASS"
        man.notes.append("Nessuna PII residua nei frame campionati dall'auditor.")
    else:
        man.verdict = "FAIL"
        man.notes.append(f"PII residua nell'output: {man.audit_residual_faces} facce, "
                         f"{man.audit_residual_plates} targhe — aumentare margine/finestra o backend.")
    if man.backend == "haar":
        man.notes.append("Backend 'haar' = smoke-test: recall basso, NON è conformità reale. "
                         "Per attestare GDPR usare 'yolo'/'deface' e revisione umana.")


# ───────────────────────────── CLI ─────────────────────────────
def iter_videos(p: Path):
    if p.is_file():
        yield p
    else:
        for f in sorted(p.rglob("*")):
            if f.suffix.lower() in VIDEO_EXT:
                yield f


def main():
    ap = argparse.ArgumentParser(description="Oscura facce e targhe nei log video (GDPR).")
    ap.add_argument("input", help="file video o cartella (ricorsiva)")
    ap.add_argument("-o", "--output", required=True, help="file o cartella di output (anonimizzati)")
    ap.add_argument("--backend", choices=["yolo", "deface", "haar"], default="haar",
                    help="detector: yolo=produzione, deface=facce HQ, haar=smoke-test offline")
    ap.add_argument("--no-faces", action="store_true", help="non oscurare le facce")
    ap.add_argument("--no-plates", action="store_true", help="non oscurare le targhe")
    ap.add_argument("--style", choices=["gaussian", "pixelate", "box"], default="gaussian")
    ap.add_argument("--blur", type=int, default=31, help="kernel minimo del blur (dispari)")
    ap.add_argument("--margin", type=float, default=0.25, help="allargamento box (frazione lato)")
    ap.add_argument("--window", type=int, default=3, help="smoothing temporale ± frame")
    ap.add_argument("--audit-stride", type=int, default=5, help="auditor: 1 frame ogni N")
    ap.add_argument("--plate-model", default=None, help="(yolo) pesi .pt del detector targhe")
    args = ap.parse_args()

    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    src_root = Path(args.input)
    out_root = Path(args.output)
    do_faces, do_plates = not args.no_faces, not args.no_plates

    manifests = []
    for vid in iter_videos(src_root):
        if src_root.is_file():
            dst = out_root if out_root.suffix else out_root / (vid.stem + "_anon.mp4")
        else:
            rel = vid.relative_to(src_root).with_suffix("")
            dst = out_root / (str(rel) + "_anon.mp4")
        print(f"[anon] {vid}  →  {dst}  (backend={args.backend})")
        man = process_video(
            vid, dst, args.backend, do_faces, do_plates, args.style, args.blur,
            args.margin, args.window, args.audit_stride, args.plate_model, now_utc,
        )
        man_path = dst.with_suffix(".audit.json")
        man_path.write_text(json.dumps(asdict(man), indent=2, ensure_ascii=False))
        manifests.append((vid.name, man))
        print(f"       verdict={man.verdict}  facce={man.det_faces} targhe={man.det_plates} "
              f"residuo={man.audit_residual_faces + man.audit_residual_plates}  "
              f"({man.seconds_elapsed}s)  referto→ {man_path.name}")

    n_fail = sum(1 for _, m in manifests if m.verdict != "PASS")
    print(f"\n[anon] fatti {len(manifests)} video, {n_fail} da rivedere (verdict≠PASS).")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
