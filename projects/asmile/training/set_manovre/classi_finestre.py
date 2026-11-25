#!/usr/bin/env python3
"""classi_finestre.py — SOLO classi (SAM 3 cose + Mask2Former sfondo, lista unica training/segmentation/classi.json) sui
fotogrammi attorno alle manovre delle unita' SENZA calibrazione valida per la distanza (logger001, logger02) o delle
sessioni #001 per cui la calib validata non e' dimostrata. Nessuna distanza qui: mai usare la calib di un'altra unita'.
Ingresso: CSV con colonne video,frame[,meta]  (meta = 'sx' per i logger side-by-side: si tiene la camera sinistra del file)
Uscita: <out>/<nome_video>_f<frame>.json  {frame, video, dets:[{c, cf, box}], fracs:{sfondo: frazione}, classi: versione}
Riprende da dove era arrivato. Uso:
  nice -n 10 ~/.asmile_depth_venv/bin/python training/set_manovre/classi_finestre.py --lista L.csv --out DIR
"""
import argparse, csv, json, os, sys
from collections import defaultdict
import numpy as np, cv2
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "training", "segmentation")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seg_teacher_student as S
import fotogrammi as F


def nome_base(video):
    """nome del file di uscita: per asmile2 il video si chiama sempre video.h264 -> si antepone la sessione"""
    b = os.path.basename(video).replace(".h264", "")
    return os.path.basename(os.path.dirname(video)) + "_video" if b == "video" else b


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lista", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    per_video = defaultdict(set); meta = {}
    for r in csv.DictReader(open(a.lista)):
        per_video[r["video"]].add(int(r["frame"])); meta[r["video"]] = r.get("meta", "")
    th = S.ThingsTeacher("mps"); assert th.kind == "sam3"; th.pred.args.save = False; th.pred.args.show = False
    stuff = S.StuffTeacher("mps")
    n = 0
    for video in sorted(per_video):
        base = nome_base(video)
        todo = [i for i in sorted(per_video[video]) if not os.path.exists(os.path.join(a.out, f"{base}_f{i:06d}.json"))]
        if not todo: continue
        G = F.grab(os.path.join(ROOT, video), todo, meta=meta[video] or None)
        for i in todo:
            img = G.get(i)
            if img is None: continue
            th.pred.set_image(img); res = th.pred(text=S.THINGS)[0]
            dets = []
            if res is not None and res.boxes is not None and len(res.boxes):
                for b, c, cf in zip(res.boxes.xyxy.tolist(), res.boxes.cls.int().tolist(), res.boxes.conf.tolist()):
                    dets.append(dict(c=S.THINGS[c], cf=round(cf, 3), box=[int(v) for v in b]))
            lab = cv2.resize(stuff(img), (320, 200), interpolation=cv2.INTER_NEAREST)
            fr = {k: round(float((lab == j).mean()), 4) for j, k in enumerate(S.STUFF)}
            json.dump(dict(frame=i, video=video, dets=dets, fracs=fr, classi=S.CLASSI_VERSIONE), open(os.path.join(a.out, f"{base}_f{i:06d}.json"), "w"))
            n += 1
            if n % 20 == 0: print(n, flush=True)
    print("fatto", n)


if __name__ == "__main__":
    main()
