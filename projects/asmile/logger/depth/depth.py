#!/usr/bin/env python3
"""
depth.py — profondita' metrica dalle coppie stereo del logger.

Due path (teacher-forte-offline -> student-leggero-edge, come Tesla):
  - SGBM + WLS + subpixel + left-right consistency  -> leggero, gira su Pi 5
    ed e' il path GARANTITO. Metrico: Z = f*B/d con B=200mm.
  - CREStereo ONNX (opzionale, --model x.onnx) -> teacher denso offline su Mac
    (onnxruntime nativo Apple Silicon, no CUDA). Serve a generare pseudo-GT.

La disparita' SGBM esce *16 (fixed point) -> /16 per il subpixel. Il filtro WLS
(ximgproc) + right-matcher danno densita' e left-right consistency.

Uso:
  python3 depth.py --video clip.h264 --calib calib_logger.json --out /tmp/depth
  python3 depth.py --video clip.h264 --calib calib_logger.json --model crestereo.onnx
"""
import argparse
import os
import numpy as np
import cv2

from stereo_common import Calib, split_sbs, depth_from_disparity, CAM_W, CAM_H

try:
    from cv2 import ximgproc
    HAS_WLS = True
except Exception:
    HAS_WLS = False


def make_sgbm(num_disp=192, block=7):
    num_disp = (num_disp // 16) * 16
    return cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=num_disp, blockSize=block,
        P1=8 * block * block, P2=32 * block * block,
        disp12MaxDiff=1, uniquenessRatio=12,
        speckleWindowSize=100, speckleRange=2,
        preFilterCap=63, mode=cv2.StereoSGBM_MODE_HH)


def disparity_sgbm(left, right, num_disp=192, block=7, wls=True):
    """Disparita' subpixel (px). Con WLS: + right-matcher + left-right consistency."""
    sgbm = make_sgbm(num_disp, block)
    dl = sgbm.compute(left, right).astype(np.float32) / 16.0
    if wls and HAS_WLS:
        right_m = ximgproc.createRightMatcher(sgbm)
        dr = right_m.compute(right, left).astype(np.float32) / 16.0
        wf = ximgproc.createDisparityWLSFilter(sgbm)
        wf.setLambda(8000.0)
        wf.setSigmaColor(1.5)
        disp = wf.filter((dl * 16).astype(np.int16), left, None,
                         (dr * 16).astype(np.int16)).astype(np.float32) / 16.0
        return disp
    return dl


# ---------- teacher denso opzionale: CREStereo ONNX ----------
class CREStereoONNX:
    def __init__(self, model_path):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"])
        self.inp = [i.name for i in self.sess.get_inputs()]
        sh = self.sess.get_inputs()[0].shape
        self.h, self.w = int(sh[2]), int(sh[3])

    def disparity(self, left, right):
        def prep(g):
            g = cv2.resize(g, (self.w, self.h))
            g = cv2.cvtColor(g, cv2.COLOR_GRAY2RGB).astype(np.float32)
            return g.transpose(2, 0, 1)[None]
        feeds = {self.inp[0]: prep(left), self.inp[1]: prep(right)} if len(self.inp) > 1 \
            else {self.inp[0]: prep(left)}
        out = self.sess.run(None, feeds)[0]
        disp = np.squeeze(out)
        if disp.ndim == 3:
            disp = disp[0]
        # riscala la disparita' alla larghezza originale
        return cv2.resize(disp, (CAM_W, CAM_H)) * (CAM_W / self.w)


def colorize(depth, zmax=15.0):
    d = np.clip(depth, 0, zmax)
    d = (255 * (1 - d / zmax)).astype(np.uint8)
    d[depth <= 0] = 0
    return cv2.applyColorMap(d, cv2.COLORMAP_TURBO)


def object_depth(depth, mask):
    """Distanza mediana robusta dentro una maschera (per depth per-oggetto edge)."""
    vals = depth[(mask > 0) & (depth > 0)]
    return float(np.median(vals)) if vals.size else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--out", default="/tmp/asmile_depth")
    ap.add_argument("--model", help="CREStereo ONNX (teacher offline). Se assente: SGBM")
    ap.add_argument("--num-disp", type=int, default=192)
    ap.add_argument("--max-frames", type=int, default=30)
    ap.add_argument("--order", default="LR", choices=["LR", "RL"])
    ap.add_argument("--no-flip", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    calib = Calib.load(args.calib)
    rect = calib.rectify()
    f, B = rect["focal_px"], rect["baseline_m"]
    print(f"focal={f:.1f}px  baseline={B*1000:.1f}mm  WLS={'on' if HAS_WLS else 'OFF (pip opencv-contrib)'}")
    teacher = CREStereoONNX(args.model) if args.model else None
    if teacher:
        print(f"teacher CREStereo ONNX: {args.model}")

    cap = cv2.VideoCapture(args.video)
    n = 0
    while n < args.max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        left, right = split_sbs(frame, order=args.order, flip180=not args.no_flip)
        lr = cv2.remap(left, rect["m1x"], rect["m1y"], cv2.INTER_LINEAR)
        rr = cv2.remap(right, rect["m2x"], rect["m2y"], cv2.INTER_LINEAR)
        disp = teacher.disparity(lr, rr) if teacher else disparity_sgbm(lr, rr, args.num_disp)
        depth = depth_from_disparity(disp, f, B)
        np.save(f"{args.out}/depth_{n:05d}.npy", depth)
        cv2.imwrite(f"{args.out}/depth_{n:05d}.png", colorize(depth))
        mid = depth[CAM_H // 2, CAM_W // 2]
        print(f"  frame {n}: centro={mid:.2f}m  densita'={(depth>0).mean()*100:.0f}%")
        n += 1
    cap.release()
    print(f"fatto: {n} depth map -> {args.out}")


if __name__ == "__main__":
    main()
