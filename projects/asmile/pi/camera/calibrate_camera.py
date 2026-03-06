#!/usr/bin/env python3
"""
Camera calibration using OpenCV with a chessboard pattern.

Usage:
  1. Print a chessboard pattern (default 9x6 inner corners) on A4/Letter paper
     and attach it to a flat rigid surface.
  2. Run this script — it will capture images from the camera (RTSP or local).
  3. Press SPACE to capture a frame, aim for 15-25 captures from different angles.
  4. Press 'c' to run calibration once you have enough captures.
  5. Press 'q' to quit.

The calibration result (camera matrix, distortion coefficients) is saved to a
YAML file that can be loaded later for undistortion.
"""

import cv2
import numpy as np
import os
import sys
import time
import argparse
import json
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser(description="Camera calibration with chessboard")
    p.add_argument("--source", default="rtsp://192.168.1.112:8554/stream",
                   help="Video source: RTSP URL, device index (0,1..), or video file")
    p.add_argument("--cols", type=int, default=9,
                   help="Number of inner corners per row (default: 9)")
    p.add_argument("--rows", type=int, default=6,
                   help="Number of inner corners per column (default: 6)")
    p.add_argument("--square-size", type=float, default=25.0,
                   help="Size of a chessboard square in mm (default: 25)")
    p.add_argument("--output", default=None,
                   help="Output calibration file path (default: auto-generated)")
    p.add_argument("--img-dir", default=None,
                   help="Directory to save captured images (default: ./calibration_images)")
    p.add_argument("--min-captures", type=int, default=15,
                   help="Minimum captures before allowing calibration (default: 15)")
    p.add_argument("--no-display", action="store_true",
                   help="Headless mode: auto-capture from all frames (for pre-recorded video)")
    return p.parse_args()


def open_camera(source):
    """Open video source — RTSP URL, device index, or file."""
    # Try as integer (local camera index)
    try:
        idx = int(source)
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            print(f"Opened local camera {idx}")
            return cap
    except ValueError:
        pass

    # Try as URL or file path
    # For RTSP, use TCP transport for reliability
    if source.startswith("rtsp://"):
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    else:
        cap = cv2.VideoCapture(source)

    if cap.isOpened():
        print(f"Opened source: {source}")
        return cap

    print(f"ERROR: Cannot open source: {source}")
    sys.exit(1)


def calibrate(obj_points, img_points, img_size):
    """Run camera calibration and return results."""
    print(f"\nCalibrating with {len(obj_points)} images...")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, img_size, None, None
    )

    # Compute reprojection error
    total_error = 0
    for i in range(len(obj_points)):
        projected, _ = cv2.projectPoints(obj_points[i], rvecs[i], tvecs[i],
                                         camera_matrix, dist_coeffs)
        error = cv2.norm(img_points[i], projected, cv2.NORM_L2) / len(projected)
        total_error += error
    mean_error = total_error / len(obj_points)

    print(f"Calibration RMS error: {ret:.4f}")
    print(f"Mean reprojection error: {mean_error:.4f} pixels")
    print(f"\nCamera Matrix:\n{camera_matrix}")
    print(f"\nDistortion Coefficients:\n{dist_coeffs.ravel()}")

    return ret, camera_matrix, dist_coeffs, rvecs, tvecs, mean_error


def save_calibration(filepath, camera_matrix, dist_coeffs, img_size, rms_error, mean_error, square_size, n_images):
    """Save calibration to YAML file (OpenCV FileStorage format)."""
    fs = cv2.FileStorage(filepath, cv2.FILE_STORAGE_WRITE)
    fs.write("calibration_date", datetime.now().isoformat())
    fs.write("image_width", img_size[0])
    fs.write("image_height", img_size[1])
    fs.write("square_size_mm", square_size)
    fs.write("n_images", n_images)
    fs.write("rms_error", rms_error)
    fs.write("mean_reprojection_error", mean_error)
    fs.write("camera_matrix", camera_matrix)
    fs.write("dist_coeffs", dist_coeffs)

    # Also compute and save optimal new camera matrix
    new_matrix, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, img_size, 1, img_size
    )
    fs.write("new_camera_matrix", new_matrix)
    fs.write("roi_x", roi[0])
    fs.write("roi_y", roi[1])
    fs.write("roi_w", roi[2])
    fs.write("roi_h", roi[3])
    fs.release()
    print(f"\nCalibration saved to: {filepath}")


