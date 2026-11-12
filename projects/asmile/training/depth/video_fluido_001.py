#!/usr/bin/env python3
"""video_fluido_001.py — STADIO B del video fluido v6 (12/11/2026), SOLO #001. Legge le misure per fotogramma di depth_fluido_a_001.py (regole v5),
fa tracking per oggetto con ID stabili (Hungarian su IoU di box con moto costante del centro: 'ByteTrack-lite', un solo stadio), filtra la distanza per traccia
con un Kalman a stato [Z, w] (w = velocita' propria dell'oggetto lungo l'asse; Z' = Z - (v_enc - w) dt: coerente con la velocita' encoder), definisce il
corridoio come ARCO (curvatura da ego_001: giroscopio + encoder) e disegna: maschere tinte col colore della distanza (scala fissa 0-20 m), contorno per famiglia,
etichette solo su oggetti nel corridoio o a <8 m, banner primo ostacolo + TTC, barra con t, velocita', sterzo, curvatura.
Uso: video_fluido_001.py SESSIONE [--jpg f1,f2] [--stats-only]
"""
import os, sys, json, pickle, subprocess, argparse, csv
import numpy as np, cv2
from scipy.optimize import linear_sum_assignment
import depth_seg_001 as D
from ego_001 import Ego, x_path, path_xz

W, H, BAR = 1280, 800, 48
OUT = os.path.join(D.HERE, "out_20261112_v6")
SAM_DIR = os.path.join(D.HERE, "..", "..", "asmile-loggers", "_seg_sam3")
FAMCOL = {"veicolo": (255, 144, 30), "persona": (64, 64, 255), "bici-moto": (255, 60, 180), "paletto-palo": (0, 215, 255),
          "barriera-cancello": (200, 200, 0), "altro": (170, 170, 170), "ostacolo": (0, 140, 255)}
FAMNAME = {"veicolo": "veicolo", "persona": "persona", "bici-moto": "bici/moto", "paletto-palo": "paletto", "barriera-cancello": "barriera", "altro": "altro", "ostacolo": "ostacolo"}
FAMCLASS = {"car": "veicolo", "van": "veicolo", "truck": "veicolo", "bus": "veicolo", "tractor": "veicolo", "person": "persona", "child": "persona", "stroller": "persona",
            "wheelchair": "persona", "bicycle": "bici-moto", "motorcycle": "bici-moto", "pole": "paletto-palo", "bollard": "paletto-palo", "traffic cone": "paletto-palo",
            "barrier": "barriera-cancello", "fence": "barriera-cancello", "gate": "barriera-cancello", "ostacolo": "ostacolo"}
STATIC = {"paletto-palo", "barriera-cancello", "ostacolo", "altro"}
CORR = (255, 255, 255)
F_PX, B_M = 1379.8882680918412, 0.19656132417315123
CONFIRM, MAXMISS = 3, 8
COAST = 4            # un oggetto confermato non visto per <=4 fotogrammi (0.27 s) resta candidato 'primo ostacolo' con la Z predetta dal Kalman (niente maschera disegnata)
HITS_BLOB = 8        # un ostacolo senza classe (blob) deve durare >=8 fotogrammi (0.53 s) per contare/comparire
ZMAX_SCALE = 20.0
TURBO = cv2.applyColorMap(np.arange(256, dtype=np.uint8).reshape(-1, 1), cv2.COLORMAP_TURBO).reshape(256, 3)


def zcol(Z):
    return tuple(int(c) for c in TURBO[int(255 * (1 - min(max(Z, 0.0), ZMAX_SCALE) / ZMAX_SCALE))])


def wband(Z): return 1.5 + 0.03 * Z


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def fam_obj(o, famv2, frame):
    if o["src"] == "blob": return "ostacolo"
    if o["src"] == "sam":
        f = famv2.get((frame, o["sam_idx"]))
        if f and f not in ("unknown", "altro"): return f
    return FAMCLASS.get(o["classe"], "altro")


