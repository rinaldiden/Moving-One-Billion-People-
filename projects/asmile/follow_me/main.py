#!/usr/bin/env python3
"""
Asmile Follow-Me — Main Loop

State machine:
  IDLE → (button hold 2s) → ACQUIRING → (cone locked) → FOLLOWING → (lost/timeout) → IDLE

Usage:
  python3 main.py              # full mode (requires Pi hardware)
  python3 main.py --dry-run    # logs everything, does not actuate servo/brake

Logging:
  training_data/follow_me/YYYYMMDD_HHMMSS.csv
"""

import argparse
import lgpio
import logging
import numpy as np
import os
import sys
import time
from datetime import datetime
from enum import Enum, auto

# ═══════════════════════════════════════════════════════════
# Module imports
# ═══════════════════════════════════════════════════════════
from config_loader import load_config
from buzzer import Buzzer
from disparity import DisparityEngine
from cone_detector import ConeDetector
from tracker import Tracker
from safety_envelope import SafetyEnvelope
from control import FollowController
from gpio_handler import ButtonHandler, ButtonEvent


# ═══════════════════════════════════════════════════════════
# State machine
# ═══════════════════════════════════════════════════════════
class State(Enum):
    IDLE = auto()
    ACQUIRING = auto()
    FOLLOWING = auto()


# ═══════════════════════════════════════════════════════════
# Logging setup
# ═══════════════════════════════════════════════════════════
LOG_FORMAT = "[%(asctime)s] %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
log = logging.getLogger("follow_me")


def setup_csv_logger(base_dir: str) -> str:
    """Create CSV log directory and return the log file path."""
    log_dir = os.path.join(base_dir, "training_data", "follow_me")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(log_dir, f"{ts}.csv")
    with open(path, "w") as f:
        f.write("timestamp,state,target_d_m,target_cx,target_cy,confidence,"
                "brake_pct,steer_pct,zone,obstacle_min_m,fps\n")
    return path


def log_csv(path: str, state: str, target_d: float, cx: int, cy: int,
            conf: float, brake: float, steer: float, zone: str,
            obs_min: float, fps: float):
    """Append one row to the CSV log."""
    ts = datetime.now().isoformat(timespec="milliseconds")
    with open(path, "a") as f:
        f.write(f"{ts},{state},{target_d:.3f},{cx},{cy},{conf:.3f},"
                f"{brake:.1f},{steer:.1f},{zone},{obs_min:.2f},{fps:.1f}\n")


# ═══════════════════════════════════════════════════════════
# Camera
# ═══════════════════════════════════════════════════════════
def init_camera(cfg: dict):
    """Initialize picamera2 for stereo capture.

    Returns a Picamera2 instance configured for side-by-side frames.
    """
    from picamera2 import Picamera2

    cam = Picamera2()
    stereo = cfg["stereo"]
    cam_config = cam.create_still_configuration(
        main={"size": (stereo["frame_width"], stereo["frame_height"]),
              "format": "YUV420"},
    )
    cam.configure(cam_config)
    cam.start()
    time.sleep(1.0)  # let auto-exposure settle
    return cam


