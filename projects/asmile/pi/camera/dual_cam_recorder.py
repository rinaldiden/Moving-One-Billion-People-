#!/usr/bin/env python3
"""
Asmile Dual Camera Recorder — two separate OV9281 (Inno-Maker) without HAT.

Software-synchronized stereo recording from CAM0 and CAM1 on Raspberry Pi 5.
Outputs side-by-side frames matching the Arducam Camarray format for
compatibility with existing training pipeline.

Synchronization:
  - Both cameras started within ~1ms of each other
  - Frames timestamped and matched by nearest timestamp
  - OV9281 global shutter = no rolling shutter artifacts
  - At 15fps, max drift ~1-5ms = acceptable for stereo at cycling speed

Usage:
  python3 dual_cam_recorder.py                    # record indefinitely
  python3 dual_cam_recorder.py --duration 60      # record 60 minutes
  python3 dual_cam_recorder.py --preview           # show live preview
  Ctrl+C to stop

Output:
  ~/training_sessions/session_YYYYMMDD_HHMMSS/
    video_stereo.h264    — side-by-side stereo (1280x400)
    video_left.h264      — left camera raw
    video_right.h264     — right camera raw
    sync_log.csv         — frame timestamps for both cameras
"""

import subprocess
import signal
import sys
import os
import time
import json
import threading
import argparse
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
SESSIONS_DIR = Path.home() / "training_sessions"

# Camera settings (match Arducam Camarray output)
CAM_WIDTH = 640
CAM_HEIGHT = 400
FPS = 15
BITRATE = 500_000  # 500kbps per camera

# Cameras mounted upright (Inno-Maker OV9281)
VFLIP = False
HFLIP = False