class Track:
    nid = 0

    def __init__(s, o, fam, Z, t):
        Track.nid += 1; s.id = Track.nid; s.src = o["src"]; s.fam = fam; s.fams = [fam]; s.classe = o["classe"]
        s.box = list(o["box"]); s.cen = np.array([(o["box"][0] + o["box"][2]) / 2, (o["box"][1] + o["box"][3]) / 2]); s.vel = np.zeros(2)
        s.hits = 1; s.miss = 0; s.born = t; s.zs = [Z]
        s.stat = fam in STATIC
        sa = 0.3 if s.stat else 1.0
        s.sa = sa; s.x = np.array([Z, 0.0]); sg = s.sig(Z); s.P = np.diag([sg ** 2, (0.3 if s.stat else 1.0) ** 2])
        s.out = 0; s.tan = o["X"] / max(o["Z_picco"], 0.1); s.decl = [bool(o["declassato"])]; s.sosp = [bool(o["sospetto"])]
        s.in_arc = False; s.lastfirst = False; s.lab_xy = None; s.o = o; s.Zraw = [o["Z_picco"]]; s.t_obs = [t]; s.Zf = [Z]; s.s_obs = []

    @staticmethod
    def sig(Z): return float(np.hypot(0.03 * Z, Z * Z * 0.4 / (F_PX * B_M)))

    def pred_box(s, rot=0.0):
        c = s.cen + s.vel + np.array([rot, 0.0]); w = s.box[2] - s.box[0]; h = s.box[3] - s.box[1]
        return [c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2]

    def predict(s, dt, v):
        F = np.array([[1, dt], [0, 1]]); s.x = F @ s.x; s.x[0] -= v * dt
        Q = s.sa ** 2 * np.array([[dt ** 3 / 3, dt ** 2 / 2], [dt ** 2 / 2, dt]]); Q[0, 0] += 0.02 * dt
        s.P = F @ s.P @ F.T + Q; s.x[0] = max(s.x[0], 0.3)

    def update(s, z):
        r = s.sig(z) ** 2; S = s.P[0, 0] + r; y = z - s.x[0]
        if y * y / S > 9.0:           # outlier a 3 sigma: nessun aggiornamento (la predizione dell'encoder regge)
            s.out += 1
            if s.out >= 4: s.x = np.array([z, 0.0]); s.P = np.diag([r, 1.0]); s.out = 0
            return False
        K = s.P[:, 0] / S; s.x = s.x + K * y; s.P = s.P - np.outer(K, s.P[0]); s.out = 0
        return True


def load_famv2(sess):
    fn = os.path.join(SAM_DIR, sess + "_001_fluido_v2", "index.jsonl"); m = {}
    if not os.path.exists(fn): return m
    for l in open(fn):
        r = json.loads(l)
        for d in r["detections"]:
            m[(r["frame"], d["idx"])] = d["family"]
            for a in d.get("alternatives", []): m[(r["frame"], a["idx"])] = d["family"]
    return m


