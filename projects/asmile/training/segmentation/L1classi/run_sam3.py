"""L1.classi: SAM 3 (THINGS attuali, conf 0.30 come il maestro) con e senza gate/fence.
Salva le detection GREZZE (niente filtro temporale), jsonl riprendibile. Uso: run_sam3.py gate|ctrl"""
import sys, os, json, time, subprocess
sys.path.insert(0, "training/segmentation")
import numpy as np, cv2
import seg_teacher_student as S
OUT = "asmile-loggers/_seg_sam3_L1classi"
FULL = list(S.THINGS); OLD = [t for t in FULL if t not in ("gate", "fence")]
mode = sys.argv[1]
from ultralytics.models.sam import SAM3SemanticPredictor
pred = SAM3SemanticPredictor(overrides=dict(conf=0.30, task="segment", mode="predict",
        model=os.path.join(S.MODELS, "sam3.pt"), device="mps", verbose=False))

def run(img, names):
    pred.set_image(img)
    r = pred(text=names)[0]
    if r is None or r.boxes is None or not len(r.boxes): return []
    return [dict(c=names[c], conf=round(cf, 3), box=[int(v) for v in b])
            for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist())]

def frames_of(video, wanted, crop):
    want = set(wanted); mx = max(want); got = {}
    for i, img in enumerate(S.video_frames(video, mx + 1)):
        if i in want and img.size:
            got[i] = img[:, :1280] if crop else img
    return got

if mode == "gate":
    jobs = [("gate", "asmile-loggers/_work/asmile-logger/rientro_160535_c67-71/rientro_160535_c67-71_left.h264", list(range(1500, 1555)), False, "rientro_c67-71")]
else:
    cf = json.load(open("training/segmentation/L1classi/controllo_fisso.json"))
    jobs = []
    for unit in ("asmile-001", "riserva_asmile-001", "asmile-logger001", "riserva_asmile-logger001"):
        by = {}
        for it in cf[unit]: by.setdefault((it["video"], it.get("crop") == "left_half"), []).append(it["frame"])
        for (v, crop), fr in by.items(): jobs.append((unit, v, fr, crop, os.path.basename(v)))
fn = f"{OUT}/res_{mode}.jsonl"
done = set()
if os.path.exists(fn):
    for l in open(fn): d = json.loads(l); done.add((d["unit"], d["video"], d["frame"]))
fo = open(fn, "a"); t0 = time.time(); n = 0
for unit, v, fr, crop, tag in jobs:
    todo = [f for f in fr if (unit, tag, f) not in done]
    if not todo: continue
    got = frames_of(v, todo, crop)
    for f in todo:
        if f not in got: continue
        img = got[f]
        d = dict(unit=unit, video=tag, frame=f)
        t1 = time.time(); d["full"] = run(img, FULL); d["old"] = run(img, OLD); d["s"] = round(time.time() - t1, 2)
        if mode == "ctrl" or f % 6 == 0:
            cv2.imwrite(f"{OUT}/{unit}_{tag.replace('.h264','')}_{f:05d}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        fo.write(json.dumps(d) + "\n"); fo.flush(); n += 1
        if n % 10 == 0: print(mode, n, f"{time.time()-t0:.0f}s", flush=True)
print("FINE", mode, n, f"{time.time()-t0:.0f}s")
