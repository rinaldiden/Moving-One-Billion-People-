#!/usr/bin/env python3
"""
Prepare training data from recorded sessions and train behavioral cloning model.

Reads video frames + sensors.csv from sessions, creates train/val splits,
and launches training.

Usage:
    python3 prepare_and_train.py --sessions-dir ~/segmentazione/da_segmentare/
    python3 prepare_and_train.py --sessions-dir ~/segmentazione/da_segmentare/ --epochs 100
"""

import os
import sys
import csv
import json
import cv2
import numpy as np
import argparse
import random
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "..", "segmentazione", "da_segmentare")

# Encoder center (dritto) — from driving_patterns.md
ENCODER_CENTER = 2750
ENCODER_RANGE = 500  # ±500 from center = ±1.0 normalized

# Speed normalization
SPEED_MAX = 6.0  # m/s

# Braking threshold
BRAKE_ACCEL_THRESHOLD = 0.10  # accel_x > 0.2 = braking


def load_sensors(csv_path):
    rows = []
    with open(csv_path, errors="replace") as f:
        clean = (line.replace("\x00", "") for line in f)
        reader = csv.DictReader(clean)
        for row in reader:
            try:
                row["_speed"] = float(row.get("gps_speed_ms", 0))
                row["_accel_x"] = float(row.get("imu_accel_x", 0))
                row["_gyro_z"] = float(row.get("imu_gyro_z", 0))
                row["_enc"] = int(row.get("encoder_pos", -1))
                rows.append(row)
            except (ValueError, KeyError):
                pass
    return rows


def prepare_dataset(sessions_dir, output_dir, val_split=0.15):
    """Extract frames + labels from all sessions."""
    os.makedirs(output_dir, exist_ok=True)
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    sessions = sorted([d for d in os.listdir(sessions_dir)
                       if d.startswith("session_") and
                       os.path.exists(os.path.join(sessions_dir, d, "video.mp4")) and
                       os.path.exists(os.path.join(sessions_dir, d, "sensors.csv"))])

    all_samples = []
    total_frames = 0

    for sess in sessions:
        sess_dir = os.path.join(sessions_dir, sess)
        video_path = os.path.join(sess_dir, "video.mp4")
        sensors_path = os.path.join(sess_dir, "sensors.csv")

        sensors = load_sensors(sensors_path)
        if len(sensors) < 20:
            continue

        cap = cv2.VideoCapture(video_path)
        vtotal = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = 15

        if vtotal < 100:
            cap.release()
            continue

        # Sample every 5th frame (3fps effective — enough variety, not too redundant)
        step = 5
        enc_center = np.median([r["_enc"] for r in sensors if r["_enc"] > 0])
        if enc_center <= 0:
            enc_center = ENCODER_CENTER

        n_extracted = 0
        for fi in range(50, vtotal - 10, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ret, frame = cap.read()
            if not ret:
                continue

            # Left camera only (first half for display cam)
            left = frame[:, :frame.shape[1] // 2]
            if left.mean() < 30 or left.mean() > 240:
                continue

            # Corresponding sensor row
            sensor_idx = min(len(sensors) - 1, max(0, int(fi / vtotal * len(sensors))))
            s = sensors[sensor_idx]

            enc = s["_enc"]
            speed = s["_speed"]
            accel_x = s["_accel_x"]
            gyro_z = s["_gyro_z"]

            if enc <= 0:
                continue

            # Normalize steering: encoder → -1..+1
            enc_delta = enc - enc_center
            if enc_delta > 2048:
                enc_delta -= 4096
            elif enc_delta < -2048:
                enc_delta += 4096
            steering = np.clip(enc_delta / ENCODER_RANGE, -1.0, 1.0)

            # Brake: 1 if decelerating, 0 otherwise
            brake = min(1.0, max(0.0, accel_x / 0.3)) if accel_x > BRAKE_ACCEL_THRESHOLD or speed < 0.5 else 0.0

            # Speed normalized
            speed_norm = min(speed / SPEED_MAX, 1.0)

            # Road quality from IMU variance (rough)
            road_quality = min(abs(accel_x) / 0.5, 1.0)

            # Save frame
            frame_name = f"{sess}_{fi:06d}.png"
            frame_path = os.path.join(frames_dir, frame_name)

            # Save grayscale, resized to model input
            gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left
            cv2.imwrite(frame_path, gray)

            all_samples.append({
                "frame_path": frame_path,
                "depth_path": "",
                "steering_target": round(steering, 4),
                "brake_target": round(brake, 1),
                "speed_target": round(speed_norm, 4),
                "road_quality": round(road_quality, 4),
                "session": sess,
                "frame_idx": fi,
                "encoder_raw": enc,
                "speed_ms": round(speed, 2),
                "gyro_z": round(gyro_z, 1),
            })
            n_extracted += 1

        cap.release()
        total_frames += n_extracted
        if n_extracted > 0:
            print(f"  {sess}: {n_extracted} frames")

    print(f"\nTotal: {total_frames} training frames from {len(sessions)} sessions")

    # Split train/val
    random.seed(42)
    random.shuffle(all_samples)
    split = int(len(all_samples) * (1 - val_split))
    train_samples = all_samples[:split]
    val_samples = all_samples[split:]

    # Save CSVs
    for name, samples in [("train_labels.csv", train_samples),
                           ("val_labels.csv", val_samples)]:
        path = os.path.join(output_dir, name)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=samples[0].keys())
            writer.writeheader()
            writer.writerows(samples)
        print(f"Saved {path} ({len(samples)} samples)")

    # Stats
    steerings = [s["steering_target"] for s in all_samples]
    brakes = [s["brake_target"] for s in all_samples]
    speeds = [s["speed_ms"] for s in all_samples]

    print(f"\nDataset stats:")
    print(f"  Train: {len(train_samples)}, Val: {len(val_samples)}")
    print(f"  Steering: mean={np.mean(steerings):.3f}, std={np.std(steerings):.3f}")
    print(f"  Braking frames: {sum(1 for b in brakes if b > 0)} ({sum(1 for b in brakes if b > 0) / len(brakes) * 100:.0f}%)")
    print(f"  Speed: mean={np.mean(speeds):.1f}m/s, max={max(speeds):.1f}m/s")

    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Prepare data and train Asmile model")
    parser.add_argument("--sessions-dir", default=BASE_DIR)
    parser.add_argument("--output-dir", default=os.path.join(SCRIPT_DIR, "training_data"))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Only prepare data, don't train")
    args = parser.parse_args()

    print("=" * 50)
    print("  ASMILE BEHAVIORAL CLONING")
    print("=" * 50)
    print(f"Sessions: {args.sessions_dir}")
    print()

    # Step 1: Prepare dataset
    print("Step 1: Preparing dataset...")
    data_dir = prepare_dataset(args.sessions_dir, args.output_dir)

    if args.prepare_only:
        print("\nData prepared. Run with --train to start training.")
        return

    # Step 2: Train
    print(f"\nStep 2: Training model ({args.epochs} epochs)...")
    from behavioral_cloning import train
    model_path = os.path.join(args.output_dir, "asmile_model.pth")
    train(data_dir, model_path, epochs=args.epochs,
          batch_size=args.batch_size, lr=args.lr)

    print(f"\nDone! Model saved: {model_path}")


if __name__ == "__main__":
    main()
