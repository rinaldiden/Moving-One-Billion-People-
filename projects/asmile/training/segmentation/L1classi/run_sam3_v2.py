"""L1.classi v2: SAM 3 raw detections (conf 0.30) su set_v2 validi + positivi extra. Prompt: THINGS (con gate/fence) + door + garage door
in UNA passata (prompt indipendenti), e passata 'old' (THINGS senza gate/fence) per le classi vecchie. Riprendibile."""
import sys, os, json, time
sys.path.insert(0, "training/segmentation")
import cv2
import seg_teacher_student as S
O = "asmile-loggers/_seg_sam3_L1classi_v2"; L = "training/segmentation/L1classi"
FULL = list(S.THINGS) + ["door", "garage door"]; OLD = [t for t in S.THINGS if t not in ("gate", "fence")]
from ultralytics.models.sam import SAM3SemanticPredictor
pred = SAM3SemanticPredictor(overrides=dict(conf=0.30, task="segment", mode="predict", model=os.path.join(S.MODELS, "sam3.pt"), device="mps", verbose=False))
def run(img, names):
    pred.set_image(img); r = pred(text=names)[0]
    if r is None or r.boxes is None or not len(r.boxes): return []
    return [dict(c=names[c], conf=round(cf, 3), box=[int(v) for v in b]) for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist())]
st = json.load(open(f"{L}/set_v2.json")); ce = json.load(open(f"{L}/certificazione_v2.json"))
jobs = []   # (key, video, frames, crop)
for u in ("asmile-001", "asmile-logger001"):
    inv = set(ce[u]["invalido"])
    by = {}
    for it in st[u]:
        if it["idx"] in inv or not os.path.exists(f"{O}/frames/{u}_{it['idx']:03d}.jpg"): continue
        by.setdefault(it["video"], []).append((it["idx"], it["frame"]))
    for v, l in by.items(): jobs.append((u, v, l, None))
V1 = "asmile-loggers/asmile-001/session_20261109_094146_left.h264"
jobs.append(("pos_001_E1", V1, [(i, i) for i in range(6640, 6701, 5)], None))
jobs.append(("pos_001_E2", V1, [(i, i) for i in range(7120, 7201, 5)], None))
jobs.append(("pos_logger_rientro", ce["eventi_positivi_extra"]["logger_rientro_cancello"]["video"], [(i, i) for i in range(1500, 1555)], None))
fn = f"{O}/res_v2.jsonl"; done = set()
if os.path.exists(fn):
    for l in open(fn): d = json.loads(l); done.add((d["key"], d["idx"]))
fo = open(fn, "a"); t0 = time.time(); n = 0
for key, v, fr, _ in jobs:
    todo = {f: idx for idx, f in fr if (key, idx) not in done}
    if not todo: continue
    for i, img in enumerate(S.video_frames(v, max(todo) + 1)):
        if i not in todo or not img.size: continue
        if key == "asmile-logger001": img = img[:, :1280]
        H, W = img.shape[:2]
        d = dict(key=key, idx=todo[i], frame=i, W=W, H=H); t1 = time.time()
        d["full"] = run(img, FULL); d["old"] = run(img, OLD); d["s"] = round(time.time() - t1, 2)
        if key.startswith("pos_"): cv2.imwrite(f"{O}/frames/{key}_{i:05d}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        fo.write(json.dumps(d) + "\n"); fo.flush(); n += 1
        if n % 20 == 0: print(n, f"{time.time()-t0:.0f}s", flush=True)
print("FINE", n, f"{time.time()-t0:.0f}s")
