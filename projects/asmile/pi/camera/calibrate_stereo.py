#!/usr/bin/env python3
"""
Stereo calibration for Arducam Camarray (dual OV9281, side-by-side).

The camera outputs a single 1280x400 frame: left 640x400 | right 640x400.
This script:
  1. Captures frames from the RTSP stream (or saved images)
  2. Splits each frame into left/right
  3. Finds chessboard corners in both halves
  4. Calibrates each camera individually, then stereo pair
  5. Computes rectification maps for disparity/depth

Usage (headless, capture from stream):
  python3 calibrate_stereo.py --capture --source rtsp://localhost:8554/stream

Usage (from saved images):
  python3 calibrate_stereo.py --img-dir ./calibration_images

Controls (if display available, i.e. X forwarding):
  SPACE  - Capture frame (only when pattern found in BOTH halves)
  c      - Run calibration
  q/ESC  - Quit
"""

import cv2
import numpy as np
import os
import sys
import time
import argparse
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser(description="Stereo calibration for Arducam Camarray")
    p.add_argument("--source", default="rtsp://localhost:8554/stream",
                   help="RTSP URL or device index")
    p.add_argument("--cols", type=int, default=9,
                   help="Inner corners per row (default: 9)")
    p.add_argument("--rows", type=int, default=6,
                   help="Inner corners per column (default: 6)")
    p.add_argument("--square-size", type=float, default=29.0,
                   help="Square size in mm (default: 29)")
    p.add_argument("--output", default=None,
                   help="Output calibration file (default: stereo_calibration.yaml)")
    p.add_argument("--img-dir", default=None,
                   help="Directory with saved stereo frames (skip capture)")
    p.add_argument("--capture", action="store_true",
                   help="Capture mode: grab frames from stream")
    p.add_argument("--save-dir", default=None,
                   help="Where to save captured frames (default: ./stereo_captures)")
    p.add_argument("--min-captures", type=int, default=15,
                   help="Minimum captures for calibration")
    p.add_argument("--headless", action="store_true",
                   help="No GUI — auto-capture when pattern found in both halves")
    p.add_argument("--max-captures", type=int, default=40,
                   help="Stop auto-capture after this many (headless mode)")
    return p.parse_args()


def split_stereo(frame):
    """Split side-by-side frame into left and right halves."""
    h, w = frame.shape[:2]
    mid = w // 2
    return frame[:, :mid], frame[:, mid:]


def find_corners(gray, board_size, criteria):
    """Find and refine chessboard corners."""
    found, corners = cv2.findChessboardCorners(
        gray, board_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_FAST_CHECK | cv2.CALIB_CB_NORMALIZE_IMAGE
    )
    if found:
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    return found, corners


def calibrate_single(obj_points, img_points, img_size, name):
    """Calibrate a single camera."""
    print(f"\nCalibrating {name} camera ({len(obj_points)} images)...")
    rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, img_size, None, None
    )
    print(f"  {name} RMS error: {rms:.4f}")
    return rms, mtx, dist, rvecs, tvecs


def calibrate_stereo(obj_pts, img_pts_l, img_pts_r, img_size,
                     mtx_l, dist_l, mtx_r, dist_r):
    """Run stereo calibration."""
    print(f"\nRunning stereo calibration ({len(obj_pts)} image pairs)...")

    flags = (cv2.CALIB_FIX_INTRINSIC)

    rms, M1, D1, M2, D2, R, T, E, F = cv2.stereoCalibrate(
        obj_pts, img_pts_l, img_pts_r,
        mtx_l, dist_l, mtx_r, dist_r,
        img_size, flags=flags,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    )

    print(f"Stereo RMS error: {rms:.4f}")
    print(f"Baseline (T): [{T[0,0]:.2f}, {T[1,0]:.2f}, {T[2,0]:.2f}] mm")
    baseline_mm = np.linalg.norm(T)
    print(f"Baseline distance: {baseline_mm:.2f} mm")

    return rms, M1, D1, M2, D2, R, T, E, F


def compute_rectification(M1, D1, M2, D2, R, T, img_size):
    """Compute stereo rectification maps."""
    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        M1, D1, M2, D2, img_size, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0
    )

    map1_l, map2_l = cv2.initUndistortRectifyMap(M1, D1, R1, P1, img_size, cv2.CV_16SC2)
    map1_r, map2_r = cv2.initUndistortRectifyMap(M2, D2, R2, P2, img_size, cv2.CV_16SC2)

    return R1, R2, P1, P2, Q, roi1, roi2, map1_l, map2_l, map1_r, map2_r


