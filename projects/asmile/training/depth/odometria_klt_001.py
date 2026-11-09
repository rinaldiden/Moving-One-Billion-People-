#!/usr/bin/env python3
"""odometria_klt_001.py — gate L1.depth_moto #001, versione NON circolare (veto 1/3 di asmile-occhio).
Oggetti COMPATTI e FERMI per classe (palo, bollard, cestino, cono) scelti dal CSV SOLO per classe/conf/posizione (mai per Z
in rapporto all'encoder). Si segmenta con SAM 3 al frame di partenza, poi la maschera viene SEGUITA frame per frame (15 fps)
con KLT + similitudine (nessuna associazione fra passate SAM, nessun filtro su Z). Ad ogni frame: SGBM rettificato e
mask_depth() (stessa misura della pipeline). Z(t) contro S(t) = metri encoder ruota (2.1219e-5 m/count).
Atteso per oggetto fermo: Z = A - c*S, c = cos(pitch 7.4) = 0.992 (componente lungo l'asse OTTICO). Si riporta pendenza OLS
e Theil-Sen, residuo rms (m) e errore % vs retta a pendenza fissa c.
Uso: ~/.asmile_depth_venv/bin/python training/depth/odometria_klt_001.py --csv out_20261109/objects_giro.csv --out X.json
"""
import argparse, csv, json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depth_seg_001 import Rect, gray_frames, mask_depth, read_t, enc_interp, iou, LOGS, W, H
C = np.cos(np.radians(7.4))
COMPACT = ("pole", "bollard", "trash can", "traffic cone")


