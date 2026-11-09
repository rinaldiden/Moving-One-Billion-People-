#!/usr/bin/env python3
"""
depth_seg_001.py — asmile #001: depth stereo RETTIFICATA + segmentazione SAM 3 con distanza per oggetto (2026-11-09).
SOLO #001 (2 OV9281 separate). Calib: logger/depth/calib_asmile-001.json. Nessun dato/calib del logger.

Convenzioni (da calib_001_20261109): order RL -> immagine "sinistra" della calib = file *_right (fisicamente SINISTRA),
"destra" = file *_left (fisicamente destra). Rettifica = stereo_common.Calib.rectify() (stessa del banco fisso).
Z = f_rect * B / d, f_rect=1312.49 px (P1), B=0.2 m, d0=0.

Sottocomandi
  run      segmenta (SAM 3) + SGBM rettificato; per ogni oggetto Z = mediana robusta della disparita' sulla maschera;
           scrive objects_*.csv + fuso_*.mp4 (maschere + etichetta "classe  X.X m" + lista a lato)
  banco    rifa il banco fisso (soste 1..15 m, sessione 093216) con la pipeline vera (SGBM rettificato)
  analizza test in movimento (oggetti statici: Z vs distanza percorsa dall'encoder ruota) + bordi
Uso: ~/.asmile_depth_venv/bin/python training/depth/depth_seg_001.py run --start 4500 --n 2700 ...
"""
import argparse, csv, json, os, pickle, subprocess, sys, time
from collections import defaultdict
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "logger", "depth"))
sys.path.insert(0, os.path.join(ROOT, "training", "segmentation"))
from stereo_common import Calib  # noqa: E402

W, H, B = 1280, 800, 0.2
CALIB = os.path.join(ROOT, "logger", "depth", "calib_asmile-001.json")
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-001")
M_PER_COUNT = 2.1219e-5


