#!/usr/bin/env python3
"""
reverse_baseline_test.py — PROVA A RITROSO della pipeline depth.

Dato che la baseline è NOTA (200mm), verifichiamo che la pipeline sia geometricamente
consistente RICAVANDOLA dai dati, invece di usarla.

Metodo (focale-indipendente): un oggetto di altezza reale nota (persona in piedi ~1.70m)
  depth_da_dimensione = f · H_real / h_px        (pinhole, monoculare)
  depth_da_stereo      = f · baseline / disp     (stereo)
uguagliando → la focale si semplifica →  **baseline = H_real · disp / h_px**
Se la pipeline/geometria è giusta, torna ~200mm. (Su video mal-rettificati verrà diverso:
è anche un check della rettifica.)

Gira nel venv. Uso:
  ~/.asmile_depth_venv/bin/python reverse_baseline_test.py --video <...> --preset camarray2560 --nframes 20
"""
import argparse
import os
import sys

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stereo_depth import PRESETS, compute_depth  # noqa

H_PERSON_M = 1.70        # altezza reale assunta per una persona in piedi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--preset", default="camarray2560", choices=list(PRESETS))
    ap.add_argument("--nframes", type=int, default=20)
    ap.add_argument("--Hreal", type=float, default=H_PERSON_M)
    ap.add_argument("--known-depth", type=float, default=None,
                    help="modo RIGHELLO (esatto): distanza REALE in m di un oggetto misurata "
                         "col metro. Usa l'oggetto piu' grande nel frame: baseline = "
                         "dist_nota*disparita/focale. Su #001 ben calibrato deve dare ~200mm.")
    a = ap.parse_args()
    cfg = PRESETS[a.preset]
    model = YOLO("yolo11n-seg.pt")

    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
    step = max(1, n // a.nframes)
    recovered = []
    i = done = 0
    while done < a.nframes:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mid = g.shape[1] // 2
            L, R = g[:, :mid], g[:, mid:]
            _, disp = compute_depth(L, R, cfg["focal_px"], cfg["baseline_mm"],
                                    cfg["sgbm"], cfg["sgbm_swap"])
            Lbgr = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
            res = model.predict(Lbgr, conf=0.4, verbose=False)[0]
            if a.known_depth is not None and res.boxes is not None and len(res.boxes):
                # MODO RIGHELLO (esatto): oggetto piu' grande, distanza reale NOTA (metro)
                #   baseline = dist_nota * disparita / focale   → su #001 calibrato deve dare ~200mm
                xy = res.boxes.xyxy.cpu().numpy()
                k = int(np.argmax((xy[:, 2] - xy[:, 0]) * (xy[:, 3] - xy[:, 1])))
                x1, y1, x2, y2 = xy[k].astype(int)
                reg = disp[y1:y2, x1:x2]
                dv = reg[reg > 1]
                if dv.size >= 100:
                    d_med = float(np.median(dv))
                    b_rec = a.known_depth * d_med / cfg["focal_px"] * 1000.0
                    recovered.append(b_rec)
                    print(f"  frame {i}: {model.names[int(res.boxes.cls[k])]} @ {a.known_depth}m (metro) "
                          f"disp={d_med:.1f} → baseline={b_rec:.0f}mm")
            elif res.boxes is not None:
                for k in range(len(res.boxes)):
                    if model.names[int(res.boxes.cls[k])] != "person":
                        continue
                    x1, y1, x2, y2 = res.boxes.xyxy[k].cpu().numpy().astype(int)
                    h_px = y2 - y1
                    # persona deve essere INTERA e in piedi: box alto, non tagliato ai bordi
                    if h_px < 120 or y1 < 3 or y2 > L.shape[0] - 3 or h_px < (x2 - x1) * 1.6:
                        continue
                    reg = disp[y1:y2, x1:x2]
                    dv = reg[reg > 1]
                    if dv.size < 100:
                        continue
                    d_med = float(np.median(dv))
                    b_rec = a.Hreal * d_med / h_px * 1000.0     # mm
                    recovered.append(b_rec)
                    print(f"  frame {i}: persona h={h_px}px disp={d_med:.1f} → baseline_ricavata={b_rec:.0f}mm")
            done += 1
        i += 1
    cap.release()
    if recovered:
        r = np.array(recovered)
        print(f"\n[RISULTATO] baseline NOTA=200mm · RICAVATA mediana={np.median(r):.0f}mm "
              f"(n={len(r)}, range {r.min():.0f}-{r.max():.0f}) → errore {abs(np.median(r)-200)/200*100:.0f}%")
    else:
        print("[!] nessuna persona in piedi intera trovata (video non adatto alla prova a ritroso)")


if __name__ == "__main__":
    main()
