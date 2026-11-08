"""
seg_teacher_student.py — segmentazione nuova di Asmile: maestro offline + allievo per il Pi (2026-11-08).

Due tipi di classe, trattati diversamente:
  COSE    (contabili: persone, veicoli, cartelli, animali, coni…) → istanze + tracking nel tempo
  SFONDO  (superfici: strada, marciapiede, prato, alberi, muri, cielo…) → semantica per pixel

Maestro (Mac/GPU, offline, fa da etichettatore):
  cose   = SAM 3 con la lista di frasi (se c'è sam3.pt, accesso su huggingface.co/facebook/sam3),
           altrimenti YOLOE-26-L open-vocabulary con la stessa lista
  sfondo = Mask2Former Swin-L Mapillary Vistas (65 classi stradali), 3 volte al secondo
Allievo (quello che girerà sul Pi): YOLOE-26-N con le classi fissate, 320 px, NON ancora affinato
  sui nostri dati → il pannello di destra mostra da dove parte, il sinistro dove deve arrivare.

Uscite in <out>/<sessione>/:
  seg_<cam>.mp4        maestro | allievo affiancati
  objects_<cam>.csv    frame,t_ms,track_id,classe,conf,x1,y1,x2,y2,area_px (maestro)
  stuff_<cam>.csv      frame,t_ms,% strada,% marciapiede,… (maestro, sui frame dove gira)
  summary.json         tempi per frame di maestro e allievo, conteggi per classe

Uso:
  ~/.asmile_depth_venv/bin/python training/segmentation/seg_teacher_student.py \
      asmile-loggers/asmile-001/session_20261107_170056 [--cam left] [--max-frames N]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict

import cv2
import numpy as np

MODELS = os.path.expanduser("~/.asmile_seg_models")

# Lista delle COSE (prompt testuali: identici per SAM 3, YOLOE maestro e allievo)
THINGS = ["person", "child", "bicycle", "motorcycle", "car", "van", "truck", "bus", "tractor",
          "dog", "cat", "stop sign", "traffic sign", "traffic light", "traffic cone", "bollard",
          "pole", "barrier", "trash can", "bench", "stroller", "wheelchair"]
TRACK_EVERY = {"traffic sign": 5, "stop sign": 5, "traffic light": 5}   # cartelli: 3 Hz basta

# SFONDO: classi Mapillary → nostre superfici (colori Cityscapes dove esistono)
STUFF = {
    "strada":      ([13, 14, 7, 10, 24], (128, 64, 128)),     # Road, Service/Bike Lane, Parking, segnaletica
    "strisce":     ([8, 23], (255, 255, 255)),               # attraversamento pedonale
    "marciapiede": ([15, 11, 9], (244, 35, 232)),            # Sidewalk, Pedestrian Area, Curb Cut
    "cordolo":     ([2], (196, 196, 0)),
    "prato":       ([29, 26, 28], (152, 251, 152)),           # Terrain, Sand, Snow
    "alberi":      ([30], (107, 142, 35)),
    "edifici":     ([17, 16, 18], (70, 70, 70)),
    "muri":        ([6, 3, 4, 5], (102, 102, 156)),           # Wall, Fence, Guard Rail, Barrier
    "cielo":       ([27], (70, 130, 180)),
    "tombino":     ([36, 41], (0, 255, 255)),
    "buca":        ([43], (0, 0, 255)),                      # solo indizio: le buche vanno con la depth
}


def video_frames(path, max_frames=None):
    """Decodifica l'h264 grezzo con ffmpeg (i .h264 della bici non hanno contenitore)."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", path, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    w, h = probe_size(path)
    n = 0
    while max_frames is None or n < max_frames:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        n += 1
    p.kill()


def probe_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True)
    w, h = out.stdout.strip().split(",")[:2]
    return int(w), int(h)


def read_pts(path):
    """pts_<cam>.txt (timecode v2, ms dall'inizio). Con frames_<cam>.csv (metodo unico) usa t_ms vero."""
    d = os.path.dirname(path)
    cam = "left" if "_left" in path else "right"
    fcsv = os.path.join(d, f"frames_{cam}.csv")
    if os.path.exists(fcsv):
        return [int(r["t_ms"]) for r in csv.DictReader(open(fcsv))]
    ptxt = os.path.join(d, f"pts_{cam}.txt")
    if os.path.exists(ptxt):
        return [int(round(float(x))) for x in open(ptxt) if x.strip() and not x.startswith("#")]
    return []


