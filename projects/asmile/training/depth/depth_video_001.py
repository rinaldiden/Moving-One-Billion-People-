#!/usr/bin/env python3
"""depth_video_001.py — depth densa nel corridoio + distanza per oggetto sui video in moto di #001 (2026-11-12).
SOLO #001. Calib logger/depth/calib_asmile-001.json (B30, nessuna correzione Z), rettifica stereo_common. Z = f_rect * baseline_m / d
con baseline_m=0.19656 dalla calib (NON B=0.2 come depth_seg_001.py: bug +1.7% da correggere, qui non toccato).
Campionamento: 1 fotogramma/s (t_ms), solo frame in moto (encoder ruota v>0.3 m/s su +-0.5 s, wheel_circum 0.3374 attivo).
Depth: SGBM blockSize 7, padding sx 224 px, 224 disparita' (Z>=1.22 m): il lato sx non e' cieco. Oggetti: YOLO11n-seg su CPU (SAM3 non rigirato:
niente maschere salvate, e calcolato con B=0.2); per ogni oggetto Z_med e Z_picco (regola picco_vicino fissata prima dei video, in
depth_ncc_patch_001.py). Ostacoli senza classe: pixel nel corridoio |X|<=1.5+0.03Z con altezza sopra il piano strada >=0.25 m
(piano da obstacles_v2.ground_plane, importato senza modifiche). Controllo encoder: tracce KLT 1 s, pendenza -dZ/ds.
v4 (12/11, VETO 1/3 occhio): oggetti sottili da maschere SAM 3 (asmile-loggers/_seg_sam3/<sess>_001), slicing per continuita' di profondita' nei blob
di fallback, coerenza di contatto a terra (flag sospetto). --nosam --noslice riproducono v3.
Uso: depth_video_001.py SESSIONE [--max N] [--frames a,b,c] [--tag X]
"""
import os, sys, csv, json, time, argparse
import numpy as np, cv2
import depth_seg_001 as D
from obstacles_v2 import ground_plane
from depth_ncc_patch_001 import picco_vicino

cv2.setNumThreads(2)
PAD = NDISP = 224
FILL_MIN_AREA = 3000
ZNEAR = 3.0; ZN_OK = 0.5   # v3: blob con Z<3 m: almeno SUP_MIN dei pixel candidati con ZNCC 15x15 > 0.5 alla disparita' misurata (verifica L-R a piena risoluzione)
SUP_MIN = 0.20; SCARTATI = []
DENS_NEAR = 0.35   # blob con Z<1.9 m (passata vicina) richiedono densita pixel candidati >=0.35 del box (falsi asfalto 0.22-0.29, bici vera 0.49: soglia dichiarata su 4 blob, POCHI)
OUT = os.path.join(D.HERE, "out_20261112_v4")
# v4 (VETO 1/3 occhio, ostacoli sottili fusi nel muro): (1) maschere d'istanza SAM 3 come oggetti, distanza = statistica della depth DENTRO la maschera;
# (2) fallback senza maschera: componenti connesse per CONTINUITA' di profondita' (due pixel vicini sono collegati solo se |ln Za - ln Zb| < SLICE_LN):
# un paletto a 4.5 m davanti a un muro a 9 m e' un'altra componente, la distanza si calcola per componente e non per box.
SAM_DIR = os.path.join(D.HERE, "..", "..", "asmile-loggers", "_seg_sam3")
SAM_CLASSES = {"bollard", "pole", "person", "child", "car", "van", "truck", "trash can", "stroller", "dog", "cat", "bicycle", "motorcycle", "traffic cone", "bench"}
SAM_CONF = 0.45          # tier low o sure; sotto = 'unknown' (dichiarato ex-ante)
SLICE_LN = 0.12          # salto di Z fra pixel adiacenti oltre il quale si separa (12%), dichiarato ex-ante
SLICE_ON = True; ZSPLIT = 2.5   # sotto: closing 7x7 come v3 (passata vicina rumorosa)


