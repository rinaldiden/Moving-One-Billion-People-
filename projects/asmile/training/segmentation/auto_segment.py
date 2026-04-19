#!/usr/bin/env python3
"""
auto_segment.py -- Zero-ML automatic segmentation from stereo depth.

Creates initial segmentation masks using only depth maps and simple
heuristics.  No annotations, no trained models, no network downloads.
Dependencies: Python 3, OpenCV, NumPy (already on every Asmile Pi).

Pipeline
--------
1. Compute depth map from stereo pair (via depth_extractor).
2. Detect ground plane (RANSAC on bottom half of depth map).
3. Sky: top rows with invalid / very far depth.
4. Vertical obstacles: pixels significantly above the ground plane.
5. Height-based classification of obstacles.
6. Moving-object detection via consecutive-frame differencing + depth.
7. Output coloured PNG mask per frame.

Usage
-----
    python3 auto_segment.py \\
        --session ~/wip/recorder/session_20260417_181452/ \\
        --output  ~/wip/segmentation/auto/ \\
        --max-frames 100
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

# -- Sibling imports ---------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_TRAINING_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_TRAINING_DIR))

from frame_extractor import (
    load_sensor_csv,
    timestamp_to_frame_index,
    split_stereo,
    open_video,
    seek_and_read,
    VIDEO_FPS,
)
from depth_extractor import DepthExtractor

# -- Category constants ------------------------------------------------------
CAT_BACKGROUND = 0
CAT_ROAD = 1
CAT_SIDEWALK = 2
CAT_PERSON = 3
CAT_VEHICLE = 4
CAT_BICYCLE = 5
CAT_WALL = 6
CAT_BUILDING = 7
CAT_POLE = 8
CAT_VEGETATION = 9
CAT_SKY = 10
CAT_OBSTACLE = 11
CAT_ANIMAL = 12

NUM_CATEGORIES = 13

# BGR colours (OpenCV convention) matching categories.yaml
CATEGORY_COLORS_BGR = {
    0:  (0, 0, 0),
    1:  (128, 64, 128),
    2:  (232, 35, 244),
    3:  (60, 20, 220),
    4:  (142, 0, 0),
    5:  (32, 11, 119),
    6:  (156, 102, 102),
    7:  (70, 70, 70),
    8:  (153, 153, 153),
    9:  (35, 142, 107),
    10: (180, 130, 70),
    11: (0, 0, 255),
    12: (0, 165, 255),
}


# ---------------------------------------------------------------------------
# Ground-plane fitting (RANSAC)
# ---------------------------------------------------------------------------

def _pixel_to_3d(row: np.ndarray, col: np.ndarray,
                 depth_mm: np.ndarray,
                 fx: float, fy: float,
                 cx: float, cy: float):
    """Back-project pixel + depth to 3-D (X, Y, Z) in mm."""
    z = depth_mm.astype(np.float64)
    x = (col.astype(np.float64) - cx) * z / fx
    y = (row.astype(np.float64) - cy) * z / fy
    return x, y, z


def fit_ground_plane_ransac(depth_mm: np.ndarray,
                            fx: float, fy: float,
                            cx: float, cy: float,
                            n_iter: int = 200,
                            inlier_thresh_mm: float = 60.0,
                            sample_step: int = 4):
    """Fit a ground plane to the bottom half of the depth map.

    Returns (a, b, c, d) of plane  ax + by + cz + d = 0
    with the normal pointing roughly upward (positive Y in camera frame
    points downward, so b < 0 for a floor plane).
    Returns None if fitting fails.
    """
    h, w = depth_mm.shape
    # Sample from bottom half where ground is likely visible
    roi = depth_mm[h // 2:, :]
    rows_roi, cols_roi = np.where((roi > 200) & (roi < 15000))
    if len(rows_roi) < 100:
        return None
    rows_full = rows_roi + h // 2

    # Sub-sample for speed
    idx_all = np.arange(len(rows_roi))
    if len(idx_all) > 8000:
        idx_all = np.random.choice(idx_all, 8000, replace=False)
    r = rows_full[idx_all]
    c = cols_roi[idx_all]
    d = depth_mm[r, c]
    x, y, z = _pixel_to_3d(r, c, d, fx, fy, cx, cy)
    pts = np.stack([x, y, z], axis=1)  # (N, 3)

    best_plane = None
    best_inliers = 0
    rng = np.random.default_rng(42)

    for _ in range(n_iter):
        idx3 = rng.choice(len(pts), 3, replace=False)
        p0, p1, p2 = pts[idx3]
        normal = np.cross(p1 - p0, p2 - p0)
        norm_len = np.linalg.norm(normal)
        if norm_len < 1e-9:
            continue
        normal /= norm_len
        dd = -normal.dot(p0)

        dists = np.abs(pts @ normal + dd)
        n_in = int(np.sum(dists < inlier_thresh_mm))
        if n_in > best_inliers:
            best_inliers = n_in
            best_plane = (normal[0], normal[1], normal[2], dd)

    if best_plane is None:
        return None

    # Ensure normal points "up" (Y < 0 in camera coords = up in the scene)
    if best_plane[1] > 0:
        best_plane = (-best_plane[0], -best_plane[1],
                      -best_plane[2], -best_plane[3])
    return best_plane


def height_above_ground(depth_mm: np.ndarray, plane,
                        fx: float, fy: float,
                        cx: float, cy: float) -> np.ndarray:
    """Compute signed height (mm) above the ground plane for every pixel.

    Positive = above ground, negative = below.
    Pixels with depth == 0 get height = NaN.
    """
    h, w = depth_mm.shape
    rows, cols = np.mgrid[0:h, 0:w]
    valid = depth_mm > 0
    x, y, z = _pixel_to_3d(
        rows[valid].ravel(), cols[valid].ravel(),
        depth_mm[valid].ravel(), fx, fy, cx, cy,
    )
    a, b, c, d = plane
    # Signed distance from plane (positive = above ground)
    dist = a * x + b * y + c * z + d
    # The sign convention: distance > 0 means above ground given our normal
    height = np.full((h, w), np.nan, dtype=np.float64)
    height[valid] = dist
    return height


# ---------------------------------------------------------------------------
# Sky detection
# ---------------------------------------------------------------------------

def detect_sky(depth_mm: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Detect sky: top portion of frame where depth is invalid or >30m,
    and the region is bright."""
    h, w = depth_mm.shape
    sky = np.zeros((h, w), dtype=bool)
    # Start from top, scan downward row by row
    for row in range(h):
        invalid_frac = np.mean(
            (depth_mm[row] == 0) | (depth_mm[row] > 30000)
        )
        bright_frac = np.mean(gray[row] > 100) if gray is not None else 0.5
        if invalid_frac > 0.7 and bright_frac > 0.3:
            sky[row, :] = True
        else:
            # Allow a few non-sky rows then stop
            if row > 10:
                break
    return sky


