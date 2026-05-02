#!/usr/bin/env python3
"""
Build training dataset — align segmented frames with rider actions.

For each segmented frame, finds the closest sensor reading and outputs:
  - frame path (segmented PNG with YOLO bbox/mask)
  - rider actions: speed, steering, braking, acceleration

Output: dataset.csv with columns:
  session, frame_file, timestamp, frame_idx,
  gps_speed_ms, gps_heading, encoder_pos,
  imu_accel_x, imu_accel_y, imu_accel_z,
  imu_gyro_x, imu_gyro_y, imu_gyro_z,
  is_braking, speed_delta, steering_delta

Usage:
  python3 build_dataset.py --sessions-dir ~/segmentazione/da_segmentare/ --output dataset.csv
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime


def parse_timestamp(ts_str):
    """Parse ISO timestamp from sensors.csv."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def load_sensors(csv_path):
    """Load sensors.csv, return list of dicts with parsed timestamps."""
    rows = []
    with open(csv_path, errors="replace") as f:
        # Filter out NUL bytes from corrupted CSVs
        clean = (line.replace("\x00", "") for line in f)
        reader = csv.DictReader(clean)
        for row in reader:
            ts = parse_timestamp(row["timestamp"])
            if ts is None:
                continue
            row["_ts"] = ts
            # Convert numeric fields
            for k in ("gps_speed_ms", "gps_heading", "gps_lat", "gps_lon",
                       "imu_accel_x", "imu_accel_y", "imu_accel_z",
                       "imu_gyro_x", "imu_gyro_y", "imu_gyro_z"):
                try:
                    row[k] = float(row[k])
                except (ValueError, KeyError):
                    row[k] = 0.0
            try:
                row["encoder_pos"] = int(row["encoder_pos"])
            except (ValueError, KeyError):
                row["encoder_pos"] = -1
            rows.append(row)
    return rows


def frame_to_timestamp(frame_idx, start_time, fps):
    """Convert frame index to timestamp."""
    from datetime import timedelta
    return start_time + timedelta(seconds=frame_idx / fps)


def find_closest_sensor(target_ts, sensors):
    """Find sensor reading closest to target timestamp."""
    best = None
    best_diff = float("inf")
    for row in sensors:
        diff = abs((row["_ts"] - target_ts).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best = row
    return best, best_diff


def process_session(session_dir, session_name):
    """Process one session, return list of aligned data points."""
    sensors_path = os.path.join(session_dir, "sensors.csv")
    meta_path = os.path.join(session_dir, "metadata.json")

    if not os.path.exists(sensors_path):
        print(f"  SKIP {session_name}: no sensors.csv")
        return []

    # Load metadata
    fps = 15
    start_time = None
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        fps = meta.get("video_fps", 15)
        start_time = parse_timestamp(meta.get("start_time", ""))

    # Load sensors
    sensors = load_sensors(sensors_path)
    if not sensors:
        print(f"  SKIP {session_name}: empty sensors.csv")
        return []

    if start_time is None:
        start_time = sensors[0]["_ts"]

    # Find segmented frames
    frames = sorted([f for f in os.listdir(session_dir)
                     if f.startswith("frame_") and f.endswith(".png")])
    if not frames:
        print(f"  SKIP {session_name}: no segmented frames")
        return []

    # Video total frames (from metadata or estimate)
    total_video_frames = len(sensors) * fps // 10  # rough estimate from 10Hz sensors

    # Frame step used during segmentation (max 60 frames sampled)
    max_seg_frames = 60
    step = max(1, total_video_frames // max_seg_frames)

    results = []
    prev_speed = None
    prev_encoder = None

    for i, fname in enumerate(frames):
        # Estimate video frame index for this segmented frame
        frame_num = int(fname.replace("frame_", "").replace(".png", ""))
        video_frame_idx = 200 + frame_num * step  # matches YOLO script sampling

        # Convert to timestamp
        frame_ts = frame_to_timestamp(video_frame_idx, start_time, fps)

        # Find closest sensor
        sensor, diff_s = find_closest_sensor(frame_ts, sensors)
        if diff_s > 2.0:  # more than 2s off, skip
            continue

        # Compute deltas
        speed = sensor["gps_speed_ms"]
        encoder = sensor["encoder_pos"]
        speed_delta = speed - prev_speed if prev_speed is not None else 0.0
        steering_delta = encoder - prev_encoder if prev_encoder is not None else 0
        is_braking = 1 if speed_delta < -0.3 else 0  # decelerating > 0.3 m/s

        results.append({
            "session": session_name,
            "frame_file": fname,
            "frame_path": os.path.join(session_dir, fname),
            "timestamp": sensor["timestamp"],
            "video_frame_idx": video_frame_idx,
            "sensor_offset_s": round(diff_s, 3),
            "gps_speed_ms": round(speed, 3),
            "gps_heading": round(sensor["gps_heading"], 1),
            "gps_lat": round(sensor["gps_lat"], 7),
            "gps_lon": round(sensor["gps_lon"], 7),
            "encoder_pos": encoder,
            "imu_accel_x": round(sensor["imu_accel_x"], 4),
            "imu_accel_y": round(sensor["imu_accel_y"], 4),
            "imu_accel_z": round(sensor["imu_accel_z"], 4),
            "imu_gyro_x": round(sensor["imu_gyro_x"], 2),
            "imu_gyro_y": round(sensor["imu_gyro_y"], 2),
            "imu_gyro_z": round(sensor["imu_gyro_z"], 2),
            "is_braking": is_braking,
            "speed_delta": round(speed_delta, 3),
            "steering_delta": steering_delta,
        })

        prev_speed = speed
        prev_encoder = encoder

    return results


def main():
    parser = argparse.ArgumentParser(description="Build training dataset from segmented sessions")
    parser.add_argument("--sessions-dir", required=True, help="Directory with session_* folders")
    parser.add_argument("--output", default="dataset.csv", help="Output CSV path")
    args = parser.parse_args()

    sessions_dir = args.sessions_dir
    all_data = []

    # Find all sessions
    sessions = sorted([d for d in os.listdir(sessions_dir)
                       if d.startswith("session_") and os.path.isdir(os.path.join(sessions_dir, d))])

    print(f"Found {len(sessions)} sessions")

    for sess in sessions:
        sess_dir = os.path.join(sessions_dir, sess)
        print(f"\nProcessing {sess}...")
        data = process_session(sess_dir, sess)
        all_data.extend(data)
        print(f"  {len(data)} aligned frame-action pairs")

    # Write CSV
    if all_data:
        fields = list(all_data[0].keys())
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_data)

        # Stats
        braking = sum(1 for d in all_data if d["is_braking"])
        speeds = [d["gps_speed_ms"] for d in all_data]
        print(f"\n{'='*50}")
        print(f"Dataset: {len(all_data)} frame-action pairs")
        print(f"Sessions: {len(sessions)}")
        print(f"Braking events: {braking} ({braking/len(all_data)*100:.0f}%)")
        print(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} m/s")
        print(f"Saved to: {args.output}")
    else:
        print("No data collected!")


if __name__ == "__main__":
    main()
