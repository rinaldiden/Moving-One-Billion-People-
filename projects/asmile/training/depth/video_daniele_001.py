#!/usr/bin/env python3
"""video_daniele_001.py — video leggibile per Daniele (12/11/2026, giro 5). SOLO #001.
Immagine rettificata della camera sinistra (fisica) con: maschere SAM 3 colorate per FAMIGLIA, etichetta "famiglia distanza m" sugli oggetti nel corridoio,
primo ostacolo nel corridoio in grande, corridoio disegnato sul piano strada, barra in basso (tempo, velocita' encoder, primo ostacolo, TTC), miniatura depth.
Distanze = quelle di depth_video_001.py v5 (objects.csv/frames.csv di out_20261112_v5): qui non si calcola nulla di nuovo, si disegna.
Maschere/famiglie: asmile-loggers/_seg_sam3/<sess>_001_v2/index.jsonl (093909: prodotto con seg_postprocess_v2.py).
Uso: video_daniele_001.py 20261109_094146 [--jpg f1,f2,...]
"""
import os, sys, csv, json, subprocess, argparse
import numpy as np, cv2
import depth_seg_001 as D

FAMCOL = {  # BGR
    "veicolo": (255, 144, 30), "persona": (64, 64, 255), "bici-moto": (255, 60, 180), "paletto-palo": (0, 215, 255),
    "barriera-cancello": (200, 200, 0), "altro": (170, 170, 170), "ostacolo": (0, 140, 255)}
CORR = (255, 255, 0)
FAMCLASS = {"car": "veicolo", "van": "veicolo", "truck": "veicolo", "bus": "veicolo", "person": "persona", "child": "persona", "stroller": "persona",
            "bicycle": "bici-moto", "motorcycle": "bici-moto", "pole": "paletto-palo", "bollard": "paletto-palo", "traffic cone": "paletto-palo",
            "barrier": "barriera-cancello", "fence": "barriera-cancello", "gate": "barriera-cancello"}
SAM_DIR = os.path.join(D.HERE, "..", "..", "asmile-loggers", "_seg_sam3")
W, H, BAR = 1280, 800, 48


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def cont(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))


def chip(img, x, y, txt, col, sc=0.8, th=2, anchor="bl"):
    (w, h), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, th)
    x = int(min(max(0, x), W - w - 8)); y = int(min(max(h + 6, y), H - 4))
    cv2.rectangle(img, (x, y - h - 6), (x + w + 8, y + 4), col, -1)
    cv2.putText(img, txt, (x + 4, y - 1), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)
    return (x, y - h - 6, x + w + 8, y + 4)


def text_shadow(img, x, y, txt, sc, col, th=2):
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th + 3, cv2.LINE_AA)
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_DUPLEX, sc, col, th, cv2.LINE_AA)


def fam_of(classe):
    return FAMCLASS.get(classe, "altro")