def gray_frames(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", path, "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    while True:
        buf = p.stdout.read(W * H)
        if len(buf) < W * H:
            p.kill(); return
        yield np.frombuffer(buf, np.uint8).reshape(H, W)


class Rect:
    def __init__(self, calib=CALIB):
        self.c = Calib.load(calib)
        self.r = self.c.rectify()
        self.f = self.r["focal_px"]
        self.cx, self.cy = self.r["P1"][0, 2], self.r["P1"][1, 2]
        self.sgbm = cv2.StereoSGBM_create(minDisparity=0, numDisparities=288, blockSize=7, P1=8 * 49, P2=32 * 49,
                                          disp12MaxDiff=1, uniquenessRatio=8, speckleWindowSize=150, speckleRange=2,
                                          preFilterCap=31, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)

    def __call__(self, Lraw, Rraw):
        L = cv2.remap(Lraw, self.r["m1x"], self.r["m1y"], cv2.INTER_LINEAR)
        R = cv2.remap(Rraw, self.r["m2x"], self.r["m2y"], cv2.INTER_LINEAR)
        return L, R

    def disparity(self, L, R):
        return self.sgbm.compute(L, R).astype(np.float32) / 16.0      # <=0 invalido

    def rect_pt(self, p):
        return cv2.undistortPoints(np.asarray(p, np.float64).reshape(-1, 1, 2), self.c.K1, self.c.d1,
                                   R=self.r["R1"], P=self.r["P1"]).reshape(-1, 2)

    def Z(self, d):
        return self.f * B / d


def mask_depth(rc, disp, mask, dmin=4.0, thin_frac=None):
    """Mediana robusta della disparita' sulla maschera (erosa 3 px). Ritorna (Z, Zp25, Zp75, n_valid, frac_valid)."""
    m = cv2.erode(mask, np.ones((5, 5), np.uint8)) > 0
    if m.sum() < 40:
        m = mask > 0
    v = disp[m]
    v = v[v > dmin]
    if len(v) < 30 or len(v) < 0.10 * m.sum():
        return None
    thin = thin_frac is not None and thin_frac < 0.45        # oggetto sottile (palo): lo sfondo trapela nella maschera
    d = float(np.percentile(v, 70 if thin else 50))           # sfondo = disparita' minore -> si prende il percentile alto
    q1, q3 = np.percentile(v, [25, 75])
    return rc.Z(d), rc.Z(q3), rc.Z(q1), int(len(v)), len(v) / m.sum()


def enc_interp(t_lo, t_hi):
    """distanza cumulativa (m) dall'encoder ruota, interpolata a t_ms. Ritorna f(t_ms)."""
    import pandas as pd
    fs = []
    for f in sorted(os.listdir(os.path.join(LOGS, "_sensors", "sensors"))):
        if f.startswith("sensors_20261109") and f.endswith(".csv"):
            d = pd.read_csv(os.path.join(LOGS, "_sensors", "sensors", f), usecols=["t_ms", "enc_wheel_cum"])
            fs.append(d)
    d = pd.concat(fs).drop_duplicates("t_ms").sort_values("t_ms")
    d = d[(d.t_ms >= t_lo - 5000) & (d.t_ms <= t_hi + 5000)]
    t, s = d.t_ms.values.astype(float), d.enc_wheel_cum.values.astype(float) * M_PER_COUNT
    return lambda x: np.interp(x, t, s)


def read_t(sess, cam):
    return [int(r["t_ms"]) for r in csv.DictReader(open(os.path.join(LOGS, sess, f"frames_{cam}.csv")))]


# ------------------------------------------------------------------ run
def label_img(img, x, y, big, small, col):
    (wb, hb), _ = cv2.getTextSize(big, cv2.FONT_HERSHEY_DUPLEX, 1.1, 2)
    (ws, hs), _ = cv2.getTextSize(small, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    tw, th = max(wb, ws) + 12, hb + hs + 18
    x = int(min(max(0, x), W - tw)); y = int(min(max(0, y), H - th))
    cv2.rectangle(img, (x, y), (x + tw, y + th), col, -1)
    cv2.rectangle(img, (x, y), (x + tw, y + th), (0, 0, 0), 1)
    cv2.putText(img, big, (x + 6, y + hb + 6), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(img, small, (x + 6, y + th - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    return (x, y, tw, th)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def zcol(Z):
    return (60, 60, 255) if Z < 4 else (0, 165, 255) if Z < 8 else (0, 220, 0)


def cmd_run(a):
    from seg_teacher_student import ThingsTeacher
    sess = a.session
    out = os.path.join(a.out)
    os.makedirs(out, exist_ok=True)
    rc = Rect()
    tL = read_t(sess, "right")                      # file right = fisicamente sinistra
    tag = a.tag
    teacher = ThingsTeacher(a.device)
    if teacher.kind == "sam3":
        teacher.pred.args.save = False
    vL = os.path.join(LOGS, f"{sess}_right.h264"); vR = os.path.join(LOGS, f"{sess}_left.h264")
    PW, S = 440, 0.8
    pw, ph = int(W * S), int(H * S)
    raw = os.path.join(out, f"fuso_{tag}_raw.mp4")
    vw = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), 15, (pw + PW, ph))
    fo = csv.writer(open(os.path.join(out, f"objects_{tag}.csv"), "w", newline=""))
    fo.writerow(["frame", "t_ms", "classe", "conf", "x1", "y1", "x2", "y2", "u_c", "v_c", "Z_m", "Z_p25", "Z_p75",
                 "n_valid", "frac_valid", "area_px"])
    enc = None
    cur, seen, total = [], defaultdict(int), defaultdict(float)
    t_sam = []
    end = a.start + a.n
    gl, gr = gray_frames(vL), gray_frames(vR)
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i < a.start:
            continue
        if i >= end:
            break
        L, R = rc(Lr, Rr)
        if (i - a.start) % a.step == 0:
            t0 = time.time()
            disp = rc.disparity(L, R)
            img3 = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
            r = teacher(img3)
            t_sam.append(time.time() - t0)
            cur = []
            if r is not None and r.boxes is not None and len(r.boxes):
                order = np.argsort(-r.boxes.conf.cpu().numpy())
                keepk, kb = [], []
                for k in order:                                  # NMS tra classi: stesso oggetto con 2 nomi -> 1
                    bb = r.boxes.xyxy[k].tolist()
                    if all(iou(bb, o) < 0.7 for o in kb):
                        keepk.append(int(k)); kb.append(bb)
                names = __import__("seg_teacher_student").THINGS
                polys = r.masks.xy if r.masks is not None else []
                allb, allc, allf = r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist()
                for k in keepk:
                    b, c, cf = allb[k], allc[k], allf[k]
                    if k >= len(polys) or len(polys[k]) < 3:
                        continue
                    m = np.zeros((H, W), np.uint8)
                    cv2.fillPoly(m, [polys[k].astype(np.int32)], 1)
                    bw, bh = max(1, b[2] - b[0]), max(1, b[3] - b[1])
                    md = mask_depth(rc, disp, m, thin_frac=float(m.sum()) / (bw * bh))
                    ys, xs = np.nonzero(m)
                    row = [i, tL[i], names[c], round(cf, 3), *[int(v) for v in b], int(xs.mean()), int(ys.mean())]
                    if md and md[0] <= a.zmax and cf >= 0.5 and md[3] >= 150:
                        row += [round(md[0], 2), round(md[1], 2), round(md[2], 2), md[3], round(md[4], 2)]
                        cur.append((names[c], cf, polys[k], md[0], b, m))
                    elif md:
                        row += [round(md[0], 2), round(md[1], 2), round(md[2], 2), md[3], round(md[4], 2)]
                    else:
                        row += [None, None, None, 0, 0]
                    row += [int(m.sum())]
                    fo.writerow(row)
                    seen[names[c]] += 1
            if i % 150 == 0:
                print(f"frame {i}  {1000*np.mean(t_sam[-20:]):.0f} ms/passata  oggetti {len(cur)}", flush=True)
        img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
        ov = img.copy()
        for cls, cf, poly, Z, b, m in cur:
            ov[m > 0] = zcol(Z)
        img = cv2.addWeighted(img, 0.6, ov, 0.4, 0)
        placed = []
        for cls, cf, poly, Z, b, m in sorted(cur, key=lambda o: -o[3]):     # i vicini sopra i lontani
            col = zcol(Z)
            cv2.polylines(img, [poly.astype(np.int32)], True, col, 2)
            placed.append(label_img(img, b[0], b[1] - 44, f"{Z:.1f} m", f"{cls} {cf:.2f}", col))
        cv2.putText(img, f"#001 depth stereo rettificata | f={i} t={tL[i]/1000:.1f}s", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        panel = np.zeros((ph, PW, 3), np.uint8)
        y = 24
        cv2.putText(panel, "OGGETTI (vicini prima)", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        for cls, cf, poly, Z, b, m in sorted(cur, key=lambda o: o[3])[:16]:
            y += 24
            cv2.rectangle(panel, (10, y - 14), (24, y), zcol(Z), -1)
            cv2.putText(panel, f"{Z:5.1f} m  {cls}  ({cf:.2f})", (32, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (230, 230, 230), 1)
        y = ph - 60 - 18 * min(len(seen), 8)
        cv2.putText(panel, "visti finora (rilevazioni)", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
        for cls, n in sorted(seen.items(), key=lambda x: -x[1])[:8]:
            y += 18
            cv2.putText(panel, f"{cls}: {n}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
        cv2.putText(panel, "Z = mediana disparita' su maschera, calib 2026-11-09", (10, ph - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 120, 120), 1)
        vw.write(np.hstack([cv2.resize(img, (pw, ph)), panel]))
    vw.release()
    dst = os.path.join(out, f"fuso_{tag}.mp4")
    if subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p",
                       dst]).returncode == 0:
        os.remove(raw)
    json.dump(dict(sess=sess, start=a.start, n=a.n, step=a.step, teacher=teacher.kind,
                   ms_per_pass=round(1000 * float(np.median(t_sam)), 0), detections=dict(seen)),
              open(os.path.join(out, f"summary_{tag}.json"), "w"), indent=1)
    print("fatto", dst)


# ------------------------------------------------------------------ banco fisso
def cmd_banco(a):
    rc = Rect()
    M = pickle.load(open(a.meas, "rb"))
    sess = "session_20261109_093216"
    tL = read_t(sess, "right")
    want = {}
    for mi, m in enumerate(M):
        for t, ok in zip(m["t"], m["ok"]):
            if ok:
                want.setdefault(int(round(t * 15)), []).append(mi)
    gl = gray_frames(os.path.join(LOGS, f"{sess}_right.h264")); gr = gray_frames(os.path.join(LOGS, f"{sess}_left.h264"))
    res = defaultdict(list)
    last = max(want)
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i > last:
            break
        if i not in want:
            continue
        L, R = rc(Lr, Rr)
        disp = rc.disparity(L, R)
        for mi in want[i]:
            m = M[mi]
            k = list(m["t"]).index(next(t for t in m["t"] if int(round(t * 15)) == i))
            u = rc.rect_pt(m["b1"][k])[0]
            Z0 = m["Z"]
            hw = max(6, int(0.10 * rc.f / Z0))             # +-10 cm attorno al punto del tabellone
            x0, x1, y0, y1 = int(u[0]) - hw, int(u[0]) + hw, int(u[1]) - hw, int(u[1]) + hw
            v = disp[max(0, y0):y1, max(0, x0):x1]
            v = v[v > 4]
            if len(v) >= 20:
                res[mi].append((float(np.median(v)), len(v)))
    rows = []
    for mi, m in enumerate(M):
        if not res[mi]:
            rows.append(dict(Z_m=m["Z"], Z_sgbm_m=None)); continue
        d = np.array([r[0] for r in res[mi]])
        Z = rc.Z(float(np.median(d)))
        rows.append(dict(Z_m=m["Z"], role="verifica" if m["Z"] in (4, 6, 8, 12) else "fit", n_frames=len(d),
                         d_med_px=round(float(np.median(d)), 2), Z_sgbm_m=round(Z, 3),
                         err_pct=round(100 * (Z - m["Z"]) / m["Z"], 2)))
        print(rows[-1])
    json.dump(rows, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run"); r.add_argument("--session", default="session_20261109_094146")
    r.add_argument("--start", type=int, default=4500); r.add_argument("--n", type=int, default=2700)
    r.add_argument("--step", type=int, default=3); r.add_argument("--device", default="mps")
    r.add_argument("--tag", default="clip"); r.add_argument("--zmax", type=float, default=30.0); r.add_argument("--out", default=os.path.join(HERE, "out_20261109"))
    b = sp.add_parser("banco"); b.add_argument("--meas", required=True)
    b.add_argument("--out", default=os.path.join(HERE, "out_20261109", "banco_sgbm.json"))
    a = ap.parse_args()
    {"run": cmd_run, "banco": cmd_banco}[a.cmd](a)