def select(csvp, maxn, zlo, zhi, ulim, min_conf, f0, f1, classes=COMPACT):
    cand = []
    for r in csv.DictReader(open(csvp)):
        if r["classe"] not in classes or not r["Z_m"] or float(r["conf"]) < min_conf or int(r["n_valid"]) < 150:
            continue
        Z, u, fr = float(r["Z_m"]), float(r["u_c"]), int(r["frame"])
        if not (zlo <= Z <= zhi) or abs(u - 640) > ulim or not (f0 <= fr <= f1):
            continue
        cand.append((fr, r["classe"], [float(r[k]) for k in ("x1", "y1", "x2", "y2")], Z, u))
    cand.sort()
    chosen = []
    for c in cand:                                    # niente doppioni: stessa zona/classe entro 150 frame
        if any(abs(c[0] - o[0]) < 150 and iou(c[2], o[2]) > 0.2 for o in chosen):
            continue
        chosen.append(c)
    step = max(1, len(chosen) // maxn)
    return chosen[::step][:maxn]


def theil_sen(x, y):
    sl = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x)) for j in range(i + 1, len(x)) if abs(x[j] - x[i]) > 0.3]
    return float(np.median(sl)) if sl else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--session", default="session_20261109_094146"); ap.add_argument("--maxn", type=int, default=40)
    ap.add_argument("--zlo", type=float, default=8); ap.add_argument("--zhi", type=float, default=26)
    ap.add_argument("--ulim", type=float, default=450); ap.add_argument("--conf", type=float, default=0.7)
    ap.add_argument("--f0", type=int, default=1800); ap.add_argument("--f1", type=int, default=10000)
    ap.add_argument("--classes", default=",".join(COMPACT)); ap.add_argument("--maxlen", type=int, default=150); ap.add_argument("--device", default="mps")
    a = ap.parse_args()
    from seg_teacher_student import ThingsTeacher, THINGS
    sel = select(a.csv, a.maxn, a.zlo, a.zhi, a.ulim, a.conf, a.f0, a.f1, tuple(a.classes.split(",")))
    print("oggetti scelti:", len(sel), [(s[0], s[1]) for s in sel], flush=True)
    rc = Rect(); tL = read_t(a.session, "right")
    Sf = enc_interp(tL[a.f0], tL[min(len(tL) - 1, a.f1 + a.maxlen)])
    teacher = ThingsTeacher(a.device); teacher.pred.args.save = False
    gl = gray_frames(os.path.join(LOGS, f"{a.session}_right.h264")); gr = gray_frames(os.path.join(LOGS, f"{a.session}_left.h264"))
    starts = {}
    for s in sel: starts.setdefault(s[0], []).append(s)
    active, done = [], []
    last = max(starts) + a.maxlen
    prevL = None
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i < min(starts):
            continue
        if i > last or (not active and i > max(starts)):
            break
        L, R = rc(Lr, Rr)
        need_disp = bool(active) or i in starts
        disp = rc.disparity(L, R) if need_disp else None
        # 1) avanza i tracker
        for ob in list(active):
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prevL, L, ob["pts"], None, winSize=(21, 21), maxLevel=3)
            p0b, st2, _ = cv2.calcOpticalFlowPyrLK(L, prevL, p1, None, winSize=(21, 21), maxLevel=3)
            ok = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(p0b - ob["pts"], axis=2)[:, 0] < 1.0)
            if ok.sum() < 5:
                ob["why"] = "persi punti"; active.remove(ob); done.append(ob); continue
            M, inl = cv2.estimateAffinePartial2D(ob["pts"][ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if M is None:
                ob["why"] = "affine"; active.remove(ob); done.append(ob); continue
            ob["mask"] = cv2.warpAffine(ob["mask"], M, (W, H), flags=cv2.INTER_NEAREST)
            ob["pts"] = p1[ok]
            if len(ob["pts"]) < 25:                       # ripopola i punti dentro la maschera
                more = cv2.goodFeaturesToTrack(L, 60, 0.01, 3, mask=cv2.erode(ob["mask"], np.ones((5, 5), np.uint8)))
                if more is not None: ob["pts"] = np.vstack([ob["pts"], more[:60]]).astype(np.float32)
            ys, xs = np.nonzero(ob["mask"])
            if len(xs) < 60 or xs.min() < 2 or xs.max() > W - 3 or ys.max() > H - 3:
                ob["why"] = "uscito"; active.remove(ob); done.append(ob); continue
            bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            md = mask_depth(rc, disp, ob["mask"], thin_frac=len(xs) / (bw * bh), classe=ob["cls"])
            if md: ob["ser"].append((i, tL[i], md[0], float(Sf(tL[i])), float(xs.mean())))
            if len(ob["ser"]) and ob["ser"][-1][2] < 2.0 or i - ob["i0"] >= a.maxlen:
                ob["why"] = "fine"; active.remove(ob); done.append(ob)
        # 2) nuovi oggetti: SAM 3 al frame di partenza
        for s in starts.get(i, []):
            r = teacher(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR))
            if r is None or r.boxes is None or not len(r.boxes) or r.masks is None:
                continue
            best, bs = None, 0.4
            for k, (b, c) in enumerate(zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist())):
                sc = iou(b, s[2])
                if THINGS[c] == s[1] and sc > bs: best, bs = k, sc
            if best is None: continue
            m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [r.masks.xy[best].astype(np.int32)], 1)
            pts = cv2.goodFeaturesToTrack(L, 80, 0.01, 3, mask=cv2.erode(m, np.ones((5, 5), np.uint8)))
            if pts is None or len(pts) < 8: continue
            ys, xs = np.nonzero(m)
            md = mask_depth(rc, disp, m, thin_frac=len(xs) / ((np.ptp(xs) + 1) * (np.ptp(ys) + 1)), classe=s[1])
            ob = dict(cls=s[1], i0=i, mask=m, pts=pts.astype(np.float32), ser=[], conf=0)
            if md: ob["ser"].append((i, tL[i], md[0], float(Sf(tL[i])), float(xs.mean())))
            active.append(ob); print(f"f{i} avvio {s[1]} Z={s[3]}", flush=True)
        prevL = L
    done += active
    res = []
    for ob in done:
        ser = np.array(ob["ser"])
        if len(ser) < 8: continue
        Z, S = ser[:, 2], ser[:, 3]
        span = S.max() - S.min()
        if span < 3.0: continue
        ols = np.polyfit(S, Z, 1); r = Z - np.polyval(ols, S)
        ts = theil_sen(S, Z)
        A = float(np.median(Z + C * S)); e = (Z / (A - C * S) - 1) * 100       # retta a pendenza FISSA c, A mediana
        res.append(dict(classe=ob["cls"], f0=int(ser[0, 0]), f1=int(ser[-1, 0]), n=len(ser), span_m=round(float(span), 1),
                        Z0=round(float(Z[0]), 1), Z1=round(float(Z[-1]), 1), slope_ols=round(float(-ols[0]), 3),
                        slope_ts=round(-ts, 3), rms_m=round(float(np.sqrt(np.mean(r ** 2))), 2),
                        err_fix_mae_pct=round(float(np.mean(np.abs(e))), 1), u_med=int(np.median(ser[:, 4])), fine=ob.get("why"),
                        pts=[(int(x[0]), round(float(x[2]), 2), round(float(x[3]), 2), int(x[4])) for x in ser]))
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"tracce utili (n>=8, S>=3 m): {len(res)}  atteso pendenza {C:.3f}")
    for t in res:
        print(f"{t['classe']:12s} f{t['f0']}-{t['f1']} n={t['n']:3d} S={t['span_m']:5.1f} Z {t['Z0']}->{t['Z1']} "
              f"pend OLS {t['slope_ols']:+.2f} TS {t['slope_ts']:+.2f} rms {t['rms_m']} m  MAE(c fisso) {t['err_fix_mae_pct']}%  u~{t['u_med']} [{t['fine']}]")
    if res:
        so = np.array([t["slope_ts"] for t in res]); print("pendenza TS: mediana %.3f  p25-p75 %.3f-%.3f" % (np.median(so), *np.percentile(so, [25, 75])))


if __name__ == "__main__":
    main()
