#!/usr/bin/env python3
"""
calib_colmap.py — calibrazione stereo via COLMAP (Structure-from-Motion), SENZA
target. Alternativa "pesante" ad autorectify/ChArUco: ricostruisce intrinseci
e posa relativa delle due camere direttamente dalla GEOMETRIA della scena guidata.

Idea. La Camarray da' a ogni istante una coppia SINCRONIZZATA L|R. Spezziamo il
clip in immagini L e R separate e le diamo a COLMAP come DUE camere rigide
(una cartella per camera -> `single_camera_per_folder`): COLMAP stima
  - gli INTRINSECI di ciascuna camera (K_left, K_right, distorsione),
  - la POSA di ogni immagine (world->cam).
La posa RELATIVA L->R e' costante nel tempo (camere rigide): la mediamo su tutti
i frame in cui sia L_i sia R_i sono registrate. SfM e' a scala arbitraria, quindi
RISCALIAMO |T| alla BASELINE NOTA (200mm) — stessa ancora metrica del progetto.

Quando usarla. Non hai ne' scacchiera ne' tabellone a monitor, ma hai un clip
di guida con buona TEXTURE e un po' di PARALLASSE (la bici si muove). E' la via
piu' "a ritroso": niente setup, ma piu' lenta e serve il binario `colmap`.

Prerequisiti:
  - COLMAP installato:  brew install colmap   (Mac)  /  apt install colmap
  - clip con texture ricca e movimento (non muro liscio, non bici ferma).

Flusso:
  python3 calib_colmap.py --video clip_guida.h264 --out calib_colmap.json \
      [--frames 80] [--work /tmp/colmap_asmile] [--colmap /path/colmap]
  # poi come sempre: validate.py (muro-test) e depth.py

Output: JSON nel formato Calib (stereo_common.py) -> drop-in in tutta la pipeline.
"""
import argparse
import datetime
import os
import shutil
import subprocess
import numpy as np
import cv2

from stereo_common import Calib, split_sbs, CAM_W, CAM_H, BASELINE_MM


# ---------- 1) estrazione frame L/R dal clip ---------------------------------
def extract_frames(video, work, size, order, flip180, n_frames):
    """Scrive work/images/left/*.png e work/images/right/*.png (sincronizzate)."""
    imgdir = os.path.join(work, "images")
    ldir, rdir = os.path.join(imgdir, "left"), os.path.join(imgdir, "right")
    os.makedirs(ldir, exist_ok=True); os.makedirs(rdir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // max(1, n_frames))
    i = saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            left, right = split_sbs(frame, order=order, flip180=flip180)
            if (left.shape[1], left.shape[0]) != size:
                left = cv2.resize(left, size); right = cv2.resize(right, size)
            name = f"f{saved:04d}.png"
            cv2.imwrite(os.path.join(ldir, name), left)
            cv2.imwrite(os.path.join(rdir, name), right)
            saved += 1
        i += 1
    cap.release()
    return imgdir, saved


# ---------- 2) run COLMAP -----------------------------------------------------
def run_colmap(colmap, work, imgdir):
    """feature_extractor (2 camere, 1 per cartella) -> matcher -> mapper."""
    db = os.path.join(work, "database.db")
    sparse = os.path.join(work, "sparse")
    os.makedirs(sparse, exist_ok=True)
    if os.path.exists(db):
        os.remove(db)

    def call(args):
        print("    $ colmap " + " ".join(args))
        subprocess.run([colmap] + args, check=True)

    # OPENCV = modello pinhole + distorsione radiale/tangenziale (fx,fy,cx,cy,k1,k2,p1,p2)
    call(["feature_extractor", "--database_path", db, "--image_path", imgdir,
          "--ImageReader.single_camera_per_folder", "1",
          "--ImageReader.camera_model", "OPENCV",
          "--SiftExtraction.estimate_affine_shape", "1",
          "--SiftExtraction.domain_size_pooling", "1"])
    call(["exhaustive_matcher", "--database_path", db,
          "--SiftMatching.guided_matching", "1"])
    call(["mapper", "--database_path", db, "--image_path", imgdir,
          "--output_path", sparse,
          "--Mapper.ba_refine_principal_point", "1"])
    # modello 0 -> TXT
    model0 = os.path.join(sparse, "0")
    if not os.path.isdir(model0):
        raise SystemExit("COLMAP non ha prodotto un modello: scena con poca texture "
                         "o poco movimento. Usa un clip piu' ricco (o ChArUco).")
    txt = os.path.join(work, "model_txt")
    os.makedirs(txt, exist_ok=True)
    call(["model_converter", "--input_path", model0, "--output_path", txt,
          "--output_type", "TXT"])
    return txt


# ---------- 3) parsing del modello COLMAP ------------------------------------
def parse_cameras(path):
    """cameras.txt -> {cam_id: (model, w, h, params[])}."""
    cams = {}
    with open(os.path.join(path, "cameras.txt")) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            t = line.split()
            cams[int(t[0])] = (t[1], int(t[2]), int(t[3]),
                               [float(x) for x in t[4:]])
    return cams


def parse_images(path):
    """images.txt -> {name: (cam_id, qvec(wxyz), tvec)}. World->cam."""
    imgs = {}
    with open(os.path.join(path, "images.txt")) as f:
        lines = [l for l in f if not l.startswith("#")]
    # ogni immagine = 2 righe (header + punti2D); teniamo solo l'header
    for i in range(0, len(lines), 2):
        t = lines[i].split()
        if len(t) < 10:
            continue
        q = np.array([float(t[1]), float(t[2]), float(t[3]), float(t[4])])  # qw,qx,qy,qz
        tv = np.array([float(t[5]), float(t[6]), float(t[7])])
        cam_id = int(t[8]); name = t[9]
        imgs[name] = (cam_id, q, tv)
    return imgs


def K_from_params(model, params):
    """Matrice K dai parametri COLMAP (supporta OPENCV / PINHOLE / SIMPLE_*)."""
    p = params
    if model in ("OPENCV", "FULL_OPENCV", "OPENCV_FISHEYE"):
        fx, fy, cx, cy = p[0], p[1], p[2], p[3]
        dist = p[4:8] if len(p) >= 8 else [0, 0, 0, 0]
    elif model == "PINHOLE":
        fx, fy, cx, cy = p[0], p[1], p[2], p[3]; dist = [0, 0, 0, 0]
    elif model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
        fx = fy = p[0]; cx, cy = p[1], p[2]
        dist = [p[3], 0, 0, 0] if len(p) > 3 else [0, 0, 0, 0]
    else:
        fx = fy = p[0]; cx, cy = p[1], p[2]; dist = [0, 0, 0, 0]
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])
    d = np.array(list(dist) + [0.0] * (5 - len(dist)))[:5]
    return K, d