# ---------------------------------------------------------------------------
# Moving-object detection
# ---------------------------------------------------------------------------

def detect_motion(prev_gray: np.ndarray, curr_gray: np.ndarray,
                  depth_mm: np.ndarray,
                  motion_thresh: int = 25,
                  min_area: int = 200) -> np.ndarray:
    """Detect moving objects by frame differencing, filtered by depth.

    Returns a boolean mask of moving pixels within 10m.
    """
    if prev_gray is None:
        return np.zeros(curr_gray.shape[:2], dtype=bool)

    diff = cv2.absdiff(prev_gray, curr_gray)
    _, motion = cv2.threshold(diff, motion_thresh, 255, cv2.THRESH_BINARY)
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    motion = cv2.morphologyEx(motion, cv2.MORPH_OPEN, kernel)
    motion = cv2.morphologyEx(motion, cv2.MORPH_CLOSE, kernel)

    # Only keep motion within 10m (likely person/animal, not noise)
    near = (depth_mm > 0) & (depth_mm < 10000)
    motion_mask = (motion > 0) & near

    # Filter small blobs
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        motion_mask.astype(np.uint8), connectivity=8,
    )
    filtered = np.zeros_like(motion_mask)
    for lbl in range(1, n_labels):
        if stats[lbl, cv2.CC_STAT_AREA] >= min_area:
            filtered[labels == lbl] = True

    return filtered