def run_tracking(frames, ego, famv2):
    Track.nid = 0; tracks = []; per = []; prev_t = None
    for fr in frames:
        t = fr["t_ms"]; v = float(ego.at(t, "v_s")); dt = 1 / 15 if prev_t is None else (t - prev_t) / 1000.0; prev_t = t
        rot = -F_PX * np.radians(float(ego.at(t, "yaw_s"))) * dt     # spostamento orizzontale dell'immagine dovuto alla rotazione della bici (imbardata a destra -> scena a sinistra)
        for tr in tracks: tr.predict(dt, v)
        obs = [o for o in fr["objs"] if o["Z_picco"] <= 60]
        fams = [fam_obj(o, famv2, fr["frame"]) for o in obs]
        C = np.full((len(tracks), len(obs)), 1e6)
        for a, tr in enumerate(tracks):
            pb = tr.pred_box(rot)
            for b, (o, f) in enumerate(zip(obs, fams)):
                if (tr.src == "blob") != (o["src"] == "blob"): continue
                if tr.fam != f and not (tr.src == "blob"): continue
                sc = iou(pb, o["box"])
                if sc < 0.05: continue
                if tr.hits >= CONFIRM and abs(np.log(max(o["Z_picco"], .3) / max(tr.x[0], .3))) > 0.45: continue
                C[a, b] = 1 - sc
        ma, mb = set(), set()
        if C.size:
            ri, ci = linear_sum_assignment(C)
            for a, b in zip(ri, ci):
                if C[a, b] < 0.95: ma.add(a); mb.add(b); tr = tracks[a]; o = obs[b]
                else: continue
                nb = o["box"]; nc = np.array([(nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2])
                tr.vel = 0.5 * tr.vel + 0.5 * (nc - tr.cen - np.array([rot, 0.0])); tr.cen = nc; tr.box = list(nb)
                tr.update(o["Z_picco"]); tr.hits += 1; tr.miss = 0; tr.o = o; tr.fams.append(fams[b]); tr.decl.append(bool(o["declassato"])); tr.sosp.append(bool(o["sospetto"]))
                tr.tan = 0.6 * tr.tan + 0.4 * o["X"] / max(o["Z_picco"], 0.1); tr.Zraw.append(o["Z_picco"]); tr.t_obs.append(t); tr.Zf.append(float(tr.x[0])); tr.s_obs.append(float(ego.at(t, "s")))
                tr.classe = o["classe"]
        for a, tr in enumerate(tracks):
            if a not in ma: tr.miss += 1; tr.cen = tr.cen + tr.vel + np.array([rot, 0.0])
        for b, (o, f) in enumerate(zip(obs, fams)):
            if b not in mb: tracks.append(Track(o, f, o["Z_picco"], t)); tracks[-1].s_obs.append(float(ego.at(t, "s")))
        tracks = [tr for tr in tracks if tr.miss <= (MAXMISS if tr.hits >= CONFIRM else 2)]
        rows = []
        for tr in tracks:
            if tr.hits >= CONFIRM and tr.miss <= COAST:
                tr.fam = max(set(tr.fams[-15:]), key=tr.fams[-15:].count)
                pb = [int(v) for v in tr.pred_box(0.0)] if tr.miss else list(tr.o["box"])
                rows.append(dict(id=tr.id, fam=tr.fam, src=tr.src, classe=tr.classe, Z=float(tr.x[0]), w=float(tr.x[1]), Zraw=float(tr.o["Z_picco"]), tan=float(tr.tan), box=pb, poly=None if tr.miss else tr.o["poly"],
                                 decl=bool(np.mean(tr.decl[-8:]) > 0.5), sosp=bool(np.mean(tr.sosp[-8:]) > 0.5), ext=tr.o.get("ext", False), hits=tr.hits, coast=tr.miss > 0, track=tr))
        per.append(rows)
    return per


def corridor_logic(per, frames, ego):
    """per ogni fotogramma: arco (k), appartenenza arco/dritta con isteresi, primo ostacolo (isteresi 0.5 m)"""
    res = []; prev_first = {"arc": None, "str": None}
    for fr, rows in zip(frames, per):
        k = float(ego.at(fr["t_ms"], "k")); pz, px = path_xz(k)
        for r in rows:
            Z = r["Z"]; X = r["tan"] * Z; r["X"] = X
            dx_arc = X - float(np.interp(Z, pz, px)); tr = r["track"]
            lim = wband(Z) * (1.15 if tr.in_arc else 1.0)
            tr.in_arc = abs(dx_arc) <= lim; r["in_arc"] = tr.in_arc
            r["in_str"] = abs(X) <= wband(Z)
            r["cand"] = (not r["decl"]) and (not r["sosp"]) and r["hits"] >= (HITS_BLOB if r["src"] == "blob" else CONFIRM)
        first = {}
        for key, flag in (("arc", "in_arc"), ("str", "in_str")):
            c = [r for r in rows if r[flag] and r["cand"]]
            best = min(c, key=lambda r: r["Z"], default=None)
            pf = prev_first[key]
            if pf is not None and best is not None:
                pr = next((r for r in c if r["id"] == pf), None)
                if pr is not None and best["Z"] > pr["Z"] - 0.5: best = pr
            prev_first[key] = None if best is None else best["id"]; first[key] = best
        res.append(dict(k=k, first=first))
    return res


def smooth_gp(frames, i, win=15):
    g = [f["gp"] for f in frames[max(0, i - win):i + win + 1] if f["gp"] is not None]
    if not g: return None
    # disegno: piano strada senza pendenza trasversale (gb=0), pendenza ga da geometria (altezza camera, pitch), solo l'orizzonte gvh = mediana temporale +-1 s delle stime per fotogramma
    return (B_M / (D.CAM_H * np.cos(D.PITCH)), float(np.median([x[1] for x in g])), 0.0)


def chip(img, x, y, txt, col, sc=0.7, th=2):
    (w, h), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, th)
    x = int(min(max(0, x), W - w - 8)); y = int(min(max(h + 6, y), H - 4))
    cv2.rectangle(img, (x, y - h - 6), (x + w + 8, y + 4), col, -1)
    cv2.putText(img, txt, (x + 4, y - 1), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)
    return (x, y - h - 6, x + w + 8, y + 4)


