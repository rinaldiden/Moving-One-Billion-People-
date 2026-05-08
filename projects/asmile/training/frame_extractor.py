#!/usr/bin/env python3
"""
frame_extractor.py — Extract video frames synchronized with sensor CSV timestamps.

Splits stereo side-by-side frames (2560x800) into left/right (1280x800 each).
Maps sensor timestamps to frame indices assuming video starts at first CSV timestamp.

Usage:
    # Extract all frames for a session
    python3 frame_extractor.py --session ~/wip/recorder/session_20260417_181452/ \
                               --output ~/wip/training_frames/

    # Extract a single frame by timestamp
    python3 frame_extractor.py --session ~/wip/recorder/session_20260417_181452/ \
                               --timestamp 2026-04-17T18:22:02.077
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_FPS = 15
STEREO_WIDTH = 1280
STEREO_HEIGHT = 400
FRAME_WIDTH = 640
FRAME_HEIGHT = 800

TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_timestamp(ts_str: str) -> float:
    """Parse a timestamp string into a POSIX float (seconds since epoch)."""
    ts_str = ts_str.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts_str, fmt).timestamp()
        except ValueError:
            continue
    # Try raw float
    try:
        return float(ts_str)
    except ValueError:
        raise ValueError(f"Cannot parse timestamp: {ts_str!r}")


def load_sensor_csv(csv_path: str) -> list[dict]:
    """Load sensor CSV and return list of dicts with parsed timestamps."""
    rows = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["_ts"] = parse_timestamp(row["timestamp"])
            rows.append(row)
    if not rows:
        raise RuntimeError(f"No rows in {csv_path}")
    return rows


def timestamp_to_frame_index(ts: float, first_ts: float) -> int:
    """Convert a timestamp to a frame index (0-based)."""
    delta = ts - first_ts
    if delta < 0:
        return 0
    return int(round(delta * VIDEO_FPS))


def split_stereo(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split a side-by-side stereo frame into left and right halves."""
    h, w = frame.shape[:2]
    mid = w // 2
    return frame[:, :mid], frame[:, mid:]


def open_video(video_path: str) -> cv2.VideoCapture:
    """Open a video file and validate it."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    return cap


def seek_and_read(cap: cv2.VideoCapture, frame_idx: int) -> np.ndarray | None:
    """Seek to frame_idx and read the frame. Returns None on failure."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret:
        return None
    return frame


def save_frame(frame: np.ndarray, output_dir: str, prefix: str,
               timestamp_str: str) -> str:
    """Save a frame as PNG, return the file path."""
    safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
    filename = f"{prefix}_{safe_ts}.png"
    path = os.path.join(output_dir, filename)
    cv2.imwrite(path, frame)
    return path


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def extract_single(session_dir: str, timestamp_str: str,
                   output_dir: str | None = None) -> dict:
    """Extract a single frame pair for a given timestamp."""
    session = Path(session_dir)
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]

    target_ts = parse_timestamp(timestamp_str)
    frame_idx = timestamp_to_frame_index(target_ts, first_ts)

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if frame_idx >= total_frames and total_frames > 0:
        print(f"Warning: frame {frame_idx} beyond video length ({total_frames}), "
              f"clamping to last frame.", file=sys.stderr)
        frame_idx = total_frames - 1

    frame = seek_and_read(cap, frame_idx)
    cap.release()

    if frame is None:
        raise RuntimeError(f"Failed to read frame {frame_idx}")

    left, right = split_stereo(frame)
    result = {"left": left, "right": right, "frame_idx": frame_idx}

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        ts_label = timestamp_str.replace(":", "-").replace(" ", "_")
        lp = save_frame(left, output_dir, "left", ts_label)
        rp = save_frame(right, output_dir, "right", ts_label)
        print(f"Saved: {lp}")
        print(f"Saved: {rp}")
        result["left_path"] = lp
        result["right_path"] = rp

    return result


def extract_all(session_dir: str, output_dir: str,
                every_n: int = 1) -> list[dict]:
    """Extract all frames aligned to sensor rows.

    Parameters
    ----------
    every_n : int
        Extract every Nth sensor row (1 = all, 10 = every 10th).
    """
    session = Path(session_dir)
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    os.makedirs(output_dir, exist_ok=True)
    session_name = session.name

    results = []
    last_idx = -1
    extracted = 0
    skipped = 0

    for i, row in enumerate(rows):
        if i % every_n != 0:
            continue

        frame_idx = timestamp_to_frame_index(row["_ts"], first_ts)
        if frame_idx == last_idx:
            skipped += 1
            continue
        if frame_idx >= total_frames and total_frames > 0:
            break

        frame = seek_and_read(cap, frame_idx)
        if frame is None:
            skipped += 1
            continue

        last_idx = frame_idx
        left, right = split_stereo(frame)

        ts_label = row["timestamp"].replace(":", "-").replace(" ", "_")
        tag = f"{session_name}_{ts_label}"
        lp = save_frame(left, output_dir, "left", tag)
        rp = save_frame(right, output_dir, "right", tag)

        results.append({
            "frame_idx": frame_idx,
            "timestamp": row["timestamp"],
            "left_path": lp,
            "right_path": rp,
        })
        extracted += 1

        if extracted % 100 == 0:
            print(f"  Extracted {extracted} frames "
                  f"(row {i+1}/{len(rows)}, skipped {skipped} duplicates)")

    cap.release()
    print(f"Done: {extracted} frames extracted, {skipped} skipped.")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract stereo video frames synced with sensor timestamps.")
    parser.add_argument("--session", required=True,
                        help="Path to session directory (contains video.h264 + sensors.csv)")
    parser.add_argument("--output", default=None,
                        help="Output directory for extracted frames")
    parser.add_argument("--timestamp", default=None,
                        help="Extract single frame at this timestamp (ISO format)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Extract every Nth sensor row (default: 1 = all)")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session directory not found: {session}", file=sys.stderr)
        sys.exit(1)

    for required in ("video.h264", "sensors.csv"):
        if not os.path.isfile(os.path.join(session, required)):
            print(f"Error: {required} not found in {session}", file=sys.stderr)
            sys.exit(1)

    if args.timestamp:
        output = args.output or "."
        extract_single(session, args.timestamp, output)
    else:
        output = args.output
        if not output:
            print("Error: --output required for batch extraction", file=sys.stderr)
            sys.exit(1)
        extract_all(session, output, every_n=args.every_n)


if __name__ == "__main__":
    main()
