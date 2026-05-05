#!/usr/bin/env python3
"""
Asmile Keyframe Extractor — selects training-worthy frames from ride sessions.

Two approaches run in parallel, results merged:

1. SMART (sensor-driven): extracts frames where something interesting happens
   - Deceleration (braking)
   - Steering change (encoder delta)
   - Speed transitions (moving→stopped, stopped→moving)
   - GPS heading change (curve)

2. BRUTE (frame-by-frame): scans every Nth frame with YOLO + CV
   - Object detection (person, car, dog, stop sign...)
   - Road marking detection (white lines, stop lines)
   - Scene change detection (frame difference)

After both runs, merge results, remove duplicates, compare what each found.

Usage:
  python3 keyframe_extractor.py --session session_20260505_093113
  python3 keyframe_extractor.py --all  # process all sessions
  python3 keyframe_extractor.py --all --brute-step 3  # every 3rd frame (slower, more thorough)

Output:
  session_dir/keyframes/
    keyframes.csv     — all selected frames with reason
    frame_XXXXX.png   — extracted frame images
    summary.json      — stats
"""

import os
import sys
import csv
import json
import cv2
import numpy as np
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, "..")
BASE_DIR = os.path.join(PROJECT_DIR, "segmentazione", "da_segmentare")


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


def smart_extract(sensors, fps=15):
    """Find interesting moments from sensor data alone."""
    keyframes = []
    n = len(sensors)
    if n < 20:
        return keyframes

    prev_speed = sensors[0]["_speed"]
    prev_enc = sensors[0]["_enc"]
    stopped_count = 0
    was_stopped = False

    for i, row in enumerate(sensors):
        speed = row["_speed"]
        accel_x = row["_accel_x"]
        gyro_z = row["_gyro_z"]
        enc = row["_enc"]
        frame_idx = int(i / n * fps * (n / 10))  # approximate video frame

        reasons = []

        # Braking: accel_x > 0.2g
        if accel_x > 0.25:
            reasons.append("braking")

        # Hard braking
        if accel_x > 0.4:
            reasons.append("hard_braking")

        # Speed transition: moving → stopped
        if speed < 0.3 and prev_speed > 1.0:
            reasons.append("stop_arrival")

        # Speed transition: stopped → moving
        if speed > 1.0 and prev_speed < 0.3 and was_stopped:
            reasons.append("departure")

        # Steering: encoder change
        enc_delta = abs(enc - prev_enc) if prev_enc > 0 and enc > 0 else 0
        if enc_delta > 2048:
            enc_delta = 4096 - enc_delta
        if enc_delta > 15:
            reasons.append("steering")
        if enc_delta > 50:
            reasons.append("hard_steering")

        # Sharp turn: gyro_z
        if abs(gyro_z) > 15:
            reasons.append("turning")
        if abs(gyro_z) > 30:
            reasons.append("sharp_turn")

        # Track stopped state
        if speed < 0.3:
            stopped_count += 1
            if stopped_count == 15:  # 1.5s stopped
                reasons.append("full_stop")
        else:
            stopped_count = 0
        was_stopped = speed < 0.3

        if reasons:
            keyframes.append({
                "sensor_idx": i,
                "frame_idx": frame_idx,
                "reasons": reasons,
                "speed": round(speed, 2),
                "accel_x": round(accel_x, 3),
                "gyro_z": round(gyro_z, 1),
                "encoder": enc,
                "enc_delta": enc_delta,
                "method": "smart",
            })

        prev_speed = speed
        prev_enc = enc

    return keyframes


