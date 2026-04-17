#!/usr/bin/env python3
"""
visualizer.py — Visualize training data with annotated overlays.

Creates annotated frames showing:
- Left camera frame
- Depth map overlay (color-coded)
- Steering indicator (arrow showing encoder direction)
- Speed bar
- Brake indicator
- Current sensor values as text overlay

Can output a single annotated PNG or a full annotated video.

Usage:
    # Create annotated video from a session
    python3 visualizer.py --session ~/wip/recorder/session_20260417_181452/ \
                          --output ~/wip/viz/annotated.mp4

    # Create single annotated frame
    python3 visualizer.py --session ~/wip/recorder/session_20260417_181452/ \
                          --timestamp 2026-04-17T18:22:02.077 \
                          --output frame.png
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame_extractor import (
    load_sensor_csv, timestamp_to_frame_index, split_stereo,
    open_video, seek_and_read, parse_timestamp, VIDEO_FPS,
)
from depth_extractor import DepthExtractor, to_grayscale
from training_dataset import (
    normalize_encoder, compute_brake_target, compute_road_quality,
    ENCODER_NEUTRAL, GYRO_Z_NOISE_FLOOR, SPEED_MAX_MS, ROAD_QUALITY_WINDOW,
)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

CANVAS_W = 960
CANVAS_H = 540
FRAME_W = 640
FRAME_H = 400
PANEL_X = FRAME_W + 10  # Right panel start
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = 0.45
FONT_MED = 0.55
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
CYAN = (255, 255, 0)
GRAY = (128, 128, 128)


def colorize_depth(depth_mm: np.ndarray, max_depth: float = 10000) -> np.ndarray:
    """Convert depth map (float32 mm) to a colorized BGR image."""
    valid = depth_mm > 0
    normalized = np.zeros_like(depth_mm)
    normalized[valid] = np.clip(depth_mm[valid] / max_depth, 0, 1)
    # Invert so close = warm, far = cool
    normalized[valid] = 1.0 - normalized[valid]
    # Scale to 0-255
    gray = (normalized * 255).astype(np.uint8)
    colored = cv2.applyColorMap(gray, cv2.COLORMAP_TURBO)
    # Set invalid pixels to black
    colored[~valid] = 0
    return colored


def draw_steering_arrow(canvas: np.ndarray, steering_norm: float,
                        cx: int, cy: int, radius: int = 40):
    """Draw a steering indicator arrow."""
    # steering_norm: -1 (left) to +1 (right)
    # Map to angle: -1 -> -90deg (left), 0 -> 0 (straight), +1 -> +90deg (right)
    # Remap from encoder range: neutral (~0.83 norm) should be center
    # Use raw steering_norm directly; the arrow shows raw encoder position
    angle_deg = steering_norm * 90.0
    angle_rad = np.radians(-angle_deg + 90)  # 90 = up
    end_x = int(cx + radius * np.cos(angle_rad))
    end_y = int(cy - radius * np.sin(angle_rad))

    # Background circle
    cv2.circle(canvas, (cx, cy), radius + 5, GRAY, 1)
    # Arrow
    color = GREEN if abs(steering_norm) < 0.3 else YELLOW
    if abs(steering_norm) > 0.7:
        color = RED
    cv2.arrowedLine(canvas, (cx, cy), (end_x, end_y), color, 2,
                    tipLength=0.3)
    cv2.putText(canvas, f"Steer: {steering_norm:+.2f}",
                (cx - 45, cy + radius + 20), FONT, FONT_SMALL, WHITE, 1)


def draw_speed_bar(canvas: np.ndarray, speed_ms: float,
                   x: int, y: int, bar_w: int = 200, bar_h: int = 20):
    """Draw a horizontal speed bar."""
    max_speed = 6.0
    fill = min(speed_ms / max_speed, 1.0)
    kmh = speed_ms * 3.6

    cv2.rectangle(canvas, (x, y), (x + bar_w, y + bar_h), GRAY, 1)
    fill_w = int(fill * bar_w)
    color = GREEN if speed_ms < 3.0 else (YELLOW if speed_ms < 4.5 else RED)
    cv2.rectangle(canvas, (x, y), (x + fill_w, y + bar_h), color, -1)
    cv2.putText(canvas, f"{kmh:.1f} km/h ({speed_ms:.1f} m/s)",
                (x, y - 5), FONT, FONT_SMALL, WHITE, 1)


def draw_brake_indicator(canvas: np.ndarray, brake: float,
                         x: int, y: int, size: int = 30):
    """Draw brake indicator (circle, red when braking)."""
    if brake > 0.01:
        intensity = int(min(brake, 1.0) * 255)
        color = (0, 0, intensity)
        cv2.circle(canvas, (x + size // 2, y + size // 2),
                   size // 2, color, -1)
        cv2.putText(canvas, f"BRAKE {brake:.0%}",
                    (x + size + 5, y + size - 5), FONT, FONT_SMALL, RED, 1)
    else:
        cv2.circle(canvas, (x + size // 2, y + size // 2),
                   size // 2, GRAY, 1)
        cv2.putText(canvas, "brake off",
                    (x + size + 5, y + size - 5), FONT, FONT_SMALL, GRAY, 1)


def draw_sensor_text(canvas: np.ndarray, row: dict, x: int, y: int):
    """Draw raw sensor values as text."""
    lines = [
        f"Time: {row.get('timestamp', 'N/A')}",
        f"GPS:  {row.get('gps_lat', 'N/A')}, {row.get('gps_lon', 'N/A')}",
        f"Hdg:  {row.get('gps_heading', 'N/A')}",
        f"Enc:  {row.get('encoder_pos', 'N/A')}",
        f"Ax:   {float(row.get('imu_accel_x', 0)):.3f} g",
        f"Ay:   {float(row.get('imu_accel_y', 0)):.3f} g",
        f"Az:   {float(row.get('imu_accel_z', 0)):.3f} g",
        f"Gx:   {float(row.get('imu_gyro_x', 0)):.1f} d/s",
        f"Gy:   {float(row.get('imu_gyro_y', 0)):.1f} d/s",
        f"Gz:   {float(row.get('imu_gyro_z', 0)):.1f} d/s",
    ]
    for i, line in enumerate(lines):
        cv2.putText(canvas, line, (x, y + i * 16), FONT, FONT_SMALL,
                    WHITE, 1, cv2.LINE_AA)


def draw_road_quality(canvas: np.ndarray, rq: float,
                      x: int, y: int, bar_w: int = 200, bar_h: int = 14):
    """Draw road quality bar (variance of az)."""
    max_rq = 0.5  # rough road
    fill = min(rq / max_rq, 1.0)
    color = GREEN if rq < 0.15 else (YELLOW if rq < 0.3 else RED)
    cv2.rectangle(canvas, (x, y), (x + bar_w, y + bar_h), GRAY, 1)
    cv2.rectangle(canvas, (x, y), (x + int(fill * bar_w), y + bar_h),
                  color, -1)
    label = "smooth" if rq < 0.1 else ("moderate" if rq < 0.3 else "rough")
    cv2.putText(canvas, f"Road: {label} ({rq:.3f})",
                (x, y - 4), FONT, FONT_SMALL, WHITE, 1)


# ---------------------------------------------------------------------------
# Frame annotation
# ---------------------------------------------------------------------------

def annotate_frame(left_bgr: np.ndarray, depth_mm: np.ndarray,
                   row: dict, az_buffer: list[float]) -> np.ndarray:
    """Create a fully annotated visualization canvas."""
    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)

    # Place left frame (top-left)
    h, w = left_bgr.shape[:2]
    if len(left_bgr.shape) == 2:
        left_bgr = cv2.cvtColor(left_bgr, cv2.COLOR_GRAY2BGR)
    canvas[:h, :w] = left_bgr

    # Depth overlay (blended on top, bottom-right area)
    depth_color = colorize_depth(depth_mm)
    # Scale depth to fit in remaining space
    depth_small_h = CANVAS_H - FRAME_H - 10
    depth_small_w = FRAME_W
    if depth_small_h > 20:
        depth_resized = cv2.resize(depth_color, (depth_small_w, depth_small_h))
        y_start = FRAME_H + 5
        canvas[y_start:y_start + depth_small_h, :depth_small_w] = depth_resized
        cv2.putText(canvas, "Depth (close=warm, far=cool)",
                    (5, y_start - 3), FONT, FONT_SMALL, CYAN, 1)

    # Extract values
    encoder = float(row.get("encoder_pos", ENCODER_NEUTRAL))
    speed = float(row.get("gps_speed_ms", 0.0))
    ax = float(row.get("imu_accel_x", 0.0))
    az = float(row.get("imu_accel_z", 0.0))
    gyro_z = float(row.get("imu_gyro_z", 0.0))

    steering_norm = normalize_encoder(encoder)
    brake = compute_brake_target(ax)
    rq = compute_road_quality(az_buffer)
    turning = abs(gyro_z) > GYRO_Z_NOISE_FLOOR

    # Right panel
    px = PANEL_X

    # Steering arrow
    draw_steering_arrow(canvas, steering_norm, px + 50, 60)

    # Speed bar
    draw_speed_bar(canvas, speed, px, 130, bar_w=280)

    # Brake indicator
    draw_brake_indicator(canvas, brake, px, 170)

    # Road quality
    draw_road_quality(canvas, rq, px, 230, bar_w=280)

    # Turning indicator
    turn_text = "TURNING" if turning else "straight"
    turn_color = YELLOW if turning else GRAY
    cv2.putText(canvas, f"Dir: {turn_text} (gz={gyro_z:.1f})",
                (px, 278), FONT, FONT_SMALL, turn_color, 1)

    # Raw sensor text
    draw_sensor_text(canvas, row, px, 310)

    return canvas


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def visualize_single(session_dir: str, timestamp_str: str,
                     output_path: str, calib_path: str | None = None):
    """Create a single annotated frame."""
    session = Path(session_dir)
    rows = load_sensor_csv(str(session / "sensors.csv"))
    first_ts = rows[0]["_ts"]
    target_ts = parse_timestamp(timestamp_str)

    # Find closest sensor row
    closest_idx = min(range(len(rows)),
                      key=lambda i: abs(rows[i]["_ts"] - target_ts))
    row = rows[closest_idx]

    # Build az buffer from preceding rows
    az_buffer = []
    start = max(0, closest_idx - ROAD_QUALITY_WINDOW)
    for r in rows[start:closest_idx + 1]:
        az_buffer.append(float(r.get("imu_accel_z", 0.0)))

    # Get video frame
    frame_idx = timestamp_to_frame_index(row["_ts"], first_ts)
    cap = open_video(str(session / "video.h264"))
    stereo = seek_and_read(cap, frame_idx)
    cap.release()

    if stereo is None:
        raise RuntimeError(f"Failed to read frame {frame_idx}")

    left, right = split_stereo(stereo)

    # Compute depth
    extractor = DepthExtractor(calib_path)
    depth_mm = extractor.process_pair(left, right)

    # Annotate
    canvas = annotate_frame(left, depth_mm, row, az_buffer)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cv2.imwrite(output_path, canvas)
    print(f"Saved annotated frame: {output_path}")


def visualize_video(session_dir: str, output_path: str,
                    calib_path: str | None = None,
                    every_n: int = 1,
                    output_fps: int = 15):
    """Create annotated video from a full session."""
    session = Path(session_dir)
    rows = load_sensor_csv(str(session / "sensors.csv"))
    first_ts = rows[0]["_ts"]

    cap = open_video(str(session / "video.h264"))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    extractor = DepthExtractor(calib_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, output_fps,
                             (CANVAS_W, CANVAS_H))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create video writer: {output_path}")

    az_buffer = []
    last_idx = -1
    written = 0

    for i, row in enumerate(rows):
        if i % every_n != 0:
            # Still track az for road quality
            az_buffer.append(float(row.get("imu_accel_z", 0.0)))
            if len(az_buffer) > ROAD_QUALITY_WINDOW:
                az_buffer.pop(0)
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

        # Update az buffer
        az_buffer.append(float(row.get("imu_accel_z", 0.0)))
        if len(az_buffer) > ROAD_QUALITY_WINDOW:
            az_buffer.pop(0)

        # Compute depth
        depth_mm = extractor.process_pair(left, right)

        # Annotate
        canvas = annotate_frame(left, depth_mm, row, list(az_buffer))
        writer.write(canvas)
        written += 1

        if written % 50 == 0:
            print(f"  Written {written} frames (row {i+1}/{len(rows)})")

    writer.release()
    cap.release()
    print(f"Done: {written} annotated frames -> {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visualize training data with annotated overlays.")
    parser.add_argument("--session", required=True,
                        help="Path to session directory")
    parser.add_argument("--output", required=True,
                        help="Output path (.mp4 for video, .png for single frame)")
    parser.add_argument("--timestamp", default=None,
                        help="Single timestamp to visualize (ISO format)")
    parser.add_argument("--calibration", default=None,
                        help="Stereo calibration YAML path")
    parser.add_argument("--every-n", type=int, default=1,
                        help="Process every Nth row for video (default: 1)")
    parser.add_argument("--fps", type=int, default=15,
                        help="Output video FPS (default: 15)")
    args = parser.parse_args()

    session = args.session.rstrip("/")
    if not os.path.isdir(session):
        print(f"Error: session not found: {session}", file=sys.stderr)
        sys.exit(1)

    if args.timestamp:
        visualize_single(session, args.timestamp, args.output,
                         args.calibration)
    else:
        if not args.output.endswith((".mp4", ".avi", ".mkv")):
            print("Warning: output should be a video file (.mp4) "
                  "for batch mode.", file=sys.stderr)
        visualize_video(session, args.output, args.calibration,
                        args.every_n, args.fps)


if __name__ == "__main__":
    main()