def load_sam(sess):
    fn = os.path.join(SAM_DIR, sess + "_001", "index.jsonl")
    return {r["frame"]: r for r in map(json.loads, open(fn))} if os.path.exists(fn) else {}


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def _cont(a, b):
    """frazione del box a contenuta nel box b"""
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))


def sam_objects(rec):
    """Detection SAM 3 utili all'ostacolo: classi in SAM_CLASSES, conf>=SAM_CONF; pole/bollard sovrapposti (stesso box, IoU>0.6) = un solo oggetto (conf piu' alta)."""
    ds = sorted([d for d in rec["detections"] if d["class_raw"] in SAM_CLASSES and d["conf"] >= SAM_CONF and len(d["poly"]) >= 3], key=lambda d: -d["conf"])
    out = []
    for d in ds:
        if any(_iou(d["box"], o["box"]) > 0.6 for o in out): continue
        out.append(d)
    return out


def depth_components(Z, cand):
    """Componenti connesse dei pixel candidati collegando solo vicini (distanza 1 o 2 px, orizz. e vert.) con |ln Za - ln Zb| < SLICE_LN."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    H, W = cand.shape; idx = np.arange(H * W).reshape(H, W)
    zm = cv2.medianBlur(np.where(cand, Z, 0).astype(np.float32).clip(0, 60), 5)   # mediana 5x5: il rumore della passata vicina (nearest da mezza risoluzione) non spezza l'oggetto
    lz = np.log(np.where(cand & (zm > 0), zm, 1.0))
    rs, cs = [], []
    for dy, dx in ((0, 1), (0, 2), (0, 3), (1, 0), (2, 0), (3, 0)):
        a = cand[:H - dy, :W - dx] & cand[dy:, dx:] & (np.abs(lz[:H - dy, :W - dx] - lz[dy:, dx:]) < SLICE_LN)
        rs.append(idx[:H - dy, :W - dx][a]); cs.append(idx[dy:, dx:][a])
    r = np.concatenate(rs); c = np.concatenate(cs)
    g = coo_matrix((np.ones(len(r), np.uint8), (r, c)), shape=(H * W, H * W))
    n, lab = connected_components(g, directed=False)
    lab = lab.reshape(H, W) + 1; lab[~cand] = 0
    return lab
_sg = cv2.StereoSGBM_create(minDisparity=0, numDisparities=NDISP, blockSize=7, P1=8 * 49, P2=32 * 49, disp12MaxDiff=1,
                            uniquenessRatio=8, speckleWindowSize=150, speckleRange=2, preFilterCap=31,
                            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)


def disparity(L, R):
    Lp = cv2.copyMakeBorder(L, 0, 0, PAD, 0, cv2.BORDER_CONSTANT, value=0)
    Rp = cv2.copyMakeBorder(R, 0, 0, PAD, 0, cv2.BORDER_CONSTANT, value=0)
    return (_sg.compute(Lp, Rp).astype(np.float32) / 16.0)[:, PAD:]


_sgn = cv2.StereoSGBM_create(minDisparity=0, numDisparities=224, blockSize=5, P1=8 * 25, P2=32 * 25, disp12MaxDiff=1,
                             uniquenessRatio=8, speckleWindowSize=60, speckleRange=2, preFilterCap=31, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)


def disparity_near(L, R):
    """V2 (critico f9938): seconda passata a MEZZA risoluzione, 224 disparita' a meta' = 448 px a piena -> Zmin ~0.61 m.
    Ritorna disparita' in unita' del fotogramma pieno (d_half*2), NaN-free: 0 dove non valida o con d_full<184 (Z>1.5 m, gia' coperto)."""
    l = cv2.resize(L, (640, 400), interpolation=cv2.INTER_AREA); r = cv2.resize(R, (640, 400), interpolation=cv2.INTER_AREA)
    P = 224
    lp = cv2.copyMakeBorder(l, 0, 0, P, 0, cv2.BORDER_CONSTANT, value=0); rp = cv2.copyMakeBorder(r, 0, 0, P, 0, cv2.BORDER_CONSTANT, value=0)
    d = (_sgn.compute(lp, rp).astype(np.float32) / 16.0)[:, P:]
    d[d < 92] = 0   # Z<1.5 m: oltre non serve (la piena copre 1.22+) e i riempimenti lontani univano blob diversi (f9265)
    return cv2.resize(d * 2.0, (1280, 800), interpolation=cv2.INTER_NEAREST)


def segnale_oltre_zmin(L, valid):
    """V2: celle 64x64 nella parte bassa (y 448-768, x 192-1280) con tessitura forte (>=30% pixel con gradiente >30) e quasi nessuna
    disparita' valida (<5%, dopo le due passate) -> ostacolo/superficie vicina oltre la portata. Ritorna (n_celle, n_connesse_max, celle)."""
    g = cv2.GaussianBlur(L, (5, 5), 0).astype(np.float32)
    gm = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)) / 8.0
    cells = np.zeros((5, 17), bool)
    for cy in range(5):
        for cx_ in range(17):
            y0, x0 = 448 + cy * 64, 192 + cx_ * 64
            cells[cy, cx_] = (gm[y0:y0 + 64, x0:x0 + 64] > 30).mean() >= 0.30 and valid[y0:y0 + 64, x0:x0 + 64].mean() < 0.05
    n, lab, st, _ = cv2.connectedComponentsWithStats(cells.astype(np.uint8))
    big = int(st[1:, 4].max()) if n > 1 else 0
    return int(cells.sum()), big, cells


