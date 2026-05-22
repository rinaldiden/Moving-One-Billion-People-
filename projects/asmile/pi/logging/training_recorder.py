#!/usr/bin/env python3
"""
Asmile Training Recorder — records everything for autonomous driving training.

Saves synchronized:
  - Stereo video (H264 compressed, ~500kbps)
  - GPS (lat, lon, speed, heading)
  - IMU (accel xyz, gyro xyz)
  - Encoder (steering position)
  - VESC telemetry (rpm, current, tachometer, temperature, voltage)
  - Brake events

All data timestamped for frame-level correlation.

Usage:
  sudo python3 training_recorder.py              # start recording
  sudo python3 training_recorder.py --duration 60 # record 60 minutes
  Ctrl+C to stop

Output structure:
  ~/training_sessions/
    session_YYYYMMDD_HHMMSS/
      video.h264          — compressed stereo video
      sensors.csv         — 10Hz sensor data
      metadata.json       — session info (start time, duration, params)
"""

import subprocess
import signal
import sys
import os
import time
import json
import struct
import threading
import argparse
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
import pwd
_USER = os.environ.get("USER") or os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
_HOME = f"/home/{_USER}"
SESSIONS_DIR = os.path.join(_HOME, "wip/recorder")
ARDUCAM_FIX = os.path.join(_HOME, "streaming/arducam_fix.so")

# Video
WIDTH = 2560
HEIGHT = 800
FPS = 15
BITRATE = 2_000_000  # 500kbps — ~3.5MB/min

# Sensors
SENSOR_HZ = 10
ENCODER_FILE = "/tmp/encoder_position"

# IMU
I2C_BUS = 1
MPU6050_ADDR = 0x68
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
ACCEL_SCALE = 16384.0
GYRO_SCALE = 131.0

# GPS
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400

# VESC
VESC_PORT = "/dev/ttyAMA0"
VESC_BAUD = 115200

# ═══════════════════════════════════════════════════════════
# GLOBALS
# ═══════════════════════════════════════════════════════════
running = True
session_dir = ""
gps_data = {"lat": 0, "lon": 0, "speed_ms": 0, "heading": 0, "fix": False}
gps_lock = threading.Lock()
vesc_data = {"rpm": 0, "duty": 0, "i_motor": 0, "i_input": 0, "v_in": 0,
             "tach": 0, "tach_abs": 0, "temp_fet": 0, "temp_motor": 0, "fault": 0}
vesc_lock = threading.Lock()


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ═══════════════════════════════════════════════════════════
# IMU
# ═══════════════════════════════════════════════════════════
def init_imu():
    import smbus2
    bus = smbus2.SMBus(I2C_BUS)
    bus.write_byte_data(MPU6050_ADDR, 0x6B, 0x00)
    time.sleep(0.1)
    bus.write_byte_data(MPU6050_ADDR, 0x1C, 0x00)  # ±2g
    bus.write_byte_data(MPU6050_ADDR, 0x1B, 0x00)  # ±250°/s
    return bus


def read_imu(bus):
    def raw(reg):
        h = bus.read_byte_data(MPU6050_ADDR, reg)
        l = bus.read_byte_data(MPU6050_ADDR, reg + 1)
        v = (h << 8) | l
        return v - 0x10000 if v >= 0x8000 else v

    return {
        "ax": raw(ACCEL_XOUT_H) / ACCEL_SCALE,
        "ay": raw(ACCEL_XOUT_H + 2) / ACCEL_SCALE,
        "az": raw(ACCEL_XOUT_H + 4) / ACCEL_SCALE,
        "gx": raw(GYRO_XOUT_H) / GYRO_SCALE,
        "gy": raw(GYRO_XOUT_H + 2) / GYRO_SCALE,
        "gz": raw(GYRO_XOUT_H + 4) / GYRO_SCALE,
    }


# ═══════════════════════════════════════════════════════════
# GPS (background thread)
# ═══════════════════════════════════════════════════════════
def nmea_to_decimal(coord, direction):
    if len(coord) < 4:
        return 0.0
    dot = coord.index(".")
    degrees = int(coord[:dot - 2])
    minutes = float(coord[dot - 2:])
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


GPS_STATE_FILE = "/tmp/gps_state.json"


def gps_thread():
    """Read GPS from /tmp/gps_state.json (published by speed_limiter v2).

    Avoids UART port contention. speed_limiter owns ttyAMA3 and publishes
    NMEA-parsed state to a shared file at up to 10Hz.
    """
    global gps_data, running
    import json as _json

    print(f"[GPS] Reading from {GPS_STATE_FILE} (published by speed_limiter)")
    while running:
        try:
            with open(GPS_STATE_FILE) as f:
                gps = _json.load(f)
            with gps_lock:
                gps_data["lat"] = gps.get("lat", 0)
                gps_data["lon"] = gps.get("lon", 0)
                gps_data["speed_ms"] = gps.get("speed_ms", 0)
                gps_data["heading"] = gps.get("heading", 0)
                gps_data["fix"] = gps.get("fix", False)
        except (FileNotFoundError, ValueError, OSError):
            pass
        time.sleep(0.2)


