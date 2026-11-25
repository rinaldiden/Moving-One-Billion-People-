#!/usr/bin/env python3
"""frenate_estrai_001.py — estrazione per-fotogramma per la classificazione delle frenate di Daniele (#001, giro 20261125_095037).
SOLO Mac. Camera di segmentazione = la FISICAMENTE DESTRA (file *_left.h264), pulita; la sinistra fisica (file *_right) ha la barra sfocata
e serve solo allo stereo. Calib VALIDATA logger/depth/calib_asmile-001.json.
Per ogni fotogramma della griglia (i % STEP == 0, 3 Hz):
  - SAM 3 (stesso THINGS di seg_teacher_student) sulla destra rettificata -> istanze (classe, conf, box, poligono semplificato)
  - SGBM mezza risoluzione con riferimento DESTRA (trucco del ribaltamento) -> Z stereo per istanza (mediana disparita' valida sulla maschera)
  - piano strada (a, vh) da RANSAC sulla stessa disparita' -> Z da punto di contatto (riga piu' bassa della maschera)
  - Mask2Former Mapillary (STUFF) -> mappa sfondo 104x166 (salvata) + bordi del guidabile a Z=4..20 m
Uscite: <out>/f<frame>.json (piccoli) + <out>/stuff_f<frame>.npy ; si riprende da dove era arrivato.
Uso: ~/.asmile_depth_venv/bin/python frenate_estrai_001.py --start 0 --end 2736 --out DIR
"""
import os, sys, json, csv, argparse, time
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "training", "depth")); sys.path.insert(0, os.path.join(ROOT, "training", "segmentation"))
import depth_seg_001 as D
import seg_teacher_student as S
SESS = "session_20261125_095037"
STEP = 5
XOFF_R = 0.098           # camera destra: +9.8 cm dall'asse bici (la sinistra e' -9.8 cm come in ombra_ostacoli_001)
BAR = (230, 680)
PLANE_FISSO = (0.249, 227.5, 0.0)
ZS = [4, 6, 8, 10, 14, 18]


