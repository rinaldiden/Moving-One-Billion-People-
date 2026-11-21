#!/usr/bin/env python3
"""giro_logger001.py — video del giro di asmile-logger001 con l'ULTIMA versione del video di #001 (video_fluido_001.py VFMODE v14), 21/11/2026.
Non cambia #001: stadio A (depth_fluido_a_001) e stadio B (video_fluido_001) vengono ripresi tali e quali con sostituzioni a runtime (vedi giro_logger001_lib.py);
per lo stadio B si legge il sorgente di video_fluido_001.py e si applicano sostituzioni di testo ESPLICITE (cx immagine, focale, testo barra senza sterzo, Ego del logger),
ognuna con assert. Cosi' ogni miglioria futura di #001 si propaga e #001 non e' toccato.
Sottocomandi:  sel | sam [--step N] | a | b [--jpg i1,i2,..]
Ambiente: GL_CAL = json di calibrazione (default: CANDIDATO_20261121 se esiste, altrimenti self 18/11), GL_OUT = cartella di lavoro.
"""
import os, sys, json, time, pickle, csv, types, argparse
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import giro_logger001_lib as G
import depth_seg_001 as D
OUT = os.environ.get("GL_OUT", os.path.join(G.ROOT, "asmile-loggers", "_work", "giro_logger001_20261121")); os.makedirs(OUT, exist_ok=True)
CAL_SELF18 = os.path.join(G.CAL_DIR, "calib_asmile-logger.CANDIDATO_self_20261118.json")
CAL = os.environ.get("GL_CAL") or (G.CAL_NEW if os.path.exists(G.CAL_NEW) else CAL_SELF18)
SESS = "session_20261121_logger"

# ---- sostituzioni di D (PRIMA di importare i moduli che copiano D.CAM_H/PITCH all'import)
D.CAM_H = G.CAM_H_LOGGER; D.PITCH = np.radians(7.3)       # pitch dal piano strada (orizzonte a riga ~280 su 800, f=935: atan(120/935)=7.3 gradi)
RectLogger, CAL_USED, CAL_D = G.make_rect_class(D, CAL)
D.Rect = RectLogger
sel, FT, EGO = G.select_frames()
SESSION = G.Session(sel, FT)
D.gray_frames = lambda path: SESSION.gen("L" if str(path).endswith("L") else "R")
D.read_t = lambda sess, cam: SESSION.t
_rc = RectLogger(); F_RECT = _rc.f; CX_RECT = float(_rc.cx)


def cmd_sel(a):
    print(len(sel), "fotogrammi scelti,", round(len(sel) / 15), "s;", "calib", CAL_USED, "f", F_RECT, "cx", CX_RECT)
    cut = np.nonzero(np.diff(sel) > 1)[0]
    s0 = 0
    for c in list(cut) + [len(sel) - 1]:
        print("tratto", sel[s0], sel[c], round((sel[c] - sel[s0]) / 15), "s", EGO.wall(FT[sel[s0]]).strftime("%H:%M:%S"), "-", EGO.wall(FT[sel[c]]).strftime("%H:%M:%S")); s0 = c + 1


def sam_record(rc, th, i, Limg, S):
    """record SAM nello stesso formato di seg_sam3_001.py (stesse soglie/tier)"""
    from seg_sam3_001 import tier, EGO_LIKE
    img = cv2.cvtColor(Limg, cv2.COLOR_GRAY2BGR); h, w = Limg.shape
    th.pred.set_image(img); res = th.pred(text=S.THINGS)[0]; dets = []
    if res is not None and res.boxes is not None and len(res.boxes):
        lap = cv2.Laplacian(Limg, cv2.CV_32F); sh = float(lap.var()) + 1e-6
        boxes, cls, conf = res.boxes.xyxy.tolist(), res.boxes.cls.int().tolist(), res.boxes.conf.tolist()
        polys = res.masks.xy if res.masks is not None else [np.zeros((0, 2))] * len(boxes)
        for k, (b, ci, cf, m) in enumerate(zip(boxes, cls, conf, polys)):
            cn = S.THINGS[ci]
            if cn in EGO_LIKE and b[3] >= h - 4 and (b[3] - b[1]) > 0.55 * h and (b[2] - b[0]) < 0.35 * w and S.ThingsTeacher.blurry(res, k, lap, sh): continue
            tr, cf_ = tier(cn, cf)
            dets.append(dict(class_raw=cn, class_final=cf_, tier=tr, conf=round(cf, 3), box=[int(v) for v in b], area_px=int(cv2.contourArea(m.astype(np.float32))) if len(m) else 0, poly=m.astype(np.int32).tolist()))
    dets.sort(key=lambda d: d["conf"])
    for j, d in enumerate(dets): d["idx"] = j + 1
    return dict(frame=i, t_ms=SESSION.t[i], n_det=len(dets), detections=dets[:250], ego_excluded=[])


