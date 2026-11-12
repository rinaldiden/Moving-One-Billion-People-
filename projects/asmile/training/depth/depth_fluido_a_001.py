#!/usr/bin/env python3
"""depth_fluido_a_001.py — STADIO A del video fluido v6 (12/11/2026): le STESSE regole di distanza di depth_video_001.py v5 (SGBM + passata vicina,
maschere SAM 3, picco/mediana, R1/R2/R3 declassa/fantasma, ZNCC vicino, blob per continuita'), ma su TUTTI i fotogrammi consecutivi (15 fps) di un intervallo.
Nessuna regola di distanza cambiata; cambia solo: (1) frame consecutivi invece di 1/s e senza il filtro v>0.3 (il video e' continuo); (2) indice SAM 3 letto
man mano (poll) mentre seg_sam3_001.py lo scrive; (3) si salvano le poligonali dei blob e una mappa Z a 320x200 per la miniatura; niente overlay, niente KLT.
Uscita: out_20261112_v6/<sess>_A/frames.pkl (lista per fotogramma), zmap.npz (uint8 Z*10, 255 = non valida, clip 25 m).
Uso: depth_fluido_a_001.py SESSIONE FRAME_A FRAME_B   (B escluso)
"""
import os, sys, json, time, pickle
import numpy as np, cv2
import depth_seg_001 as D
from obstacles_v2 import ground_plane
from depth_ncc_patch_001 import picco_vicino
import depth_video_001 as V
from ego_001 import Ego, x_path
from depth_video_001 import (disparity, disparity_near, zncc_map, segnale_oltre_zmin, depth_components, sam_objects, _iou, _cont,
                             FILL_MIN_AREA, ZNEAR, ZN_OK, SUP_MIN, DENS_NEAR, N_VALID_MIN, AREA_ANGOLO, GHOST_WMAX, ZSPLIT, SAM_DIR)
cv2.setNumThreads(2)
OUT = os.environ.get("VFA_OUT", os.path.join(D.HERE, "out_20261112_v6"))


def sam_get(path, cache, i, timeout=4 * 3600):
    t0 = time.time()
    while i not in cache:
        if os.path.exists(path):
            for l in open(path):
                try: r = json.loads(l)
                except Exception: continue
                cache[r["frame"]] = r
        if i in cache: break
        if time.time() - t0 > timeout: raise RuntimeError(f"SAM index manca f{i}")
        time.sleep(4)
    return cache[i]