def save_calibration(filepath, M1, D1, M2, D2, R, T, E, F,
                     R1, R2, P1, P2, Q, img_size, rms_mono_l, rms_mono_r,
                     rms_stereo, square_size, n_images):
    """Save full stereo calibration to YAML."""
    fs = cv2.FileStorage(filepath, cv2.FILE_STORAGE_WRITE)
    fs.write("calibration_date", datetime.now().isoformat())
    fs.write("image_width", img_size[0])
    fs.write("image_height", img_size[1])
    fs.write("square_size_mm", square_size)
    fs.write("n_image_pairs", n_images)
    fs.write("rms_left", rms_mono_l)
    fs.write("rms_right", rms_mono_r)
    fs.write("rms_stereo", rms_stereo)

    # Intrinsics
    fs.write("camera_matrix_left", M1)
    fs.write("dist_coeffs_left", D1)
    fs.write("camera_matrix_right", M2)
    fs.write("dist_coeffs_right", D2)

    # Extrinsics
    fs.write("R", R)
    fs.write("T", T)
    fs.write("E", E)
    fs.write("F", F)

    # Rectification
    fs.write("R1", R1)
    fs.write("R2", R2)
    fs.write("P1", P1)
    fs.write("P2", P2)
    fs.write("Q", Q)

    fs.release()
    print(f"\nCalibration saved to: {filepath}")