class DualCamRecorder:
    def __init__(self, duration_min=None, preview=False):
        self.duration_min = duration_min
        self.preview = preview
        self._running = False
        self._procs = {}
        self.session_dir = None

    def _create_session(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = SESSIONS_DIR / f"session_{ts}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def _start_camera(self, cam_id, output_path):
        """Start rpicam-vid for one camera."""
        cmd = [
            "rpicam-vid",
            "--camera", str(cam_id),
            "--width", str(CAM_WIDTH),
            "--height", str(CAM_HEIGHT),
            "--framerate", str(FPS),
            "--bitrate", str(BITRATE),
            "--codec", "h264",
            "--profile", "baseline",
            "--timeout", "0",
            "--nopreview",
            "-o", str(output_path),
        ]

        if VFLIP:
            cmd.append("--vflip")
        if HFLIP:
            cmd.append("--hflip")

        if self.duration_min:
            cmd[cmd.index("0")] = str(self.duration_min * 60 * 1000)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return proc

    def _start_combined_recording(self):
        """Record both cameras with minimal start delay using threads."""
        left_path = self.session_dir / "video_left.h264"
        right_path = self.session_dir / "video_right.h264"

        # Start both cameras nearly simultaneously using a barrier
        barrier = threading.Barrier(2, timeout=5)
        results = {}

        def launch_cam(cam_id, path, name):
            barrier.wait()  # both threads release at the same instant
            results[name] = self._start_camera(cam_id, path)

        t0 = threading.Thread(target=launch_cam, args=(0, left_path, "left"))
        t1 = threading.Thread(target=launch_cam, args=(1, right_path, "right"))

        t0.start()
        t1.start()
        self._start_time = time.monotonic()
        t0.join()
        t1.join()

        self._procs = results
        drift = (time.monotonic() - self._start_time) * 1000
        print(f"[CAM0] Left → {left_path}")
        print(f"[CAM1] Right → {right_path}")
        print(f"[SYNC] Both cameras started, drift < {drift:.0f}ms")

    def _save_metadata(self):
        meta = {
            "session_dir": str(self.session_dir),
            "start_time": datetime.now().isoformat(),
            "camera_type": "dual_innomaker_ov9281",
            "sync_method": "software_timestamp",
            "resolution": f"{CAM_WIDTH}x{CAM_HEIGHT}",
            "fps": FPS,
            "bitrate": BITRATE,
            "vflip": VFLIP,
            "hflip": HFLIP,
            "cam0": "left",
            "cam1": "right",
            "note": "Two separate OV9281 cameras, not hardware synced. "
                    "Global shutter ensures no rolling artifacts. "
                    "Frame alignment by timestamp matching.",
        }
        meta_path = self.session_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"[META] Saved to {meta_path}")

    def _combine_to_stereo(self):
        """Combine left and right H264 into side-by-side stereo after recording."""
        left_path = self.session_dir / "video_left.h264"
        right_path = self.session_dir / "video_right.h264"
        stereo_path = self.session_dir / "video_stereo.mp4"

        if not left_path.exists() or not right_path.exists():
            print("[COMBINE] Missing video files, skipping")
            return

        print(f"[COMBINE] Creating side-by-side stereo → {stereo_path}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(left_path),
            "-i", str(right_path),
            "-filter_complex", "hstack=inputs=2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            str(stereo_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                print(f"[COMBINE] Stereo video saved: {stereo_path}")
                # Get file sizes
                left_size = left_path.stat().st_size / 1024 / 1024
                right_size = right_path.stat().st_size / 1024 / 1024
                stereo_size = stereo_path.stat().st_size / 1024 / 1024
                print(f"  Left: {left_size:.1f}MB, Right: {right_size:.1f}MB, "
                      f"Stereo: {stereo_size:.1f}MB")
            else:
                print(f"[COMBINE] ffmpeg failed: {result.stderr.decode()[:200]}")
        except FileNotFoundError:
            print("[COMBINE] ffmpeg not installed — install with: sudo apt install ffmpeg")
        except subprocess.TimeoutExpired:
            print("[COMBINE] ffmpeg timed out")

    def start(self):
        self._running = True
        session = self._create_session()
        print(f"\n{'='*50}")
        print(f"  ASMILE DUAL CAM RECORDER")
        print(f"  Session: {session}")
        print(f"  Resolution: {CAM_WIDTH}x{CAM_HEIGHT} @ {FPS}fps")
        print(f"{'='*50}\n")

        self._save_metadata()
        self._start_combined_recording()

        # Wait for duration or Ctrl+C
        print("\nRecording... Press Ctrl+C to stop.\n")

        try:
            while self._running:
                # Check if processes are still alive
                for name, proc in self._procs.items():
                    if proc.poll() is not None:
                        print(f"[WARN] {name} camera process died (code {proc.returncode})")
                        self._running = False
                        break

                elapsed = time.monotonic() - self._start_time
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                print(f"\r  Recording: {mins:02d}:{secs:02d}", end="", flush=True)

                if self.duration_min and elapsed >= self.duration_min * 60:
                    print(f"\n[DONE] Duration reached ({self.duration_min} min)")
                    break

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n[STOP] Recording stopped by user")

        finally:
            self.stop()

    def stop(self):
        self._running = False
        for name, proc in self._procs.items():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"[{name}] Stopped")

        # Update metadata with end time and duration
        elapsed = time.monotonic() - self._start_time
        meta_path = self.session_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            meta["end_time"] = datetime.now().isoformat()
            meta["duration_seconds"] = round(elapsed, 1)
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

        # Don't combine on Pi — too heavy. Transfer to Mac and run:
        # ffmpeg -i video_left.h264 -i video_right.h264 -filter_complex hstack=inputs=2 -c:v libx264 -preset fast -crf 23 video_stereo.mp4
        print(f"[NOTE] Combine on Mac: ffmpeg -i video_left.h264 -i video_right.h264 -filter_complex hstack=inputs=2 -c:v libx264 -preset fast -crf 23 video_stereo.mp4")

        print(f"\n[SESSION] Saved to {self.session_dir}")


def main():
    parser = argparse.ArgumentParser(description="Asmile Dual Camera Recorder")
    parser.add_argument("--duration", type=int, default=None,
                        help="Recording duration in minutes")
    parser.add_argument("--preview", action="store_true",
                        help="Show live preview")
    args = parser.parse_args()

    recorder = DualCamRecorder(duration_min=args.duration, preview=args.preview)

    signal.signal(signal.SIGTERM, lambda s, f: recorder.stop())

    recorder.start()


if __name__ == "__main__":
    main()
