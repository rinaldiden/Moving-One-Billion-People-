#!/usr/bin/env python3
"""
Asmile Vision Safety Check — camera-based obstacle detection.

Runs alongside speed_limiter during rides. Captures frames from the camera,
detects obstacles and road boundaries using simple CV (no YOLO on Pi).
Logs danger events. Can trigger emergency brake via flag file.

This is a SHADOW MODE tool: it observes and logs, optionally brakes.
The main navigation is GPS+IMU. Vision is a safety overlay.

Detection methods (lightweight, runs on Pi):
1. Motion/change detection: large changes between frames = something appeared
2. Bottom-half obstacle: dark/different blob in lower center = close obstacle
3. Road boundary: where road ends (edge detection) = lateral safety

Usage:
  python3 vision_safety.py                    # shadow mode (log only)
  python3 vision_safety.py --active           # can trigger brake
  python3 vision_safety.py --video file.mp4   # offline analysis
"""

import os
import sys
import time
import csv
import signal
import argparse
import numpy as np
import cv2
from datetime import datetime

running = True

def signal_handler(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Config
CHECK_HZ = 3           # frames per second to analyze
FRAME_W = 640           # resize for fast processing
FRAME_H = 400
OBSTACLE_ZONE_TOP = 0.4      # top 40% = sky/far, ignore
OBSTACLE_ZONE_CENTER_L = 0.3  # center band left
OBSTACLE_ZONE_CENTER_R = 0.7  # center band right
MOTION_THRESHOLD = 30         # pixel diff threshold
OBSTACLE_AREA_MIN = 0.05      # min fraction of zone to count as obstacle
BRAKE_AREA_THRESHOLD = 0.15   # fraction of center zone → trigger brake
EMERGENCY_BRAKE_FILE = "/tmp/emergency_brake"


class VisionSafety:
    def __init__(self, active=False, video_path=None):
        self.active = active  # if True, can write brake flag
        self.video_path = video_path
        self.prev_frame = None
        self.cap = None

        # Log
        log_dir = os.path.expanduser("~/wip/logging/vision_safety")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(log_dir, f"vision_{ts}.csv")
        self.log_file = open(self.log_path, "w", newline="")
        self.writer = csv.writer(self.log_file)
        self.writer.writerow([
            "timestamp", "motion_pct", "obstacle_pct",
            "road_left_px", "road_right_px", "road_width_px",
            "danger", "action"
        ])

        self.frame_count = 0
        self.danger_count = 0

    def _open_camera(self):
        """Open camera or video file."""
        if self.video_path:
            self.cap = cv2.VideoCapture(self.video_path)
            return self.cap.isOpened()

        # Try rpicam via v4l2
        for dev in ["/dev/video0", "/dev/video1"]:
            cap = cv2.VideoCapture(dev)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)
                self.cap = cap
                return True
            cap.release()

        # Try libcamera
        cap = cv2.VideoCapture(
            "libcamerasrc ! video/x-raw,width=1280,height=800,framerate=5/1 ! "
            "videoconvert ! appsink", cv2.CAP_GSTREAMER)
        if cap.isOpened():
            self.cap = cap
            return True

        return False

    def _grab_frame(self):
        """Grab a frame, return left camera grayscale resized."""
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        # Left camera (first half of stereo)
        w = frame.shape[1]
        left = frame[:, :w // 2] if w > 1000 else frame
        gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left
        resized = cv2.resize(gray, (FRAME_W, FRAME_H))
        return resized

    def _detect_motion(self, frame):
        """Detect motion between current and previous frame.
        Returns fraction of pixels that changed significantly."""
        if self.prev_frame is None:
            return 0.0
        diff = cv2.absdiff(frame, self.prev_frame)
        motion_mask = (diff > MOTION_THRESHOLD).astype(np.uint8)
        # Focus on lower half (road area)
        lower = motion_mask[int(FRAME_H * OBSTACLE_ZONE_TOP):, :]
        return lower.sum() / lower.size

    def _detect_obstacle_center(self, frame):
        """Detect objects in center-bottom using frame differencing.
        Only counts CHANGES from previous frame — static bike parts ignored."""
        if self.prev_frame is None:
            return 0.0

        # Center-bottom zone (exclude right 30% = own bike)
        y_top = int(FRAME_H * 0.5)  # bottom half only
        x_left = int(FRAME_W * 0.15)
        x_right = int(FRAME_W * 0.65)  # exclude right side (own bike)
        zone_curr = frame[y_top:, x_left:x_right]
        zone_prev = self.prev_frame[y_top:, x_left:x_right]

        # Difference = new objects appearing
        diff = cv2.absdiff(zone_curr, zone_prev)
        _, thresh = cv2.threshold(diff, 40, 255, cv2.THRESH_BINARY)

        # Morphology to remove noise
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.dilate(thresh, kernel, iterations=1)

        return thresh.sum() / (thresh.size * 255)

    def _detect_road_boundaries(self, frame):
        """Detect road edges in bottom portion of frame.
        Returns (left_boundary_px, right_boundary_px, road_width)."""
        # Bottom 30% of frame
        bottom = frame[int(FRAME_H * 0.7):, :]

        # Edge detection
        edges = cv2.Canny(bottom, 30, 100)

        # Find leftmost and rightmost edges in each row, take median
        left_edges = []
        right_edges = []
        for row in range(edges.shape[0]):
            cols = np.where(edges[row] > 0)[0]
            if len(cols) > 2:
                left_edges.append(cols[0])
                right_edges.append(cols[-1])

        if left_edges and right_edges:
            left = int(np.median(left_edges))
            right = int(np.median(right_edges))
            return left, right, right - left
        return 0, FRAME_W, FRAME_W

    def step(self):
        """Analyze one frame. Returns danger level."""
        frame = self._grab_frame()
        if frame is None:
            return "no_frame"

        self.frame_count += 1

        # Detect
        motion_pct = self._detect_motion(frame)
        obstacle_pct = self._detect_obstacle_center(frame)
        road_left, road_right, road_width = self._detect_road_boundaries(frame)

        self.prev_frame = frame

        # Assess danger
        danger = "safe"
        action = "none"

        if obstacle_pct > BRAKE_AREA_THRESHOLD:
            danger = "brake"
            action = "brake_recommended"
            self.danger_count += 1
            if self.active:
                with open(EMERGENCY_BRAKE_FILE, "w") as f:
                    f.write("40")
                action = "BRAKE_SENT"
        elif obstacle_pct > OBSTACLE_AREA_MIN:
            danger = "caution"
        elif motion_pct > 0.3:
            danger = "motion"

        # Release brake if danger passed
        if danger == "safe" and self.active:
            try:
                os.remove(EMERGENCY_BRAKE_FILE)
            except FileNotFoundError:
                pass

        # Log
        ts = datetime.now().isoformat(timespec="milliseconds")
        self.writer.writerow([
            ts, f"{motion_pct:.3f}", f"{obstacle_pct:.3f}",
            road_left, road_right, road_width,
            danger, action
        ])
        self.log_file.flush()

        return danger

    def run(self):
        global running

        print(f"{'='*50}")
        print(f"  ASMILE VISION SAFETY")
        print(f"{'='*50}")
        print(f"Mode: {'ACTIVE (can brake)' if self.active else 'SHADOW (log only)'}")
        print(f"Log: {self.log_path}")

        if not self._open_camera():
            print("WARNING: Cannot open camera — running without vision")
            # Still run loop for logging
            while running:
                time.sleep(1.0 / CHECK_HZ)
            return

        print(f"Camera opened, analyzing at {CHECK_HZ} fps")
        print(f"Ctrl+C to stop\n")

        while running:
            danger = self.step()
            if danger in ("brake", "motion"):
                print(f"\r  DANGER: {danger} (frame {self.frame_count})", end="", flush=True)
            time.sleep(1.0 / CHECK_HZ)

        if self.cap:
            self.cap.release()
        self.log_file.close()

        print(f"\n\nVision safety stopped.")
        print(f"Frames: {self.frame_count}, Danger events: {self.danger_count}")
        print(f"Log: {self.log_path}")


def offline_analysis(video_path):
    """Analyze a recorded video offline."""
    vs = VisionSafety(active=False, video_path=video_path)
    if not vs._open_camera():
        print(f"Cannot open {video_path}")
        return

    print(f"Analyzing {video_path}...")
    dangers = {"safe": 0, "caution": 0, "brake": 0, "motion": 0}

    while True:
        danger = vs.step()
        if danger == "no_frame":
            break
        dangers[danger] = dangers.get(danger, 0) + 1

    vs.log_file.close()
    if vs.cap:
        vs.cap.release()

    print(f"\nResults:")
    print(f"  Frames: {vs.frame_count}")
    for d, c in sorted(dangers.items(), key=lambda x: -x[1]):
        print(f"  {d}: {c} ({c*100//max(vs.frame_count,1)}%)")
    print(f"Log: {vs.log_path}")


def main():
    parser = argparse.ArgumentParser(description="Asmile Vision Safety Check")
    parser.add_argument("--active", action="store_true",
                        help="Active mode: can trigger brake")
    parser.add_argument("--video", help="Offline analysis of video file")
    args = parser.parse_args()

    if args.video:
        offline_analysis(args.video)
    else:
        vs = VisionSafety(active=args.active)
        vs.run()


if __name__ == "__main__":
    main()