# ---------------------------------------------------------------------------
# Main segmentation logic
# ---------------------------------------------------------------------------

def segment_frame(depth_mm: np.ndarray, gray: np.ndarray,
                  plane, fx: float, fy: float,
                  cx: float, cy: float,
                  prev_gray: np.ndarray = None) -> np.ndarray:
    """Produce a category-ID mask (uint8, H x W) from depth + heuristics.

    Priority (later overwrites earlier):
        background -> sky -> road -> sidewalk -> tall_object -> obstacle
        -> person-height -> moving objects
    """
    h, w = depth_mm.shape
    mask = np.full((h, w), CAT_BACKGROUND, dtype=np.uint8)

    # --- Sky ---
    sky = detect_sky(depth_mm, gray)
    mask[sky] = CAT_SKY

    # --- Ground-plane based classes ---
    if plane is not None:
        height = height_above_ground(depth_mm, plane, fx, fy, cx, cy)
        valid = ~np.isnan(height)

        # Road: close to ground plane, within 15m
        on_ground = valid & (np.abs(height) < 80) & (depth_mm < 15000)
        mask[on_ground] = CAT_ROAD

        # Sidewalk: slightly above road level (80-200mm), bottom 60% of frame
        curb = valid & (height > 80) & (height < 200) & (depth_mm < 10000)
        mask[curb] = CAT_SIDEWALK

        # Obstacles by height above ground
        low_obs = valid & (height > 200) & (height < 500) & (depth_mm < 10000)
        mask[low_obs] = CAT_OBSTACLE

        # Person/animal height (500-1800mm) within 10m
        person_h = valid & (height > 500) & (height < 1800) & (depth_mm < 10000)
        mask[person_h] = CAT_PERSON  # could be animal too; ML refines later

        # Tall objects (>1800mm): vehicle, wall, building
        tall = valid & (height > 1800)
        # Differentiate: within 10m and narrow = pole, wide = building/wall
        tall_near = tall & (depth_mm < 10000)
        mask[tall_near] = CAT_VEHICLE  # conservative: treat as vehicle
        tall_far = tall & (depth_mm >= 10000)
        mask[tall_far] = CAT_BUILDING

        # Far vegetation heuristic: far depth + green-ish appearance
        # (not available in grayscale, skip for now)

    else:
        # Fallback: no ground plane found
        # Bottom 40% with valid depth < 8m -> road
        road_rows = slice(int(h * 0.6), h)
        road_mask = (depth_mm[road_rows] > 200) & (depth_mm[road_rows] < 8000)
        mask[road_rows][road_mask] = CAT_ROAD

    # --- Moving objects override ---
    motion = detect_motion(prev_gray, gray, depth_mm)
    mask[motion] = CAT_PERSON  # moving objects near us are likely people

    return mask


def mask_to_color(mask: np.ndarray) -> np.ndarray:
    """Convert category-ID mask to BGR colour image."""
    h, w = mask.shape
    color = np.zeros((h, w, 3), dtype=np.uint8)
    for cat_id, bgr in CATEGORY_COLORS_BGR.items():
        color[mask == cat_id] = bgr
    return color


# ---------------------------------------------------------------------------
# Session processing
# ---------------------------------------------------------------------------