def grab_frame(cam) -> np.ndarray:
    """Capture a grayscale frame from picamera2.

    Returns side-by-side grayscale array (H, W) where W = 2 * camera_width.
    """
    # YUV420: Y plane is the first H rows of the full buffer
    yuv = cam.capture_array("main")
    # Y channel is grayscale
    if len(yuv.shape) == 3:
        gray = yuv[:, :, 0] if yuv.shape[2] >= 1 else yuv[:, :]
    else:
        gray = yuv
    return gray


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Asmile Follow-Me")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log everything but do not actuate servo/brake")
    parser.add_argument("--config", default=None,
                        help="Path to asmile_config.yaml")
    args = parser.parse_args()

    dry_run = args.dry_run

    # ── Load config ──
    cfg = load_config(args.config)
    fm_cfg = cfg["follow_me"]
    gpio_cfg = cfg["gpio"]

    log.info("=" * 50)
    log.info("  ASMILE FOLLOW-ME")
    log.info("=" * 50)

    if dry_run:
        log.warning("DRY-RUN MODE — no actuators will be driven")

    # ── PLACEHOLDER warnings ──
    asmile = cfg["asmile"]
    placeholders = []
    for key in ["larghezza_max_cm", "sporgenza_muso_cm",
                "altezza_cam_da_terra_cm", "distanza_frenata_cm"]:
        placeholders.append(f"  {key}: {asmile[key]}")
    log.warning("PLACEHOLDER values — measure on the real tricycle:")
    for p in placeholders:
        log.warning(p)

    # ── GPIO ──
    chip = gpio_cfg["gpio_chip"]
    h = lgpio.gpiochip_open(chip)
    log.info(f"GPIO chip {chip} opened")

    # ── Modules ──
    buzzer = Buzzer(h, cfg)
    button = ButtonHandler(h, cfg)
    disparity_engine = DisparityEngine(cfg)
    cone_det = ConeDetector(cfg)
    tracker = Tracker(cfg)
    controller = FollowController(cfg)
    safety = SafetyEnvelope(cfg)

    log.info(f"Buzzer on GPIO {gpio_cfg['buzzer_pin']}")
    log.info(f"Button on GPIO {gpio_cfg['button_pin']}")
    log.info(f"Stereo baseline: {disparity_engine.baseline_mm:.1f} mm")
    log.info(f"Stereo focal: {disparity_engine.focal_px:.1f} px")

    # ── Camera ──
    cam = None
    if not dry_run:
        try:
            cam = init_camera(cfg)
            log.info("Camera initialized")
        except Exception as e:
            log.error(f"Camera init failed: {e}")
            log.error("Run with --dry-run to test without camera")
            buzzer.cleanup()
            button.cleanup()
            lgpio.gpiochip_close(h)
            sys.exit(1)
    else:
        log.info("Camera skipped (dry-run)")

    # ── CSV log ──
    project_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), ".."))
    csv_path = setup_csv_logger(project_dir)
    log.info(f"Logging to {csv_path}")

    # ── State machine ──
    state = State.IDLE
    acq_start_time = 0.0
    acq_frame_count = 0
    acq_best = None
    session_start = 0.0
    frame_count = 0
    fps_timer = time.monotonic()

    buzzer.ready()
    log.info("System ready. Hold button for 2s to start acquisition.")

    try:
        while True:
            loop_start = time.monotonic()

            # ── Button events ──
            ev = button.poll_event()

            # ── FPS counter ──
            frame_count += 1
            elapsed_fps = time.monotonic() - fps_timer
            fps = frame_count / elapsed_fps if elapsed_fps > 0 else 0.0
            if elapsed_fps >= 5.0:
                frame_count = 0
                fps_timer = time.monotonic()

            # ── Grab frame ──
            gray = None
            left_rect = None
            depth_mm = None
            if cam is not None:
                gray = grab_frame(cam)
                left_rect, depth_mm = disparity_engine.process_frame(gray)

            # ── State: IDLE ──
            if state == State.IDLE:
                if ev == ButtonEvent.HOLD_COMPLETE:
                    state = State.ACQUIRING
                    acq_start_time = time.monotonic()
                    acq_frame_count = 0
                    acq_best = None
                    buzzer.window_active()
                    log.info("ACQUIRING — look for cone in front of camera")

                log_csv(csv_path, "IDLE", 0, 0, 0, 0, 0, 0, "idle", 0, fps)

            # ── State: ACQUIRING ──
            elif state == State.ACQUIRING:
                window_elapsed = time.monotonic() - acq_start_time

                # Timeout
                if window_elapsed > fm_cfg["acquisition_window_s"]:
                    state = State.IDLE
                    tracker.reset()
                    buzzer.target_lost()
                    log.warning("Acquisition timed out")
                    continue

                # Cancel on button release
                if ev == ButtonEvent.RELEASE:
                    state = State.IDLE
                    tracker.reset()
                    buzzer.stop()
                    log.info("Acquisition cancelled")
                    continue

                # Detect cones
                if left_rect is not None:
                    detections = cone_det.detect(left_rect)

                    for det in detections:
                        if det["confidence"] >= fm_cfg["acquisition_min_confidence"]:
                            acq_frame_count += 1
                            if acq_best is None or det["confidence"] > acq_best["confidence"]:
                                acq_best = det

                    if acq_frame_count >= fm_cfg["acquisition_min_frames"] and acq_best:
                        tracker.acquire(acq_best)
                        state = State.FOLLOWING
                        session_start = time.monotonic()
                        buzzer.target_acquired()
                        log.info(f"TARGET ACQUIRED — confidence {acq_best['confidence']:.2f} "
                                 f"at {acq_best['centroid']}")

                conf = acq_best["confidence"] if acq_best else 0
                log_csv(csv_path, "ACQUIRING", 0, 0, 0, conf, 0, 0, "acquiring", 0, fps)

            # ── State: FOLLOWING ──
            elif state == State.FOLLOWING:
                # Session timeout
                session_elapsed = (time.monotonic() - session_start) / 60.0
                if session_elapsed > fm_cfg["timeout_sessione_min"]:
                    state = State.IDLE
                    tracker.reset()
                    buzzer.target_lost()
                    log.warning(f"Session timeout ({fm_cfg['timeout_sessione_min']} min)")
                    continue

                # Button hold → manual stop
                if ev == ButtonEvent.HOLD_COMPLETE:
                    state = State.IDLE
                    tracker.reset()
                    buzzer.stop()
                    log.info("Manual stop via button")
                    continue

                target_d_m = 0.0
                cx, cy = 0, 0
                conf = 0.0
                cmd_zone = "idle"
                brake_pct = 0.0
                steer_pct = 0.0
                obs_min = float("inf")

                if left_rect is not None and depth_mm is not None:
                    # Detect and track
                    detections = cone_det.detect(left_rect)
                    matched = tracker.update(detections)

                    if matched is None:
                        # Target lost
                        state = State.IDLE
                        tracker.reset()
                        buzzer.target_lost()
                        log.warning("Target LOST")
                        log_csv(csv_path, "FOLLOWING", 0, 0, 0, 0, 0, 0, "lost", 0, fps)
                        continue

                    cx, cy = matched["centroid"]
                    conf = matched["confidence"]
                    bbox = matched["bbox"]

                    # Target depth from depth map (median in bbox)
                    bx, by, bw, bh = bbox
                    roi = depth_mm[by:by+bh, bx:bx+bw]
                    valid_depths = roi[roi > 0]
                    if len(valid_depths) > 0:
                        target_d_m = float(np.median(valid_depths)) / 1000.0
                    else:
                        target_d_m = 0.0

                    # Safety check (exclude target from obstacles)
                    safety_result = safety.check(depth_mm, target_bbox=bbox)
                    obs_min = safety_result["min_obstacle_m"]

                    # Control
                    frame_w = left_rect.shape[1]
                    cmd = controller.compute(target_d_m, cx, frame_w)
                    cmd_zone = cmd.zone
                    brake_pct = cmd.brake_pct
                    steer_pct = cmd.steer_pct

                    # Safety override: obstacle closer than target
                    if safety_result["obstacle_stop"]:
                        brake_pct = 100.0
                        cmd_zone = "obstacle_stop"
                        buzzer.obstacle_lateral()
                        log.warning(f"OBSTACLE STOP at {obs_min:.1f}m")
                    elif safety_result["obstacle_brake"]:
                        obs_brake = safety_result["obstacle_brake_factor"] * 100.0
                        brake_pct = max(brake_pct, obs_brake)
                        cmd_zone = "obstacle_brake"

                    # Buzzer feedback
                    if cmd.buzzer_action and not safety_result["obstacle_stop"]:
                        if cmd.buzzer_action == "target_lost":
                            buzzer.target_lost()
                        elif cmd.buzzer_action == "window_active":
                            buzzer.window_active()
                        elif cmd.buzzer_action.startswith("too_close:"):
                            proximity = float(cmd.buzzer_action.split(":")[1])
                            buzzer.too_close(proximity)

                    # Actuate (unless dry-run)
                    if not dry_run:
                        _actuate(brake_pct, steer_pct)
                    else:
                        if brake_pct > 0 or abs(steer_pct) > 5:
                            log.info(f"[DRY] brake={brake_pct:.0f}% steer={steer_pct:.1f}% "
                                     f"d={target_d_m:.1f}m zone={cmd_zone}")

                log_csv(csv_path, "FOLLOWING", target_d_m, cx, cy, conf,
                        brake_pct, steer_pct, cmd_zone, obs_min, fps)

            # ── Loop timing ──
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, 0.033 - elapsed)  # ~30 FPS target
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        buzzer.cleanup()
        button.cleanup()
        if cam is not None:
            cam.stop()
        lgpio.gpiochip_close(h)
        log.info("Cleanup complete")


def _actuate(brake_pct: float, steer_pct: float):
    """Send commands to brake servo and VESC steering.

    TODO: integrate with servofreno_server.py and steering_vesc_encoder.py.
    Currently a placeholder — the actual integration depends on whether
    follow-me runs as a standalone process or calls into existing services.
    """
    # Brake: map 0-100% to servo angle 0-88°
    # Steering: map -100..+100% to VESC duty cycle
    #
    # Integration options:
    # 1. HTTP POST to servofreno_server.py (already running)
    # 2. Direct lgpio PWM (requires exclusive GPIO access)
    # 3. Unix socket / shared memory
    #
    # For now, this is a no-op. The actual wiring will depend on
    # how the master_switch.py orchestrates services.
    pass


if __name__ == "__main__":
    main()