def draw_frame(img, fr, objs, sam_rec, ga_gb, zthumb, t0_ms, legend, rc):
    out = img.copy()
    f, cx = rc.f, rc.cx; Bm = rc.r["baseline_m"]
    # corridoio sul piano strada
    ga, gvh, gb = ga_gb if ga_gb else (None, None, None)
    if ga:
        Lp, Rp = [], []
        for Z in np.geomspace(2.0, 30.0, 24):
            d = f * Bm / Z
            for sgn, o in ((-1, Lp), (1, Rp)):
                u = cx + sgn * (1.5 + 0.03 * Z) * f / Z; v = gvh + (d - gb * (u - cx)) / ga
                o.append((u, v, Z))
        poly = np.array([(u, v) for u, v, _ in Lp] + [(u, v) for u, v, _ in Rp][::-1], np.int32)
        lay = out.copy(); cv2.fillPoly(lay, [poly], CORR); out = cv2.addWeighted(lay, 0.14, out, 0.86, 0)
        for P in (Lp, Rp):
            cv2.polylines(out, [np.array([(u, v) for u, v, _ in P], np.int32)], False, CORR, 2, cv2.LINE_AA)
        for Zt in (3, 5, 10, 20):
            d = f * Bm / Zt; xl = cx - (1.5 + 0.03 * Zt) * f / Zt; xr = cx + (1.5 + 0.03 * Zt) * f / Zt; v = int(gvh + d / ga)
            if 0 < v < H - BAR:
                cv2.line(out, (int(xl), v), (int(xr), v), CORR, 1, cv2.LINE_AA)
                text_shadow(out, int(xl) + 8, v - 5, f"{Zt} m", 0.55, CORR, 1)
    # maschere: tutte quelle misurate, colorate per famiglia
    dets = [d for d in (sam_rec["detections"] if sam_rec else []) if d["conf"] >= 0.45 and len(d["poly"]) >= 3]
    first = None
    lab = []
    ov = out.copy()
    for o in objs:
        Z = float(o["Z_picco"]); b = [int(v) for v in o["box"].split()]
        corr = o["corridoio"] == "True"; dec = bool(o["declassato"]) or o["sospetto"] == "True"
        if o["src"] == "sam":
            m = max(dets, key=lambda d: iou(d["box"], b), default=None)
            if m is None or iou(m["box"], b) < 0.5: poly = None; fam = fam_of(o["classe"])
            else:
                poly = np.array(m["poly"], np.int32); fam = m["family"] if m["family"] not in ("unknown", "altro") else fam_of(o["classe"])
        elif o["src"] == "yolo": poly = None; fam = fam_of(o["classe"])
        else: poly = None; fam = "ostacolo"
        col = FAMCOL.get(fam, FAMCOL["altro"])
        if dec: col = (110, 110, 110)
        if Z > 30 and not corr: continue
        if poly is not None:
            if corr and not dec: cv2.fillPoly(ov, [poly], col)
            cv2.polylines(out, [poly], True, col, 3 if (corr and not dec) else 1, cv2.LINE_AA)
        else:
            if fam == "ostacolo":
                if not corr or Z > 12: continue
                if any(cont(b, [int(v) for v in p["box"].split()]) > 0.5 for p in objs if p["src"] != "blob" and p["corridoio"] == "True" and p is not o): continue
                cv2.rectangle(out, (b[0], b[1]), (b[2], b[3]), col, 2 if Z <= 8 else 1)
            else: cv2.rectangle(out, (b[0], b[1]), (b[2], b[3]), col, 3 if (corr and not dec) else 1)
        if corr and not dec:
            if fam != "ostacolo" or Z <= 8: lab.append((Z, b, fam, col, o))   # blob senza classe: etichetta solo sotto 8 m (sopra: riquadro sottile, niente testo)
            if first is None or Z < first[0]: first = (Z, b, fam, col, o)
    out = cv2.addWeighted(ov, 0.30, out, 0.70, 0)
    # etichette (le piu' vicine sopra), niente sovrapposizioni brutali
    placed = []
    for Z, b, fam, col, o in sorted(lab, key=lambda r: r[0]):
        if Z > 30: continue
        txt = f"{fam} {Z:.1f} m"; y = b[1] - 8
        for _ in range(8):
            (w, h), _b = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)
            r = (b[0], y - h - 6, b[0] + w + 8, y + 4)
            if all(not (r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3]) for q in placed): break
            y -= (h + 8)
            if y < 90: y = b[3] + 22 + 0; break
        placed.append(chip(out, b[0], y, txt, col, 0.7, 2))
    if first is not None:
        Z, b, fam, col, o = first
        cv2.rectangle(out, (b[0] - 3, b[1] - 3), (b[2] + 3, b[3] + 3), (255, 255, 255), 3)
        cv2.rectangle(out, (W // 2 - 250, 8), (W // 2 + 250, 72), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 250, 8), (W // 2 + 250, 72), col, 3)
        text_shadow(out, W // 2 - 238, 38, "PRIMO OSTACOLO NEL CORRIDOIO", 0.6, (255, 255, 255), 1)
        text_shadow(out, W // 2 - 238, 66, f"{Z:.1f} m  ({fam})", 0.95, col, 2)
    else:
        cv2.rectangle(out, (W // 2 - 250, 8), (W // 2 + 250, 52), (0, 0, 0), -1)
        text_shadow(out, W // 2 - 238, 40, "corridoio: nessun ostacolo misurato", 0.8, (0, 255, 0), 2)
    # miniatura depth
    if zthumb is not None:
        th = zthumb; x0, y0 = W - 256 - 8, H - 160 - 26
        out[y0:y0 + 160, x0:x0 + 256] = th; cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + 256, y0 + 160), (255, 255, 255), 1)
        text_shadow(out, x0, y0 - 6, "depth: rosso vicino, blu lontano", 0.45, (255, 255, 255), 1)
    if legend:
        x, y = 14, 96; lay = out.copy(); cv2.rectangle(lay, (x - 6, y - 24), (x + 520, y + 8 + 30 * 10), (0, 0, 0), -1); out = cv2.addWeighted(lay, 0.8, out, 0.2, 0)
        text_shadow(out, x, y, "LEGENDA (maschere SAM 3 + distanza stereo)", 0.62, (255, 255, 255), 1); y += 34
        for k, name in (("veicolo", "veicolo (auto, furgone, camion)"), ("persona", "persona (anche bimbo, passeggino)"), ("bici-moto", "bici / moto"),
                        ("paletto-palo", "paletto / palo / cono"), ("barriera-cancello", "barriera / cancello"), ("altro", "altro"), ("ostacolo", "ostacolo senza classe (solo stereo)")):
            cv2.rectangle(out, (x, y - 16), (x + 28, y + 6), FAMCOL[k], -1); text_shadow(out, x + 40, y + 3, name, 0.6, (255, 255, 255), 1); y += 30
        cv2.rectangle(out, (x, y - 16), (x + 28, y + 6), CORR, 2); text_shadow(out, x + 40, y + 3, "corridoio davanti alla bici (sul piano strada)", 0.6, (255, 255, 255), 1); y += 30
        cv2.rectangle(out, (x, y - 16), (x + 28, y + 6), (110, 110, 110), -1); text_shadow(out, x + 40, y + 3, "grigio = scartato (troppo piccolo / in aria)", 0.6, (255, 255, 255), 1); y += 30
        text_shadow(out, x, y + 3, "etichette solo nel corridoio; calibrazione #001 provvisoria", 0.5, (200, 200, 200), 1)
    return out, first


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--jpg", default=""); ap.add_argument("--vdir", default="out_20261112_v5"); ap.add_argument("--tag", default="_f"); a = ap.parse_args()
    sess = "session_" + a.session; od = os.path.join(D.HERE, a.vdir, sess + a.tag)
    rc = D.Rect()
    fr_rows = {int(r["frame"]): r for r in csv.DictReader(open(os.path.join(od, "frames.csv")))}
    ob = {}
    for r in csv.DictReader(open(os.path.join(od, "objects.csv"))): ob.setdefault(int(r["frame"]), []).append(r)
    sfn = os.path.join(SAM_DIR, sess + "_001_v2", "index.jsonl")
    sam = {r["frame"]: r for r in map(json.loads, open(sfn))}
    sel = sorted(fr_rows); selset = set(sel)
    t0 = int(fr_rows[sel[0]]["t_ms"])
    jpg = [int(x) for x in a.jpg.split(",") if x]
    outdir = os.path.join(D.HERE, a.vdir); mp4 = os.path.join(outdir, f"video_daniele_{a.session[-6:]}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H + BAR}", "-r", "2", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    n = 0; stats = []
    for i, Lr in enumerate(D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264"))):
        if i > sel[-1]: break
        if i not in selset: continue
        L = cv2.remap(Lr, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR)
        img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
        img = cv2.convertScaleAbs(img, alpha=1.15, beta=8)
        fr = fr_rows[i]; gp = (float(fr["gp_a"]), float(fr["gp_vh"]), float(fr["gp_b"])) if fr.get("gp_a") else None
        zt = cv2.imread(os.path.join(od, "zthumb", f"f{i:06d}.png"))
        out, first = draw_frame(img, fr, ob.get(i, []), sam.get(i), gp, zt, t0, n == 0, rc)
        v = float(fr["v_ms"]); t = (int(fr["t_ms"]) - t0) / 1000
        canvas = np.zeros((H + BAR, W, 3), np.uint8); canvas[:H] = out
        if first: Z, b, fam, col, o = first; ps = f"primo ostacolo {Z:.1f} m ({fam})  TTC {Z / max(v, 0.3):.1f} s"
        else: ps = "corridoio libero"
        txt = f"{a.session[-6:]}  f{i}   t = {t:.0f} s   vel. encoder {v:.1f} m/s ({v * 3.6:.0f} km/h)   {ps}"
        cv2.putText(canvas, txt, (12, H + 31), cv2.FONT_HERSHEY_DUPLEX, 0.72, (0, 255, 0), 1, cv2.LINE_AA)
        stats.append((i, None if first is None else round(first[0], 2)))
        reps = 3 if n == 0 else 1
        for _ in range(reps): ff.stdin.write(canvas.tobytes())
        if i in jpg: cv2.imwrite(os.path.join(D.HERE, "..", "..", "agents", "rapporti", "img", f"video_daniele_{a.session[-6:]}_f{i}.jpg"), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
        n += 1
    ff.stdin.close(); ff.wait()
    print(mp4, n, "frame")
    json.dump(stats, open(os.path.join(outdir, f"video_daniele_{a.session[-6:]}_primo.json"), "w"))


if __name__ == "__main__":
    main()