def brute_extract(video_path, step=5):
    """Scan frames with CV for road markings, scene changes, objects."""
    try:
        from ultralytics import YOLO
        yolo = YOLO("yolov8m-seg.pt")
        has_yolo = True
    except Exception:
        has_yolo = False

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    keyframes = []
    prev_gray = None

    for fi in range(100, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv2.flip(frame, -1)
        left = frame[:, :frame.shape[1] // 2]
        gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left
        h, w = gray.shape
        reasons = []

        # Scene change detection
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            change_pct = np.mean(diff) / 255 * 100
            if change_pct > 5:
                reasons.append("scene_change")

        # Road marking detection (bottom half)
        road = gray[h // 2:, :]
        road_mean = np.mean(road)

        # White lines (lane markings, stop lines)
        _, white = cv2.threshold(road, int(road_mean + 40), 255, cv2.THRESH_BINARY)
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 8))
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 2))
        white_v = cv2.morphologyEx(white, cv2.MORPH_OPEN, kernel_v)
        white_h = cv2.morphologyEx(white, cv2.MORPH_OPEN, kernel_h)
        white_v_pct = np.sum(white_v > 0) / white_v.size * 100
        white_h_pct = np.sum(white_h > 0) / white_h.size * 100

        if white_v_pct > 1.5:
            reasons.append("lane_marking")
        if white_h_pct > 2.0:
            reasons.append("stop_line")

        # Hough lines for strong horizontal lines (stop lines)
        edges = cv2.Canny(road, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 40, minLineLength=w // 3, maxLineGap=15)
        if lines is not None:
            horiz = sum(1 for l in lines if abs(np.degrees(np.arctan2(
                l[0][3] - l[0][1], l[0][2] - l[0][0]))) < 15)
            if horiz >= 2:
                reasons.append("strong_stop_line")

        # YOLO detection
        if has_yolo:
            results = yolo(left, verbose=False, conf=0.3)
            r = results[0]
            if r.boxes is not None:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    name = yolo.names[cls_id]
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    obj_size = (x2 - x1) * (y2 - y1) / (h * w)

                    if name in ["person", "dog", "cat"] and obj_size > 0.01:
                        reasons.append(f"obj_{name}")
                    elif name in ["car", "truck", "bus", "motorcycle", "bicycle"] and obj_size > 0.03:
                        reasons.append(f"obj_{name}")
                    elif name in ["stop sign", "traffic light"]:
                        reasons.append(f"obj_{name}")

        if reasons:
            keyframes.append({
                "frame_idx": fi,
                "reasons": reasons,
                "method": "brute",
            })

        prev_gray = gray.copy()

    cap.release()
    return keyframes


def merge_keyframes(smart_kf, brute_kf, total_frames, fps=15, merge_window=10):
    """Merge smart and brute keyframes, remove duplicates within merge_window frames."""
    all_kf = []

    for kf in smart_kf:
        kf["_sort_key"] = kf["frame_idx"]
        all_kf.append(kf)

    for kf in brute_kf:
        kf["_sort_key"] = kf["frame_idx"]
        all_kf.append(kf)

    all_kf.sort(key=lambda x: x["_sort_key"])

    # Merge nearby keyframes
    merged = []
    for kf in all_kf:
        if merged and abs(kf["_sort_key"] - merged[-1]["_sort_key"]) < merge_window:
            # Merge reasons
            existing = merged[-1]
            for r in kf.get("reasons", []):
                if r not in existing["reasons"]:
                    existing["reasons"].append(r)
            if kf["method"] != existing["method"]:
                existing["method"] = "both"
        else:
            merged.append(kf)

    return merged


def extract_frame_images(video_path, keyframes, output_dir):
    """Save frame images for selected keyframes."""
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)

    for kf in keyframes:
        fi = kf["frame_idx"]
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv2.flip(frame, -1)
        left = frame[:, :frame.shape[1] // 2]
        fname = f"frame_{fi:06d}.png"
        cv2.imwrite(os.path.join(output_dir, fname), left)
        kf["file"] = fname

    cap.release()


def process_session(sess_dir, brute_step=5):
    """Process one session: smart + brute extraction, merge, save."""
    sess_name = os.path.basename(sess_dir)
    sensors_path = os.path.join(sess_dir, "sensors.csv")
    video_path = os.path.join(sess_dir, "video.mp4")
    output_dir = os.path.join(sess_dir, "keyframes")

    if not os.path.exists(video_path):
        print(f"  SKIP {sess_name}: no video.mp4")
        return None

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    print(f"\n{sess_name} ({total_frames} frames)")

    # Smart extraction from sensors
    smart_kf = []
    if os.path.exists(sensors_path):
        sensors = load_sensors(sensors_path)
        smart_kf = smart_extract(sensors)
        print(f"  Smart: {len(smart_kf)} keyframes")
    else:
        print(f"  Smart: no sensors.csv")

    # Brute extraction from video
    print(f"  Brute: scanning every {brute_step} frames...")
    brute_kf = brute_extract(video_path, step=brute_step)
    print(f"  Brute: {len(brute_kf)} keyframes")

    # Merge
    merged = merge_keyframes(smart_kf, brute_kf, total_frames)
    print(f"  Merged: {len(merged)} unique keyframes")

    # Count by reason
    reason_counts = {}
    for kf in merged:
        for r in kf.get("reasons", []):
            reason_counts[r] = reason_counts.get(r, 0) + 1

    # What each method found exclusively
    smart_only = [kf for kf in merged if kf["method"] == "smart"]
    brute_only = [kf for kf in merged if kf["method"] == "brute"]
    both = [kf for kf in merged if kf["method"] == "both"]
    print(f"  Smart only: {len(smart_only)}, Brute only: {len(brute_only)}, Both: {len(both)}")
    if reason_counts:
        top = sorted(reason_counts.items(), key=lambda x: -x[1])[:10]
        print(f"  Top reasons: {', '.join(f'{k}:{v}' for k,v in top)}")

    # Extract frame images
    extract_frame_images(video_path, merged, output_dir)

    # Save keyframes CSV
    csv_path = os.path.join(output_dir, "keyframes.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_idx", "method", "reasons", "speed", "accel_x",
                          "gyro_z", "encoder", "file"])
        for kf in merged:
            writer.writerow([
                kf.get("frame_idx", -1),
                kf.get("method", ""),
                "|".join(kf.get("reasons", [])),
                kf.get("speed", ""),
                kf.get("accel_x", ""),
                kf.get("gyro_z", ""),
                kf.get("encoder", ""),
                kf.get("file", ""),
            ])

    # Save summary
    summary = {
        "session": sess_name,
        "total_frames": total_frames,
        "keyframes": len(merged),
        "smart_only": len(smart_only),
        "brute_only": len(brute_only),
        "both": len(both),
        "reasons": reason_counts,
        "extraction_rate": round(len(merged) / max(total_frames, 1) * 100, 2),
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Asmile Keyframe Extractor")
    parser.add_argument("--session", help="Single session directory name")
    parser.add_argument("--all", action="store_true", help="Process all sessions")
    parser.add_argument("--brute-step", type=int, default=5,
                        help="Brute scan every N frames (default: 5)")
    args = parser.parse_args()

    if args.session:
        sess_dir = os.path.join(BASE_DIR, args.session)
        process_session(sess_dir, args.brute_step)
    elif args.all:
        sessions = sorted([d for d in os.listdir(BASE_DIR)
                           if d.startswith("session_") and
                           os.path.isdir(os.path.join(BASE_DIR, d))])
        all_summaries = []
        for sess in sessions:
            summary = process_session(os.path.join(BASE_DIR, sess), args.brute_step)
            if summary:
                all_summaries.append(summary)

        # Global summary
        if all_summaries:
            total_kf = sum(s["keyframes"] for s in all_summaries)
            total_frames = sum(s["total_frames"] for s in all_summaries)
            global_reasons = {}
            for s in all_summaries:
                for k, v in s["reasons"].items():
                    global_reasons[k] = global_reasons.get(k, 0) + v

            print(f"\n{'=' * 60}")
            print(f"TOTALE: {total_kf} keyframes da {total_frames} frame "
                  f"({total_kf / max(total_frames, 1) * 100:.1f}%)")
            print(f"{'=' * 60}")
            print(f"Smart only: {sum(s['smart_only'] for s in all_summaries)}")
            print(f"Brute only: {sum(s['brute_only'] for s in all_summaries)}")
            print(f"Both:       {sum(s['both'] for s in all_summaries)}")
            print(f"\nRagioni globali:")
            for k, v in sorted(global_reasons.items(), key=lambda x: -x[1]):
                print(f"  {k}: {v}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
