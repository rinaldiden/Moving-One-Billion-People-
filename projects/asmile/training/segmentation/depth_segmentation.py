#!/usr/bin/env python3
"""
depth_segmentation.py -- Pure-depth segmentation (Approach 3).

Segments the scene using ONLY depth information, no ML.  Produces a
simplified five-class segmentation useful for immediate obstacle avoidance:

    road, low_obstacle, person_height, tall_object, sky

Works TODAY on any Asmile session with zero training data.

Usage
-----
    python3 depth_segmentation.py \\
        --session ~/wip/recorder/session_20260417_181452/ \\
        --output  ~/wip/segmentation/depth_based/

    # With distance report per frame
    python3 depth_segmentation.py \\
        --session ~/wip/recorder/session_20260417_181452/ \\
        --output  ~/wip/segmentation/depth_based/ \\
        --report
"""

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

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

# -- Simplified categories ---------------------------------------------------
ROAD = 0
LOW_OBSTACLE = 1
PERSON_HEIGHT = 2
TALL_OBJECT = 3
SKY = 4
NO_DATA = 5

SIMPLE_COLORS_BGR = {
    ROAD:           (128, 64, 128),
    LOW_OBSTACLE:   (0, 255, 255),
    PERSON_HEIGHT:  (60, 20, 220),
    TALL_OBJECT:    (142, 0, 0),
    SKY:            (180, 130, 70),
    NO_DATA:        (0, 0, 0),
}

SIMPLE_NAMES = {
    ROAD: "road",
    LOW_OBSTACLE: "low_obstacle",
    PERSON_HEIGHT: "person_height",
    TALL_OBJECT: "tall_object",
    SKY: "sky",
    NO_DATA: "no_data",
}


# ---------------------------------------------------------------------------
# Ground-plane fitting
# ---------------------------------------------------------------------------

def fit_ground_plane(depth_mm: np.ndarray,
                     fx: float, fy: float,
                     cx: float, cy: float,
                     n_iter: int = 150,
                     thresh_mm: float = 60.0):
    """RANSAC ground-plane fit on bottom third of depth image."""
    h, w = depth_mm.shape
    roi_start = int(h * 0.65)
    roi = depth_mm[roi_start:, :]
    ys, xs = np.where((roi > 300) & (roi < 12000))
    if len(ys) < 80:
        return None
    ys_full = ys + roi_start
    depths = depth_mm[ys_full, xs].astype(np.float64)

    # Back-project to 3-D
    Z = depths
    X = (xs.astype(np.float64) - cx) * Z / fx
    Y = (ys_full.astype(np.float64) - cy) * Z / fy
    pts = np.column_stack([X, Y, Z])

    # Sub-sample
    if len(pts) > 6000:
        idx = np.random.default_rng(42).choice(len(pts), 6000, replace=False)
        pts = pts[idx]

    best_plane = None
    best_count = 0
    rng = np.random.default_rng(42)

    for _ in range(n_iter):
        s = rng.choice(len(pts), 3, replace=False)
        p0, p1, p2 = pts[s]
        n = np.cross(p1 - p0, p2 - p0)
        nl = np.linalg.norm(n)
        if nl < 1e-12:
            continue
        n /= nl
        d = -n.dot(p0)

        dists = np.abs(pts @ n + d)
        count = int(np.sum(dists < thresh_mm))
        if count > best_count:
            best_count = count
            best_plane = (n[0], n[1], n[2], d)

    if best_plane and best_plane[1] > 0:
        best_plane = (-best_plane[0], -best_plane[1],
                      -best_plane[2], -best_plane[3])
    return best_plane


def pixel_heights(depth_mm: np.ndarray, plane,
                  fx: float, fy: float,
                  cx: float, cy: float) -> np.ndarray:
    """Signed height above ground plane (mm). NaN where depth is invalid."""
    h, w = depth_mm.shape
    rows, cols = np.mgrid[0:h, 0:w]
    valid = depth_mm > 0
    Z = depth_mm[valid].astype(np.float64)
    X = (cols[valid].astype(np.float64) - cx) * Z / fx
    Y = (rows[valid].astype(np.float64) - cy) * Z / fy
    a, b, c, d = plane
    dist = a * X + b * Y + c * Z + d
    out = np.full((h, w), np.nan, dtype=np.float64)
    out[valid] = dist
    return out


