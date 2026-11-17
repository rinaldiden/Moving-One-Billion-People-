#!/usr/bin/env python3
"""seg_sam3_001.py — SAM 3 sui fotogrammi campionati dalla depth (stessa rettifica, camera sinistra fisica), SOLO #001.
Frame = colonna `frame` di training/depth/out_20261112_v2/<sess>/frames.csv (indice nel video *_right.h264 = sinistra fisica),
rettificati con calib_asmile-001.json (m1x/m1y) come la depth: maschere e Z si sovrappongono pixel a pixel.
Nessun filtro di conferma temporale (frame sparsi). Ogni detection SAM 3 con conf>=0.30 e' registrata, con tier:
  sure     conf>=0.70 (gate/fence >=0.90, soglia congelata L1.classi v2: sotto, falsi 19% su #001)
  low      0.45<=conf<0.70
  unknown  conf<0.45, oppure gate/fence sotto 0.90 -> class_final='unknown' (class_raw conservata, mai forzata)
Ego-bici (pezzo sfocato basso, classi da palo) escluso e registrato a parte.
Uscite: <out>/index.jsonl (un record per frame), masks/f<frame>.npz (labels uint8 = idx+1, painted a conf crescente; 0=nulla)
Uso: ~/.asmile_depth_venv/bin/python training/segmentation/seg_sam3_001.py session_20261109_094146
"""
import os, sys, csv, json, time, argparse, hashlib
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "logger", "depth"))
import seg_teacher_student as S
from stereo_common import Calib
import subprocess
CALIB = os.path.join(ROOT, "logger", "depth", "calib_asmile-001.json")
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-001")
GF = {"gate": 0.90, "fence": 0.90}
EGO_LIKE = S.EGO_LIKE


def gray_frames(path, w=1280, h=800):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", path, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h: break
        yield np.frombuffer(b, np.uint8).reshape(h, w)
    p.kill()


def tier(cls, cf):
    if cls in GF:
        return ("sure", cls) if cf >= GF[cls] else ("unknown", "unknown")
    if cf >= 0.70: return "sure", cls
    if cf >= 0.45: return "low", cls
    return "unknown", "unknown"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--out", default=None)
    ap.add_argument("--max", type=int, default=10 ** 9); ap.add_argument("--frames", default=None)
    ap.add_argument("--list", default=None, help="csv con colonna frame")
    a = ap.parse_args()
    sess = a.session if a.session.startswith("session_") else "session_" + a.session
    lst = a.list or os.path.join(ROOT, "training", "depth", "out_20261112_v2", sess, "frames.csv")
    sel = sorted(int(r["frame"]) for r in csv.DictReader(open(lst)))[:a.max]
    if a.frames: sel = sorted(int(v) for v in a.frames.split(","))
    out = a.out or os.path.join(ROOT, "asmile-loggers", "_seg_sam3", sess + "_001"); os.makedirs(os.path.join(out, "masks"), exist_ok=True)
    c = Calib.load(CALIB); r = c.rectify(); m1x, m1y = r["m1x"], r["m1y"]
    t_ms = [int(x["t_ms"]) for x in csv.DictReader(open(os.path.join(LOGS, sess, "frames_right.csv")))]
    th = S.ThingsTeacher("mps"); assert th.kind == "sam3"
    th.pred.args.save = False; th.pred.args.show = False
    selset = set(sel); path_out = os.path.join(out, "index.jsonl")
    done = set()
    if os.path.exists(path_out):
        done = {json.loads(l)["frame"] for l in open(path_out)}
    fo = open(path_out, "a"); t0 = time.time(); n = 0
    for i, g in enumerate(gray_frames(os.path.join(LOGS, sess + "_right.h264"))):
        if i > sel[-1]: break
        if i not in selset or i in done: continue
        L = cv2.remap(g, m1x, m1y, cv2.INTER_LINEAR); img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR); h, w = L.shape
        tt = time.time(); th.pred.set_image(img); res = th.pred(text=S.THINGS)[0]; dt = time.time() - tt
        dets, ego = [], []
        if res is not None and res.boxes is not None and len(res.boxes):
            lap = cv2.Laplacian(L, cv2.CV_32F); sh = float(lap.var()) + 1e-6
            boxes, cls, conf = res.boxes.xyxy.tolist(), res.boxes.cls.int().tolist(), res.boxes.conf.tolist()
            polys = res.masks.xy if res.masks is not None else [np.zeros((0, 2))] * len(boxes)
            for k, (b, ci, cf, m) in enumerate(zip(boxes, cls, conf, polys)):
                cn = S.THINGS[ci]
                if cn in EGO_LIKE and b[3] >= h - 4 and (b[3] - b[1]) > 0.55 * h and (b[2] - b[0]) < 0.35 * w and S.ThingsTeacher.blurry(res, k, lap, sh):
                    ego.append(dict(class_raw=cn, conf=round(cf, 3), box=[int(v) for v in b])); continue
                tr, cf_ = tier(cn, cf)
                mk = res.masks.data[k].cpu().numpy() if res.masks is not None else None
                dets.append(dict(class_raw=cn, class_final=cf_, tier=tr, conf=round(cf, 3), box=[int(v) for v in b],
                                 area_px=int(cv2.contourArea(m.astype(np.float32))) if len(m) else 0,
                                 poly=m.astype(np.int32).tolist(), _mk=mk))
        dets.sort(key=lambda d: d["conf"])
        lab = np.zeros((h, w), np.uint8)
        for j, d in enumerate(dets):
            d["idx"] = j + 1
            if d["_mk"] is not None:
                mk = cv2.resize(d["_mk"].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
                lab[mk] = j + 1
            del d["_mk"]
        dets = dets[:250]
        np.savez_compressed(os.path.join(out, "masks", f"f{i:06d}.npz"), labels=lab)
        rec = dict(sess=sess, frame=i, t_ms=t_ms[i], cam="left_phys_rectified", size=[w, h], sam3_s=round(dt, 2), n_det=len(dets),
                   detections=dets, ego_excluded=ego)
        fo.write(json.dumps(rec) + "\n"); fo.flush(); n += 1
        if n % 20 == 0: print(f"{n}/{len(sel)} frame, {(time.time() - t0) / n:.2f} s/frame", flush=True)
    print("fatto", n, "frame in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
