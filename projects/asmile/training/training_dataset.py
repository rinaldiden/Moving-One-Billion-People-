#!/usr/bin/env python3
"""
training_dataset.py — Create paired (frame, depth, sensors, labels) training samples.

For each sensor row, extracts the corresponding video frame + depth map and
computes behavioral cloning labels from sensor data.

Labels:
    steering_target : encoder_pos normalized to -1..+1 (range 2048-4095, neutral ~3923)
    brake_target    : 1.0 if ax < -0.3g, proportional for -0.1..-0.3g, else 0
    speed_target    : gps_speed_ms normalized (0..1 over 0..6 m/s)
    road_quality    : rolling az variance (2s window at 10Hz = 20 samples)
    turning         : 1 if |gyro_z| > 22 (above noise floor), else 0

Output formats:
    npz       — single NPZ file with all frames + labels (small datasets)
    directory — PNGs + labels.csv (large datasets)

Usage:
    python3 training_dataset.py --sessions ~/wip/recorder/ \
                                --output ~/wip/training_data/ \
                                --format directory

    python3 training_dataset.py --sessions ~/wip/recorder/ \
                                --output ~/wip/training_data/dataset.npz \
                                --format npz
"""

import argparse
import csv
import glob
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame_extractor import (
    load_sensor_csv, timestamp_to_frame_index, split_stereo,
    open_video, seek_and_read,
)
from depth_extractor import DepthExtractor, to_grayscale


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENCODER_MIN = 2048
ENCODER_MAX = 4095
ENCODER_NEUTRAL = 3923
ENCODER_RANGE = ENCODER_MAX - ENCODER_MIN  # 2047

SPEED_MAX_MS = 6.0  # normalization cap
G_ACCEL = 9.81  # m/s^2

ROAD_QUALITY_WINDOW = 20  # 2 seconds at 10Hz
GYRO_Z_NOISE_FLOOR = 22.0  # deg/s — 3-sigma from analysis


# ---------------------------------------------------------------------------
# Label computation
# ---------------------------------------------------------------------------

def normalize_encoder(encoder_pos: float) -> float:
    """Normalize encoder position to -1..+1.

    2048 -> -1.0 (full left)
    3923 -> ~+0.83 (neutral/straight — asymmetric due to physical range)
    4095 -> +1.0 (full right)
    """
    return 2.0 * (encoder_pos - ENCODER_MIN) / ENCODER_RANGE - 1.0


def compute_brake_target(ax: float) -> float:
    """Compute brake target from longitudinal acceleration.

    ax is in g-units (negative = deceleration).
    Returns 0..1 brake intensity.
    """
    if ax >= -0.1:
        return 0.0
    elif ax <= -0.3:
        return 1.0
    else:
        # Linear ramp from 0 at -0.1g to 1 at -0.3g
        return ((-0.1) - ax) / 0.2


def compute_road_quality(az_history: list[float]) -> float:
    """Compute road quality as rolling variance of az (vertical accel).

    Higher variance = rougher road.
    """
    if len(az_history) < 2:
        return 0.0
    return float(np.var(az_history))


def compute_labels_for_rows(rows: list[dict]) -> list[dict]:
    """Compute labels for all sensor rows."""
    labels = []
    az_buffer = []

    for i, row in enumerate(rows):
        encoder_pos = float(row.get("encoder_pos", ENCODER_NEUTRAL))
        ax = float(row.get("imu_accel_x", 0.0))
        az = float(row.get("imu_accel_z", 0.0))
        gyro_z = float(row.get("imu_gyro_z", 0.0))
        speed = float(row.get("gps_speed_ms", 0.0))

        # Update rolling buffer for road quality
        az_buffer.append(az)
        if len(az_buffer) > ROAD_QUALITY_WINDOW:
            az_buffer.pop(0)

        labels.append({
            "timestamp": row["timestamp"],
            "steering_target": normalize_encoder(encoder_pos),
            "brake_target": compute_brake_target(ax),
            "speed_target": min(speed / SPEED_MAX_MS, 1.0),
            "road_quality": compute_road_quality(az_buffer),
            "turning": 1.0 if abs(gyro_z) > GYRO_Z_NOISE_FLOOR else 0.0,
            # Raw values for reference
            "encoder_pos_raw": encoder_pos,
            "speed_ms_raw": speed,
            "ax_raw": ax,
            "gyro_z_raw": gyro_z,
        })

    return labels


