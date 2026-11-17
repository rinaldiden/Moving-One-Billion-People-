#!/usr/bin/env python3
"""Mosaico di 12 frame rappresentativi + statistiche dall'index.jsonl di seg_sam3_001.py (SOLO lettura dei risultati)."""
import os, sys, json, csv, collections
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "logger", "depth"))
from stereo_common import Calib
from seg_sam3_001 import gray_frames, LOGS, CALIB
sess = sys.argv[1]; out = os.path.join(ROOT, "asmile-loggers", "_seg_sam3", sess + "_001")
recs = [json.loads(l) for l in open(os.path.join(out, "index.jsonl"))]
R = Calib.load(CALIB).rectify()
cnt = collections.Counter(); cnt_t = collections.Counter(); fr_cls = collections.Counter(); ct = collections.Counter(); raw_unk = collections.Counter()
for r in recs:
    seen = set()
    for d in r["detections"]:
        ct[d["tier"]] += 1; cnt[d["class_final"]] += 1; cnt_t[(d["class_raw"], d["tier"])] += 1
        if d["class_final"] == "unknown": raw_unk[d["class_raw"]] += 1
        else: seen.add(d["class_final"])
    for c in seen: fr_cls[c] += 1
st = dict(n_frames=len(recs), n_det=sum(r["n_det"] for r in recs), tier=dict(ct), per_class_final=dict(cnt.most_common()),
          frames_with_class=dict(fr_cls.most_common()), unknown_by_raw=dict(raw_unk.most_common()),
          ego_frames=sum(bool(r["ego_excluded"]) for r in recs), sam3_s_median=float(np.median([r["sam3_s"] for r in recs])),
          sam3_s_mean=float(np.mean([r["sam3_s"] for r in recs])), frames_zero_det=sum(r["n_det"] == 0 for r in recs))
json.dump(st, open(os.path.join(out, "stats.json"), "w"), indent=1)
print(json.dumps(st, indent=1))
# 12 frame: linspace sugli indici, sostituendo con il piu' vicino con >=1 det sure se disponibile? NO: deterministico, nessuna scelta ciliegia
pick = [recs[int(k)] for k in np.linspace(0, len(recs) - 1, 12)]
want = {r["frame"] for r in pick}; imgs = {}
m1x, m1y = R["m1x"], R["m1y"]
for i, g in enumerate(gray_frames(os.path.join(LOGS, sess + "_right.h264"))):
    if i in want: imgs[i] = cv2.remap(g, m1x, m1y, cv2.INTER_LINEAR)
    if i >= max(want): break
COL = {"sure": None, "low": (0, 200, 255), "unknown": (160, 160, 160)}
def col(c): return tuple(int(v) for v in np.random.default_rng(abs(hash(c)) % 1000 + len(c)).integers(80, 255, 3))
tiles = []
for r in pick:
    img = cv2.cvtColor(imgs[r["frame"]], cv2.COLOR_GRAY2BGR); lab = np.load(os.path.join(out, "masks", f"f{r['frame']:06d}.npz"))["labels"]
    ov = img.copy()
    for d in r["detections"]:
        c = COL[d["tier"]] or col(d["class_final"]); ov[lab == d["idx"]] = c
    img = cv2.addWeighted(img, 0.55, ov, 0.45, 0)
    for d in r["detections"]:
        c = COL[d["tier"]] or col(d["class_final"]); x1, y1 = d["box"][:2]
        t = f"{d['class_final']} {d['conf']:.2f}" + ("" if d["class_final"] != "unknown" else f" ({d['class_raw']}?)")
        cv2.putText(img, t, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3); cv2.putText(img, t, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 1)
    cv2.putText(img, f"f{r['frame']} t={r['t_ms']/1000:.0f}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    tiles.append(cv2.resize(img, (640, 400)))
rows = [np.hstack(tiles[k:k + 3]) for k in range(0, 12, 3)]
for k in range(2):
    cv2.imwrite(os.path.join(ROOT, "agents", "rapporti", "img", f"seg_sam3_094146_{k+1}.jpg"), np.vstack(rows[2 * k:2 * k + 2]), [cv2.IMWRITE_JPEG_QUALITY, 85])
print("frame mosaico", [r["frame"] for r in pick])
