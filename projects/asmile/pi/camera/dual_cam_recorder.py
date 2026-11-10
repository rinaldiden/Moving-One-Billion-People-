#!/usr/bin/env python3
"""
Asmile Dual Camera Recorder — two separate OV9281 (Inno-Maker) without HAT.

Software-synchronized stereo recording from CAM0 and CAM1 on Raspberry Pi 5.
Outputs side-by-side frames matching the Arducam Camarray format for
compatibility with existing training pipeline.

Synchronization (2026-11-07):
  - rpicam-apps sync nativo del Pi 5: cam1 = --sync client (parte prima), cam0 = --sync server.
    libcamera allinea i frame delle due OV9281 (verificato su #001: "Sync achieved! Difference
    -18us"), la registrazione parte al punto di sync (~5-7 s dopo l'avvio).
    Prima c'era solo una barriera sull'AVVIO dei processi: poi ogni sensore andava col suo
    orologio (10 frame di deriva su 7 min) → stereo falsato in movimento.
  - --save-pts per camera (pts_left.txt / pts_right.txt) → verifica coppie a posteriori.
  - OV9281 global shutter = no rolling shutter artifacts
  - Upgrade possibile: trigger hardware FSIN (J3 EXT TRIG Inno-Maker + dtoverlay trigger-mode=1),
    vedi docs/ov9281_hardware_sync.md

Usage:
  python3 dual_cam_recorder.py                    # record indefinitely
  python3 dual_cam_recorder.py --duration 60      # record 60 minutes
  python3 dual_cam_recorder.py --preview           # show live preview
  Ctrl+C to stop

Output:
  ~/training_sessions/session_YYYYMMDD_HHMMSS/
    video_left.h264      — cam0 raw  (⚠ su #001 è fisicamente la camera DESTRA, calib order=RL)
    video_right.h264     — cam1 raw
    pts_left.txt / pts_right.txt — timestamp per frame (timecode v2, ms dal punto di sync)
    cam_left.log / cam_right.log — log rpicam (contiene "Sync achieved! Difference …us")
    frames_left.csv / frames_right.csv — istante VERO di ogni frame (SensorTimestamp) in t_ms,
                   lo stesso orologio del CSV unico del sensor_hub → frame↔sensori al ms (2026-11-07)
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame_times import FrameTimeWriter, metadata_args  # noqa: E402

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
SESSIONS_DIR = Path.home() / "training_sessions"

# Camera settings (match Arducam Camarray output)
CAM_WIDTH = 1280
CAM_HEIGHT = 800
FPS = 15
BITRATE = 500_000  # 500kbps per camera (guida normale)
# Calibrazione: a 500 kbps i corner ChArUco si spostano ~0.3 px (RMS mono 0.55 > gate 0.5, sessione 2026-11-10)
BITRATE_CALIB = 6_000_000

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
        self._frame_writers = {}

    def _create_session(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = SESSIONS_DIR / f"session_{ts}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def _start_camera(self, cam_id, output_path, sync_role, pts_path, log_path):
        """Start rpicam-vid for one camera (sync_role: 'server' | 'client')."""
        cmd = [
            "rpicam-vid",
            "--camera", str(cam_id),
            "--width", str(CAM_WIDTH),
            "--height", str(CAM_HEIGHT),
            "--framerate", str(FPS),
            "--bitrate", str(BITRATE),
            "--codec", "h264",
            "--profile", "baseline",
            "--timeout", str(self.duration_min * 60 * 1000 if self.duration_min else 0),
            "--nopreview",
            "--sync", sync_role,
            "--save-pts", str(pts_path),
            "-o", str(output_path),
        ]

        if VFLIP:
            cmd.append("--vflip")
        if HFLIP:
            cmd.append("--hflip")
        meta_args = metadata_args()                # [] se questo rpicam-vid non ha --metadata
        cmd += meta_args

        log = open(log_path, "w")                  # su file: una PIPE mai letta si riempie e blocca rpicam
        if not meta_args:
            return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log)   # stdout = metadati per frame
        name = "left" if cam_id == 0 else "right"
        w = FrameTimeWriter(proc.stdout, self.session_dir / f"frames_{name}.csv")
        w.start()                                  # svuota SEMPRE la pipe
        self._frame_writers[name] = w
        return proc

    def _start_combined_recording(self):
        """Record both cameras frame-synchronized via rpicam --sync (client first, then server)."""
        d = self.session_dir
        self._procs = {
            "right": self._start_camera(1, d / "video_right.h264", "client",
                                        d / "pts_right.txt", d / "cam_right.log"),
        }
        time.sleep(1.5)                                 # il client deve essere in ascolto prima del server
        self._procs["left"] = self._start_camera(0, d / "video_left.h264", "server",
                                                 d / "pts_left.txt", d / "cam_left.log")
        self._start_time = time.monotonic()
        print(f"[CAM0] server → {d / 'video_left.h264'}")
        print(f"[CAM1] client → {d / 'video_right.h264'}")
        print("[SYNC] rpicam --sync attivo: la registrazione parte al punto di sync (vedi cam_*.log)")

    def _sync_result(self):
        """Dai log rpicam: differenza di sync (µs) e ISTANTE del sync (uptime s, orologio dei log
        libcamera) = istante del frame 0 nei pts."""
        out = {}
        for name in ("left", "right"):
            p = self.session_dir / f"cam_{name}.log"
            if p.exists():
                for line in p.read_text(errors="ignore").splitlines():
                    if "Sync achieved" in line:
                        out[name] = line.split("Difference")[-1].strip()
                        try:                                  # "[0:31:31.468847157] ..." → secondi
                            h, m, sec = line[1:line.index("]")].split(":")
                            out[f"{name}_sync_uptime_s"] = int(h) * 3600 + int(m) * 60 + float(sec)
                        except ValueError:
                            pass
        return out

    @staticmethod
    def _clock_map():
        """Legame orologio di sistema ↔ uptime (CLOCK_BOOTTIME e MONOTONIC), per portare i pts
        video sull'ora dei CSV sensori:  t_wall(frame i) = sync_uptime_s + pts_i/1000 + offset."""
        wall = time.time()
        return {"wall_minus_boottime_s": wall - time.clock_gettime(time.CLOCK_BOOTTIME),
                "wall_minus_monotonic_s": wall - time.monotonic()}

    def _save_metadata(self):
        meta = {
            "session_dir": str(self.session_dir),
            "start_time": datetime.now().isoformat(),
            "camera_type": "dual_innomaker_ov9281",
            "sync_method": "rpicam_sync_server_client",
            "resolution": f"{CAM_WIDTH}x{CAM_HEIGHT}",
            "fps": FPS,
            "bitrate": BITRATE,
            "vflip": VFLIP,
            "hflip": HFLIP,
            "clock_map_start": self._clock_map(),
            "cam0": "video_left (fisicamente DESTRA su #001, calib order=RL)",
            "cam1": "video_right (fisicamente SINISTRA su #001)",
            "note": "Two separate OV9281 cameras, frame-synced by libcamera (rpicam --sync, "
                    "cam0 server / cam1 client). Per-frame pts in pts_left/right.txt.",
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
            meta["sync_achieved"] = self._sync_result()   # es. {"left": "0us", "right": "-18us", ...}
            meta["clock_map_end"] = self._clock_map()
            meta["frame_times"] = {                    # controllo dominio orologio: rx-sensore ~ 10-80 ms
                n: {"frames": w.frames, "first_rx_minus_sensor_ms": w.first_rx_minus_sensor_ms}
                for n, w in self._frame_writers.items()} or "rpicam-vid senza --metadata"
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
    parser.add_argument("--calib", action="store_true",
                        help=f"sessione di calibrazione: bitrate {BITRATE_CALIB // 1_000_000} Mbps per camera")
    parser.add_argument("--bitrate", type=int, default=None, help="bitrate per camera in bit/s")
    args = parser.parse_args()

    global BITRATE
    if args.bitrate:
        BITRATE = args.bitrate
    elif args.calib:
        BITRATE = BITRATE_CALIB

    recorder = DualCamRecorder(duration_min=args.duration, preview=args.preview)

    signal.signal(signal.SIGTERM, lambda s, f: recorder.stop())

    recorder.start()


if __name__ == "__main__":
    main()
