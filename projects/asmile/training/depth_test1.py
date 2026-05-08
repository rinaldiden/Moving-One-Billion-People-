#!/usr/bin/env python3
"""
depth_test1.py — ULTRA TEMPORANEO — prima prova depth stereo

BUG NOTI:
- Muro 3.92m → 3.94m (1%) OK
- Persona 2.0m → 2.03m media (1.5%) OK su alcuni frame
- Persona 1.24m su molti frame (38% errore) — artefatto SGBM
- Focale P1=1048 corretta a 1183 dal muro — 13% inspiegato
- Left/right swappati nel Camarray: compute(right_rect, left_rect)
- Depth muro liscio instabile senza il fix

DA FARE:
- Capire perché focale 1183 vs 1048
- Eliminare artefatto 1.24m
- Testare su percorso reale in movimento
- Integrare nel training pipeline
"""

import cv2
import numpy as np


def load_calibration(yaml_path):
    fs = cv2.FileStorage(yaml_path, cv2.FILE_STORAGE_READ)
    K1 = fs.getNode("camera_matrix_left").mat()
    D1 = fs.getNode("dist_coeffs_left").mat()
    K2 = fs.getNode("camera_matrix_right").mat()
    D2 = fs.getNode("dist_coeffs_right").mat()
    R = fs.getNode("R").mat()
    T = fs.getNode("T").mat()
    w = int(fs.getNode("image_width").real())
    h = int(fs.getNode("image_height").real())
    fs.release()
    return K1, D1, K2, D2, R, T, w, h


def compute_depth(frame_2560x800, K1, D1, K2, D2, R, T, w, h,
                  focal_override=1183, baseline_override=200):
    """
    Compute depth from stereo frame.

    IMPORTANT:
    - Camarray has left/right swapped: first half = "right", second = "left"
    - SGBM must compute(right_rect, left_rect) for positive disparity
    - Focal from stereoRectify (1048) is wrong, use 1183 (calibrated from wall)
    """
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, D1, K2, D2, (w, h), R, T, alpha=0)
    m1x, m1y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (w, h), cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (w, h), cv2.CV_32FC1)

    focal = focal_override
    baseline = baseline_override

    # Split frame
    left_g = cv2.cvtColor(frame_2560x800[:, :w], cv2.COLOR_BGR2GRAY) \
        if len(frame_2560x800.shape) == 3 else frame_2560x800[:, :w]
    right_g = cv2.cvtColor(frame_2560x800[:, w:], cv2.COLOR_BGR2GRAY) \
        if len(frame_2560x800.shape) == 3 else frame_2560x800[:, w:]

    # Rectify
    lr = cv2.remap(left_g, m1x, m1y, cv2.INTER_LINEAR)
    rr = cv2.remap(right_g, m2x, m2y, cv2.INTER_LINEAR)

    # SGBM — NOTE: compute(right, left) because Camarray is swapped
    stereo = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=192, blockSize=9,
        P1=8 * 3 * 9 * 9, P2=32 * 3 * 9 * 9,
        disp12MaxDiff=1, uniquenessRatio=5,
        speckleWindowSize=200, speckleRange=2,
        preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)

    disp = stereo.compute(rr, lr).astype(np.float32) / 16.0

    depth = np.zeros_like(disp)
    valid = disp > 1
    depth[valid] = (focal * baseline) / disp[valid]

    return depth, valid


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Depth test1 — ultra temporaneo")
    parser.add_argument("--video", required=True)
    parser.add_argument("--calib", default="../config/calibration/stereo_calibration_2560x800.yaml")
    parser.add_argument("--frame", type=int, default=-1, help="Frame index (-1 = middle)")
    args = parser.parse_args()

    K1, D1, K2, D2, R, T, w, h = load_calibration(args.calib)

    cap = cv2.VideoCapture(args.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fi = args.frame if args.frame >= 0 else total // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Cannot read frame")
        exit(1)

    depth, valid = compute_depth(frame, K1, D1, K2, D2, R, T, w, h)

    print(f"Frame {fi}/{total}")
    print(f"Valid pixels: {np.sum(valid)} ({np.sum(valid) / (w * h) * 100:.0f}%)")

    center = depth[h // 3:2 * h // 3, w // 3:2 * w // 3]
    vc = center[(center > 200) & (center < 15000)]
    if len(vc) > 50:
        print(f"Centro: {np.median(vc) / 1000:.2f}m")

    for name, y1, y2, x1, x2 in [
        ("sinistra", h // 4, 3 * h // 4, 0, w // 4),
        ("destra", h // 4, 3 * h // 4, 3 * w // 4, w),
        ("basso", 2 * h // 3, h, w // 4, 3 * w // 4),
    ]:
        zone = depth[y1:y2, x1:x2]
        vz = zone[(zone > 200) & (zone < 15000)]
        if len(vz) > 50:
            print(f"{name}: {np.median(vz) / 1000:.2f}m")