def main():
    sess = "session_" + sys.argv[1].replace("session_", ""); fa, fb = int(sys.argv[2]), int(sys.argv[3])
    od = os.path.join(OUT, sess + "_A"); os.makedirs(od, exist_ok=True)
    rc = D.Rect(); f_px, Bm, cx = rc.f, rc.r["baseline_m"], rc.cx
    samfn = os.path.join(SAM_DIR, sess + "_001_fluido", "index.jsonl"); cache = {}
    from ultralytics import YOLO
    yolo = YOLO(os.path.join(D.HERE, "yolo11n-seg.pt"))
    gl = D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264")); gr = D.gray_frames(os.path.join(D.LOGS, sess + "_left.h264"))
    H_perp = D.CAM_H * np.cos(D.PITCH); t0 = time.time(); res = []; ZM = {}; SC = []
    t_ms = D.read_t(sess, "right"); ego = Ego(sess)
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i >= fb: break
        if i < fa: continue
        sam = sam_get(samfn, cache, i)
        L, R = rc(Lr, Rr); disp = disparity(L, R)
        if os.environ.get("VFA_SYNTH"):   # TEST SINTETICO (giro 9): VFA_SYNTH="Z,h_da_terra,spessore,larghezza,X" -> toppa di disparita' (ramo/transenna) inserita nella mappa PRIMA di tutto il resto
            zs_, hs_, th_, ws_, xs0 = [float(v) for v in os.environ["VFA_SYNTH"].split(",")]
            gp0 = ground_plane(disp, cx)
            if gp0 is not None:
                ga0, gvh0, gb0 = gp0; d0 = f_px * Bm / zs_; hp0 = D.CAM_H * np.cos(D.PITCH)
                u0, u1 = int(cx + (xs0 - ws_ / 2) * f_px / zs_), int(cx + (xs0 + ws_ / 2) * f_px / zs_)
                rowof = lambda h_: int(gvh0 + d0 * (1 - h_ / hp0) / ga0)      # riga dove il piano ha la disparita' d0 (1 - h/Hp)
                v0, v1 = rowof(hs_ + th_), rowof(hs_)
                disp[max(v0, 0):v1, max(u0, 0):min(u1, 1280)] = d0
                print("synth", dict(Z=zs_, h=hs_, righe=(v0, v1), colonne=(u0, u1)), flush=True)
        disp_full = disp.copy()
        dn = disparity_near(L, R); fill = (dn > 0) & (disp <= 4)
        fill = cv2.morphologyEx(fill.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        nf, lf, sf, _ = cv2.connectedComponentsWithStats(fill)
        fill = np.isin(lf, [q for q in range(1, nf) if sf[q, 4] >= FILL_MIN_AREA]); disp = np.where(fill, dn, disp)
        valid = disp > 4; Z = np.full(disp.shape, np.inf, np.float32); Z[valid] = f_px * Bm / disp[valid]
        objs, covered, sam_boxes = [], np.zeros(disp.shape, bool), []
        for d_ in sam_objects(sam):
            m = np.zeros(disp.shape, np.uint8); cv2.fillPoly(m, [np.array(d_["poly"], np.int32)], 1)
            if m.sum() < 20: continue
            me = cv2.erode(m, np.ones((3, 3), np.uint8)) > 0 if m.sum() > 400 else m > 0
            if me.sum() < 20: me = m > 0
            z = Z[me & valid]; z = z[z < 80]
            if len(z) < 15 or len(z) < 0.08 * me.sum(): continue
            zp, fr, npop = picco_vicino(z, frac_min=0.25 if len(z) >= 0.5 * me.sum() else 0.10); ys, xs = np.nonzero(m)
            if len(z) >= 0.5 * me.sum(): covered |= cv2.dilate(m, np.ones((5, 5), np.uint8)) > 0
            sam_boxes.append(d_["box"])
            objs.append(dict(src="sam", sam_idx=d_["idx"], area=int(me.sum()), classe=d_["class_raw"], conf=float(d_["conf"]), Z_med=float(np.median(z)), Z_picco=zp,
                             frac_picco=fr, n_pop=npop, n_valid=int(len(z)), frac_valid=float(len(z) / me.sum()), X=float((float(xs.mean()) - cx) * zp / f_px),
                             box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], poly=np.array(d_["poly"], np.int32)))
        r = yolo.predict(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), imgsz=640, conf=0.30, device="cpu", verbose=False)[0]
        if r.masks is not None:
            for k, poly in enumerate(r.masks.xy):
                if len(poly) < 3: continue
                m = np.zeros(disp.shape, np.uint8); cv2.fillPoly(m, [poly.astype(np.int32)], 1)
                me = cv2.erode(m, np.ones((5, 5), np.uint8)) > 0
                if me.sum() < 40: me = m > 0
                z = Z[me & valid]; z = z[z < 80]
                if len(z) < 30 or len(z) < 0.10 * me.sum(): continue
                if any(_iou([int(xs_.min()), int(ys_.min()), int(xs_.max()), int(ys_.max())], b_) > 0.3 for (ys_, xs_) in [np.nonzero(m)] for b_ in sam_boxes): continue
                zp, fr, npop = picco_vicino(z); ys, xs = np.nonzero(m); covered |= m > 0
                objs.append(dict(src="yolo", sam_idx=None, area=int(me.sum()), classe=r.names[int(r.boxes.cls[k])], conf=float(r.boxes.conf[k]), Z_med=float(np.median(z)), Z_picco=zp,
                                 frac_picco=fr, n_pop=npop, n_valid=int(len(z)), frac_valid=float(len(z) / me.sum()), X=float((float(xs.mean()) - cx) * zp / f_px),
                                 box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], poly=poly.astype(np.int32)))
        gp = ground_plane(disp_full, cx); blobs = []
        if gp is not None:
            ga, gvh, gb = gp
            vv, uu = np.mgrid[0:800, 0:1280].astype(np.float32)
            dg = ga * (vv - gvh) + gb * (uu - cx)
            with np.errstate(all="ignore"):
                h = H_perp * (disp - dg) / disp; Xm = (uu - cx) * Z / f_px
            cand_all = valid & (h >= 0.25) & (h <= 2.5) & (Z >= 0.65) & (Z <= 25) & (~covered)
            straight = np.abs(Xm) <= 1.5 + 0.03 * Z
            kf = float(ego.at(t_ms[i], "k"))
            zbl = {}

            def run_blobs(cand, ext):
                out = []
                cand0 = cand.copy()
                nearm = cand0 & (Z < ZSPLIT)
                lab = depth_components(Z, cand0 & ~nearm); n0 = int(lab.max()) + 1
                nn, ln_ = cv2.connectedComponents(cv2.morphologyEx(nearm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)))
                ln_ = np.where(nearm & (ln_ > 0), ln_ + n0 - 1, 0); lab = np.where(ln_ > 0, ln_, lab); n = n0 + nn - 1 + 1
                cnt = np.bincount(lab.ravel(), minlength=n); big = np.nonzero(cnt[1:] >= 150)[0] + 1
                ys_, xs_ = np.nonzero(lab > 0); lv = lab[ys_, xs_]; order = np.argsort(lv); lv_s = lv[order]; ys_s = ys_[order]; xs_s = xs_[order]
                bounds = np.searchsorted(lv_s, np.arange(n + 1)); st = np.zeros((n, 5), int)
                for q in big:
                    yy, xx = ys_s[bounds[q]:bounds[q + 1]], xs_s[bounds[q]:bounds[q + 1]]
                    st[q] = (xx.min(), yy.min(), xx.max() - xx.min() + 1, yy.max() - yy.min() + 1, len(yy))
                for q in big:
                    x, y, w, hh, ar = st[q]
                    if ar < 150: continue
                    z = Z[lab == q]; z = z[np.isfinite(z)]
                    if len(z) < 100: continue
                    zp, fr, npop = picco_vicino(z)
                    tocca = x <= 4 or y + hh >= 796 or x + w >= 1276
                    # giro 12: oggetti LARGHI e BASSI (sbarra 0.15 m larga >=0.60 m) esenti dal minimo di altezza 0.30 f/Z (proposta del critico: w>=0.60 f/Z, hh>=0.08 f/Z)
                    larga_bassa = os.environ.get("VFA_BARRA", "1") == "1" and w >= 0.60 * f_px / zp and hh >= 0.08 * f_px / zp
                    if w < 0.12 * f_px / zp or (hh < (0.15 if tocca else 0.30) * f_px / zp and not larga_bassa): continue
                    dens = float(cand0[lab == q].sum()) / float(w * hh)
                    if any(abs(zp / o_["Z_picco"] - 1) < 0.12 and o_["src"] == "sam" and max(x - o_["box"][2], o_["box"][0] - (x + w), 0) <= 40
                           and min(y + hh, o_["box"][3]) - max(y, o_["box"][1]) > 0.5 * hh and w <= GHOST_WMAX * max(1, o_["box"][2] - o_["box"][0]) for o_ in objs):
                        SC.append(dict(frame=i, motivo="fantasma", Z_picco=round(zp, 3))); continue
                    if zp < ZNEAR:
                        if "zm" not in zbl: zbl["zm"] = (zncc_map(L, R, np.where(valid, disp, 0)), zncc_map(L, R, np.maximum(dg, 0)))
                        zmaps = zbl["zm"]
                        pm = (lab == q) & cand0
                        zo, zg_ = float(np.median(zmaps[0][pm])), float(np.median(zmaps[1][pm])); sup = float((zmaps[0][pm] > ZN_OK).mean())
                    else: zo = zg_ = sup = None
                    if zp < ZNEAR and (sup < V.SUP_MIN or zg_ >= zo):
                        SC.append(dict(frame=i, motivo="zncc_asfalto", Z_picco=round(zp, 3))); continue
                    if zp < 1.9 and dens < DENS_NEAR: continue
                    cs, _h = cv2.findContours((lab == q).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    bp = max(cs, key=cv2.contourArea).reshape(-1, 2).astype(np.int32) if cs else None
                    out.append(dict(src="blob", ext=ext, sam_idx=None, area=int(ar), classe="ostacolo", conf=0.0, Z_med=float(np.median(z)), Z_picco=zp, frac_picco=fr, n_pop=npop,
                                    n_valid=int(len(z)), frac_valid=1.0, X=float((x + w / 2 - cx) * zp / f_px), box=[int(x), int(y), int(x + w), int(y + hh)], poly=bp))
                return out
            # passata S: banda dritta, IDENTICA a v5. passata E (solo in curva |k|>0.01): pixel nella banda attorno al PERCORSO previsto (curvatura decrescente, ego_001.path_xz) e FUORI dalla banda dritta (componenti separate: nessun
            # collegamento con la passata S). In rettilineo E e' vuota.
            blobs = run_blobs(cand_all & straight, False)
            if abs(kf) > 0.01:
                xa = x_path(kf, np.where(np.isfinite(Z), Z, 0))
                blobs += run_blobs(cand_all & ~straight & (np.abs(Xm - xa) <= 1.5 + 0.03 * Z), True)
        nc, bigc, _ = segnale_oltre_zmin(L, valid)
        objs = [o for o in objs if not (o["src"] == "sam" and o["frac_valid"] < 0.5 and any(b_["Z_picco"] < 0.85 * o["Z_picco"] and _cont(b_["box"], o["box"]) > 0.5 for b_ in blobs))]
        allo = objs + blobs
        for o in objs:
            o["sospetto"] = False
            if o["src"] == "sam" and o["classe"] in ("pole", "bollard", "trash can", "traffic cone") and gp is not None and o["box"][3] < 796:
                dgb = ga * (o["box"][3] - gvh) + gb * (0.5 * (o["box"][0] + o["box"][2]) - cx)
                zg_base = f_px * Bm / dgb if dgb > 1 else 1e9
                o["sospetto"] = bool(o["Z_picco"] < 0.5 * zg_base)
        for o in blobs: o["sospetto"] = False
        for o in objs: o["ext"] = False
        for o in allo:
            o["declassato"] = ""
            if o["src"] != "sam": continue
            if o["n_valid"] < N_VALID_MIN: o["declassato"] = "R1_pochi_pixel"
            elif o["classe"] in ("pole", "bollard", "traffic cone") and (o["box"][2] >= 1276 or o["box"][3] >= 796) and o["area"] < AREA_ANGOLO: o["declassato"] = "R2_angolo"
        zq = np.where(valid, np.clip(Z * 10, 0, 250), 255); ZM[i] = cv2.resize(zq.astype(np.uint8), (320, 200), interpolation=cv2.INTER_NEAREST)
        res.append(dict(frame=i, t_ms=t_ms[i], objs=allo, k=float(ego.at(t_ms[i], 'k')), gp=None if gp is None else tuple(float(v) for v in gp), valid_frac=float(valid[400:760, 200:1080].mean()), oltre_zmin=(nc, bigc)))
        if len(res) % 50 == 0:
            print(f"{len(res)}/{fb - fa}  {(time.time() - t0) / len(res):.2f} s/frame", flush=True)
            pickle.dump(res, open(os.path.join(od, "frames.pkl"), "wb"))
    pickle.dump(res, open(os.path.join(od, "frames.pkl"), "wb")); json.dump(SC, open(os.path.join(od, "scartati.json"), "w"))
    np.savez_compressed(os.path.join(od, "zmap.npz"), **{f"f{k}": v for k, v in ZM.items()})
    print("fatto", len(res), "frame", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
