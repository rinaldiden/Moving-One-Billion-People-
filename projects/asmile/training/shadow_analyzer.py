#!/usr/bin/env python3
"""
shadow_analyzer.py — Compare model predictions vs human driver (shadow mode).

Runs a trained behavioral cloning model on an entire session and compares
its predictions with the actual human driving inputs from the sensor CSV.

Outputs:
    - Per-frame disagreement score
    - Timestamps where model diverges from human
    - Statistics: mean error, correlation, worst disagreements
    - Edge case identification for targeted data collection

Usage:
    python3 shadow_analyzer.py --model model.pth \
                               --session ~/wip/recorder/session_20260417_181452/ \
                               --output shadow_report.csv

    python3 shadow_analyzer.py --model model.pth \
                               --session ~/wip/recorder/session_20260417_181452/ \
                               --output shadow_report.csv \
                               --threshold 0.3
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame_extractor import (
    load_sensor_csv, timestamp_to_frame_index, split_stereo,
    open_video, seek_and_read, VIDEO_FPS,
)
from depth_extractor import DepthExtractor, to_grayscale
from training_dataset import (
    normalize_encoder, compute_brake_target, compute_road_quality,
    ENCODER_NEUTRAL, SPEED_MAX_MS, ROAD_QUALITY_WINDOW,
)
from behavioral_cloning import infer, preprocess_frame, preprocess_depth, TORCH_AVAILABLE

if TORCH_AVAILABLE:
    import torch
    from behavioral_cloning import DrivingCNN, INPUT_H, INPUT_W, SPEED_MAX
else:
    from behavioral_cloning import (
        NumpyDrivingModel, INPUT_H, INPUT_W, SPEED_MAX,
    )


# ---------------------------------------------------------------------------
# Shadow analysis
# ---------------------------------------------------------------------------

def load_model(model_path: str):
    """Load model for batch inference."""
    if TORCH_AVAILABLE and model_path.endswith(".pth"):
        device = torch.device("cpu")
        model = DrivingCNN().to(device)
        checkpoint = torch.load(model_path, map_location=device,
                                weights_only=False)
        if "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
        else:
            model.load_state_dict(checkpoint)
        model.eval()
        return ("torch", model, device)
    else:
        model = NumpyDrivingModel()
        if os.path.isfile(model_path):
            model.load(model_path)
        return ("numpy", model, None)


def predict_batch(model_info, frame: np.ndarray, depth: np.ndarray,
                  speed: float, road_quality: float) -> dict:
    """Run prediction using loaded model."""
    kind, model, device = model_info

    if kind == "torch":
        frame_t = preprocess_frame(frame)
        depth_t = preprocess_depth(depth)
        visual = np.concatenate([frame_t, depth_t], axis=0)
        visual_tensor = torch.from_numpy(visual).unsqueeze(0).to(device)

        speed_norm = min(speed / SPEED_MAX, 1.0)
        scalars = torch.tensor([[speed_norm, road_quality]],
                               dtype=torch.float32).to(device)

        with torch.no_grad():
            steer, brake = model(visual_tensor, scalars)

        return {
            "steering_pred": float(steer.item()),
            "brake_pred": float(brake.item()),
        }
    else:
        result = model.predict(frame, depth, speed, road_quality)
        return {
            "steering_pred": result["steering"],
            "brake_pred": result["brake"],
        }


def analyze_session(model_path: str, session_dir: str, output_path: str,
                    calib_path: str | None = None,
                    threshold: float = 0.2,
                    every_n: int = 1) -> dict:
    """Run shadow analysis on a full session.

    Returns summary statistics dict.
    """
    session = Path(session_dir)
    session_name = session.name
    rows = load_sensor_csv(str(session / "sensors.csv"))
    first_ts = rows[0]["_ts"]

    # Preferisci il .mp4 muxato (seekable, frame_count valido) al .h264 grezzo
    # (elementary stream: cv2 non lo apre / non ci si posiziona). Fallback a .h264.
    video_file = session / "video.mp4"
    if not video_file.is_file():
        video_file = session / "video.h264"
    cap = open_video(str(video_file))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    depth_ext = DepthExtractor(calib_path)
    model_info = load_model(model_path)

    print(f"\nShadow analysis: {session_name}")
    print(f"  Sensor rows: {len(rows)}")
    print(f"  Video frames: {total_frames}")
    print(f"  Model: {model_path}")
    print(f"  Disagreement threshold: {threshold}")
    print()

    results = []
    az_buffer = []
    last_idx = -1
    processed = 0

    for i, row in enumerate(rows):
        az = float(row.get("imu_accel_z", 0.0))
        az_buffer.append(az)
        if len(az_buffer) > ROAD_QUALITY_WINDOW:
            az_buffer.pop(0)

        if i % every_n != 0:
            continue

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

        # Human ground truth
        encoder = float(row.get("encoder_pos", ENCODER_NEUTRAL))
        ax = float(row.get("imu_accel_x", 0.0))
        speed = float(row.get("gps_speed_ms", 0.0))
        gyro_z = float(row.get("imu_gyro_z", 0.0))

        human_steering = normalize_encoder(encoder)
        human_brake = compute_brake_target(ax)
        road_quality = compute_road_quality(list(az_buffer))

        # Compute depth
        depth_mm = depth_ext.process_pair(left, right)
        left_gray = to_grayscale(left)

        # Model prediction
        pred = predict_batch(model_info, left_gray, depth_mm,
                             speed, road_quality)

        # Disagreement scores
        steer_err = abs(pred["steering_pred"] - human_steering)
        brake_err = abs(pred["brake_pred"] - human_brake)
        disagreement = 0.7 * steer_err + 0.3 * brake_err

        result = {
            "timestamp": row["timestamp"],
            "frame_idx": frame_idx,
            "speed_ms": speed,
            "human_steering": human_steering,
            "model_steering": pred["steering_pred"],
            "steering_error": steer_err,
            "human_brake": human_brake,
            "model_brake": pred["brake_pred"],
            "brake_error": brake_err,
            "disagreement": disagreement,
            "is_disagreement": 1 if disagreement > threshold else 0,
            "encoder_raw": encoder,
            "ax_raw": ax,
            "gyro_z": gyro_z,
            "road_quality": road_quality,
        }
        results.append(result)
        processed += 1

        if processed % 100 == 0:
            n_disagree = sum(1 for r in results if r["is_disagreement"])
            print(f"  Processed {processed} frames, "
                  f"{n_disagree} disagreements so far")

    cap.release()

    if not results:
        print("Error: no frames processed.", file=sys.stderr)
        return {}

    # Write detailed CSV
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fieldnames = list(results[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nDetailed report: {output_path} ({len(results)} rows)")

    # Compute summary statistics
    steer_errors = [r["steering_error"] for r in results]
    brake_errors = [r["brake_error"] for r in results]
    disagreements = [r["disagreement"] for r in results]
    n_disagree = sum(1 for r in results if r["is_disagreement"])

    # Correlation
    human_steers = [r["human_steering"] for r in results]
    model_steers = [r["model_steering"] for r in results]
    human_brakes = [r["human_brake"] for r in results]
    model_brakes = [r["model_brake"] for r in results]

    steer_corr = float(np.corrcoef(human_steers, model_steers)[0, 1]) \
        if len(set(human_steers)) > 1 else 0.0
    brake_corr = float(np.corrcoef(human_brakes, model_brakes)[0, 1]) \
        if len(set(human_brakes)) > 1 and len(set(model_brakes)) > 1 else 0.0

    # Worst disagreements
    sorted_by_disagree = sorted(results, key=lambda r: r["disagreement"],
                                reverse=True)
    worst_10 = sorted_by_disagree[:10]

    summary = {
        "session": session_name,
        "total_frames": len(results),
        "disagreements": n_disagree,
        "disagreement_rate": n_disagree / len(results),
        "steering_error_mean": float(np.mean(steer_errors)),
        "steering_error_std": float(np.std(steer_errors)),
        "steering_error_p95": float(np.percentile(steer_errors, 95)),
        "steering_error_max": float(np.max(steer_errors)),
        "steering_correlation": steer_corr,
        "brake_error_mean": float(np.mean(brake_errors)),
        "brake_error_std": float(np.std(brake_errors)),
        "brake_correlation": brake_corr,
        "disagreement_mean": float(np.mean(disagreements)),
        "disagreement_p95": float(np.percentile(disagreements, 95)),
        "worst_timestamps": [w["timestamp"] for w in worst_10],
    }

    # Print summary
    print("\n" + "=" * 60)
    print("SHADOW MODE ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Session:           {summary['session']}")
    print(f"Frames analyzed:   {summary['total_frames']}")
    print(f"Disagreements:     {summary['disagreements']} "
          f"({summary['disagreement_rate']:.1%})")
    print()
    print("Steering:")
    print(f"  Mean error:      {summary['steering_error_mean']:.4f}")
    print(f"  Std error:       {summary['steering_error_std']:.4f}")
    print(f"  P95 error:       {summary['steering_error_p95']:.4f}")
    print(f"  Max error:       {summary['steering_error_max']:.4f}")
    print(f"  Correlation:     {summary['steering_correlation']:.4f}")
    print()
    print("Braking:")
    print(f"  Mean error:      {summary['brake_error_mean']:.4f}")
    print(f"  Correlation:     {summary['brake_correlation']:.4f}")
    print()
    print("Worst disagreements:")
    for w in worst_10[:5]:
        print(f"  {w['timestamp']}  "
              f"score={w['disagreement']:.3f}  "
              f"steer_err={w['steering_error']:.3f}  "
              f"brake_err={w['brake_error']:.3f}  "
              f"speed={w['speed_ms']:.1f}m/s")

    # Save summary JSON
    summary_path = output_path.rsplit(".", 1)[0] + "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved: {summary_path}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Shadow mode analysis: compare model vs human driver.")
    parser.add_argument("--model", required=True,
                        help="Trained model path (.pth or .npz)")
    parser.add_argument("--session", required=True,
                        help="Session directory path")
    parser.add_argument("--output", required=True,
                        help="Output CSV path for detailed report")
    parser.add_argument("--calibration", default=None,
                        help="Stereo calibration YAML path")
    parser.add_argument("--threshold", type=float, default=0.2,
                        help="Disagreement threshold (default: 0.2)")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Analyze every Nth sensor row (default: 1)")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session not found: {session}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.model):
        print(f"Error: model not found: {args.model}", file=sys.stderr)
        sys.exit(1)

    analyze_session(args.model, session, args.output,
                    args.calibration, args.threshold, args.every_n)


if __name__ == "__main__":
    main()
