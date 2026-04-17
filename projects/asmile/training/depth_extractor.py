#!/usr/bin/env python3
"""
depth_extractor.py — Compute depth maps from stereo frames using calibration.

Loads stereo calibration (OpenCV FileStorage YAML), rectifies left/right frames,
computes disparity with StereoSGBM, and converts to depth in millimeters.

Usage:
    # Process all frames in a session
    python3 depth_extractor.py --session ~/wip/recorder/session_20260417_181452/ \
                               --output ~/wip/training_depth/

    # Process a single timestamp
    python3 depth_extractor.py --session ~/wip/recorder/session_20260417_181452/ \
                               --output ~/wip/training_depth/ \
                               --timestamp 2026-04-17T18:22:02.077
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

# Add parent for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame_extractor import (
    load_sensor_csv, timestamp_to_frame_index, split_stereo,
    open_video, seek_and_read, parse_timestamp, VIDEO_FPS,
)


# ---------------------------------------------------------------------------
# Calibration loader
# ---------------------------------------------------------------------------

# Default calibration path relative to this file
_THIS_DIR = Path(__file__).resolve().parent
DEFAULT_CALIB_PATH = str(_THIS_DIR.parent / "config" / "stereo_calibration.yaml")


def load_calibration(calib_path: str | None = None) -> dict:
    """Load stereo calibration from OpenCV FileStorage YAML.

    Returns dict with keys: camera_matrix_left, dist_coeffs_left,
    camera_matrix_right, dist_coeffs_right, R1, R2, P1, P2, Q, T,
    plus derived focal_px and baseline_mm.
    """
    path = calib_path or DEFAULT_CALIB_PATH
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Calibration file not found: {path}")

    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise RuntimeError(f"Cannot open calibration file: {path}")

    keys = [
        "camera_matrix_left", "dist_coeffs_left",
        "camera_matrix_right", "dist_coeffs_right",
        "R1", "R2", "P1", "P2", "Q", "T",
    ]
    calib = {}
    for k in keys:
        node = fs.getNode(k)
        if node.empty():
            raise KeyError(f"Missing calibration key: {k}")
        calib[k] = node.mat()

    fs.release()

    # Derived values
    calib["focal_px"] = calib["P1"][0, 0]
    calib["baseline_mm"] = abs(calib["T"][0, 0])

    print(f"Calibration loaded: focal={calib['focal_px']:.1f}px, "
          f"baseline={calib['baseline_mm']:.1f}mm")
    return calib


# ---------------------------------------------------------------------------
# Stereo processing
# ---------------------------------------------------------------------------

def create_stereo_matcher(num_disparities: int = 192,
                          block_size: int = 7,
                          uniqueness_ratio: int = 15) -> cv2.StereoSGBM:
    """Create a StereoSGBM matcher with tuned parameters."""
    matcher = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=num_disparities,
        blockSize=block_size,
        P1=8 * 1 * block_size * block_size,
        P2=32 * 1 * block_size * block_size,
        disp12MaxDiff=1,
        uniquenessRatio=uniqueness_ratio,
        speckleWindowSize=100,
        speckleRange=32,
        preFilterCap=63,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
    )
    return matcher


def build_rectify_maps(calib: dict, image_size: tuple[int, int] = (640, 400)):
    """Pre-compute rectification maps for left and right cameras."""
    map_left_x, map_left_y = cv2.initUndistortRectifyMap(
        calib["camera_matrix_left"], calib["dist_coeffs_left"],
        calib["R1"], calib["P1"], image_size, cv2.CV_32FC1,
    )
    map_right_x, map_right_y = cv2.initUndistortRectifyMap(
        calib["camera_matrix_right"], calib["dist_coeffs_right"],
        calib["R2"], calib["P2"], image_size, cv2.CV_32FC1,
    )
    return (map_left_x, map_left_y), (map_right_x, map_right_y)


def rectify_pair(left: np.ndarray, right: np.ndarray,
                 maps_left: tuple, maps_right: tuple) -> tuple:
    """Rectify a stereo pair using precomputed maps."""
    rect_left = cv2.remap(left, maps_left[0], maps_left[1],
                          cv2.INTER_LINEAR)
    rect_right = cv2.remap(right, maps_right[0], maps_right[1],
                           cv2.INTER_LINEAR)
    return rect_left, rect_right


def compute_depth(left_gray: np.ndarray, right_gray: np.ndarray,
                  matcher: cv2.StereoSGBM,
                  focal_px: float, baseline_mm: float) -> np.ndarray:
    """Compute depth map in millimeters from rectified grayscale pair.

    Returns float32 array where 0 means invalid/no depth.
    """
    # StereoSGBM returns disparity * 16 as int16
    disparity_raw = matcher.compute(left_gray, right_gray)
    disparity = disparity_raw.astype(np.float32) / 16.0

    # Mask invalid disparities
    valid = disparity > 0.0
    depth_mm = np.zeros_like(disparity, dtype=np.float32)
    depth_mm[valid] = (focal_px * baseline_mm) / disparity[valid]

    # Clamp unreasonable depths (> 50m)
    depth_mm[depth_mm > 50_000] = 0.0

    return depth_mm


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    """Convert to grayscale if needed."""
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

class DepthExtractor:
    """Stateful depth extractor that caches calibration and maps."""

    def __init__(self, calib_path: str | None = None,
                 num_disparities: int = 192, block_size: int = 7,
                 uniqueness_ratio: int = 15):
        self.calib = load_calibration(calib_path)
        self.matcher = create_stereo_matcher(num_disparities, block_size,
                                             uniqueness_ratio)
        self.maps_left, self.maps_right = build_rectify_maps(self.calib)

    def process_pair(self, left: np.ndarray,
                     right: np.ndarray) -> np.ndarray:
        """Process a stereo pair into a depth map (mm, float32)."""
        left_gray = to_grayscale(left)
        right_gray = to_grayscale(right)
        rect_l, rect_r = rectify_pair(left_gray, right_gray,
                                      self.maps_left, self.maps_right)
        return compute_depth(rect_l, rect_r, self.matcher,
                             self.calib["focal_px"],
                             self.calib["baseline_mm"])

    def process_stereo_frame(self, stereo_frame: np.ndarray) -> np.ndarray:
        """Process a full side-by-side stereo frame."""
        left, right = split_stereo(stereo_frame)
        return self.process_pair(left, right)


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_session(session_dir: str, output_dir: str,
                    calib_path: str | None = None,
                    timestamp: str | None = None,
                    every_n: int = 1) -> list[dict]:
    """Process a session: extract depth maps for all or one timestamp."""
    session = Path(session_dir)
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    extractor = DepthExtractor(calib_path)
    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]

    os.makedirs(output_dir, exist_ok=True)
    session_name = session.name

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Single timestamp mode
    if timestamp:
        target_ts = parse_timestamp(timestamp)
        idx = timestamp_to_frame_index(target_ts, first_ts)
        if idx >= total_frames and total_frames > 0:
            idx = total_frames - 1
        frame = seek_and_read(cap, idx)
        cap.release()
        if frame is None:
            raise RuntimeError(f"Failed to read frame {idx}")
        depth = extractor.process_stereo_frame(frame)
        ts_safe = timestamp.replace(":", "-").replace(" ", "_")
        out_path = os.path.join(output_dir, f"depth_{ts_safe}.npy")
        np.save(out_path, depth)
        print(f"Saved depth map: {out_path} "
              f"(range: {depth[depth>0].min():.0f}-{depth[depth>0].max():.0f}mm)")
        return [{"frame_idx": idx, "path": out_path}]

    # Batch mode
    results = []
    last_idx = -1
    processed = 0

    for i, row in enumerate(rows):
        if i % every_n != 0:
            continue

        frame_idx = timestamp_to_frame_index(row["_ts"], first_ts)
        if frame_idx == last_idx:
            continue
        if frame_idx >= total_frames and total_frames > 0:
            break

        frame = seek_and_read(cap, frame_idx)
        if frame is None:
            continue

        last_idx = frame_idx
        depth = extractor.process_stereo_frame(frame)

        ts_safe = row["timestamp"].replace(":", "-").replace(" ", "_")
        tag = f"{session_name}_{ts_safe}"
        out_path = os.path.join(output_dir, f"depth_{tag}.npy")
        np.save(out_path, depth)

        # Also save a uint16 PNG for visualization (mm, clamped to 65535)
        depth_u16 = np.clip(depth, 0, 65535).astype(np.uint16)
        png_path = os.path.join(output_dir, f"depth_{tag}.png")
        cv2.imwrite(png_path, depth_u16)

        results.append({
            "frame_idx": frame_idx,
            "timestamp": row["timestamp"],
            "npy_path": out_path,
            "png_path": png_path,
        })
        processed += 1

        if processed % 50 == 0:
            valid = depth[depth > 0]
            stats = (f"range {valid.min():.0f}-{valid.max():.0f}mm"
                     if valid.size > 0 else "no valid pixels")
            print(f"  Processed {processed} depth maps "
                  f"(row {i+1}/{len(rows)}) [{stats}]")

    cap.release()
    print(f"Done: {processed} depth maps saved to {output_dir}")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute depth maps from stereo video using calibration.")
    parser.add_argument("--session", required=True,
                        help="Path to session directory")
    parser.add_argument("--output", required=True,
                        help="Output directory for depth maps")
    parser.add_argument("--calibration", default=None,
                        help=f"Stereo calibration YAML (default: {DEFAULT_CALIB_PATH})")
    parser.add_argument("--timestamp", default=None,
                        help="Process single timestamp (ISO format)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Process every Nth sensor row (default: 1)")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session directory not found: {session}", file=sys.stderr)
        sys.exit(1)

    process_session(session, args.output, args.calibration,
                    args.timestamp, args.every_n)


if __name__ == "__main__":
    main()