# ═══════════════════════════════════════════════════════════
# ENCODER
# ═══════════════════════════════════════════════════════════
def read_encoder():
    try:
        with open(ENCODER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


# ═══════════════════════════════════════════════════════════
# VESC TELEMETRY (background thread)
# ═══════════════════════════════════════════════════════════
COMM_GET_VALUES = 4

def _crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _vesc_packet(payload: bytes) -> bytes:
    c = _crc16(payload)
    return bytes([0x02, len(payload)]) + payload + struct.pack(">H", c) + bytes([0x03])


def _parse_vesc(data: bytes):
    if len(data) < 10:
        return None
    idx = data.find(b'\x02')
    if idx < 0 or idx + 2 > len(data):
        return None
    plen = data[idx + 1]
    payload = data[idx + 2:idx + 2 + plen]
    if len(payload) < 56 or payload[0] != COMM_GET_VALUES:
        return None
    p = payload[1:]
    try:
        return {
            'temp_fet': struct.unpack(">h", p[0:2])[0] / 10.0,
            'temp_motor': struct.unpack(">h", p[2:4])[0] / 10.0,
            'i_motor': struct.unpack(">i", p[4:8])[0] / 100.0,
            'i_input': struct.unpack(">i", p[8:12])[0] / 100.0,
            'duty': struct.unpack(">h", p[20:22])[0] / 1000.0,
            'rpm': struct.unpack(">i", p[22:26])[0],
            'v_in': struct.unpack(">h", p[26:28])[0] / 10.0,
            'tach': struct.unpack(">i", p[44:48])[0],
            'tach_abs': struct.unpack(">i", p[48:52])[0],
            'fault': p[52],
        }
    except (struct.error, IndexError):
        return None


def vesc_thread():
    """Read VESC telemetry via UART. Runs in background, updates vesc_data."""
    global vesc_data, running
    import serial

    try:
        ser = serial.Serial(VESC_PORT, VESC_BAUD, timeout=0.2)
        ser.reset_input_buffer()
        print(f"[VESC] Connected on {VESC_PORT}")
    except Exception as e:
        print(f"[VESC] Not available: {e}")
        return

    while running:
        try:
            ser.reset_input_buffer()
            ser.write(_vesc_packet(bytes([COMM_GET_VALUES])))
            time.sleep(0.05)
            resp = ser.read(ser.in_waiting or 128)
            if resp:
                time.sleep(0.01)
                resp += ser.read(ser.in_waiting or 64)
            vals = _parse_vesc(resp)
            if vals:
                with vesc_lock:
                    vesc_data.update(vals)
        except Exception:
            pass
        time.sleep(0.08)  # ~12Hz polling, faster than 10Hz logging

    ser.close()


# ═══════════════════════════════════════════════════════════
# VIDEO RECORDER
# ═══════════════════════════════════════════════════════════
def start_video(output_path):
    """Record video using rpicam-vid (correct auto-exposure, unlike gst-launch)."""
    env = os.environ.copy()
    if os.path.isfile(ARDUCAM_FIX):
        env["LD_PRELOAD"] = ARDUCAM_FIX

    cmd = [
        "rpicam-vid",
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        "--framerate", str(FPS),
        "--bitrate", str(BITRATE),
        "--codec", "h264",
        "--profile", "baseline",
        "--timeout", "0",       # unlimited recording
        "--nopreview",
        *(["--vflip", "--hflip"] if not os.path.isfile(ARDUCAM_FIX) else []),
        "-o", output_path,
    ]

    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return proc


# ═══════════════════════════════════════════════════════════
# SENSOR LOGGER
# ═══════════════════════════════════════════════════════════
def sensor_logger(csv_path, imu_bus):
    global running

    with open(csv_path, "w") as f:
        f.write("timestamp,gps_lat,gps_lon,gps_speed_ms,gps_heading,"
                "imu_accel_x,imu_accel_y,imu_accel_z,"
                "imu_gyro_x,imu_gyro_y,imu_gyro_z,"
                "encoder_pos,"
                "vesc_rpm,vesc_duty,vesc_i_motor,vesc_i_input,vesc_v_in,"
                "vesc_tach,vesc_tach_abs,vesc_temp_fet,vesc_temp_motor,vesc_fault\n")

        while running:
            ts = datetime.now().isoformat(timespec="milliseconds")
            try:
                imu = read_imu(imu_bus)
            except OSError:
                imu = {"ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}
            with gps_lock:
                gps = gps_data.copy()
            enc = read_encoder()
            with vesc_lock:
                vesc = vesc_data.copy()

            f.write(f"{ts},{gps['lat']:.7f},{gps['lon']:.7f},"
                    f"{gps['speed_ms']:.3f},{gps['heading']:.1f},"
                    f"{imu['ax']:.4f},{imu['ay']:.4f},{imu['az']:.4f},"
                    f"{imu['gx']:.2f},{imu['gy']:.2f},{imu['gz']:.2f},"
                    f"{enc},"
                    f"{vesc['rpm']},{vesc['duty']:.3f},"
                    f"{vesc['i_motor']:.2f},{vesc['i_input']:.2f},{vesc['v_in']:.1f},"
                    f"{vesc['tach']},{vesc['tach_abs']},"
                    f"{vesc['temp_fet']:.1f},{vesc['temp_motor']:.1f},{vesc['fault']}\n")
            f.flush()
            time.sleep(1.0 / SENSOR_HZ)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    global running, session_dir

    parser = argparse.ArgumentParser(description="Asmile Training Recorder")
    parser.add_argument("--duration", type=int, default=0, help="Recording duration in minutes (0=unlimited)")
    args = parser.parse_args()

    # Create session directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(SESSIONS_DIR, f"session_{ts}")
    os.makedirs(session_dir, exist_ok=True)

    video_path = os.path.join(session_dir, "video.h264")
    csv_path = os.path.join(session_dir, "sensors.csv")
    meta_path = os.path.join(session_dir, "metadata.json")

    print("=" * 50)
    print("  ASMILE TRAINING RECORDER")
    print("=" * 50)
    print(f"Session: {session_dir}")

    # Init IMU
    try:
        imu_bus = init_imu()
        imu_test = read_imu(imu_bus)
        print(f"[IMU] OK — az={imu_test['az']:.2f}g")
    except Exception as e:
        print(f"[IMU] FAILED: {e}")
        sys.exit(1)

    # Init GPS
    gps_t = threading.Thread(target=gps_thread, daemon=True)
    gps_t.start()
    print("[GPS] Thread started")

    # Init Encoder
    enc = read_encoder()
    print(f"[ENCODER] Position: {enc}")

    # Init VESC telemetry
    vesc_t = threading.Thread(target=vesc_thread, daemon=True)
    vesc_t.start()

    # Start video
    print(f"[VIDEO] Recording {WIDTH}x{HEIGHT}@{FPS}fps → {video_path}")
    video_proc = start_video(video_path)
    time.sleep(3)

    if video_proc.poll() is not None:
        stderr = video_proc.stderr.read().decode() if video_proc.stderr else ""
        print(f"[VIDEO] FAILED: {stderr[:200]}")
        sys.exit(1)

    print("[VIDEO] Recording...")

    # Start sensor logger
    sensor_t = threading.Thread(target=sensor_logger, args=(csv_path, imu_bus), daemon=True)
    sensor_t.start()
    print(f"[SENSORS] Logging at {SENSOR_HZ}Hz → {csv_path}")

    # Save metadata
    start_time = datetime.now()
    meta = {
        "start_time": start_time.isoformat(),
        "video_file": "video.h264",
        "sensor_file": "sensors.csv",
        "video_width": WIDTH,
        "video_height": HEIGHT,
        "video_fps": FPS,
        "video_bitrate": BITRATE,
        "sensor_hz": SENSOR_HZ,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print()
    if args.duration > 0:
        print(f"Recording for {args.duration} minutes. Ctrl+C to stop early.")
    else:
        print("Recording unlimited. Ctrl+C to stop.")
    print()

    # Wait
    elapsed = 0
    try:
        while running:
            time.sleep(1)
            elapsed += 1

            if elapsed % 30 == 0:
                with gps_lock:
                    fix = "FIX" if gps_data["fix"] else "no fix"
                    spd = gps_data["speed_ms"]
                enc = read_encoder()
                vsize = os.path.getsize(video_path) / (1024 * 1024) if os.path.exists(video_path) else 0
                print(f"  [{elapsed//60}m{elapsed%60:02d}s] GPS:{fix} {spd:.1f}m/s | Enc:{enc} | Video:{vsize:.1f}MB")

            if args.duration > 0 and elapsed >= args.duration * 60:
                print(f"\nDuration reached ({args.duration} min)")
                break

    except KeyboardInterrupt:
        pass

    # Stop
    running = False
    print("\n[*] Stopping...")

    video_proc.terminate()
    try:
        video_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        video_proc.kill()

    # Update metadata
    end_time = datetime.now()
    meta["end_time"] = end_time.isoformat()
    meta["duration_seconds"] = (end_time - start_time).total_seconds()
    meta["video_size_mb"] = os.path.getsize(video_path) / (1024 * 1024) if os.path.exists(video_path) else 0
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSession saved: {session_dir}")
    print(f"  Video: {meta['video_size_mb']:.1f} MB")
    print(f"  Duration: {meta['duration_seconds']:.0f}s")
    print("  Done.")


if __name__ == "__main__":
    main()
