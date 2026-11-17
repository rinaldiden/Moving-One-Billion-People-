#!/usr/bin/env python3
"""L1.ostacoli in ombra (2026-11-10): strato ostacolo SGBM (depth_seg_001.obstacles, invariato) sui frame di frames_ostacoli.json.
#001, calib PROVVISORIA (punto A in corso). Niente SAM/GPU. Scrive clean/ (rettificata sx senza overlay), overlay/, ostacoli_det.json."""
import json, os, sys, time, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D
OUT = os.path.join(HERE, "out_20261110")
fl = json.load(open(os.path.join(OUT, "frames_ostacoli.json")))
SESS = fl["sessione"]; want = {f["frame"]: f for f in fl["frames"]}
os.makedirs(OUT + "/clean", exist_ok=True); os.makedirs(OUT + "/overlay", exist_ok=True)
rc = D.Rect()
vL = os.path.join(D.LOGS, f"{SESS}_right.h264"); vR = os.path.join(D.LOGS, f"{SESS}_left.h264")
res = []; last = max(want)
for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
    if i > last: break
    if i not in want: continue
    L, R = rc(Lr, Rr)
    cv2.imwrite(f"{OUT}/clean/f{i:05d}.png", L)
    t0 = time.time()
    disp = rc.disparity(L, R)
    obs = D.obstacles(rc, disp, np.zeros((D.H, D.W), np.uint8))
    ms = (time.time() - t0) * 1000
    ov = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR); dets = []
    for z, box, mk, h in obs:
        uc = 0.5 * (box[0] + box[2]); X = (uc - rc.cx) * z / rc.f
        lato = "sx" if X < -1.2 else ("dx" if X > 1.2 else "centro")
        fascia = "<5" if z < 5 else ("5-12" if z <= 12 else "12-15")
        dets.append({"box": box, "Z_m": round(z, 2), "X_m": round(float(X), 2), "h_m": round(h, 2), "lato": lato, "fascia_Z": fascia})
        ov[mk > 0] = (0.5 * ov[mk > 0] + 0.5 * np.array([255, 0, 255])).astype(np.uint8)
        cv2.rectangle(ov, tuple(box[:2]), tuple(box[2:]), (0, 255, 255), 2)
        cv2.putText(ov, f"{z:.1f}m {lato}", (box[0], max(20, box[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.imwrite(f"{OUT}/overlay/f{i:05d}.jpg", ov)
    res.append({"frame": i, "t_ms": want[i]["t_ms"], "ms": round(ms, 1), "n": len(dets), "det": dets})
    print(i, len(dets), f"{ms:.0f}ms", flush=True)
json.dump({"calib": "PROVVISORIA, punto A in corso", "unita": "asmile-001", "sessione": SESS,
           "definizione": "lato: |X|<=1.2 m centro, altrimenti sx/dx (X=(u_c-cx)Z/f); fascia Z: <5, 5-12 (12-15 fuori gate); corridoio |X|<=4.5 m, Z 2-15 m",
           "ms_medio": round(float(np.mean([r['ms'] for r in res])), 1), "frames": res}, open(f"{OUT}/ostacoli_det.json", "w"), indent=1)
