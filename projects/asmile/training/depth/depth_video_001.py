#!/usr/bin/env python3
"""depth_video_001.py — depth densa nel corridoio + distanza per oggetto sui video in moto di #001 (2026-11-12).
SOLO #001. Calib logger/depth/calib_asmile-001.json (B30, nessuna correzione Z), rettifica stereo_common. Z = f_rect * baseline_m / d
con baseline_m=0.19656 dalla calib (NON B=0.2 come depth_seg_001.py: bug +1.7% da correggere, qui non toccato).
Campionamento: 1 fotogramma/s (t_ms), solo frame in moto (encoder ruota v>0.3 m/s su +-0.5 s, wheel_circum 0.3374 attivo).
Depth: SGBM blockSize 7, padding sx 224 px, 224 disparita' (Z>=1.22 m): il lato sx non e' cieco. Oggetti: YOLO11n-seg su CPU (SAM3 non rigirato:
niente maschere salvate, e calcolato con B=0.2); per ogni oggetto Z_med e Z_picco (regola picco_vicino fissata prima dei video, in
depth_ncc_patch_001.py). Ostacoli senza classe: pixel nel corridoio |X|<=1.5+0.03Z con altezza sopra il piano strada >=0.25 m
(piano da obstacles_v2.ground_plane, importato senza modifiche). Controllo encoder: tracce KLT 1 s, pendenza -dZ/ds.
Uso: depth_video_001.py SESSIONE [--max N]
"""
import os, sys, csv, json, time, argparse
import numpy as np, cv2
import depth_seg_001 as D
from obstacles_v2 import ground_plane
from depth_ncc_patch_001 import picco_vicino

cv2.setNumThreads(2)
PAD = NDISP = 224
OUT = os.path.join(D.HERE, "out_20261112")
_sg = cv2.StereoSGBM_create(minDisparity=0, numDisparities=NDISP, blockSize=7, P1=8 * 49, P2=32 * 49, disp12MaxDiff=1,
                            uniquenessRatio=8, speckleWindowSize=150, speckleRange=2, preFilterCap=31,
                            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)


def disparity(L, R):
    Lp = cv2.copyMakeBorder(L, 0, 0, PAD, 0, cv2.BORDER_CONSTANT, value=0)
    Rp = cv2.copyMakeBorder(R, 0, 0, PAD, 0, cv2.BORDER_CONSTANT, value=0)
    return (_sg.compute(Lp, Rp).astype(np.float32) / 16.0)[:, PAD:]


def colorize(Z, dmax=30.0):
    v = np.clip(np.nan_to_num(Z, nan=dmax) / dmax, 0, 1)
    c = cv2.applyColorMap((255 * (1 - v)).astype(np.uint8), cv2.COLORMAP_TURBO)
    c[~np.isfinite(Z)] = 0
    return c


def label(img, x, y, txt, col, sc=0.7, th=2):
    (w, h), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, th)
    x = int(min(max(0, x), 1280 - w - 6)); y = int(min(max(h + 4, y), 800 - 4))
    cv2.rectangle(img, (x, y - h - 4), (x + w + 6, y + 4), col, -1)
    cv2.putText(img, txt, (x + 3, y), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)