def qvec_to_R(q):
    """Quaternione COLMAP (w,x,y,z) -> matrice di rotazione."""
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2*(y*y+z*z), 2*(x*y - z*w),   2*(x*z + y*w)],
        [2*(x*y + z*w),   1 - 2*(x*x+z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),   2*(y*z + x*w),   1 - 2*(x*x+y*y)],
    ])


def R_to_qvec(R):
    """Rotazione -> quaternione (w,x,y,z), per mediare le rotazioni."""
    q = np.empty(4)
    tr = np.trace(R)
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        q[0] = 0.25 * s
        q[1] = (R[2, 1] - R[1, 2]) / s
        q[2] = (R[0, 2] - R[2, 0]) / s
        q[3] = (R[1, 0] - R[0, 1]) / s
    else:
        i = np.argmax([R[0, 0], R[1, 1], R[2, 2]])
        if i == 0:
            s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
            q = np.array([(R[2, 1]-R[1, 2])/s, 0.25*s,
                          (R[0, 1]+R[1, 0])/s, (R[0, 2]+R[2, 0])/s])
        elif i == 1:
            s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
            q = np.array([(R[0, 2]-R[2, 0])/s, (R[0, 1]+R[1, 0])/s,
                          0.25*s, (R[1, 2]+R[2, 1])/s])
        else:
            s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
            q = np.array([(R[1, 0]-R[0, 1])/s, (R[0, 2]+R[2, 0])/s,
                          (R[1, 2]+R[2, 1])/s, 0.25*s])
    return q / np.linalg.norm(q)


def average_quaternions(qs):
    """Media robusta di quaternioni (autovettore dominante di sum q q^T)."""
    qs = np.array([q if q[0] >= 0 else -q for q in qs])   # emisfero comune
    M = qs.T @ qs
    w, v = np.linalg.eigh(M)
    q = v[:, np.argmax(w)]
    return q / np.linalg.norm(q)


