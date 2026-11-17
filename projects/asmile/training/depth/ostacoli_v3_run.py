#!/usr/bin/env python3
"""ostacoli_v3_run.py <frames.json> <tag> [--noimg] [--K 3] — L1.ostacoli v3 (2026-11-10), #001, calib PROVVISORIA. NON apre verita_occhio*.json.
Conferma CAUSALE: un blob a Z>=5 m e' confermato se compare in t-K (K=3, 0.2 s nel passato) con X entro 0.8 m e
  (a) Z entro 0.5+12% della Z prevista dall'encoder ruota, OPPURE
  (b) (oggetto in movimento, nessuna dipendenza dall'encoder) |Z_prima - Z| <= 2.0+0.15 Z, |dX|<=0.8 e IoU box >= 0.3.
Z < 5 m: confermato subito (un ostacolo vicino vale subito). Nessun frame futuro (t+k) e' mai usato.
Bande: corridoio |X|<=1.5+0.03 Z ; laterale_vicino Z<6 e |X|<=2.5 ; laterale resto (fino a 4.5)."""
import json, os, sys, time, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D, obstacles_v3 as O
a = sys.argv[1:]; K = 3
if "--K" in a: K = int(a[a.index("--K") + 1])
noimg = "--noimg" in a
fl = json.load(open(a[0] if os.path.isabs(a[0]) else os.path.join(HERE, a[0]))); tag = a[1]
OUT = os.path.join(HERE, "out_20261110")
SESS = fl["sessione"]; want = {f["frame"]: f for f in fl["frames"]}
need = sorted({f + d for f in want for d in (-K, 0)})
if not noimg:
    for d_ in (f"clean_{tag}", f"overlay_v3_{tag}"): os.makedirs(os.path.join(OUT, d_), exist_ok=True)
t_all = np.array(D.read_t(SESS, "right"), float); enc = D.enc_interp(t_all[0], t_all[-1])
rc = D.Rect(); vL = os.path.join(D.LOGS, f"{SESS}_right.h264"); vR = os.path.join(D.LOGS, f"{SESS}_left.h264")
cache = {}; imgs = {}; ms = {}; last = max(need)
for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
    if i > last: break
    if i not in need: continue
    L, R = rc(Lr, Rr); t0 = time.time()
    disp = O.disparity_v3(L, R); obs, g = O.obstacles_v3(rc, disp)
    ms[i] = (time.time() - t0) * 1000; cache[i] = (obs, g)
    if i in want: imgs[i] = L
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); I = ix * iy
    U = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - I
    return I / U if U > 0 else 0
def conferma(o, t):
    k = t - K
    if o["Z"] < 5.0: return True, "vicino<5m"
    if k not in cache: return False, "nessun_passato"
    zp = o["Z"] - float(enc(t_all[k]) - enc(t_all[t]))
    for p in cache[k][0]:
        if abs(p["X"] - o["X"]) > 0.8: continue
        if abs(p["Z"] - zp) < 0.5 + 0.12 * zp: return True, "t-3_encoder"
        if abs(p["Z"] - o["Z"]) <= 2.0 + 0.15 * o["Z"] and iou(p["box"], o["box"]) >= 0.3: return True, "t-3_movimento"
    return False, "non_confermato"
res = []
for i in sorted(want):
    obs, g = cache[i]; ov = cv2.cvtColor(imgs[i], cv2.COLOR_GRAY2BGR); dets = []
    for o in obs:
        conf, how = conferma(o, i)
        lato = "sx" if o["X"] < -1.2 else ("dx" if o["X"] > 1.2 else "centro")
        z = o["Z"]; fascia = "<5" if z < 5 else ("5-12" if z <= 12 else "12-15")
        if z > 15: continue
        dets.append({"box": o["box"], "Z_m": round(z, 2), "X_m": round(o["X"], 2), "h_m": round(o["h_med"], 2), "lato": lato, "fascia_Z": fascia,
                     "banda": o["banda"], "multiframe": bool(conf), "conferma": how})
        if conf:
            col = {"corridoio": (0, 255, 255), "laterale_vicino": (255, 0, 255), "laterale": (255, 255, 0)}[o["banda"]]
            ov[o["mask"] > 0] = (0.6 * ov[o["mask"] > 0] + 0.4 * np.array([255, 0, 255])).astype(np.uint8)
            b = o["box"]; cv2.rectangle(ov, tuple(b[:2]), tuple(b[2:]), col, 2)
            cv2.putText(ov, f"{z:.1f}m {o['banda'][:4]}", (b[0], max(20, b[1] - 6)), 0, 0.8, col, 2)
    if not noimg:
        cv2.imwrite(f"{OUT}/clean_{tag}/f{i:05d}.png", imgs[i]); cv2.imwrite(f"{OUT}/overlay_v3_{tag}/f{i:05d}.jpg", ov)
    res.append({"frame": i, "t_ms": want[i]["t_ms"], "ms_frame_singolo": round(ms[i], 1), "n_confermati": sum(d["multiframe"] for d in dets),
                "piano_a_vh_b": None if g is None else [round(x, 4) for x in g], "det": dets})
    print(i, len(dets), sum(d["multiframe"] and d["banda"] == "corridoio" for d in dets), f"{ms[i]:.0f}ms", flush=True)
tot = sum(ms.values())
json.dump({"versione": "v3", "calib": "PROVVISORIA, punto A in corso", "unita": "asmile-001", "sessione": SESS, "K_frame": K,
           "definizione": "corridoio |X|<=1.5+0.03 Z (centro box, Z p20); laterale_vicino Z<6 e |X|<=2.5; laterale resto fino 4.5; conta multiframe=true (causale t-3; Z<5 m sempre true); Z 1.8-15; fasce <5, 5-12, 12-15",
           "ms_per_frame_singolo_medio": round(float(np.mean(list(ms.values()))), 1),
           "ms_per_frame_con_coerenza": round(tot / len(want), 1), "frames": res}, open(f"{OUT}/ostacoli_det_v3_{tag}.json", "w"), indent=1)
print("ms/frame singolo", np.mean(list(ms.values())).round(1), "con conferma causale", round(tot / len(want), 1))