# ---------------------------------------------------------------------------
# Dataset creation
# ---------------------------------------------------------------------------

def find_sessions(sessions_dir: str) -> list[str]:
    """Find all session directories under the given path."""
    pattern = os.path.join(sessions_dir, "session_*")
    sessions = sorted(glob.glob(pattern))
    valid = []
    for s in sessions:
        if (os.path.isfile(os.path.join(s, "video.h264")) and
                os.path.isfile(os.path.join(s, "sensors.csv"))):
            valid.append(s)
    return valid


def process_session_to_directory(session_dir: str, output_dir: str,
                                 depth_extractor: DepthExtractor,
                                 every_n: int = 1) -> list[dict]:
    """Process a session: extract frames, depth, and labels to a directory."""
    session = Path(session_dir)
    session_name = session.name
    video_path = str(session / "video.h264")
    csv_path = str(session / "sensors.csv")

    rows = load_sensor_csv(csv_path)
    first_ts = rows[0]["_ts"]
    labels = compute_labels_for_rows(rows)

    cap = open_video(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frames_dir = os.path.join(output_dir, "frames")
    depth_dir = os.path.join(output_dir, "depth")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(depth_dir, exist_ok=True)

    samples = []
    last_idx = -1
    processed = 0

    for i, (row, label) in enumerate(zip(rows, labels)):
        if i % every_n != 0:
            continue

        frame_idx = timestamp_to_frame_index(row["_ts"], first_ts)
        if frame_idx == last_idx:
            continue
        if frame_idx >= total_frames and total_frames > 0:
            break

        stereo_frame = seek_and_read(cap, frame_idx)
        if stereo_frame is None:
            continue

        last_idx = frame_idx
        left, right = split_stereo(stereo_frame)

        # Compute depth
        depth_mm = depth_extractor.process_pair(left, right)

        # Save left frame as grayscale
        left_gray = to_grayscale(left)
        tag = f"{session_name}_{i:06d}"
        frame_path = os.path.join(frames_dir, f"{tag}.png")
        cv2.imwrite(frame_path, left_gray)

        # Save depth as uint16 PNG (mm)
        depth_u16 = np.clip(depth_mm, 0, 65535).astype(np.uint16)
        depth_path = os.path.join(depth_dir, f"{tag}.png")
        cv2.imwrite(depth_path, depth_u16)

        sample = {
            "sample_id": tag,
            "session": session_name,
            "frame_path": frame_path,
            "depth_path": depth_path,
            **label,
        }
        samples.append(sample)
        processed += 1

        if processed % 100 == 0:
            print(f"  [{session_name}] {processed} samples "
                  f"(row {i+1}/{len(rows)})")

    cap.release()
    print(f"  [{session_name}] Total: {processed} samples")
    return samples


def split_train_val(samples: list[dict],
                    val_ratio: float = 0.2,
                    seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Split samples into train and validation sets."""
    rng = np.random.RandomState(seed)
    indices = rng.permutation(len(samples))
    split = int(len(samples) * (1 - val_ratio))
    train_idx = indices[:split]
    val_idx = indices[split:]
    train = [samples[i] for i in train_idx]
    val = [samples[i] for i in val_idx]
    return train, val


def write_labels_csv(samples: list[dict], csv_path: str):
    """Write labels CSV for a set of samples."""
    if not samples:
        return

    fieldnames = [
        "sample_id", "session", "frame_path", "depth_path",
        "timestamp", "steering_target", "brake_target", "speed_target",
        "road_quality", "turning",
        "encoder_pos_raw", "speed_ms_raw", "ax_raw", "gyro_z_raw",
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in samples:
            writer.writerow({k: s.get(k, "") for k in fieldnames})

    print(f"Labels written: {csv_path} ({len(samples)} rows)")


def create_npz_dataset(samples: list[dict], npz_path: str):
    """Create NPZ file with all frames, depth maps, and labels."""
    n = len(samples)
    if n == 0:
        print("No samples to save.")
        return

    # Load first frame to determine shape
    test_frame = cv2.imread(samples[0]["frame_path"], cv2.IMREAD_GRAYSCALE)
    test_depth = cv2.imread(samples[0]["depth_path"], cv2.IMREAD_UNCHANGED)
    h, w = test_frame.shape

    frames = np.zeros((n, h, w), dtype=np.uint8)
    depths = np.zeros((n, h, w), dtype=np.uint16)
    steering = np.zeros(n, dtype=np.float32)
    brake = np.zeros(n, dtype=np.float32)
    speed = np.zeros(n, dtype=np.float32)
    road_quality = np.zeros(n, dtype=np.float32)
    turning = np.zeros(n, dtype=np.float32)

    for i, s in enumerate(samples):
        frames[i] = cv2.imread(s["frame_path"], cv2.IMREAD_GRAYSCALE)
        depths[i] = cv2.imread(s["depth_path"], cv2.IMREAD_UNCHANGED)
        steering[i] = s["steering_target"]
        brake[i] = s["brake_target"]
        speed[i] = s["speed_target"]
        road_quality[i] = s["road_quality"]
        turning[i] = s["turning"]

        if (i + 1) % 200 == 0:
            print(f"  Packing NPZ: {i+1}/{n}")

    np.savez_compressed(npz_path,
                        frames=frames, depths=depths,
                        steering=steering, brake=brake,
                        speed=speed, road_quality=road_quality,
                        turning=turning)
    print(f"NPZ saved: {npz_path} ({n} samples, "
          f"{os.path.getsize(npz_path) / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create training dataset from recorded sessions.")
    parser.add_argument("--sessions", required=True,
                        help="Parent directory containing session_* folders, "
                             "or path to a single session")
    parser.add_argument("--output", required=True,
                        help="Output directory (format=directory) or .npz file path")
    parser.add_argument("--format", choices=["directory", "npz"],
                        default="directory",
                        help="Output format (default: directory)")
    parser.add_argument("--calibration", default=None,
                        help="Stereo calibration YAML path")
    parser.add_argument("--val-ratio", type=float, default=0.2,
                        help="Validation split ratio (default: 0.2)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Process every Nth sensor row (default: 1)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for train/val split")
    args = parser.parse_args()

    # Find sessions
    sessions_path = args.sessions.rstrip("/")
    if os.path.isfile(os.path.join(sessions_path, "sensors.csv")):
        # Single session
        sessions = [sessions_path]
    else:
        sessions = find_sessions(sessions_path)

    if not sessions:
        print(f"Error: no valid sessions found in {sessions_path}",
              file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(sessions)} session(s):")
    for s in sessions:
        print(f"  {s}")

    # Initialize depth extractor
    depth_ext = DepthExtractor(args.calibration)

    # Process all sessions
    all_samples = []
    for session_dir in sessions:
        output_dir = args.output if args.format == "directory" else args.output + "_tmp"
        samples = process_session_to_directory(
            session_dir, output_dir, depth_ext, args.every_n)
        all_samples.extend(samples)

    if not all_samples:
        print("Error: no samples extracted.", file=sys.stderr)
        sys.exit(1)

    print(f"\nTotal samples: {len(all_samples)}")

    # Train/val split
    train_samples, val_samples = split_train_val(
        all_samples, args.val_ratio, args.seed)
    print(f"Train: {len(train_samples)}, Val: {len(val_samples)}")

    if args.format == "directory":
        os.makedirs(args.output, exist_ok=True)
        write_labels_csv(train_samples,
                         os.path.join(args.output, "train_labels.csv"))
        write_labels_csv(val_samples,
                         os.path.join(args.output, "val_labels.csv"))
        write_labels_csv(all_samples,
                         os.path.join(args.output, "all_labels.csv"))
        print(f"\nDataset ready at: {args.output}")
        print(f"  frames/  — grayscale left camera frames (640x400)")
        print(f"  depth/   — depth maps in mm (uint16 PNG)")
        print(f"  train_labels.csv, val_labels.csv, all_labels.csv")

    elif args.format == "npz":
        npz_path = args.output
        if not npz_path.endswith(".npz"):
            npz_path += ".npz"

        os.makedirs(os.path.dirname(npz_path) or ".", exist_ok=True)

        # Write labels CSVs alongside NPZ
        base = npz_path.rsplit(".", 1)[0]
        write_labels_csv(train_samples, base + "_train.csv")
        write_labels_csv(val_samples, base + "_val.csv")

        # Pack into NPZ
        create_npz_dataset(all_samples, npz_path)


if __name__ == "__main__":
    main()