# ---------- 4) posa relativa L->R, mediata e riscalata -----------------------
def relative_pose(cams, imgs, baseline_mm):
    """
    Per ogni frame con left/fXXXX.png e right/fXXXX.png registrati, calcola la
    posa relativa L->R e la media. Ritorna (R, T, K_left, d_left, K_right,
    d_right, n_pairs, scale).
    """
    # cam_id delle due cartelle (COLMAP assegna 1 camera per cartella)
    left_cam = {imgs[n][0] for n in imgs if n.startswith("left/")}
    right_cam = {imgs[n][0] for n in imgs if n.startswith("right/")}
    if not left_cam or not right_cam:
        raise SystemExit("COLMAP non ha registrato entrambe le camere.")
    cidL, cidR = left_cam.pop(), right_cam.pop()
    K1, d1 = K_from_params(cams[cidL][0], cams[cidL][3])
    K2, d2 = K_from_params(cams[cidR][0], cams[cidR][3])

    Rs, Ts = [], []
    base = {n[len("left/"):] for n in imgs if n.startswith("left/")}
    for stem in sorted(base):
        nl, nr = "left/" + stem, "right/" + stem
        if nr not in imgs:
            continue
        _, qL, tL = imgs[nl]
        _, qR, tR = imgs[nr]
        RL, RR = qvec_to_R(qL), qvec_to_R(qR)
        # world->cam: X_L = RL X + tL ; X_R = RR X + tR
        # relativa L->R: X_R = R_rel X_L + T_rel con R_rel = RR RL^T
        R_rel = RR @ RL.T
        T_rel = tR - R_rel @ tL
        Rs.append(R_rel); Ts.append(T_rel)
    if len(Rs) < 4:
        raise SystemExit(f"Solo {len(Rs)} coppie L/R registrate: servono piu' "
                         "frame registrati (clip con piu' texture/movimento).")

    q_avg = average_quaternions([R_to_qvec(R) for R in Rs])
    R_avg = qvec_to_R(q_avg)
    T_arr = np.array(Ts)
    T_med = np.median(T_arr, axis=0)              # robusto agli outlier
    scale = baseline_mm / float(np.linalg.norm(T_med))
    T_scaled = (T_med * scale).reshape(3, 1)
    return R_avg, T_scaled, K1, d1, K2, d2, len(Rs), scale, T_arr * scale


def main():
    ap = argparse.ArgumentParser(description="Calibrazione stereo via COLMAP (SfM).")
    ap.add_argument("--video", required=True, help="clip di guida (texture + movimento)")
    ap.add_argument("--out", required=True, help="calib JSON (drop-in depth/validate)")
    ap.add_argument("--work", default="/tmp/colmap_asmile", help="cartella di lavoro COLMAP")
    ap.add_argument("--colmap", default=shutil.which("colmap") or "colmap",
                    help="path al binario colmap")
    ap.add_argument("--baseline-mm", type=float, default=BASELINE_MM,
                    help="baseline NOTA a cui riscalare T (ancora metrica)")
    ap.add_argument("--frames", type=int, default=80)
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true", help="camere NON capovolte")
    ap.add_argument("--keep", action="store_true", help="non cancellare --work a fine run")
    args = ap.parse_args()

    if not shutil.which(args.colmap) and not os.path.exists(args.colmap):
        raise SystemExit("colmap non trovato. Installa:  brew install colmap  "
                         "(Mac)  oppure  apt install colmap  (Linux). "
                         "In alternativa usa calib_charuco.py o autorectify.py.")

    size = (CAM_W, CAM_H)
    if os.path.isdir(args.work):
        shutil.rmtree(args.work)
    os.makedirs(args.work, exist_ok=True)

    print(f"[1] estraggo ~{args.frames} coppie L/R dal clip...")
    imgdir, n = extract_frames(args.video, args.work, size, args.order,
                               not args.no_flip, args.frames)
    print(f"    {n} coppie scritte in {imgdir}")

    print("[2] COLMAP SfM (feature -> match -> mapper)...")
    txt = run_colmap(args.colmap, args.work, imgdir)

    print("[3] leggo il modello e stimo la posa relativa L->R...")
    cams = parse_cameras(txt)
    imgs = parse_images(txt)
    R, T, K1, d1, K2, d2, npairs, scale, T_all = relative_pose(
        cams, imgs, args.baseline_mm)
    spread = float(np.std(np.linalg.norm(T_all, axis=1)))
    print(f"    coppie registrate: {npairs}  |  focale fx_L={K1[0,0]:.1f} fx_R={K2[0,0]:.1f}px")
    print(f"    |T| riscalato a {args.baseline_mm:.1f}mm (scala SfM x{scale:.3g}); "
          f"dispersione baseline fra i frame: {spread:.1f}mm (basso = rig rigido coerente)")

    calib = Calib(K1, d1, K2, d2, R, T, size=size, baseline_mm=args.baseline_mm)
    calib.save(args.out)
    import json
    with open(args.out) as f:
        blob = json.load(f)
    blob.update({
        "method": "COLMAP SfM (single_camera_per_folder) + baseline rescale",
        "colmap_pairs": npairs,
        "sfm_scale_to_baseline": scale,
        "baseline_spread_mm": spread,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    with open(args.out, "w") as f:
        json.dump(blob, f, indent=2)
    print(f"[4] calib salvata -> {args.out}")
    print("    NB: conferma col MURO-TEST -> python3 validate.py --calib "
          f"{args.out} --targets targets.json")
    if not args.keep:
        shutil.rmtree(args.work, ignore_errors=True)


if __name__ == "__main__":
    main()