# ---------------------------------------------------------------------------
# Moving-object detection
# ---------------------------------------------------------------------------

def detect_moving(prev_depth: np.ndarray, curr_depth: np.ndarray,
                  thresh_mm: float = 400.0,
                  min_area: int = 150) -> np.ndarray:
    """Find blobs where depth changed significantly between frames."""
    if prev_depth is None:
        return np.zeros(curr_depth.shape[:2], dtype=bool)

    both_valid = (prev_depth > 0) & (curr_depth > 0) & (curr_depth < 10000)
    diff = np.zeros_like(curr_depth)
    diff[both_valid] = np.abs(
        prev_depth[both_valid].astype(np.float32)
        - curr_depth[both_valid].astype(np.float32)
    )
    moving_raw = diff > thresh_mm

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    moving_clean = cv2.morphologyEx(
        moving_raw.astype(np.uint8), cv2.MORPH_CLOSE, kernel,
    )
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        moving_clean, connectivity=8,
    )
    result = np.zeros_like(moving_raw)
    for lbl in range(1, n_labels):
        if stats[lbl, cv2.CC_STAT_AREA] >= min_area:
            result[labels == lbl] = True
    return result


# ---------------------------------------------------------------------------
# Core segmentation
# ---------------------------------------------------------------------------

def segment_from_depth(depth_mm: np.ndarray, plane,
                       fx: float, fy: float,
                       cx: float, cy: float,
                       prev_depth: np.ndarray = None):
    """Classify every pixel into the simplified categories.

    Returns (mask, report_dict).
    """
    h, w = depth_mm.shape
    mask = np.full((h, w), NO_DATA, dtype=np.uint8)

    # Sky: top rows with mostly invalid depth
    for row in range(h):
        inv_frac = np.mean((depth_mm[row] == 0) | (depth_mm[row] > 30000))
        if inv_frac > 0.75:
            mask[row, :] = SKY
        elif row > 8:
            break

    if plane is not None:
        heights = pixel_heights(depth_mm, plane, fx, fy, cx, cy)
        valid = ~np.isnan(heights)

        on_ground = valid & (np.abs(heights) < 100)
        mask[on_ground] = ROAD

        low_obs = valid & (heights > 100) & (heights < 500) & (depth_mm < 10000)
        mask[low_obs] = LOW_OBSTACLE

        person_h = valid & (heights > 500) & (heights < 1800) & (depth_mm < 10000)
        mask[person_h] = PERSON_HEIGHT

        tall = valid & (heights > 1800)
        mask[tall] = TALL_OBJECT
    else:
        # Fallback without ground plane
        bottom = slice(int(h * 0.55), h)
        road_px = (depth_mm[bottom] > 200) & (depth_mm[bottom] < 8000)
        mask[bottom][road_px] = ROAD

    # Moving objects override to PERSON_HEIGHT
    moving = detect_moving(prev_depth, depth_mm)
    mask[moving] = PERSON_HEIGHT

    # Build report: nearest obstacle per horizontal third
    report = _build_report(mask, depth_mm, w)
    return mask, report