class ThingsTeacher:
    def __init__(self, device):
        sam3 = os.path.join(MODELS, "sam3.pt")
        self.kind = "sam3" if os.path.exists(sam3) else "yoloe-26l"
        if self.kind == "sam3":
            from ultralytics.models.sam import SAM3SemanticPredictor
            self.pred = SAM3SemanticPredictor(overrides=dict(conf=0.30, task="segment", mode="predict",
                                                             model=sam3, device=device, verbose=False))
        else:
            from ultralytics import YOLOE
            self.model = YOLOE(os.path.join(MODELS, "yoloe-26l-seg.pt"))
            self.model.set_classes(THINGS)
        self.device = device
        self.prev = []          # (classe, box) grezzi della passata prima, per la conferma su più frame
        self.ego = []           # contorni del pezzo di bici davanti alla camera (esclusi)

    def __call__(self, img):
        if self.kind == "sam3":
            self.pred.set_image(img)
            r = self.pred(text=THINGS)[0]
        else:
            r = self.model.track(img, persist=True, conf=0.25, imgsz=960, device=self.device,
                                 tracker="bytetrack.yaml", verbose=False, retina_masks=False)[0]
        return self.clean(r, img)

    def clean(self, r, img):
        h, w = img.shape[:2]
        """Etichette pulite per l'allievo (2026-11-08, dopo la prima clip SAM 3):
        - EGO: il pezzo di bici sfocato davanti alla camera sinistra veniva chiamato «palo». Una
          maschera che tocca il bordo basso ed è alta più di metà immagine non è un oggetto della
          strada: va tolta (e disegnata a parte) finché il pezzo non viene spostato.
        - Soglia CONF_MIN e conferma: sotto CONF_SURE un oggetto vale solo se la passata prima del
          maestro aveva la stessa classe nello stesso punto (IoU > 0.3) → via i «gatti» sui muri.
        Solo classi da «palo» (EGO_LIKE) e strette: una persona vicinissima NON viene mai tolta."""
        self.ego = []
        if r is None or r.boxes is None or not len(r.boxes):
            self.prev = []
            return r
        boxes, cls, conf = r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist()
        polys = r.masks.xy if r.masks is not None else [np.zeros((0, 2))] * len(boxes)
        lap = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_32F)
        sharp_all = float(lap.var()) + 1e-6
        keep, raw = [], []
        for k, (b, c, cf, m) in enumerate(zip(boxes, cls, conf, polys)):
            if THINGS[c] in EGO_LIKE and b[3] >= h - 4 and (b[3] - b[1]) > 0.55 * h \
                    and (b[2] - b[0]) < 0.35 * w and self.blurry(r, k, lap, sharp_all):
                self.ego.append(m)
                continue
            raw.append((c, b))
            seen = any(pc == c and iou(pb, b) > 0.3 for pc, pb in self.prev)
            if cf >= CONF_SURE or (cf >= CONF_MIN and seen):
                keep.append(k)
        self.prev = raw
        return r[keep] if keep else r[[]]

    @staticmethod
    def blurry(r, k, lap, sharp_all):
        """Il pezzo di bici è fuori fuoco (a pochi cm dalla lente): varianza del Laplaciano < 30% del frame.
        Sul frame 75 s della 14:50: dentro 2,2 contro 18 fuori (varianza Laplaciano)."""
        if r.masks is None:
            return False
        m = cv2.resize(r.masks.data[k].cpu().numpy().astype(np.uint8), (lap.shape[1], lap.shape[0])) > 0
        return m.any() and float(lap[m].var()) < 0.3 * sharp_all


CONF_MIN, CONF_SURE = 0.45, 0.70
EGO_LIKE = {"pole", "bollard", "barrier", "traffic sign", "traffic light", "traffic cone"}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


