#!/usr/bin/env python3
"""
Build training dataset v2 — frame + actions + spatial awareness.

For each segmented frame, computes:
  - Rider actions (speed, steering, braking) from sensors.csv
  - Depth map from stereo calibration
  - Lateral margins (distance to walls - half bike width)
  - Available gap (free width ahead)
  - Action labels (pass/brake/steer)

Uses Asmile dimensions from asmile_config.yaml for real-world decisions.

Usage:
  python3 build_dataset_v2.py --sessions-dir ~/segmentazione/da_segmentare/ --output dataset_v2.csv
"""

import os
import sys
import csv
import json
import argparse
import yaml
import cv2
import numpy as np
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, "..")


def load_asmile_config():
    config_path = os.path.join(PROJECT_DIR, "follow_me", "asmile_config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_stereo_calib(calib_path):
    with open(calib_path) as f:
        data = json.load(f)
    K_left = np.array(data["K_left"])
    K_right = np.array(data["K_right"])
    dist_left = np.array(data["dist_left"])
    dist_right = np.array(data["dist_right"])
    R = np.array(data["R"])
    T = np.array(data["T"])

    w, h = 640, 400
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
        K_left, dist_left, K_right, dist_right,
        (w, h), R, T, alpha=0
    )
    map1x, map1y = cv2.initUndistortRectifyMap(K_left, dist_left, R1, P1, (w, h), cv2.CV_32FC1)
    map2x, map2y = cv2.initUndistortRectifyMap(K_right, dist_right, R2, P2, (w, h), cv2.CV_32FC1)

    focal = P1[0, 0]
    baseline = abs(T[0, 0])

    return {
        "map1x": map1x, "map1y": map1y,
        "map2x": map2x, "map2y": map2y,
        "focal": focal, "baseline": baseline, "Q": Q,
    }


def compute_depth(left_gray, right_gray, calib):
    """Compute depth map in mm from rectified stereo pair."""
    rl = cv2.remap(left_gray, calib["map1x"], calib["map1y"], cv2.INTER_LINEAR)
    rr = cv2.remap(right_gray, calib["map2x"], calib["map2y"], cv2.INTER_LINEAR)

    stereo = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=128, blockSize=7,
        P1=8 * 7 * 7, P2=32 * 7 * 7,
        disp12MaxDiff=1, uniquenessRatio=15,
        speckleWindowSize=50, speckleRange=32
    )
    disp = stereo.compute(rl, rr).astype(np.float32) / 16.0
    depth = np.zeros_like(disp)
    valid = disp > 0
    depth[valid] = (calib["focal"] * calib["baseline"]) / disp[valid]
    return depth  # in mm


