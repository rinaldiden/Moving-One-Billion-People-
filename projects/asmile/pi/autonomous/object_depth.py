#!/usr/bin/env python3
"""
Asmile Object Depth — estimate distance to every detected object from bbox size.

No stereo matching needed. Uses YOLO detection + known object sizes + camera focal length.

Formula: distance = (real_height × focal_length) / bbox_height_pixels

Known object heights (meters):
  person: 1.70, car: 1.50, truck: 2.80, bus: 3.00, bicycle: 1.10,
  motorcycle: 1.20, dog: 0.50, cat: 0.30, stop sign: 0.75,
  traffic light: 0.60, bench: 0.80

Ground plane model for road/wall/sidewalk:
  cam_height = 0.77m, every pixel row maps to a distance on the ground.

Usage:
  # On a video
  python3 object_depth.py --video session/video.mp4

  # On a single frame
  python3 object_depth.py --frame image.png

  # As module
  from object_depth import ObjectDepthEstimator
  ode = ObjectDepthEstimator()
  objects = ode.process_frame(frame)
"""

import cv2
import numpy as np
import os
import sys
import argparse
import json
from datetime import datetime

# Camera parameters (Arducam Camarray OV9281 @ 1280x800 per cam)
FOCAL_PX = 887.0       # from checkerboard calibration
CAM_HEIGHT_M = 0.77    # camera height from ground
CAM_WIDTH_PX = 1280
CAM_HEIGHT_PX = 800
CAM_TILT_DEG = 0       # 0 = looking straight ahead

# Known object heights in meters
OBJECT_HEIGHTS = {
    "person": 1.70,
    "bicycle": 1.10,
    "car": 1.50,
    "motorcycle": 1.20,
    "bus": 3.00,
    "truck": 2.80,
    "dog": 0.50,
    "cat": 0.30,
    "horse": 1.60,
    "cow": 1.40,
    "sheep": 0.80,
    "stop sign": 0.75,
    "traffic light": 0.60,
    "fire hydrant": 0.50,
    "bench": 0.80,
    "chair": 0.90,
    "backpack": 0.50,
    "umbrella": 1.00,
    "suitcase": 0.60,
}

# Known object widths (used when object is wider than tall, e.g. car from side)
OBJECT_WIDTHS = {
    "car": 4.20,
    "truck": 6.00,
    "bus": 10.00,
    "bicycle": 1.80,
    "motorcycle": 2.00,
    "bench": 1.50,
}

# Asmile bike dimensions
ASMILE_WIDTH_M = 1.10