class StuffTeacher:
    NAME = "facebook/mask2former-swin-large-mapillary-vistas-semantic"

    def __init__(self, device):
        import torch
        from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation
        self.torch = torch
        self.proc = AutoImageProcessor.from_pretrained(self.NAME)
        self.model = Mask2FormerForUniversalSegmentation.from_pretrained(self.NAME).to(device).eval()
        self.device = device
        self.lut = np.full(256, 255, np.uint8)            # mapillary id → indice in STUFF (255 = niente)
        for i, (ids, _) in enumerate(STUFF.values()):
            self.lut[ids] = i

    def __call__(self, img):
        h, w = img.shape[:2]
        with self.torch.no_grad():
            x = self.proc(images=np.ascontiguousarray(img[:, :, ::-1]), size={"height": 512, "width": 832},
                          return_tensors="pt").to(self.device)
            seg = self.proc.post_process_semantic_segmentation(self.model(**x), target_sizes=[(h, w)])[0]
        return self.lut[seg.cpu().numpy().astype(np.uint8)]


def draw_stuff(img, lab):
    over = img.copy()
    for i, (_, col) in enumerate(STUFF.values()):
        over[lab == i] = col[::-1]
    return cv2.addWeighted(img, 0.55, over, 0.45, 0)


def draw_things(img, r, names, tag):
    out = img
    if r is not None and r.masks is not None and len(r.boxes):
        ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [None] * len(r.boxes)
        for m, b, c, cf, tid in zip(r.masks.xy, r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(),
                                    r.boxes.conf.tolist(), ids):
            col = tuple(int(v) for v in np.random.default_rng(c + 7).integers(60, 255, 3))
            if len(m):
                cv2.polylines(out, [m.astype(np.int32)], True, col, 2)
            x1, y1 = int(b[0]), int(b[1])
            lbl = f"{names[c]}{'' if tid is None else ' #%d' % tid} {cf:.2f}"
            cv2.putText(out, lbl, (x1, max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(out, lbl, (x1, max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.putText(out, tag, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
    cv2.putText(out, tag, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return out


def legend(h):
    lg = np.zeros((h, 150, 3), np.uint8)
    for i, (name, (_, col)) in enumerate(STUFF.items()):
        cv2.rectangle(lg, (8, 12 + i * 24), (26, 28 + i * 24), col[::-1], -1)
        cv2.putText(lg, name, (32, 26 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return lg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--cam", default="left")
    ap.add_argument("--out", default="asmile-loggers/_seg")
    ap.add_argument("--max-frames", type=int)
    ap.add_argument("--start", type=float, default=0, help="secondo da cui partire")
    ap.add_argument("--teacher-every", type=int, help="maestro ogni N frame (default: 3 con SAM 3, 1 con YOLOE)")
    ap.add_argument("--stuff-every", type=int, default=5, help="sfondo ogni N frame (15 fps / 5 = 3 Hz)")
    ap.add_argument("--device", default="mps")
    a = ap.parse_args()

    sess = os.path.basename(a.session.rstrip("/"))
    video = a.session.rstrip("/") + f"_{a.cam}.h264"
    if not os.path.exists(video):
        video = os.path.join(a.session, f"{sess}_{a.cam}.h264")
    pts_src = os.path.join(a.session, f"pts_{a.cam}.txt")
    pts = read_pts(pts_src) if os.path.isdir(a.session) else []
    out_dir = os.path.join(a.out, sess)
    os.makedirs(out_dir, exist_ok=True)

    from ultralytics import YOLOE
    teacher, stuff = ThingsTeacher(a.device), StuffTeacher(a.device)
    student = YOLOE(os.path.join(MODELS, "yoloe-26n-seg.pt"))
    student.set_classes(THINGS)
    names = THINGS

    w, h = probe_size(video)
    vw = cv2.VideoWriter(os.path.join(out_dir, f"seg_{a.cam}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 15,
                         (w + w // 2 + 150, h))
    fo = csv.writer(open(os.path.join(out_dir, f"objects_{a.cam}.csv"), "w", newline=""))
    fo.writerow(["frame", "t_ms", "track_id", "classe", "conf", "x1", "y1", "x2", "y2", "area_px"])
    fs = csv.writer(open(os.path.join(out_dir, f"stuff_{a.cam}.csv"), "w", newline=""))
    fs.writerow(["frame", "t_ms"] + [f"pct_{k}" for k in STUFF])

    t_teach, t_stuff, t_stud = [], [], []
    counts, tracks = Counter(), defaultdict(set)
    lab, lg, n_ego = None, legend(h), 0
    start = int(a.start * 15)
    every = a.teacher_every or (3 if teacher.kind == "sam3" else 1)   # SAM 3 ~1,9 s/frame su Mac → 5 Hz
    r = None
    for i, img in enumerate(video_frames(video, None if a.max_frames is None else start + a.max_frames)):
        if i < start:
            continue
        t_ms = pts[i] if i < len(pts) else round(i * 1000 / 15)
        fresh = (i - start) % every == 0
        if fresh:
            t0 = time.time()
            r = teacher(img)
            t_teach.append(time.time() - t0)
        if i % a.stuff_every == 0 or lab is None:
            t0 = time.time()
            lab = stuff(img)
            t_stuff.append(time.time() - t0)
            tot = lab.size
            fs.writerow([i, t_ms] + [round(100 * np.count_nonzero(lab == k) / tot, 1) for k in range(len(STUFF))])
        small = cv2.resize(img, (w // 2, h // 2))
        t0 = time.time()
        rs = student.predict(small, imgsz=320, conf=0.25, device="cpu", verbose=False)[0]
        t_stud.append(time.time() - t0)

        if fresh and r is not None and r.boxes is not None and len(r.boxes):
            ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [None] * len(r.boxes)
            areas = [int(cv2.contourArea(m.astype(np.float32))) if len(m) else 0 for m in r.masks.xy] \
                if r.masks is not None else [0] * len(r.boxes)
            for b, c, cf, tid, ar in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(),
                                         r.boxes.conf.tolist(), ids, areas):
                fo.writerow([i, t_ms, "" if tid is None else tid, names[c], round(cf, 3)] +
                            [int(v) for v in b] + [ar])
                counts[names[c]] += 1
                if tid is not None:
                    tracks[names[c]].add(tid)

        base = draw_stuff(img, lab)
        for m in (teacher.ego if fresh else []):    # pezzo di bici: grigio, escluso (solo sul frame visto)
            if len(m):
                pts_e = m.astype(np.int32)
                ov = base.copy()
                cv2.fillPoly(ov, [pts_e], (90, 90, 90))
                base = cv2.addWeighted(base, 0.4, ov, 0.6, 0)
                x, y = pts_e[:, 0].min(), int(np.median(pts_e[:, 1]))
                cv2.putText(base, "BICI (esclusa)", (int(x) + 5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if fresh:
            n_ego += bool(teacher.ego)
        left = draw_things(base, r, names,
                           f"MAESTRO {teacher.kind} + mask2former  {t_ms / 1000:6.1f}s")
        right = draw_things(small.copy(), rs, names, "ALLIEVO Pi yoloe-26n 320px")
        right = np.vstack([right, np.zeros((h - h // 2, w // 2, 3), np.uint8)])
        cv2.putText(right, f"allievo {1000 * np.mean(t_stud[-30:]):.0f} ms/frame (CPU Mac)",
                    (10, h // 2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(right, "non ancora affinato sui nostri video", (10, h // 2 + 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
        vw.write(np.hstack([left, right, lg]))
        if i % 100 == 0:
            print(f"{sess} {a.cam} frame {i}  maestro {1000 * np.mean(t_teach[-100:]):.0f} ms", flush=True)
    vw.release()

    ms = lambda v: round(1000 * float(np.median(v)), 1) if v else None
    summary = dict(session=sess, cam=a.cam, frames=len(t_teach), teacher_things=teacher.kind,
                   teacher_stuff=StuffTeacher.NAME, student="yoloe-26n-seg @320 (non affinato)",
                   ms_teacher_things=ms(t_teach), ms_teacher_stuff=ms(t_stuff), ms_student_cpu_mac=ms(t_stud),
                   frames_with_bike_part=n_ego, conf_min=CONF_MIN, conf_sure=CONF_SURE,
                   detections=dict(counts.most_common()), tracks={k: len(v) for k, v in tracks.items()},
                   things=THINGS, stuff=list(STUFF))
    json.dump(summary, open(os.path.join(out_dir, f"summary_{a.cam}.json"), "w"), indent=1)
    # mp4v non si apre ovunque: copia h264 per vederlo sul Mac/telefono
    src = os.path.join(out_dir, f"seg_{a.cam}.mp4")
    dst = os.path.join(out_dir, f"seg_{a.cam}_h264.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "libx264", "-crf", "24",
                    "-pix_fmt", "yuv420p", dst])
    if os.path.exists(dst):
        os.replace(dst, src)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