def zncc_map(L, R, dmap, k=15):
    """ZNCC locale (finestra k x k) fra L(u,v) e R(u-d,v) con disparita' per pixel dmap (R warpata)."""
    vv, uu = np.mgrid[0:800, 0:1280].astype(np.float32)
    Rw = cv2.remap(R.astype(np.float32), uu - dmap.astype(np.float32), vv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    Lf = L.astype(np.float32); bf = lambda x: cv2.boxFilter(x, -1, (k, k))
    mL, mR = bf(Lf), bf(Rw)
    return (bf(Lf * Rw) - mL * mR) / np.sqrt(np.maximum((bf(Lf * Lf) - mL ** 2) * (bf(Rw * Rw) - mR ** 2), 1e-3))


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
    ap.add_argument("--noyolo", action="store_true"); ap.add_argument("--nosam", action="store_true", help="v3: niente maschere SAM"); ap.add_argument("--noslice", action="store_true", help="v3: blob per closing come prima")
    ap.add_argument("--frames", default=None, help="lista di fotogrammi (bypassa campionamento 1/s e v>0.3)")
    ap.add_argument("--nonear", action="store_true"); ap.add_argument("--nozn", action="store_true", help="disattiva la regola v3 (per confronto prima/dopo)"); ap.add_argument("--tag", default=""); a = ap.parse_args()
    sess = a.session if a.session.startswith("session_") else "session_" + a.session
    od = os.path.join(OUT, sess + a.tag); os.makedirs(os.path.join(od, "ov"), exist_ok=True)
    rc = D.Rect(); f_px, Bm = rc.f, rc.r["baseline_m"]; cx = rc.cx
    t = np.array(D.read_t(sess, "right")); enc, n_enc = enc_session(sess); print("righe encoder", n_enc, flush=True)
    s_all = enc(t); v_all = enc(t + 500) - enc(t - 500)
    sel, last = [], -1e9
    for i in range(len(t)):
        if v_all[i] > 0.3 and t[i] - last >= 1000:
            sel.append(i); last = t[i]
    sel = sel[:a.max]
    global SUP_MIN
    global SLICE_ON
    if a.nozn: SUP_MIN = -1.0
    if a.noslice: SLICE_ON = False
    sam = {} if a.nosam else load_sam(sess)
    if a.frames: sel = sorted(int(v) for v in a.frames.split(","))
    selset = set(sel)
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
        L, R = rc(Lr, Rr); tt0 = time.time(); disp = disparity(L, R); t_full = time.time() - tt0
        disp_full = disp.copy()   # il piano strada si stima SEMPRE sulla sola passata piena (come v1)
        t_near = 0.0; n_fill = 0
        if not a.nonear:
            tt0 = time.time(); dn = disparity_near(L, R); fill = (dn > 0) & (disp <= 4)   # la near riempie SOLO dove la piena non ha disparita' (tentativo 'near vince se piu' vicino' scartato: rompeva f9265)
            fill = cv2.morphologyEx(fill.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
            nf, lf, sf, _ = cv2.connectedComponentsWithStats(fill)
            fill = np.isin(lf, [q for q in range(1, nf) if sf[q, 4] >= FILL_MIN_AREA])   # v2: solo regioni vicine ESTESE (no ponti di rumore fra blob)
            n_fill = int(fill.sum())
            disp = np.where(fill, dn, disp); t_near = time.time() - tt0
        tt0 = time.time()
        valid = disp > 4; Z = np.full(disp.shape, np.inf, np.float32); Z[valid] = f_px * Bm / disp[valid]
        ov = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR); ov = cv2.addWeighted(ov, 0.6, colorize(np.where(valid, Z, np.nan)), 0.4, 0)
        ov[~valid] = (0.85 * cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)[~valid]).astype(np.uint8)
        objs, covered = [], np.zeros(disp.shape, bool)
        sam_boxes = []
        for d_ in (sam_objects(sam[i]) if i in sam else []):
            m = np.zeros(disp.shape, np.uint8); cv2.fillPoly(m, [np.array(d_["poly"], np.int32)], 1)
            if m.sum() < 20: continue
            me = cv2.erode(m, np.ones((3, 3), np.uint8)) > 0 if m.sum() > 400 else m > 0
            if me.sum() < 20: me = m > 0
            z = Z[me & valid]; z = z[z < 80]
            if len(z) < 15 or len(z) < 0.08 * me.sum(): continue
            # maschera con meta' pixel senza disparita': la parte piu' vicina e' la meno campionata (SGBM cieco sotto Zmin) -> popolazione vicina accettata dal 10% (non 25%)
            zp, fr, npop = picco_vicino(z, frac_min=0.25 if len(z) >= 0.5 * me.sum() else 0.10); ys, xs = np.nonzero(m)
            if len(z) >= 0.5 * me.sum(): covered |= cv2.dilate(m, np.ones((5, 5), np.uint8)) > 0   # maschera con meta' pixel senza disparita' (oggetto vicino, Z<1.5 m): non coprire, lo cerca la passata vicina/blob
            sam_boxes.append(d_["box"])
            objs.append(dict(dens=None, zn_obj=None, zn_gnd=None, h_med=None, sup=None, src="sam", classe=d_["class_raw"], conf=float(d_["conf"]), Z_med=float(np.median(z)), Z_picco=zp,
                             frac_picco=fr, n_pop=npop, n_valid=int(len(z)), frac_valid=float(len(z) / me.sum()), X=float((float(xs.mean()) - cx) * zp / f_px),
                             box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], poly=np.array(d_["poly"], np.int32)))
        if yolo is not None:
            r = yolo.predict(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), imgsz=640, conf=0.30, device="cpu", verbose=False)[0]
            if r.masks is not None:
                for k, poly in enumerate(r.masks.xy):
                    if len(poly) < 3: continue
                    m = np.zeros(disp.shape, np.uint8); cv2.fillPoly(m, [poly.astype(np.int32)], 1)
                    me = cv2.erode(m, np.ones((5, 5), np.uint8)) > 0
                    if me.sum() < 40: me = m > 0
                    z = Z[me & valid]; z = z[z < 80]
                    if len(z) < 30 or len(z) < 0.10 * me.sum(): continue
                    if any(_iou([int(xs_.min()), int(ys_.min()), int(xs_.max()), int(ys_.max())], b_) > 0.3 for (ys_, xs_) in [np.nonzero(m)] for b_ in sam_boxes): continue   # v4: gia' coperto da una maschera SAM
                    zp, fr, npop = picco_vicino(z); ys, xs = np.nonzero(m)
                    covered |= m > 0   # v2: coperto solo se l'oggetto YOLO e' stato davvero misurato (prima anche se scartato -> buco)
                    X = (float(xs.mean()) - cx) * zp / f_px
                    objs.append(dict(dens=None, zn_obj=None, zn_gnd=None, h_med=None, sup=None, src="yolo", classe=r.names[int(r.boxes.cls[k])], conf=float(r.boxes.conf[k]), Z_med=float(np.median(z)), Z_picco=zp,
                                     frac_picco=fr, n_pop=npop, n_valid=int(len(z)), frac_valid=float(len(z) / me.sum()), X=float(X),
                                     box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], poly=poly.astype(np.int32)))
        # ostacoli senza classe nel corridoio
        gp = ground_plane(disp_full, cx); blobs = []; zmaps = None; scart = []
        if gp is not None:
            ga, gvh, gb = gp
            vv, uu = np.mgrid[0:800, 0:1280].astype(np.float32)
            dg = ga * (vv - gvh) + gb * (uu - cx)
            with np.errstate(all="ignore"):
                h = H_perp * (disp - dg) / disp
                Xm = (uu - cx) * Z / f_px
            cand = valid & (h >= 0.25) & (h <= 2.5) & (Z >= 0.65) & (Z <= 25) & (np.abs(Xm) <= 1.5 + 0.03 * Z) & (~covered)
            cand0 = cand.copy()
            if SLICE_ON:
                # Z<ZSPLIT=2.5 m (passata vicina, disparita' rumorosa a gradini): un oggetto cosi' vicino non ha un muro 'dietro' da separare -> closing 7x7 come v3;
                # Z>=1.9 m: componenti per continuita' di profondita'
                nearm = cand0 & (Z < ZSPLIT)
                lab = depth_components(Z, cand0 & ~nearm); n0 = int(lab.max()) + 1
                nn, ln_ = cv2.connectedComponents(cv2.morphologyEx(nearm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)))
                ln_ = np.where(nearm & (ln_ > 0), ln_ + n0 - 1, 0); lab = np.where(ln_ > 0, ln_, lab); n = n0 + nn - 1 + 1
                bb = cv2.connectedComponents  # (non usato)
                cnt = np.bincount(lab.ravel(), minlength=n)
                stats = {}
                big = np.nonzero(cnt[1:] >= 150)[0] + 1
                ys_, xs_ = np.nonzero(lab > 0); lv = lab[ys_, xs_]
                order = np.argsort(lv); lv_s = lv[order]; ys_s = ys_[order]; xs_s = xs_[order]
                bounds = np.searchsorted(lv_s, np.arange(n + 1))
                st = np.zeros((n, 5), int)
                for q in big:
                    yy, xx = ys_s[bounds[q]:bounds[q + 1]], xs_s[bounds[q]:bounds[q + 1]]
                    st[q] = (xx.min(), yy.min(), xx.max() - xx.min() + 1, yy.max() - yy.min() + 1, len(yy))
                qs = list(big)
            else:
                cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
                n, lab, st, _ = cv2.connectedComponentsWithStats(cand); qs = range(1, n)
            for q in qs:
                x, y, w, hh, ar = st[q]
                if ar < 150: continue
                z = Z[lab == q]; z = z[np.isfinite(z)]
                if len(z) < 100: continue
                zp, fr, npop = picco_vicino(z)
                tocca = x <= 4 or y + hh >= 796 or x + w >= 1276     # v2: oggetto tagliato dal bordo immagine (vicino): minimo 0.15 m invece di 0.30
                if w < 0.12 * f_px / zp or hh < (0.15 if tocca else 0.30) * f_px / zp: continue
                dens = float(cand0[lab == q].sum()) / float(w * hh)
                # v4: 'fattening' stereo: la disparita' dell'oggetto vicino sborda a sinistra del suo bordo (occlusione) e forma un blob fantasma accanto alla
                # maschera SAM dello stesso oggetto: scartato se la Z e' entro 12% di un oggetto SAM, adiacente (gap<=40 px) e con sovrapposizione verticale >50%
                if any(abs(zp / o_["Z_picco"] - 1) < 0.12 and o_["src"] == "sam" and max(x - o_["box"][2], o_["box"][0] - (x + w), 0) <= 40
                       and min(y + hh, o_["box"][3]) - max(y, o_["box"][1]) > 0.5 * hh for o_ in objs):
                    SCARTATI.append(dict(frame=i, motivo="fantasma_accanto_maschera_SAM", Z_picco=round(zp, 3), box=[int(x), int(y), int(x + w), int(y + hh)])); continue
                if zp < ZNEAR:
                    if zmaps is None:
                        zmaps = (zncc_map(L, R, np.where(valid, disp, 0)), zncc_map(L, R, np.maximum(dg, 0)))
                    pm = (lab == q) & cand0
                    zo, zg_ = float(np.median(zmaps[0][pm])), float(np.median(zmaps[1][pm])); hm = float(np.median(h[pm])); sup = float((zmaps[0][pm] > ZN_OK).mean())
                else: zo = zg_ = hm = sup = None
                if zp < ZNEAR and (sup < SUP_MIN or (zg_ >= zo and not a.nozn)):   # (2a) match non verificato, (2b) l'ipotesi 'strada' spiega le immagini almeno quanto l'ipotesi 'oggetto'
                       # v3: disparita' vicina non verificata fotometricamente (asfalto vuoto) -> scartata, registrata
                    scart.append(dict(frame=i, Z_picco=round(zp, 3), dens=round(dens, 3), zn_obj=round(zo, 3), zn_gnd=round(zg_, 3), sup=round(sup, 3), box=[int(x), int(y), int(x + w), int(y + hh)])); continue
                if zp < 1.9 and dens < DENS_NEAR: continue   # v2: la passata vicina e' piu' rumorosa (asfalto): blob vicini solo se densi
                blobs.append(dict(src="blob", dens=round(dens, 3), zn_obj=zo, zn_gnd=zg_, h_med=hm, sup=sup, classe="ostacolo", conf=0.0, Z_med=float(np.median(z)), Z_picco=zp, frac_picco=fr, n_pop=npop,
                                  n_valid=int(len(z)), frac_valid=1.0, X=float((x + w / 2 - cx) * zp / f_px), box=[int(x), int(y), int(x + w), int(y + hh)], poly=None))
        tt0 = time.time(); nc, big, _ = segnale_oltre_zmin(L, valid); t_sig = time.time() - tt0
        # v4: un blob PIU' VICINO (Z<0.85 Zsam) sovrapposto (IoU box>0.3) a un oggetto SAM con maschera a meta' vuota vince (la mediana in maschera vede solo la parte lontana)
        objs = [o for o in objs if not (o["src"] == "sam" and o["frac_valid"] < 0.5 and any(b_["Z_picco"] < 0.85 * o["Z_picco"] and _cont(b_["box"], o["box"]) > 0.5 for b_ in blobs))]
        allo = objs + blobs; SCARTATI.extend(scart)
        for sc_ in scart:
            b_ = sc_['box']; cv2.rectangle(ov, (b_[0], b_[1]), (b_[2], b_[3]), (0, 0, 255), 1); label(ov, b_[0], b_[1] + 2, f"SCARTATO {sc_['Z_picco']:.1f} m (sup {sc_['sup']:.2f})", (0, 0, 255), 0.5, 1)
        # v4: coerenza di contatto a terra per pali/colonnine/cestini/coni: la base della maschera deve stare dove il piano strada la mette alla Z misurata.
        # Se Z_picco < 0.5 * Z_piano(base) (oggetto 'a mezz'aria' molto piu' vicino del terreno sotto la sua base: base sopra l'orizzonte o disparita' spuria sullo
        # sfondo) -> 'sospetto', fuori dal conteggio corridoio/primo ostacolo (resta nel CSV e in overlay grigio). Maschere tagliate dal fondo immagine non testate.
        for o in objs:
            o["sospetto"] = False; o["zg_base"] = None
            if o["src"] == "sam" and o["classe"] in ("pole", "bollard", "trash can", "traffic cone") and gp is not None and o["box"][3] < 796:
                dgb = ga * (o["box"][3] - gvh) + gb * (0.5 * (o["box"][0] + o["box"][2]) - cx)
                zg_base = f_px * Bm / dgb if dgb > 1 else 1e9
                o["sospetto"] = bool(o["Z_picco"] < 0.5 * zg_base); o["zg_base"] = float(min(zg_base, 1e4))
        for o in blobs: o["sospetto"] = False; o["zg_base"] = None
        for o in allo:
            inb = abs(o["X"]) <= 1.5 + 0.03 * o["Z_picco"]; o["corridoio"] = bool(inb) and not o.get("sospetto", False)
            col = (255, 0, 255) if o["poly"] is None else ((0, 255, 255) if inb else (200, 200, 200))
            if o.get("sospetto"): col = (90, 90, 90)
            b = o["box"]
            if o["poly"] is not None: cv2.polylines(ov, [o["poly"]], True, col, 2)
            else: cv2.rectangle(ov, (b[0], b[1]), (b[2], b[3]), col, 2)
            label(ov, b[0], b[1] + 2, f"{o['classe']} {o['Z_picco']:.1f} m" + (" ?aria" if o.get("sospetto") else ""), col, 0.7, 2)
            label(ov, b[0], b[1] + 24, f"med {o['Z_med']:.1f}", col, 0.5, 1)
            rows_o.append(dict(sess=sess, frame=i, t_ms=int(t[i]), s_enc_m=round(float(s_all[i]), 2), v_ms=round(float(v_all[i]), 2),
                               **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items() if k not in ("poly", "box")},
                               box=" ".join(map(str, b))))
        co = [o["Z_picco"] for o in allo if o["corridoio"]]
        first = min(co) if co else None
        vf = float(valid[400:760, 200:1080].mean())
        rows_f.append(dict(sess=sess, frame=i, t_ms=int(t[i]), s_enc_m=round(float(s_all[i]), 2), v_ms=round(float(v_all[i]), 2),
                           n_obj=len(objs), n_blob=len(blobs), primo_corridoio_m=None if first is None else round(first, 2), valid_frac_basso=round(vf, 3),
                           ms_full=round(1000 * t_full), ms_near=round(1000 * t_near), ms_segnale=round(1000 * t_sig), px_riempiti_near=n_fill,
                           oltre_zmin_celle=nc, oltre_zmin_connesse=big))
        bar = f"#001 {sess[8:]} f{i} t={(t[i]-t[0])/1000:.0f}s v={v_all[i]:.1f} m/s | corridoio: " + (f"primo {first:.1f} m" if first else "libero") + f" | validi {vf*100:.0f}%"
        if big >= 3:
            label(ov, 8, 60, f"OLTRE ZMIN: tessitura forte senza disparita' ({nc} celle, {big} connesse)", (0, 0, 255), 0.7, 2)
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
    json.dump(SCARTATI, open(os.path.join(od, "scartati.json"), "w"))
    json.dump(summ, open(os.path.join(od, "summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
