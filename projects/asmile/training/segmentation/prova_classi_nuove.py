#!/usr/bin/env python3
"""prova_classi_nuove.py — quanto bene SAM 3 trova le classi di classi.json sui NOSTRI fotogrammi (Mac, sola lettura).
Per ogni fotogramma (video grezzo h264 + indice, eventualmente meta' sinistra per i logger side-by-side) gira SAM 3 con
TUTTE le frasi di classi.json (cosi' le classi si contendono le regioni come nella pipeline vera), salva il fotogramma
annotato SOLO con le classi chieste (--solo) e un json con le rilevazioni. Il giudizio "bene/male" lo da' chi guarda.
Uso: ~/.asmile_depth_venv/bin/python training/segmentation/prova_classi_nuove.py --out DIR --frames lista.txt [--solo railing,chain]
lista.txt: una riga per fotogramma: <unita> <video.h264> <indice> [sx]   (sx = tieni la meta' sinistra, logger SBS)
"""
import argparse, json, os, subprocess, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seg_teacher_student as S


def frame_at(video, idx):
    w, h = S.probe_size(video)
    p = subprocess.run(["ffmpeg", "-v", "error", "-framerate", "15", "-i", video, "-vf", f"select=eq(n\\,{idx})", "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
    if len(p.stdout) < w * h * 3: return None
    return np.frombuffer(p.stdout[:w * h * 3], np.uint8).reshape(h, w, 3)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--solo", default=""); ap.add_argument("--conf", type=float, default=0.30)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    solo = set(x for x in a.solo.split(",") if x)
    th = S.ThingsTeacher("mps"); assert th.kind == "sam3"; th.pred.args.save = False; th.pred.args.show = False
    th.pred.args.conf = a.conf
    rows = []
    for ln in open(a.frames):
        if not ln.strip() or ln.startswith("#"): continue
        parts = ln.split(); unita, video, idx = parts[0], parts[1], int(parts[2]); half = len(parts) > 3 and parts[3] == "sx"
        img = frame_at(video, idx) if os.path.exists(video) else None
        if img is None: print("manca", video, idx); continue
        if half: img = np.ascontiguousarray(img[:, : img.shape[1] // 2])
        th.pred.set_image(img); r = th.pred(text=S.THINGS)[0]
        dets = []
        vis = img.copy()
        if r is not None and r.boxes is not None and len(r.boxes):
            for b, c, cf, m in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist(), r.masks.xy):
                cn = S.THINGS[c]
                dets.append(dict(c=cn, cf=round(cf, 3), box=[int(v) for v in b]))
                if solo and cn not in solo: continue
                col = (0, 255, 255) if cn in solo else (0, 200, 0)
                if len(m): cv2.polylines(vis, [m.astype(np.int32)], True, col, 2)
                cv2.putText(vis, f"{S.THINGS_IT.get(cn, cn)} {cf:.2f}", (int(b[0]), max(14, int(b[1]) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
                cv2.putText(vis, f"{S.THINGS_IT.get(cn, cn)} {cf:.2f}", (int(b[0]), max(14, int(b[1]) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 1)
        name = f"{unita}_{os.path.basename(video).replace('.h264', '')}_f{idx}"
        cv2.putText(vis, name, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imwrite(os.path.join(a.out, name + ".jpg"), cv2.resize(vis, None, fx=0.6, fy=0.6), [cv2.IMWRITE_JPEG_QUALITY, 80])
        rows.append(dict(unita=unita, video=video, frame=idx, dets=dets))
        print(name, sorted(set(d["c"] for d in dets)), flush=True)
    json.dump(dict(classi=S.CLASSI_VERSIONE, frames=rows), open(os.path.join(a.out, "rilevazioni.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