def capture_from_stream(args, board_size, objp, criteria):
    """Capture calibration frames from live stream."""
    save_dir = args.save_dir or os.path.join(os.path.dirname(__file__), "stereo_captures")
    os.makedirs(save_dir, exist_ok=True)

    source = args.source
    try:
        source = int(source)
    except ValueError:
        pass

    if isinstance(source, str) and source.startswith("rtsp://"):
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"ERROR: Cannot open {source}")
        sys.exit(1)

    obj_points = []
    img_points_l = []
    img_points_r = []
    img_size = None
    count = 0
    last_capture = 0
    use_gui = not args.headless

    if use_gui:
        try:
            # Test if display available
            cv2.namedWindow("Stereo Calibration", cv2.WINDOW_NORMAL)
        except cv2.error:
            print("No display available, switching to headless mode")
            use_gui = False

    print(f"\nBoard: {args.cols}x{args.rows} corners, {args.square_size}mm squares")
    print(f"Saving to: {save_dir}")
    if use_gui:
        print("SPACE=capture, c=calibrate, q=quit")
    else:
        print(f"Headless: auto-capture up to {args.max_captures} frames")
        print("Ctrl+C to stop and calibrate with what we have")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.3)
                continue

            left, right = split_stereo(frame)
            if img_size is None:
                img_size = (left.shape[1], left.shape[0])
                print(f"Half-frame size: {img_size[0]}x{img_size[1]}")

            # Convert to grayscale
            if len(left.shape) == 3:
                gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
                gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
            else:
                gray_l, gray_r = left, right

            found_l, corners_l = find_corners(gray_l, board_size, criteria)
            found_r, corners_r = find_corners(gray_r, board_size, criteria)
            both_found = found_l and found_r

            do_capture = False

            if use_gui:
                display = frame.copy()
                if len(display.shape) == 2:
                    display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)
                mid = display.shape[1] // 2

                if found_l:
                    disp_l = display[:, :mid]
                    cv2.drawChessboardCorners(disp_l, board_size, corners_l, found_l)
                if found_r:
                    disp_r = display[:, mid:]
                    cv2.drawChessboardCorners(disp_r, board_size, corners_r, found_r)

                # Draw center divider
                cv2.line(display, (mid, 0), (mid, display.shape[0]), (0, 255, 255), 1)

                status = f"Captures: {count}/{args.min_captures}"
                if both_found:
                    status += " | BOTH FOUND - SPACE to capture"
                elif found_l:
                    status += " | Left only"
                elif found_r:
                    status += " | Right only"
                color = (0, 255, 0) if both_found else (0, 0, 255)
                cv2.putText(display, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.imshow("Stereo Calibration", display)

                key = cv2.waitKey(30) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key == ord(' ') and both_found:
                    do_capture = True
                elif key == ord('c') and count >= args.min_captures:
                    break

            else:
                # Headless auto-capture
                if both_found:
                    now = time.time()
                    if now - last_capture > 2.0:
                        do_capture = True
                        last_capture = now

                if count >= args.max_captures:
                    print(f"Reached {args.max_captures} captures, stopping.")
                    break

            if do_capture:
                obj_points.append(objp)
                img_points_l.append(corners_l)
                img_points_r.append(corners_r)
                count += 1
                fname = os.path.join(save_dir, f"stereo_{count:03d}.png")
                cv2.imwrite(fname, frame)
                print(f"  [{count}] Captured: {fname}")

    except KeyboardInterrupt:
        print("\nInterrupted.")

    cap.release()
    if use_gui:
        cv2.destroyAllWindows()

    return obj_points, img_points_l, img_points_r, img_size, count


def load_from_images(args, board_size, objp, criteria):
    """Load calibration data from saved stereo frames."""
    img_dir = args.img_dir
    files = sorted([f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.bmp'))])

    if not files:
        print(f"No images found in {img_dir}")
        sys.exit(1)

    print(f"Found {len(files)} images in {img_dir}")

    obj_points = []
    img_points_l = []
    img_points_r = []
    img_size = None
    count = 0

    for f in files:
        frame = cv2.imread(os.path.join(img_dir, f))
        if frame is None:
            continue

        left, right = split_stereo(frame)
        if img_size is None:
            img_size = (left.shape[1], left.shape[0])

        if len(left.shape) == 3:
            gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
            gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
        else:
            gray_l, gray_r = left, right

        found_l, corners_l = find_corners(gray_l, board_size, criteria)
        found_r, corners_r = find_corners(gray_r, board_size, criteria)

        if found_l and found_r:
            obj_points.append(objp)
            img_points_l.append(corners_l)
            img_points_r.append(corners_r)
            count += 1
            print(f"  [{count}] {f} - OK")
        else:
            side = "both" if not found_l and not found_r else ("left" if not found_l else "right")
            print(f"  {f} - pattern not found in {side}, skipping")

    return obj_points, img_points_l, img_points_r, img_size, count


def main():
    args = parse_args()
    board_size = (args.cols, args.rows)

    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
    objp *= args.square_size

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # Get calibration data
    if args.img_dir:
        obj_pts, pts_l, pts_r, img_size, n = load_from_images(
            args, board_size, objp, criteria)
    elif args.capture:
        obj_pts, pts_l, pts_r, img_size, n = capture_from_stream(
            args, board_size, objp, criteria)
    else:
        print("Specify --capture (live stream) or --img-dir (saved images)")
        sys.exit(1)

    if n < args.min_captures:
        print(f"\nOnly {n} valid pairs (need {args.min_captures}). "
              f"Use --min-captures {n} to force calibration with fewer.")
        sys.exit(1)

    # Calibrate each camera
    rms_l, M1, D1, _, _ = calibrate_single(obj_pts, pts_l, img_size, "LEFT")
    rms_r, M2, D2, _, _ = calibrate_single(obj_pts, pts_r, img_size, "RIGHT")

    # Stereo calibration
    rms_s, M1, D1, M2, D2, R, T, E, F = calibrate_stereo(
        obj_pts, pts_l, pts_r, img_size, M1, D1, M2, D2)

    # Rectification
    R1, R2, P1, P2, Q, roi1, roi2, *maps = compute_rectification(
        M1, D1, M2, D2, R, T, img_size)

    # Save
    output = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "stereo_calibration.yaml")
    save_calibration(output, M1, D1, M2, D2, R, T, E, F,
                     R1, R2, P1, P2, Q, img_size, rms_l, rms_r,
                     rms_s, args.square_size, n)

    # Quick quality check
    print(f"\n{'='*50}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*50}")
    print(f"  Image pairs:     {n}")
    print(f"  Left RMS:        {rms_l:.4f}")
    print(f"  Right RMS:       {rms_r:.4f}")
    print(f"  Stereo RMS:      {rms_s:.4f}")
    baseline = np.linalg.norm(T)
    print(f"  Baseline:        {baseline:.1f} mm")
    if rms_s < 0.5:
        print(f"  Quality:         EXCELLENT")
    elif rms_s < 1.0:
        print(f"  Quality:         GOOD")
    elif rms_s < 2.0:
        print(f"  Quality:         ACCEPTABLE")
    else:
        print(f"  Quality:         POOR - consider recalibrating")


if __name__ == "__main__":
    main()