def cmd_sam(a):
    sys.path.insert(0, os.path.join(G.ROOT, "training", "segmentation"))
    import seg_teacher_student as S
    th = S.ThingsTeacher(a.device); assert th.kind == "sam3"
    th.pred.args.save = False; th.pred.args.show = False
    rc = RectLogger(); fn = os.path.join(OUT, "sam_index.jsonl")
    done = {json.loads(l)["frame"] for l in open(fn)} if os.path.exists(fn) else set()
    fo = open(fn, "a"); t0 = time.time(); n = 0
    for i, g in enumerate(SESSION.gen("L")):
        if i % a.step or i in done: continue
        L = cv2.remap(g, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR)
        tt = time.time(); rec = sam_record(rc, th, i, L, S); rec["sam3_s"] = round(time.time() - tt, 2)
        fo.write(json.dumps(rec) + "\n"); fo.flush(); n += 1
        if n % 20 == 0: print(f"sam {n}/{len(sel) // a.step}  {(time.time() - t0) / n:.2f} s/passata", flush=True)
    print("sam fatto", n)


def load_sam():
    fn = os.path.join(OUT, "sam_index.jsonl"); recs = {}
    for l in open(fn):
        try: r = json.loads(l)
        except Exception: continue
        recs[r["frame"]] = r
    return recs, np.array(sorted(recs))


def cmd_a(a):
    import ego_logger001
    recs, keys = load_sam()
    os.environ["VFA_OUT"] = OUT
    import depth_fluido_a_001 as A
    def sam_get(path, cache, i, timeout=0):
        j = int(keys[np.argmin(np.abs(keys - i))]); r = dict(recs[j]); r["frame"] = i; r["lag"] = i - j; return r     # il SAM piu' vicino nel tempo (<= step/2 fotogrammi)
    A.sam_get = sam_get; A.OUT = OUT; A.Ego = lambda sess: EGO
    sys.argv = ["a", SESS, "0", os.environ.get("GL_NMAX", str(len(sel)))]
    A.main()


def stage_b_module():
    """video_fluido_001.py (ultima versione) con sostituzioni ESPLICITE per il logger"""
    src = open(os.path.join(HERE, "video_fluido_001.py")).read()
    def rep(old, new):
        nonlocal src
        assert src.count(old) >= 1, "sostituzione non trovata: " + old[:60]
        src = src.replace(old, new)
    rep("from ego_001 import Ego, x_path, x_arc, CENTER, DEG_STEP", "from ego_001 import x_path, x_arc, CENTER, DEG_STEP\ndef Ego(sess):\n    return EGO_OBJ")
    rep("F_PX, B_M = 1379.8882680918412, 0.19656132417315123", "F_PX, B_M = GL_F, 0.2")
    rep("out = img.copy(); cx = 660.142", "out = img.copy(); cx = GL_CX")
    rep("sterzo {st:+.0f} gradi (+ = destra)   curvatura", "(logger: niente sterzo, curvatura da giroscopio)   curvatura")
    rep("tabella soglie_attuazione_001 v", "soglie PROXY #001 (il logger non ha le sue) v")
    rep("WALL = load_wall(sess)", "WALL = lambda t_: EGO_OBJ.wall(t_).strftime('%H:%M:%S.%f')[:-5]")
    m = types.ModuleType("video_fluido_logger001"); m.__file__ = os.path.join(HERE, "video_fluido_001.py")
    m.GL_F = F_RECT; m.GL_CX = CX_RECT; m.EGO_OBJ = EGO
    sys.modules["video_fluido_logger001"] = m
    exec(compile(src, "video_fluido_001.py[logger001]", "exec"), m.__dict__)
    import bordi_001 as BD
    BD.F_PX, BD.B_M, BD.CX = F_RECT, 0.2, CX_RECT
    return m


def cmd_b(a):
    os.environ["VF_OUT_A"] = OUT; os.environ["VF_OUT"] = OUT
    m = stage_b_module(); m.OUT_A = OUT; m.OUT = OUT
    jpg = a.jpg
    sys.argv = ["b", SESS, "--out", os.path.join(OUT, "video_giro.mp4")] + (["--jpg", jpg] if jpg else [])
    orig = m.draw; nome = os.path.basename(CAL_USED)
    righe = ("CALIBRAZIONE VECCHIA/PROVVISORIA", "autocalibrazione 18/11 (non quella di oggi)") if "20261121" not in nome else ("CALIBRAZIONE 21/11 (candidato)", nome[:42])
    def draw2(*args, **kw):
        canvas, ttc = orig(*args, **kw)
        cv2.rectangle(canvas, (916, 8), (1272, 74), (0, 0, 0), -1); cv2.rectangle(canvas, (916, 8), (1272, 74), (0, 0, 255), 2)
        cv2.putText(canvas, righe[0], (922, 34), cv2.FONT_HERSHEY_DUPLEX, 0.5, (60, 60, 255), 2, cv2.LINE_AA)
        cv2.putText(canvas, righe[1], (922, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas, ttc
    m.draw = draw2
    m.main()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("sel"); s = sp.add_parser("sam"); s.add_argument("--step", type=int, default=5); s.add_argument("--device", default="mps")
    sp.add_parser("a"); b = sp.add_parser("b"); b.add_argument("--jpg", default="")
    a = ap.parse_args(); {"sel": cmd_sel, "sam": cmd_sam, "a": cmd_a, "b": cmd_b}[a.cmd](a)