def process_session(session_dir: str, output_dir: str,
                    calib_path: str = None,
                    max_frames: int = 0,
                    every_n: int = 1):
    """Process a recorded session and output segmentation masks."""
    session = Path(session_dir)
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    if not os.path.isfile(video_path):
        print(f"Error: video not found: {video_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(csv_path):
        print(f"Error: sensors.csv not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Set up depth extractor
    extractor = DepthExtractor(calib_path)
    focal = extractor.calib["focal_px"]
    baseline = extractor.calib["baseline_mm"]
    # Intrinsics for back-projection
    P1 = extractor.calib["P1"]
    fx, fy = P1[0, 0], P1[1, 1]
    cx, cy = P1[0, 2], P1[1, 2]

    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    os.makedirs(output_dir, exist_ok=True)
    frames_dir = os.path.join(output_dir, "frames")
    masks_dir = os.path.join(output_dir, "masks")
    color_dir = os.path.join(output_dir, "color")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(masks_dir, exist_ok=True)
    os.makedirs(color_dir, exist_ok=True)

    session_name = session.name
    prev_gray = None
    processed = 0
    last_idx = -1
    plane = None  # Will be fitted on first valid frame

    for i, row in enumerate(rows):
        if i % every_n != 0:
            continue
        if max_frames > 0 and processed >= max_frames:
            break

        frame_idx = timestamp_to_frame_index(row["_ts"], first_ts)
        if frame_idx == last_idx:
            continue
        if frame_idx >= total_frames and total_frames > 0:
            break

        stereo = seek_and_read(cap, frame_idx)
        if stereo is None:
            continue
        last_idx = frame_idx

        left, right = split_stereo(stereo)
        gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) \
            if len(left.shape) == 3 else left.copy()

        # Compute depth
        depth_mm = extractor.process_pair(left, right)

        # Fit ground plane every 30 frames or on first frame
        if processed % 30 == 0 or plane is None:
            new_plane = fit_ground_plane_ransac(
                depth_mm, fx, fy, cx, cy,
            )
            if new_plane is not None:
                plane = new_plane

        # Segment
        seg_mask = segment_frame(
            depth_mm, gray, plane, fx, fy, cx, cy, prev_gray,
        )

        # Build tag
        ts_safe = row["timestamp"].replace(":", "-").replace(" ", "_")
        tag = f"{session_name}_{ts_safe}"

        # Save frame (left camera)
        frame_path = os.path.join(frames_dir, f"frame_{tag}.png")
        cv2.imwrite(frame_path, left)

        # Save mask (category IDs, single channel uint8)
        mask_path = os.path.join(masks_dir, f"mask_{tag}.png")
        cv2.imwrite(mask_path, seg_mask)

        # Save coloured overlay
        color = mask_to_color(seg_mask)
        overlay = cv2.addWeighted(left, 0.5, color, 0.5, 0) \
            if len(left.shape) == 3 else cv2.addWeighted(
                cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), 0.5, color, 0.5, 0)
        color_path = os.path.join(color_dir, f"overlay_{tag}.png")
        cv2.imwrite(color_path, overlay)

        prev_gray = gray
        processed += 1

        if processed % 10 == 0:
            print(f"  [{processed:4d}] frame {frame_idx:5d}  "
                  f"road={int(np.mean(seg_mask == CAT_ROAD) * 100):2d}%  "
                  f"sky={int(np.mean(seg_mask == CAT_SKY) * 100):2d}%")

    cap.release()
    print(f"\nDone: {processed} frames segmented -> {output_dir}")
    print(f"  frames/  : left camera images")
    print(f"  masks/   : category-ID masks (uint8 PNG)")
    print(f"  color/   : overlay visualisations")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automatic segmentation from stereo depth (zero ML).")
    parser.add_argument("--session", required=True,
                        help="Path to session directory")
    parser.add_argument("--output", required=True,
                        help="Output directory for segmentation results")
    parser.add_argument("--calibration", default=None,
                        help="Stereo calibration YAML (default: auto-detect)")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Max frames to process (0 = all)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Process every Nth sensor row (default: 1)")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session not found: {session}", file=sys.stderr)
        sys.exit(1)

    process_session(session, args.output, args.calibration,
                    args.max_frames, args.every_n)


if __name__ == "__main__":
    main()
