#!/usr/bin/env python3
"""ostacoli_v2_run.py <frames.json> <tag> [--noimg] [--K 3] [--solo-primo]  — L1.ostacoli v2 (2026-11-10), #001, calib PROVVISORIA.
Per ogni frame t: obstacles_v2 su t, t-K, t+K (disparita' v2 con padding sx); un blob di t e' CONFERMATO se esiste in t-K o t+K un blob
con X entro 0.7 m e Z entro 0.5+12% della Z prevista dall'odometria (encoder ruota: Z_k = Z -(s_k - s_t)). Scrive
out_20261110/ostacoli_det_v2_<tag>.json, overlay_v2_<tag>/ e clean_<tag>/ (rettificata sx senza overlay). NON apre verita_occhio.json."""
import json, os, sys, time, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D, obstacles_v2 as O
a = sys.argv[1:]; K = 3
if "--K" in a: K = int(a[a.index("--K") + 1])
noimg = "--noimg" in a
fl = json.load(open(a[0] if os.path.isabs(a[0]) else os.path.join(HERE, a[0]))); tag = a[1]
OUT = os.path.join(HERE, "out_20261110")
SESS = fl["sessione"]; want = {f["frame"]: f for f in fl["frames"]}
need = sorted({f + d for f in want for d in (-K, 0, K)})
if not noimg:
    for d_ in (f"clean_{tag}", f"overlay_v2_{tag}"): os.makedirs(os.path.join(OUT, d_), exist_ok=True)
t_all = np.array(D.read_t(SESS, "right"), float); enc = D.enc_interp(t_all[0], t_all[-1])
rc = D.Rect(); vL = os.path.join(D.LOGS, f"{SESS}_right.h264"); vR = os.path.join(D.LOGS, f"{SESS}_left.h264")
cache = {}; imgs = {}; ms = {}; last = max(need)
for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
    if i > last: break
    if i not in need: continue
    L, R = rc(Lr, Rr); t0 = time.time()
    disp = O.disparity_v2(L, R); obs, g = O.obstacles_v2(rc, disp)
    ms[i] = (time.time() - t0) * 1000; cache[i] = (obs, g)
    if i in want: imgs[i] = L
def match(o, t, k):
    if k not in cache: return False
    dz = float(enc(t_all[k]) - enc(t_all[t]))
    zp = o["Z"] - dz
    for p in cache[k][0]:
        if abs(p["X"] - o["X"]) < 0.7 and abs(p["Z"] - zp) < 0.5 + 0.12 * zp: return True
    return False
res = []
for i in sorted(want):
    obs, g = cache[i]; ov = cv2.cvtColor(imgs[i], cv2.COLOR_GRAY2BGR); dets = []
    for o in obs:
        mm, mp = match(o, i, i - K), match(o, i, i + K)
        conf = mm or mp
        lato = "sx" if o["X"] < -1.2 else ("dx" if o["X"] > 1.2 else "centro")
        z = o["Z"]; fascia = "<5" if z < 5 else ("5-12" if z <= 12 else "12-15")
        d = {"box": o["box"], "Z_m": round(z, 2), "X_m": round(o["X"], 2), "h_m": round(o["h_med"], 2), "lato": lato, "fascia_Z": fascia,
             "banda": o["banda"], "multiframe": bool(conf), "visto_prima": bool(mm), "visto_dopo": bool(mp)}
        dets.append(d)
        if conf:
            col = (0, 255, 255) if o["banda"] == "corridoio" else (255, 255, 0)
            ov[o["mask"] > 0] = (0.5 * ov[o["mask"] > 0] + 0.5 * np.array([255, 0, 255])).astype(np.uint8)
            b = o["box"]; cv2.rectangle(ov, tuple(b[:2]), tuple(b[2:]), col, 2)
            cv2.putText(ov, f"{z:.1f}m {lato}{'' if o['banda']=='corridoio' else ' (lat)'}", (b[0], max(20, b[1] - 6)), 0, 0.8, col, 2)
    if not noimg:
        cv2.imwrite(f"{OUT}/clean_{tag}/f{i:05d}.png", imgs[i]); cv2.imwrite(f"{OUT}/overlay_v2_{tag}/f{i:05d}.jpg", ov)
    res.append({"frame": i, "t_ms": want[i]["t_ms"], "ms_frame_singolo": round(ms[i], 1), "n_confermati": sum(d["multiframe"] for d in dets),
                "piano_a_vh_b": None if g is None else [round(x, 4) for x in g], "det": dets})
    print(i, len(dets), sum(d["multiframe"] for d in dets), f"{ms[i]:.0f}ms", flush=True)
tot = sum(ms.values())
json.dump({"versione": "v2", "calib": "PROVVISORIA, punto A in corso", "unita": "asmile-001", "sessione": SESS, "K_frame": K,
           "definizione": "lato: |X|<=1.2 centro, altrimenti sx/dx; banda 'corridoio' = |X_centro|<=1.5 m (box entro 1.8 m), altrimenti 'laterale' (FUORI dal conteggio); conta solo multiframe=true; fasce Z <5, 5-12, 12-15 (fuori gate); Z 2-15 m",
           "ms_per_frame_singolo_medio": round(float(np.mean(list(ms.values()))), 1),
           "ms_per_frame_con_coerenza": round(tot / len(want), 1), "frames": res}, open(f"{OUT}/ostacoli_det_v2_{tag}.json", "w"), indent=1)
print("ms/frame singolo", np.mean(list(ms.values())).round(1), "con coerenza (3 disparita'/frame)", round(tot / len(want), 1))