def compute_spatial_metrics(depth_mm, bike_width_cm, cam_height_cm):
    """Compute lateral margins and available gap from depth map."""
    h, w = depth_mm.shape
    half_bike_mm = bike_width_cm * 10 / 2.0  # mm

    # Focus on the driving zone: middle 60% vertically, full width
    drive_zone = depth_mm[int(h * 0.3):int(h * 0.8), :]
    dz_h, dz_w = drive_zone.shape

    # Divide into left third, center, right third
    left_zone = drive_zone[:, :dz_w // 3]
    center_zone = drive_zone[:, dz_w // 3:2 * dz_w // 3]
    right_zone = drive_zone[:, 2 * dz_w // 3:]

    def median_depth(zone):
        valid = zone[(zone > 200) & (zone < 15000)]
        return float(np.median(valid)) if len(valid) > 50 else -1

    # Closest obstacle in each zone
    def closest_depth(zone):
        valid = zone[(zone > 200) & (zone < 15000)]
        return float(np.percentile(valid, 5)) if len(valid) > 50 else -1

    depth_left = closest_depth(left_zone)
    depth_center = median_depth(center_zone)
    depth_right = closest_depth(right_zone)

    # Lateral margins: distance to nearest wall/obstacle minus half bike width
    # Negative = doesn't fit
    margin_left_mm = depth_left - half_bike_mm if depth_left > 0 else -1
    margin_right_mm = depth_right - half_bike_mm if depth_right > 0 else -1

    # Available gap: estimate from depth profile at ~3m ahead
    # Look at the row where depth ≈ 3000mm
    target_depth = 3000  # 3m ahead
    gap_width_mm = -1
    for row in range(dz_h):
        row_depth = drive_zone[row, :]
        near_target = (row_depth > target_depth * 0.7) & (row_depth < target_depth * 1.3)
        if near_target.sum() > 20:
            # Count consecutive pixels with valid depth at ~3m
            cols = np.where(near_target)[0]
            if len(cols) > 10:
                # Width in pixels → width in mm using depth and focal
                pixel_span = cols[-1] - cols[0]
                gap_width_mm = pixel_span * target_depth / 530.0  # approximate
                break

    # Action suggestion
    bike_width_mm = bike_width_cm * 10
    if depth_center > 0 and depth_center < 2000:
        action = "brake"  # obstacle < 2m ahead
    elif gap_width_mm > 0 and gap_width_mm < bike_width_mm + 200:
        action = "narrow"  # tight passage, slow down
    elif margin_left_mm >= 0 and margin_left_mm < 200:
        action = "steer_right"  # too close to left wall
    elif margin_right_mm >= 0 and margin_right_mm < 200:
        action = "steer_left"  # too close to right wall
    else:
        action = "clear"  # safe to proceed

    return {
        "depth_left_mm": round(depth_left, 0) if depth_left > 0 else -1,
        "depth_center_mm": round(depth_center, 0) if depth_center > 0 else -1,
        "depth_right_mm": round(depth_right, 0) if depth_right > 0 else -1,
        "margin_left_mm": round(margin_left_mm, 0) if margin_left_mm > -1 else -1,
        "margin_right_mm": round(margin_right_mm, 0) if margin_right_mm > -1 else -1,
        "gap_width_mm": round(gap_width_mm, 0) if gap_width_mm > 0 else -1,
        "spatial_action": action,
    }


def parse_timestamp(ts_str):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def load_sensors(csv_path):
    rows = []
    with open(csv_path, errors="replace") as f:
        clean = (line.replace("\x00", "") for line in f)
        reader = csv.DictReader(clean)
        for row in reader:
            ts = parse_timestamp(row["timestamp"])
            if ts is None:
                continue
            row["_ts"] = ts
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
    from datetime import timedelta
    return start_time + timedelta(seconds=frame_idx / fps)


def find_closest_sensor(target_ts, sensors):
    best = None
    best_diff = float("inf")
    for row in sensors:
        diff = abs((row["_ts"] - target_ts).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best = row
    return best, best_diff


def process_session(session_dir, session_name, calib, config):
    sensors_path = os.path.join(session_dir, "sensors.csv")
    meta_path = os.path.join(session_dir, "metadata.json")
    video_path = os.path.join(session_dir, "video.mp4")

    if not os.path.exists(sensors_path):
        print(f"  SKIP: no sensors.csv")
        return []
    if not os.path.exists(video_path):
        print(f"  SKIP: no video.mp4")
        return []

    fps = 15
    start_time = None
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        fps = meta.get("video_fps", 15)
        start_time = parse_timestamp(meta.get("start_time", ""))

    sensors = load_sensors(sensors_path)
    if not sensors:
        print(f"  SKIP: empty sensors.csv")
        return []
    if start_time is None:
        start_time = sensors[0]["_ts"]

    frames = sorted([f for f in os.listdir(session_dir)
                     if f.startswith("frame_") and f.endswith(".png")])
    if not frames:
        print(f"  SKIP: no segmented frames")
        return []

    # Open video for stereo depth
    cap = cv2.VideoCapture(video_path)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_seg_frames = 60
    step = max(1, total_video_frames // max_seg_frames)

    bike_width = config["asmile"]["larghezza_max_cm"]
    cam_height = config["asmile"]["altezza_cam_da_terra_cm"]

    results = []
    prev_speed = None
    prev_encoder = None

    for i, fname in enumerate(frames):
        frame_num = int(fname.replace("frame_", "").replace(".png", ""))
        video_frame_idx = 200 + frame_num * step

        # Get stereo frame for depth
        cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_idx)
        ret, stereo = cap.read()
        spatial = {}
        if ret:
            stereo = cv2.flip(stereo, -1)
            left = stereo[:, :640]
            right = stereo[:, 640:]
            left_g = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left
            right_g = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if len(right.shape) == 3 else right
            try:
                depth = compute_depth(left_g, right_g, calib)
                spatial = compute_spatial_metrics(depth, bike_width, cam_height)
            except Exception:
                spatial = {}

        # Align with sensor data
        frame_ts = frame_to_timestamp(video_frame_idx, start_time, fps)
        sensor, diff_s = find_closest_sensor(frame_ts, sensors)
        if diff_s > 2.0:
            continue

        speed = sensor["gps_speed_ms"]
        encoder = sensor["encoder_pos"]
        speed_delta = speed - prev_speed if prev_speed is not None else 0.0
        steering_delta = encoder - prev_encoder if prev_encoder is not None else 0
        is_braking = 1 if speed_delta < -0.3 else 0

        row = {
            "session": session_name,
            "frame_file": fname,
            "timestamp": sensor["timestamp"],
            "video_frame_idx": video_frame_idx,
            "gps_speed_ms": round(speed, 3),
            "gps_heading": round(sensor["gps_heading"], 1),
            "encoder_pos": encoder,
            "imu_accel_x": round(sensor["imu_accel_x"], 4),
            "imu_accel_y": round(sensor["imu_accel_y"], 4),
            "imu_accel_z": round(sensor["imu_accel_z"], 4),
            "imu_gyro_z": round(sensor["imu_gyro_z"], 2),
            "is_braking": is_braking,
            "speed_delta": round(speed_delta, 3),
            "steering_delta": steering_delta,
            # Spatial awareness
            "depth_left_mm": spatial.get("depth_left_mm", -1),
            "depth_center_mm": spatial.get("depth_center_mm", -1),
            "depth_right_mm": spatial.get("depth_right_mm", -1),
            "margin_left_mm": spatial.get("margin_left_mm", -1),
            "margin_right_mm": spatial.get("margin_right_mm", -1),
            "gap_width_mm": spatial.get("gap_width_mm", -1),
            "spatial_action": spatial.get("spatial_action", "unknown"),
        }
        results.append(row)
        prev_speed = speed
        prev_encoder = encoder

    cap.release()
    return results


def main():
    parser = argparse.ArgumentParser(description="Build training dataset v2 with spatial awareness")
    parser.add_argument("--sessions-dir", required=True)
    parser.add_argument("--output", default="dataset_v2.csv")
    parser.add_argument("--calib", default=os.path.expanduser("~/wip/calibration/auto/stereo_auto.json"))
    args = parser.parse_args()

    config = load_asmile_config()
    print(f"Asmile: {config['asmile']['larghezza_max_cm']}cm wide, "
          f"cam at {config['asmile']['altezza_cam_da_terra_cm']}cm height")

    calib = load_stereo_calib(args.calib)
    print(f"Stereo: focal={calib['focal']:.0f}px, baseline={calib['baseline']:.0f}mm")

    sessions = sorted([d for d in os.listdir(args.sessions_dir)
                       if d.startswith("session_") and os.path.isdir(os.path.join(args.sessions_dir, d))])
    print(f"Found {len(sessions)} sessions\n")

    all_data = []
    for sess in sessions:
        sess_dir = os.path.join(args.sessions_dir, sess)
        print(f"Processing {sess}...")
        data = process_session(sess_dir, sess, calib, config)
        all_data.extend(data)
        print(f"  {len(data)} frame-action-spatial pairs")

    if all_data:
        fields = list(all_data[0].keys())
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_data)

        braking = sum(1 for d in all_data if d["is_braking"])
        narrow = sum(1 for d in all_data if d["spatial_action"] == "narrow")
        brake_spatial = sum(1 for d in all_data if d["spatial_action"] == "brake")
        steer = sum(1 for d in all_data if d["spatial_action"].startswith("steer"))
        clear = sum(1 for d in all_data if d["spatial_action"] == "clear")
        has_depth = sum(1 for d in all_data if d["depth_center_mm"] > 0)

        print(f"\n{'='*50}")
        print(f"Dataset: {len(all_data)} frame-action-spatial pairs")
        print(f"Sessions: {len(sessions)}")
        print(f"With depth: {has_depth} ({has_depth/len(all_data)*100:.0f}%)")
        print(f"Rider braking: {braking} ({braking/len(all_data)*100:.0f}%)")
        print(f"Spatial actions:")
        print(f"  clear: {clear}  narrow: {narrow}  brake: {brake_spatial}  steer: {steer}")
        print(f"Saved to: {args.output}")
    else:
        print("No data collected!")


if __name__ == "__main__":
    main()