class ObjectDepthEstimator:
    def __init__(self, focal_px=FOCAL_PX, cam_height_m=CAM_HEIGHT_M):
        self.focal = focal_px
        self.cam_height = cam_height_m
        self.yolo = None

    def _load_yolo(self):
        if self.yolo is None:
            from ultralytics import YOLO
            self.yolo = YOLO("yolov8m-seg.pt")

    def estimate_distance(self, name, bbox_h, bbox_w):
        """Estimate distance from object name and bbox dimensions."""
        distance = None
        method = None

        # Try height first (more reliable for people, poles, signs)
        if name in OBJECT_HEIGHTS and bbox_h > 20:
            real_h = OBJECT_HEIGHTS[name]
            distance = (real_h * self.focal) / bbox_h
            method = "height"

        # If object is much wider than tall (car from side), use width
        if name in OBJECT_WIDTHS and bbox_w > bbox_h * 1.5:
            real_w = OBJECT_WIDTHS[name]
            dist_w = (real_w * self.focal) / bbox_w
            if distance is None or dist_w < distance:
                distance = dist_w
                method = "width"

        # Ground plane fallback: where does bottom of bbox touch ground?
        if distance is None and bbox_h > 10:
            # Bottom of bbox y-coordinate relative to image center
            # Higher y = closer to camera on ground plane
            # This is approximate but works for unknown objects
            distance = self.ground_plane_distance(bbox_h)
            method = "ground"

        return distance, method

    def ground_plane_distance(self, bbox_bottom_y):
        """Estimate distance from ground plane model.
        Bottom of frame = close, middle = far."""
        # Pixel below horizon corresponds to ground distance
        # d = cam_height * focal / (y - cy)
        cy = CAM_HEIGHT_PX / 2
        y_below = bbox_bottom_y - cy
        if y_below > 10:
            return (self.cam_height * self.focal) / y_below
        return None

    def process_frame(self, frame, conf_threshold=0.25):
        """Detect all objects and estimate distance for each.

        Returns list of dicts: {name, confidence, distance_m, method, bbox, zone}
        """
        self._load_yolo()

        results = self.yolo(frame, verbose=False, conf=conf_threshold)
        r = results[0]

        objects = []
        if r.boxes is None:
            return objects

        h, w = frame.shape[:2]

        for i, box in enumerate(r.boxes):
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            name = self.yolo.names[cls_id]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

            bbox_h = y2 - y1
            bbox_w = x2 - x1
            cx = (x1 + x2) / 2

            # Estimate distance
            dist, method = self.estimate_distance(name, bbox_h, bbox_w)

            # Zone: left / center / right
            if cx < w * 0.33:
                zone = "left"
            elif cx > w * 0.66:
                zone = "right"
            else:
                zone = "center"

            # Danger assessment
            danger = "safe"
            if dist is not None:
                if dist < 1.5 and zone == "center":
                    danger = "emergency"
                elif dist < 3.0 and zone == "center":
                    danger = "brake"
                elif dist < 5.0:
                    danger = "caution"

            # Lateral margin (how much space between object and bike)
            lateral_offset_px = abs(cx - w / 2)
            lateral_offset_m = (lateral_offset_px / self.focal) * (dist if dist else 5.0)
            margin_m = lateral_offset_m - ASMILE_WIDTH_M / 2

            obj = {
                "name": name,
                "confidence": round(conf, 2),
                "distance_m": round(dist, 2) if dist else None,
                "method": method,
                "bbox": (int(x1), int(y1), int(x2), int(y2)),
                "bbox_h": bbox_h,
                "bbox_w": bbox_w,
                "zone": zone,
                "danger": danger,
                "lateral_margin_m": round(margin_m, 2) if dist else None,
            }
            objects.append(obj)

        # Sort by distance (closest first)
        objects.sort(key=lambda o: o["distance_m"] if o["distance_m"] else 999)

        return objects

    def annotate_frame(self, frame, objects):
        """Draw detections with distances on frame."""
        display = frame.copy()
        if len(display.shape) == 2:
            display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)

        danger_colors = {
            "emergency": (0, 0, 255),    # red
            "brake": (0, 128, 255),      # orange
            "caution": (0, 255, 255),    # yellow
            "safe": (0, 255, 0),         # green
        }

        for obj in objects:
            x1, y1, x2, y2 = obj["bbox"]
            color = danger_colors.get(obj["danger"], (200, 200, 200))

            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

            dist_str = f"{obj['distance_m']:.1f}m" if obj['distance_m'] else "?"
            label = f"{obj['name']} {obj['confidence']*100:.0f}% {dist_str}"

            cv2.putText(display, label, (x1, y1 - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            if obj["danger"] in ("emergency", "brake"):
                cv2.putText(display, obj["danger"].upper(), (x1, y2 + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return display


def process_video(video_path, output_path=None, max_frames=300):
    """Process video: detect objects, estimate depth, create annotated video."""
    ode = ObjectDepthEstimator()

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total // max_frames)
    fps = 15

    print(f"Video: {total} frames, processing every {step}")

    all_frames = []
    all_objects = []

    for fi in range(0, total, step):
        if len(all_frames) >= max_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue

        # Use left camera
        left = frame[:, :frame.shape[1] // 2]
        if left.mean() < 30:
            continue

        objects = ode.process_frame(left)
        display = ode.annotate_frame(left, objects)

        all_objects.extend([{**o, "frame": fi} for o in objects])
        all_frames.append(display)

        if len(all_frames) % 50 == 0:
            print(f"  [{len(all_frames)}/{max_frames}] frame {fi}, {len(objects)} objects")

    cap.release()

    # Save video
    if all_frames and output_path:
        h, w = all_frames[0].shape[:2]
        vw = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for f in all_frames:
            vw.write(f)
        vw.release()
        print(f"Saved: {output_path} ({len(all_frames)} frames)")

    # Stats
    if all_objects:
        print(f"\nObjects detected: {len(all_objects)}")
        names = {}
        for o in all_objects:
            names[o["name"]] = names.get(o["name"], 0) + 1
        for n, c in sorted(names.items(), key=lambda x: -x[1]):
            dists = [o["distance_m"] for o in all_objects if o["name"] == n and o["distance_m"]]
            avg_d = f"{np.mean(dists):.1f}m" if dists else "?"
            print(f"  {n}: {c} detections, avg distance {avg_d}")

        emergencies = [o for o in all_objects if o["danger"] == "emergency"]
        brakes = [o for o in all_objects if o["danger"] == "brake"]
        print(f"\nDanger events: {len(emergencies)} emergency, {len(brakes)} brake")

    return all_objects


def main():
    parser = argparse.ArgumentParser(description="Asmile Object Depth Estimation")
    parser.add_argument("--video", help="Video file to process")
    parser.add_argument("--frame", help="Single frame to process")
    parser.add_argument("--output", help="Output video path")
    parser.add_argument("--max-frames", type=int, default=300)
    args = parser.parse_args()

    if args.video:
        out = args.output or args.video.replace(".mp4", "_depth.mp4")
        process_video(args.video, out, args.max_frames)
    elif args.frame:
        ode = ObjectDepthEstimator()
        frame = cv2.imread(args.frame)
        objects = ode.process_frame(frame)
        for o in objects:
            print(f"{o['name']} {o['confidence']*100:.0f}%: {o['distance_m']}m ({o['zone']}, {o['danger']})")
        display = ode.annotate_frame(frame, objects)
        cv2.imwrite(args.frame.replace(".png", "_depth.png"), display)


if __name__ == "__main__":
    main()