def setup():
    rc = D.Rect(D.CALIB)
    rc.B = float(np.linalg.norm(rc.c.T)) if hasattr(rc.c, "T") else 0.19656
    rc.sgbm = cv2.StereoSGBM_create(minDisparity=0, numDisparities=160, blockSize=9, P1=8 * 81, P2=24 * 81, disp12MaxDiff=2,
        uniquenessRatio=5, speckleWindowSize=100, speckleRange=1, preFilterCap=31, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    rc.fh, rc.cxh = rc.f / 2, rc.cx / 2
    return rc


def disp_right(rc, L, R):
    Lh = cv2.resize(L, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA); Rh = cv2.resize(R, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    d = rc.sgbm.compute(np.ascontiguousarray(Rh[:, ::-1]), np.ascontiguousarray(Lh[:, ::-1])).astype(np.float32) / 16.0
    d = d[:, ::-1].copy()          # riferimento DESTRA, mezza risoluzione
    # barra sfocata sulla sinistra fisica: colonne ~230-680 (piena ris.) della sinistra rettificata (visto a occhio sul f620). Un pixel destro il cui
    # corrispondente x+d cade li' non e' misurabile -> invalido (altrimenti abbina la sfocatura: Z sbagliata, visto: persona a 8 m data a 1.5 m)
    xs = np.arange(d.shape[1], dtype=np.float32)[None, :] + np.maximum(d, 0)
    d[(xs >= BAR[0] / 2) & (xs <= BAR[1] / 2)] = -1
    return d


def disp_left(rc, L, R):
    Lh = cv2.resize(L, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA); Rh = cv2.resize(R, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    return rc.sgbm.compute(Lh, Rh).astype(np.float32) / 16.0


def fit_ground(disp, B):
    """come ombra_ostacoli_001.fit_ground: disparita' con riferimento SINISTRA, colonne fuori dalla barra; d = a (v - vh). Il piano vale anche per la destra (stesse righe rettificate)."""
    sub = np.hstack([disp[225:, 110:330], disp[225:, 470:550]])
    vs, us = np.nonzero(sub > 6)
    if len(vs) < 1500: return None
    rng = np.random.default_rng(0)
    idx = rng.choice(len(vs), min(len(vs), 20000), replace=False)
    v = vs[idx] + 225.0; d = sub[vs[idx], us[idx]]
    best = None; rng = np.random.default_rng(1)
    for _ in range(200):
        i, j = rng.choice(len(v), 2, replace=False)
        if abs(v[i] - v[j]) < 30: continue
        a = (d[i] - d[j]) / (v[i] - v[j])
        if not 0.12 < a < 0.45: continue
        vh = v[i] - d[i] / a
        n = int((np.abs(d - a * (v - vh)) < 1.0).sum())
        if best is None or n > best[0]: best = (n, a, vh)
    if best is None or best[0] < 0.20 * len(v): return None
    n, a, vh = best
    inl = np.abs(d - a * (v - vh)) < 1.0
    A = np.vstack([v[inl], np.ones(inl.sum())]).T
    s, c = np.linalg.lstsq(A, d[inl], rcond=None)[0]
    if s <= 0 or not 0.70 <= B / s <= 0.95: return None
    return float(s), float(-c / s), float(inl.mean())


def road_edges(lab, a, vh, rc):
    """bordi del guidabile (classi con guidabile=true in classi.json) a Z fissati: x sinistro/destro (m, asse bici, + destra) della corsa contigua piu' vicina al centro immagine.
    lab = mappa sfondo a piena risoluzione 800x1280 ridotta 1/4 (200x320)."""
    out = {}
    Hq, Wq = lab.shape
    for Z in ZS:
        v = vh + rc.fh * rc.B / (a * Z)               # riga a mezza risoluzione
        r = int(round(v / 2))                          # riga a 1/4
        if r < 0 or r >= Hq: out[Z] = None; continue
        row = np.isin(lab[r], getattr(S, 'STUFF_GUIDABILE', (0, 1)))   # guidabile da classi.json (strada, strisce, linee)
        c0 = int(rc.cx / 4)
        # corsa contigua che contiene (o e' piu' vicina a) il centro
        xs = np.nonzero(row)[0]
        if len(xs) == 0: out[Z] = None; continue
        near = xs[np.argmin(np.abs(xs - c0))]
        l = near
        while l > 0 and row[l - 1]: l -= 1
        rr = near
        while rr < Wq - 1 and row[rr + 1]: rr += 1
        sc = Z / (rc.f / 4)
        out[Z] = [round((l - rc.cx / 4) * sc + XOFF_R, 2), round((rr + 1 - rc.cx / 4) * sc + XOFF_R, 2)]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--start", type=int, default=0); ap.add_argument("--end", type=int, default=10 ** 9)
    ap.add_argument("--out", required=True); ap.add_argument("--max", type=int, default=10 ** 9); ap.add_argument("--frames", default=None)
    ap.add_argument("--sess", default=SESS, help="sessione #001 (default: giro 25/11 09:50)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rc = setup()
    sess = a.sess
    sd = os.path.join(D.LOGS, sess)
    fr = list(csv.DictReader(open(os.path.join(sd, "frames_left.csv"))))
    off = json.load(open(os.path.join(sd, "metadata.json")))["clock_map_start"]["wall_minus_boottime_s"]
    th = S.ThingsTeacher("mps"); assert th.kind == "sam3"; th.pred.args.save = False; th.pred.args.show = False
    stuff = S.StuffTeacher("mps")
    want = set(int(v) for v in a.frames.split(",")) if a.frames else None
    vL = os.path.join(D.LOGS, f"{sess}_right.h264"); vR = os.path.join(D.LOGS, f"{sess}_left.h264")
    n = 0; t0 = time.time(); last_g = [None, 999]
    for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
        if i >= a.end or n >= a.max or (want is not None and i > max(want)): break
        if i < a.start or (want is None and i % STEP) or (want is not None and i not in want): continue
        jf = os.path.join(a.out, f"f{i:06d}.json")
        if os.path.exists(jf): continue
        L, R = rc(Lr, Rr)
        disp = disp_right(rc, L, R)
        g = fit_ground(disp_left(rc, L, R), rc.B)          # per-fotogramma riuscito solo ~2/15 (frame 100..1500): lo registro, ma uso il piano FISSO
        gg = PLANE_FISSO                                    # (a, vh, frac): mediana dei 2 fit riusciti (0.232/216, 0.267/239) ~ geometria camera; Z da contatto = GROSSOLANA (+-25%)
        img = cv2.cvtColor(R, cv2.COLOR_GRAY2BGR); h, w = R.shape
        th.pred.set_image(img); res = th.pred(text=S.THINGS)[0]
        lab = stuff(img)                                   # 800x1280 indici STUFF
        lab_q = cv2.resize(lab, (320, 200), interpolation=cv2.INTER_NEAREST)
        np.save(os.path.join(a.out, f"stuff_f{i:06d}.npy"), cv2.resize(lab, (160, 100), interpolation=cv2.INTER_NEAREST))
        dets = []
        if res is not None and res.boxes is not None and len(res.boxes):
            lap = cv2.Laplacian(R, cv2.CV_32F); sh = float(lap.var()) + 1e-6
            boxes, cls, conf = res.boxes.xyxy.tolist(), res.boxes.cls.int().tolist(), res.boxes.conf.tolist()
            polys = res.masks.xy if res.masks is not None else [np.zeros((0, 2))] * len(boxes)
            for k, (b, ci, cf, m) in enumerate(zip(boxes, cls, conf, polys)):
                cn = S.THINGS[ci]
                mk = cv2.resize(res.masks.data[k].cpu().numpy().astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0 if res.masks is not None else None
                zst = nst = None; zgr = None; xx = None
                if mk is not None and mk.any():
                    mh = cv2.resize(mk.astype(np.uint8), (w // 2, h // 2), interpolation=cv2.INTER_NEAREST) > 0
                    dv = disp[mh]; dv = dv[dv > 5]
                    nst = int(len(dv))
                    if nst >= 25:
                        zz = rc.fh * rc.B / np.maximum(dv, 1e-3); zst = float(np.median(zz))
                    ys_, xs_ = np.nonzero(mk)
                    vb = float(np.percentile(ys_, 97)) / 2
                    if gg is not None:
                        dgb = gg[0] * (vb - gg[1])
                        if dgb > 1.0: zgr = float(rc.fh * rc.B / dgb)
                    zuse = zst if zst is not None else zgr
                    if zuse is not None:
                        xx = float((np.median(xs_) / 2 - rc.cxh) * zuse / rc.fh + XOFF_R)
                ego = cn in S.EGO_LIKE and b[3] >= h - 4 and (b[3] - b[1]) > 0.55 * h and (b[2] - b[0]) < 0.35 * w
                poly = cv2.approxPolyDP(m.astype(np.float32), 3.0, True).reshape(-1, 2).astype(int).tolist() if len(m) else []
                dets.append(dict(c=cn, cf=round(cf, 3), box=[int(v) for v in b], poly=poly, z_st=None if zst is None else round(zst, 2), n_st=nst,
                                 z_gr=None if zgr is None else round(zgr, 2), x=None if xx is None else round(xx, 2), ego=bool(ego)))
        edges = road_edges(lab_q, gg[0], gg[1], rc) if gg is not None else None
        fracs = {k: round(float((lab_q == j).mean()), 4) for j, k in enumerate(S.STUFF)}
        rec = dict(frame=i, t_ms=int(fr[i]["t_ms"]), t_wall=round(int(fr[i]["t_ms"]) / 1000 + off, 3), plane=dict(a=gg[0], vh=gg[1], fit_frame=None if g is None else dict(a=g[0], vh=g[1], frac=g[2])),
                   dets=dets, edges=edges, fracs=fracs, classi=getattr(S, 'CLASSI_VERSIONE', 'pre-2026-11-25'))
        json.dump(rec, open(jf, "w"))
        n += 1
        if n % 10 == 0: print(i, n, f"{(time.time() - t0) / n:.2f} s/frame", flush=True)
    print("fatto", n, "frame", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