def _build_report(mask: np.ndarray, depth_mm: np.ndarray,
                  w: int) -> dict:
    """Describe what is where: left / centre / right thirds."""
    thirds = {
        "left":   (0, w // 3),
        "centre": (w // 3, 2 * w // 3),
        "right":  (2 * w // 3, w),
    }
    report = {}
    for zone_name, (c0, c1) in thirds.items():
        zone_mask = mask[:, c0:c1]
        zone_depth = depth_mm[:, c0:c1]

        items = []
        for cat in [LOW_OBSTACLE, PERSON_HEIGHT, TALL_OBJECT]:
            px = (zone_mask == cat) & (zone_depth > 0)
            if np.sum(px) < 20:
                continue
            nearest_mm = float(np.min(zone_depth[px]))
            items.append({
                "class": SIMPLE_NAMES[cat],
                "distance_m": round(nearest_mm / 1000.0, 1),
            })

        road_px = zone_mask == ROAD
        road_clear = bool(np.sum(road_px) > 0.3 * zone_mask.size)

        report[zone_name] = {
            "road_clear": road_clear,
            "obstacles": items,
        }
    return report


def report_to_text(report: dict) -> str:
    """Human-readable one-liner from report dict."""
    parts = []
    for zone in ["left", "centre", "right"]:
        info = report.get(zone, {})
        if info.get("road_clear") and not info.get("obstacles"):
            parts.append(f"{zone}: clear")
        else:
            obs_parts = []
            for o in info.get("obstacles", []):
                obs_parts.append(f"{o['class']} {o['distance_m']}m")
            if obs_parts:
                parts.append(f"{zone}: {', '.join(obs_parts)}")
            elif not info.get("road_clear"):
                parts.append(f"{zone}: no road")
    return " | ".join(parts) if parts else "no data"


def mask_to_color(mask: np.ndarray) -> np.ndarray:
    """Convert simplified mask to BGR colour image."""
    h, w = mask.shape
    color = np.zeros((h, w, 3), dtype=np.uint8)
    for cat_id, bgr in SIMPLE_COLORS_BGR.items():
        color[mask == cat_id] = bgr
    return color


# ---------------------------------------------------------------------------
# Session processing
# ---------------------------------------------------------------------------

def process_session(session_dir: str, output_dir: str,
                    calib_path: str = None,
                    max_frames: int = 0,
                    every_n: int = 1,
                    write_report: bool = False):
    """Process a session with depth-only segmentation."""
    session = Path(session_dir)
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    for p, name in [(video_path, "video.h264"), (csv_path, "sensors.csv")]:
        if not os.path.isfile(p):
            print(f"Error: {name} not found: {p}", file=sys.stderr)
            sys.exit(1)

    extractor = DepthExtractor(calib_path)
    P1 = extractor.calib["P1"]
    fx, fy = P1[0, 0], P1[1, 1]
    cx, cy = P1[0, 2], P1[1, 2]

    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    os.makedirs(output_dir, exist_ok=True)
    masks_dir = os.path.join(output_dir, "masks")
    color_dir = os.path.join(output_dir, "color")
    os.makedirs(masks_dir, exist_ok=True)
    os.makedirs(color_dir, exist_ok=True)

    session_name = session.name
    prev_depth = None
    plane = None
    processed = 0
    last_idx = -1
    all_reports = []

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
        depth_mm = extractor.process_pair(left, right)

        # Re-fit ground plane periodically
        if processed % 20 == 0 or plane is None:
            new_plane = fit_ground_plane(depth_mm, fx, fy, cx, cy)
            if new_plane is not None:
                plane = new_plane

        seg_mask, report = segment_from_depth(
            depth_mm, plane, fx, fy, cx, cy, prev_depth,
        )

        ts_safe = row["timestamp"].replace(":", "-").replace(" ", "_")
        tag = f"{session_name}_{ts_safe}"

        mask_path = os.path.join(masks_dir, f"depth_seg_{tag}.png")
        cv2.imwrite(mask_path, seg_mask)

        color = mask_to_color(seg_mask)
        frame_bgr = left if len(left.shape) == 3 else cv2.cvtColor(
            left, cv2.COLOR_GRAY2BGR)
        overlay = cv2.addWeighted(frame_bgr, 0.5, color, 0.5, 0)
        color_path = os.path.join(color_dir, f"depth_overlay_{tag}.png")
        cv2.imwrite(color_path, overlay)

        if write_report:
            report["frame"] = tag
            report["text"] = report_to_text(report)
            all_reports.append(report)

        prev_depth = depth_mm
        processed += 1

        if processed % 10 == 0:
            text = report_to_text(report)
            print(f"  [{processed:4d}] {text}")

    cap.release()

    if write_report and all_reports:
        rpt_path = os.path.join(output_dir, "reports.json")
        with open(rpt_path, "w") as f:
            json.dump(all_reports, f, indent=2)
        print(f"Reports saved: {rpt_path}")

    print(f"\nDone: {processed} frames -> {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Depth-only segmentation (Approach 3, zero ML).")
    parser.add_argument("--session", required=True,
                        help="Session directory")
    parser.add_argument("--output", required=True,
                        help="Output directory")
    parser.add_argument("--calibration", default=None,
                        help="Stereo calibration YAML")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Max frames (0 = all)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Process every Nth row")
    parser.add_argument("--report", action="store_true",
                        help="Write per-frame obstacle report JSON")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session not found: {session}", file=sys.stderr)
        sys.exit(1)

    process_session(session, args.output, args.calibration,
                    args.max_frames, args.every_n, args.report)


if __name__ == "__main__":
    main()