def enc_session(sess):
    """Encoder ruota della SOLA sessione: righe sensors_* filtrate per ora 'wall' (start..start+durata, +-5 s). depth_seg_001.enc_interp
    unisce tutti i file del giorno, ma t_ms e' uptime e riparte a ogni accensione: due accensioni si sovrappongono (085334 e 162301) -> salti
    fino a -6.4e7 conteggi. Qui no. Ritorna f(t_ms) in metri."""
    import datetime as dt, glob
    m = json.load(open(os.path.join(D.LOGS, sess, "metadata.json")))
    a = dt.datetime.fromisoformat(m["start_time"]) - dt.timedelta(seconds=5)
    b = dt.datetime.fromisoformat(m["start_time"]) + dt.timedelta(seconds=float(m.get("duration_seconds", 0)) + 5)
    T, C = [], []
    for fn in sorted(glob.glob(os.path.join(D.LOGS, "_sensors", "sensors", "sensors_" + sess[8:16] + "_*.csv"))):
        for r in csv.DictReader(open(fn)):
            if r["enc_wheel_cum"] and r["wall"]:
                w = dt.datetime.fromisoformat(r["wall"])
                if a <= w <= b:
                    T.append(float(r["t_ms"])); C.append(float(r["enc_wheel_cum"]))
    T, C = np.array(T), np.array(C) * D.M_PER_COUNT
    o = np.argsort(T)
    return (lambda x: np.interp(x, T[o], C[o])), len(T)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--max", type=int, default=10 ** 9)
    ap.add_argument("--noyolo", action="store_true"); a = ap.parse_args()
    sess = a.session if a.session.startswith("session_") else "session_" + a.session
    od = os.path.join(OUT, sess); os.makedirs(os.path.join(od, "ov"), exist_ok=True)
    rc = D.Rect(); f_px, Bm = rc.f, rc.r["baseline_m"]; cx = rc.cx
    t = np.array(D.read_t(sess, "right")); enc, n_enc = enc_session(sess); print("righe encoder", n_enc, flush=True)
    s_all = enc(t); v_all = enc(t + 500) - enc(t - 500)
    sel, last = [], -1e9
    for i in range(len(t)):
        if v_all[i] > 0.3 and t[i] - last >= 1000:
            sel.append(i); last = t[i]
    sel = sel[:a.max]; selset = set(sel)
    print(sess, "frame", len(t), "campionati (1/s, v>0.3):", len(sel), flush=True)
    if not sel:
        json.dump(dict(sess=sess, n_frames=len(t), n_campionati=0, nota="nessun tratto in moto (v>0.3)"), open(os.path.join(od, "summary.json"), "w"))
        return
    yolo = None
    if not a.noyolo:
        from ultralytics import YOLO
        yolo = YOLO(os.path.join(D.HERE, "yolo11n-seg.pt"))
    gl = D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264")); gr = D.gray_frames(os.path.join(D.LOGS, sess + "_left.h264"))
    vw = None; rows_o, rows_f = [], []; tracks, prevL, prev_t = [], None, None; done = []
    H_perp = D.CAM_H * np.cos(D.PITCH); t0 = time.time()
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i > sel[-1]: break
        if i not in selset: continue
        L, R = rc(Lr, Rr); disp = disparity(L, R)
        valid = disp > 4; Z = np.full(disp.shape, np.inf, np.float32); Z[valid] = f_px * Bm / disp[valid]
        ov = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR); ov = cv2.addWeighted(ov, 0.6, colorize(np.where(valid, Z, np.nan)), 0.4, 0)
        ov[~valid] = (0.85 * cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)[~valid]).astype(np.uint8)
        objs, covered = [], np.zeros(disp.shape, bool)
        if yolo is not None:
            r = yolo.predict(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), imgsz=640, conf=0.30, device="cpu", verbose=False)[0]
            if r.masks is not None:
                for k, poly in enumerate(r.masks.xy):
                    if len(poly) < 3: continue
                    m = np.zeros(disp.shape, np.uint8); cv2.fillPoly(m, [poly.astype(np.int32)], 1)
                    covered |= m > 0
                    me = cv2.erode(m, np.ones((5, 5), np.uint8)) > 0
                    if me.sum() < 40: me = m > 0
                    z = Z[me & valid]; z = z[z < 80]
                    if len(z) < 30 or len(z) < 0.10 * me.sum(): continue
                    zp, fr, npop = picco_vicino(z); ys, xs = np.nonzero(m)
                    X = (float(xs.mean()) - cx) * zp / f_px
                    objs.append(dict(classe=r.names[int(r.boxes.cls[k])], conf=float(r.boxes.conf[k]), Z_med=float(np.median(z)), Z_picco=zp,
                                     frac_picco=fr, n_pop=npop, n_valid=int(len(z)), frac_valid=float(len(z) / me.sum()), X=float(X),
                                     box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], poly=poly.astype(np.int32)))
        # ostacoli senza classe nel corridoio
        gp = ground_plane(disp, cx); blobs = []
        if gp is not None:
            ga, gvh, gb = gp
            vv, uu = np.mgrid[0:800, 0:1280].astype(np.float32)
            dg = ga * (vv - gvh) + gb * (uu - cx)
            with np.errstate(all="ignore"):
                h = H_perp * (disp - dg) / disp
                Xm = (uu - cx) * Z / f_px
            cand = valid & (h >= 0.25) & (h <= 2.5) & (Z >= 1.3) & (Z <= 25) & (np.abs(Xm) <= 1.5 + 0.03 * Z) & (~covered)
            cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
            n, lab, st, _ = cv2.connectedComponentsWithStats(cand)
            for q in range(1, n):
                x, y, w, hh, ar = st[q]
                if ar < 150: continue
                z = Z[lab == q]; z = z[np.isfinite(z)]
                if len(z) < 100: continue
                zp, fr, npop = picco_vicino(z)
                if w < 0.12 * f_px / zp or hh < 0.30 * f_px / zp: continue
                blobs.append(dict(classe="ostacolo", conf=0.0, Z_med=float(np.median(z)), Z_picco=zp, frac_picco=fr, n_pop=npop,
                                  n_valid=int(len(z)), frac_valid=1.0, X=float((x + w / 2 - cx) * zp / f_px), box=[int(x), int(y), int(x + w), int(y + hh)], poly=None))
        allo = objs + blobs
        for o in allo:
            inb = abs(o["X"]) <= 1.5 + 0.03 * o["Z_picco"]; o["corridoio"] = bool(inb)
            col = (255, 0, 255) if o["poly"] is None else ((0, 255, 255) if inb else (200, 200, 200))
            b = o["box"]
            if o["poly"] is not None: cv2.polylines(ov, [o["poly"]], True, col, 2)
            else: cv2.rectangle(ov, (b[0], b[1]), (b[2], b[3]), col, 2)
            label(ov, b[0], b[1] + 2, f"{o['classe']} {o['Z_picco']:.1f} m", col, 0.7, 2)
            label(ov, b[0], b[1] + 24, f"med {o['Z_med']:.1f}", col, 0.5, 1)
            rows_o.append(dict(sess=sess, frame=i, t_ms=int(t[i]), s_enc_m=round(float(s_all[i]), 2), v_ms=round(float(v_all[i]), 2),
                               **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items() if k not in ("poly", "box")},
                               box=" ".join(map(str, b))))
        co = [o["Z_picco"] for o in allo if o["corridoio"]]
        first = min(co) if co else None
        vf = float(valid[400:760, 200:1080].mean())
        rows_f.append(dict(sess=sess, frame=i, t_ms=int(t[i]), s_enc_m=round(float(s_all[i]), 2), v_ms=round(float(v_all[i]), 2),
                           n_obj=len(objs), n_blob=len(blobs), primo_corridoio_m=None if first is None else round(first, 2), valid_frac_basso=round(vf, 3)))
        bar = f"#001 {sess[8:]} f{i} t={(t[i]-t[0])/1000:.0f}s v={v_all[i]:.1f} m/s | corridoio: " + (f"primo {first:.1f} m" if first else "libero") + f" | validi {vf*100:.0f}%"
        cv2.rectangle(ov, (0, 772), (1280, 800), (0, 0, 0), -1); cv2.putText(ov, bar, (6, 793), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(od, "ov", f"f{i:06d}.jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 85])
        small = cv2.resize(ov, (960, 600))
        if vw is None: vw = cv2.VideoWriter(os.path.join(od, f"depth_{sess[8:]}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 3, (960, 600))
        vw.write(small)
        # KLT 1 s
        gcur = L
        if prevL is not None and t[i] - prev_t <= 1500 and tracks:
            p0 = np.array([tr["p"] for tr in tracks], np.float32).reshape(-1, 1, 2)
            p1, st1, _ = cv2.calcOpticalFlowPyrLK(prevL, gcur, p0, None, winSize=(31, 31), maxLevel=4)
            p0b, st2, _ = cv2.calcOpticalFlowPyrLK(gcur, prevL, p1, None, winSize=(31, 31), maxLevel=4)
            ok = (st1[:, 0] == 1) & (st2[:, 0] == 1) & (np.abs(p0b - p0).reshape(-1, 2).max(1) < 1.0)
            keep = []
            for tr, p, o_ in zip(tracks, p1.reshape(-1, 2), ok):
                x, y = int(round(p[0])), int(round(p[1]))
                if o_ and 5 <= x < 1275 and 5 <= y < 795:
                    dd = disp[y - 2:y + 3, x - 2:x + 3]; dd = dd[dd > 4]
                    if len(dd) >= 8:
                        zz = f_px * Bm / float(np.median(dd))
                        if 2.0 <= zz <= 14.0:
                            tr["p"] = (float(p[0]), float(p[1])); tr["z"].append(zz); tr["s"].append(float(s_all[i])); keep.append(tr); continue
                done.append(tr)
            tracks = keep
        else:
            done += tracks; tracks = []
        if len(tracks) < 200:
            pts = cv2.goodFeaturesToTrack(L[:500], 300, 0.01, 12)
            if pts is not None:
                for p in pts.reshape(-1, 2):
                    x, y = int(p[0]), int(p[1])
                    if any((tr["p"][0] - x) ** 2 + (tr["p"][1] - y) ** 2 < 144 for tr in tracks): continue
                    dd = disp[y - 2:y + 3, x - 2:x + 3]; dd = dd[dd > 4]
                    if len(dd) >= 8:
                        zz = f_px * Bm / float(np.median(dd))
                        if 2.0 <= zz <= 14.0: tracks.append(dict(p=(float(x), float(y)), z=[zz], s=[float(s_all[i])]))
        prevL, prev_t = L.copy(), t[i]
        if len(rows_f) % 20 == 0:
            print(f"  {len(rows_f)}/{len(sel)}  {(time.time()-t0)/len(rows_f):.2f} s/campione", flush=True)
    if vw: vw.release()
    done += tracks
    ratios = []
    for tr in done:
        if len(tr["z"]) >= 5 and tr["s"][-1] - tr["s"][0] >= 3.0:
            sl = np.polyfit(tr["s"], tr["z"], 1)[0]; ratios.append(-sl)
    ratios = np.array(ratios)
    klt = dict(n_tracce=int(len(ratios)), pendenza_mediana=float(np.median(ratios)) if len(ratios) else None,
               iqr=[float(np.percentile(ratios, 25)), float(np.percentile(ratios, 75))] if len(ratios) else None,
               nota="pendenza = -dZ/ds_encoder su feature statiche (attesa 1.0 se Z ed encoder sono entrambi giusti; non filtra le feature in moto)")
    for name, rows in (("objects.csv", rows_o), ("frames.csv", rows_f)):
        if rows:
            with open(os.path.join(od, name), "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summ = dict(sess=sess, n_frames=len(t), n_campionati=len(rows_f), durata_moto_s=len(rows_f), n_oggetti=len(rows_o),
                s_per_campione=round((time.time() - t0) / max(1, len(rows_f)), 2), klt=klt,
                valid_frac_basso_mediana=float(np.median([r["valid_frac_basso"] for r in rows_f])),
                frame_con_ostacolo_corridoio=int(sum(r["primo_corridoio_m"] is not None for r in rows_f)),
                dist_enc_m=float(s_all[sel[-1]] - s_all[sel[0]]))
    json.dump(summ, open(os.path.join(od, "summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