def load_calibration(filepath):
    """Load calibration from YAML file."""
    fs = cv2.FileStorage(filepath, cv2.FILE_STORAGE_READ)
    camera_matrix = fs.getNode("camera_matrix").mat()
    dist_coeffs = fs.getNode("dist_coeffs").mat()
    img_w = int(fs.getNode("image_width").real())
    img_h = int(fs.getNode("image_height").real())
    new_camera_matrix = fs.getNode("new_camera_matrix").mat()
    fs.release()
    return camera_matrix, dist_coeffs, (img_w, img_h), new_camera_matrix


def main():
    args = parse_args()

    board_size = (args.cols, args.rows)
    square_size = args.square_size

    # Prepare object points (0,0,0), (1,0,0), (2,0,0) ... scaled by square_size
    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
    objp *= square_size

    obj_points = []  # 3D points in real world
    img_points = []  # 2D points in image plane

    # Image save directory
    img_dir = args.img_dir or os.path.join(os.path.dirname(__file__), "calibration_images")
    os.makedirs(img_dir, exist_ok=True)

    cap = open_camera(args.source)
    img_size = None
    capture_count = 0

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    print(f"\nChessboard: {args.cols}x{args.rows} inner corners, {square_size}mm squares")
    print(f"Images will be saved to: {img_dir}")
    if not args.no_display:
        print("\nControls:")
        print("  SPACE  - Capture frame")
        print("  c      - Run calibration (need >= {args.min_captures} captures)")
        print("  u      - Toggle undistort preview (after calibration)")
        print("  q/ESC  - Quit")

    calibrated = False
    camera_matrix = None
    dist_coeffs = None
    show_undistorted = False
    last_capture_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            if args.no_display:
                break
            print("Failed to read frame, retrying...")
            time.sleep(0.5)
            continue

        if img_size is None:
            img_size = (frame.shape[1], frame.shape[0])
            print(f"Frame size: {img_size[0]}x{img_size[1]}")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        display = frame.copy()

        # Find chessboard corners
        found, corners = cv2.findChessboardCorners(
            gray, board_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if found:
            # Refine corner positions
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            cv2.drawChessboardCorners(display, board_size, corners_refined, found)

            # Auto-capture in headless mode
            if args.no_display:
                now = time.time()
                if now - last_capture_time > 1.0:  # max 1 capture per second
                    obj_points.append(objp)
                    img_points.append(corners_refined)
                    capture_count += 1
                    img_path = os.path.join(img_dir, f"calib_{capture_count:03d}.png")
                    cv2.imwrite(img_path, frame)
                    print(f"  Captured {capture_count}: {img_path}")
                    last_capture_time = now

        if not args.no_display:
            # Show status
            status = f"Captures: {capture_count}/{args.min_captures}"
            if found:
                status += " | PATTERN FOUND - press SPACE"
            color = (0, 255, 0) if found else (0, 0, 255)
            cv2.putText(display, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            if calibrated and show_undistorted:
                display = cv2.undistort(display, camera_matrix, dist_coeffs)
                cv2.putText(display, "UNDISTORTED", (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (255, 0, 0), 2)

            cv2.imshow("Camera Calibration", display)
            key = cv2.waitKey(30) & 0xFF

            if key == ord('q') or key == 27:
                break
            elif key == ord(' ') and found:
                obj_points.append(objp)
                img_points.append(corners_refined)
                capture_count += 1
                img_path = os.path.join(img_dir, f"calib_{capture_count:03d}.png")
                cv2.imwrite(img_path, frame)
                print(f"  Captured {capture_count}: {img_path}")
            elif key == ord('c') and capture_count >= args.min_captures:
                rms, camera_matrix, dist_coeffs, rvecs, tvecs, mean_err = calibrate(
                    obj_points, img_points, img_size
                )
                output_path = args.output or os.path.join(
                    os.path.dirname(__file__), "camera_calibration.yaml"
                )
                save_calibration(output_path, camera_matrix, dist_coeffs, img_size,
                                 rms, mean_err, square_size, capture_count)
                calibrated = True
            elif key == ord('c') and capture_count < args.min_captures:
                print(f"  Need at least {args.min_captures} captures (have {capture_count})")
            elif key == ord('u') and calibrated:
                show_undistorted = not show_undistorted

    # Auto-calibrate in headless mode
    if args.no_display and capture_count >= args.min_captures:
        rms, camera_matrix, dist_coeffs, rvecs, tvecs, mean_err = calibrate(
            obj_points, img_points, img_size
        )
        output_path = args.output or os.path.join(
            os.path.dirname(__file__), "camera_calibration.yaml"
        )
        save_calibration(output_path, camera_matrix, dist_coeffs, img_size,
                         rms, mean_err, square_size, capture_count)
    elif args.no_display and capture_count < args.min_captures:
        print(f"\nOnly {capture_count} valid captures found (need {args.min_captures})")

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