def shadow(img, x, y, txt, sc, col, th=2):
    for dx, dy in ((2, 2), (-1, -1), (2, -1), (-1, 2)): cv2.putText(img, txt, (x + dx, y + dy), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_DUPLEX, sc, col, th, cv2.LINE_AA)


def ztxt(Z): return "> 25 m" if Z > 25 else f"{Z:.1f} m"


def draw(img, fr, rows, cs, gp, zthumb, ego, sess, t0, i):
    out = img.copy(); cx = 660.142
    k = cs["k"]
    if gp:
        ga, gvh, gb = gp
        Zs = np.geomspace(1.8, 30.0, 40); pz, px = path_xz(k); Lp, Rp, Cp = [], [], []
        for Z in Zs:
            xc = float(np.interp(Z, pz, px)); d = F_PX * B_M / Z
            for X, o in ((xc - wband(Z), Lp), (xc + wband(Z), Rp), (xc, Cp)):
                u = cx + X * F_PX / Z; o.append((u, gvh + (d - gb * (u - cx)) / ga))
        poly = np.array(Lp + Rp[::-1], np.int32)
        lay = out.copy(); cv2.fillPoly(lay, [poly], CORR); out = cv2.addWeighted(lay, 0.13, out, 0.87, 0)
        for P in (Lp, Rp): cv2.polylines(out, [np.array(P, np.int32)], False, CORR, 2, cv2.LINE_AA)
        for Zt in (3, 5, 10, 20):
            xc = float(np.interp(Zt, pz, px)); d = F_PX * B_M / Zt
            pts = []
            for X in (xc - wband(Zt), xc + wband(Zt)):
                u = cx + X * F_PX / Zt; pts.append((int(u), int(gvh + (d - gb * (u - cx)) / ga)))
            if 0 < pts[0][1] < H - 10:
                cv2.line(out, pts[0], pts[1], CORR, 1, cv2.LINE_AA); shadow(out, min(pts[0][0], pts[1][0]) + 8, pts[0][1] - 5, f"{Zt} m", 0.5, CORR, 1)
    first = cs["first"]["arc"]; fid = None if first is None else first["id"]
    draw_rows = [r for r in rows if not r["coast"] and r["Z"] <= 40 and not r["decl"] and not (r["src"] == "blob" and r["hits"] < HITS_BLOB) and not r["sosp"]
                 and (r["src"] != "blob" or (r["in_arc"] and r["Z"] <= 8)) and (r["fam"] in ("persona", "veicolo", "bici-moto", "paletto-palo", "barriera-cancello", "ostacolo") or r["in_arc"] or r["Z"] < 8)]
    solid = [r for r in draw_rows if r["src"] != "blob"]
    cont_ = lambda a, b: max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1])) / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))
    draw_rows = [r for r in draw_rows if not (r["src"] == "blob" and r["id"] != fid and any(cont_(r["box"], q["box"]) > 0.5 for q in solid))]
    ov = out.copy()
    for r in sorted(draw_rows, key=lambda r: -r["Z"]):
        if r["poly"] is not None and len(r["poly"]) >= 3: cv2.fillPoly(ov, [np.asarray(r["poly"], np.int32)], zcol(r["Z"]))
        elif r["src"] != "blob":
            b = r["box"]; cv2.rectangle(ov, (b[0], b[1]), (b[2], b[3]), zcol(r["Z"]), -1)
    out = cv2.addWeighted(ov, 0.5, out, 0.5, 0)
    for r in sorted(draw_rows, key=lambda r: -r["Z"]):
        fc = FAMCOL[r["fam"]]; th = 3 if r["in_arc"] else 2
        if r["poly"] is not None and len(r["poly"]) >= 3: cv2.polylines(out, [np.asarray(r["poly"], np.int32)], True, fc, th, cv2.LINE_AA)
        else: b = r["box"]; cv2.rectangle(out, (b[0], b[1]), (b[2], b[3]), fc, th)
    for r in [q for q in rows if not q["coast"]]:   # scartati/declassati: contorno grigio sottile se vicini
        if (r["decl"] or r["sosp"]) and r["Z"] < 8 and r["poly"] is not None and len(r["poly"]) >= 3: cv2.polylines(out, [np.asarray(r["poly"], np.int32)], True, (110, 110, 110), 1, cv2.LINE_AA)
    if first is not None and not first["coast"]:
        b = first["box"]; cv2.rectangle(out, (b[0] - 4, b[1] - 4), (b[2] + 4, b[3] + 4), (255, 255, 255), 3)
    placed = []
    lab = [r for r in draw_rows if (r["in_arc"] or r["Z"] < 8) and not (r["src"] == "blob" and r["Z"] > 8)]
    for r in sorted(lab, key=lambda r: r["Z"]):
        tr = r["track"]; b = r["box"]; txt = f"{FAMNAME[r['fam']]} {ztxt(r['Z'])}"
        tx, ty = b[0], max(b[1] - 8, 96)
        if tr.lab_xy is not None: tx = 0.5 * tr.lab_xy[0] + 0.5 * tx; ty = 0.5 * tr.lab_xy[1] + 0.5 * ty
        (w_, h_), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)
        for _ in range(8):
            rc_ = (tx, ty - h_ - 6, tx + w_ + 8, ty + 4)
            if all(not (rc_[0] < q[2] and q[0] < rc_[2] and rc_[1] < q[3] and q[1] < rc_[3]) for q in placed): break
            ty -= (h_ + 8)
            if ty < 96: ty = b[3] + 24; break
        tr.lab_xy = (tx, ty); placed.append(chip(out, tx, ty, txt, FAMCOL[r["fam"]], 0.7, 2))
    t = (fr["t_ms"] - t0) / 1000; v = max(0.0, float(ego.at(fr["t_ms"], "v_s"))); st = float(ego.at(fr["t_ms"], "steer_s")); ttc = None
    if first is not None:
        cl = v if first["fam"] in STATIC else v - first["w"]   # famiglie ferme (paletti, barriere, senza classe): velocita' propria 0, TTC = Z/v_encoder; veicoli/persone/bici: Z/(v - w) con w dal Kalman
        ttc = first["Z"] / cl if cl > 0.3 else None
        col = FAMCOL[first["fam"]]
        cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), col, 3)
        shadow(out, W // 2 - 258, 34, "PRIMO OSTACOLO NEL CORRIDOIO", 0.55, (255, 255, 255), 1)
        shadow(out, W // 2 - 258, 66, f"{ztxt(first['Z'])}  {FAMNAME[first['fam']]}   TTC " + (f"{ttc:.1f} s" if ttc is not None and ttc < 60 else "-"), 0.95, col, 2)
    else:
        cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 52), (0, 0, 0), -1); shadow(out, W // 2 - 258, 40, "corridoio: nessun ostacolo misurato", 0.8, (0, 255, 0), 2)
    # scala distanza + legenda famiglie
    x0, y0 = 14, 20
    for j in range(260): cv2.line(out, (x0 + j, y0), (x0 + j, y0 + 16), zcol(ZMAX_SCALE * j / 259), 1)
    cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + 260, y0 + 16), (255, 255, 255), 1)
    for m in (0, 5, 10, 15, 20): shadow(out, x0 + int(m / 20 * 259) - (8 if m else 0), y0 + 38, f"{m}", 0.5, (255, 255, 255), 1)
    shadow(out, x0, y0 + 56, "distanza (m): rosso vicino, blu lontano", 0.45, (255, 255, 255), 1)
    lay = out.copy(); yy = H - 150; cv2.rectangle(lay, (8, yy - 18), (196, yy + 7 * 17 + 4), (0, 0, 0), -1); out = cv2.addWeighted(lay, 0.6, out, 0.4, 0)
    for n_, kf in enumerate(("veicolo", "persona", "bici-moto", "paletto-palo", "barriera-cancello", "ostacolo")):
        cv2.rectangle(out, (14, yy + n_ * 17 - 10), (30, yy + n_ * 17 + 2), FAMCOL[kf], -1); shadow(out, 38, yy + n_ * 17 + 2, FAMNAME[kf] + (" (senza classe)" if kf == "ostacolo" else ""), 0.42, (255, 255, 255), 1)
    cv2.rectangle(out, (14, yy + 6 * 17 - 10), (30, yy + 6 * 17 + 2), CORR, 2); shadow(out, 38, yy + 6 * 17 + 2, "corridoio (percorso previsto)", 0.42, (255, 255, 255), 1)
    if zthumb is not None:
        zt = np.where(zthumb == 255, 0, 255 - np.clip(zthumb.astype(np.float32) / 10 / ZMAX_SCALE * 255, 0, 255)).astype(np.uint8)
        c = TURBO[zt.reshape(-1)].reshape(zt.shape + (3,)); c[zthumb == 255] = 0; c = cv2.resize(c, (256, 160), interpolation=cv2.INTER_AREA)
        x0, y0 = W - 264, H - 188; out[y0:y0 + 160, x0:x0 + 256] = c; cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + 256, y0 + 160), (255, 255, 255), 1)
        shadow(out, x0, y0 - 6, "depth stereo (stessa scala)", 0.45, (255, 255, 255), 1)
    canvas = np.zeros((H + BAR, W, 3), np.uint8); canvas[:H] = out
    Rm = "rett." if abs(k) < 0.004 else f"R {1 / abs(k):.0f} m"
    txt = f"{sess[-6:]}  f{i}  t = {t:.1f} s   v = {v:.1f} m/s ({v * 3.6:.0f} km/h)   sterzo {st:+.0f} gradi (+ = destra)   curvatura {k:+.3f} 1/m ({Rm})"
    cv2.putText(canvas, txt, (12, H + 31), cv2.FONT_HERSHEY_DUPLEX, 0.68, (0, 255, 0), 1, cv2.LINE_AA)
    return canvas, ttc


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--jpg", default=""); ap.add_argument("--out", default=None); ap.add_argument("--stats-only", action="store_true"); a = ap.parse_args()
    sess = "session_" + a.session.replace("session_", ""); sid = sess[8:]
    frames = pickle.load(open(os.path.join(OUT, sess + "_A", "frames.pkl"), "rb")); zf_ = os.path.join(OUT, sess + "_A", "zmap.npz"); zm = np.load(zf_) if os.path.exists(zf_) else None
    ego = Ego(sess); famv2 = load_famv2(sess)
    per = run_tracking(frames, ego, famv2); cs = corridor_logic(per, frames, ego)
    f0, f1 = frames[0]["frame"], frames[-1]["frame"]; t0 = D.read_t(sess, "right")[0]
    name = f"video_fluido_{sid[-6:]}.mp4" if sid.endswith("093909") else f"video_fluido_{sid[-6:]}_{int(round((frames[0]['t_ms'] - t0) / 1000))}-{int(round((frames[-1]['t_ms'] - t0) / 1000))}.mp4"
    mp4 = a.out or os.path.join(OUT, name)
    jpg = {int(x) for x in a.jpg.split(",") if x}
    stats_rows = []
    if not a.stats_only:
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H + BAR}", "-r", "15", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "20", "-preset", "medium", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
        rc = D.Rect(); fmap = {f["frame"]: n for n, f in enumerate(frames)}
        for i, Lr in enumerate(D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264"))):
            if i > f1: break
            if i < f0: continue
            n = fmap[i]; L = cv2.remap(Lr, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR)
            img = cv2.convertScaleAbs(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), alpha=1.15, beta=8)
            canvas, ttc = draw(img, frames[n], per[n], cs[n], smooth_gp(frames, n), (zm[f"f{i}"] if zm is not None and f"f{i}" in zm.files else None), ego, sess, t0, i)
            ff.stdin.write(canvas.tobytes())
            if i in jpg: cv2.imwrite(os.path.join(D.ROOT, "agents", "rapporti", "img", f"video_fluido_{sid[-6:]}_f{i}.jpg"), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
        ff.stdin.close(); ff.wait(); print(mp4)
    pickle.dump(dict(per=[[{k: v for k, v in r.items() if k not in ("track", "poly")} for r in rows] for rows in per], cs=[dict(k=c["k"], first={kk: (None if v is None else v["id"]) for kk, v in c["first"].items()},
                firstZ={kk: (None if v is None else v["Z"]) for kk, v in c["first"].items()}) for c in cs], frames=[f["frame"] for f in frames], t_ms=[f["t_ms"] for f in frames]),
                open(os.path.join(OUT, f"tracks_{sid}.pkl"), "wb"))


if __name__ == "__main__":
    main()
