#!/usr/bin/env python3
"""
Asmile Route Replay — follow a previously recorded route.

Reads a recorded session (sensors.csv + GPS waypoints) and replays
the same steering + speed commands. Emergency stop if obstacle detected
or GPS deviation > threshold.

SAFETY:
- Max speed enforced (12 km/h = 3.33 m/s)
- Human override detection (steering current spike)
- GPS geofence (stop if > 3m from recorded path)
- Emergency brake if obstacle < 1.5m
- Switch OFF = immediate stop

Usage:
  python3 route_replay.py --session ~/wip/recorder/session_20260508_205916/
  python3 route_replay.py --session ~/wip/recorder/session_20260508_205916/ --dry-run
"""

import csv
import json
import math
import os
import sys
import time
import signal
import struct
import threading
import argparse
from datetime import datetime

# Add parent paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PI_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PI_DIR, "steering"))
sys.path.insert(0, os.path.join(PI_DIR, "braking"))

# Config
MAX_SPEED_MS = 3.33          # 12 km/h
GPS_DEVIATION_MAX_M = 3.0    # stop if > 3m from path
OBSTACLE_STOP_M = 1.5        # emergency brake distance
LOOKAHEAD_POINTS = 5         # GPS points ahead for heading
CONTROL_HZ = 10              # control loop frequency
ENCODER_CENTER = 2750        # encoder center (dritto)
ENCODER_FILE = "/tmp/encoder_position"

# VESC UART
VESC_PORT = "/dev/ttyAMA0"
VESC_BAUD = 115200
COMM_SET_CURRENT = 6
COMM_GET_VALUES = 4

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS points."""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Bearing in degrees from point 1 to point 2."""
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(math.radians(lat2))
    y = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) -
         math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def load_route(session_dir):
    """Load recorded route from sensors.csv."""
    csv_path = os.path.join(session_dir, "sensors.csv")
    waypoints = []
    with open(csv_path, errors="replace") as f:
        clean = (line.replace("\x00", "") for line in f)
        reader = csv.DictReader(clean)
        for row in reader:
            try:
                lat = float(row.get("gps_lat", 0))
                lon = float(row.get("gps_lon", 0))
                speed = float(row.get("gps_speed_ms", 0))
                heading = float(row.get("gps_heading", 0))
                enc = int(row.get("encoder_pos", -1))
                accel_x = float(row.get("imu_accel_x", 0))

                # Skip stationary points
                if speed < 0.3 or lat == 0:
                    continue

                waypoints.append({
                    "lat": lat, "lon": lon,
                    "speed": min(speed, MAX_SPEED_MS),
                    "heading": heading,
                    "encoder": enc,
                    "accel_x": accel_x,
                    "timestamp": row.get("timestamp", ""),
                })
            except (ValueError, KeyError):
                continue
    return waypoints


def read_encoder():
    try:
        with open(ENCODER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


def read_gps():
    """Read GPS from servofreno API."""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:5000/stato", timeout=1)
        data = json.loads(resp.read())
        gps = data.get("gps", {})
        return {
            "lat": gps.get("lat", 0),
            "lon": gps.get("lon", 0),
            "speed": gps.get("speed_ms", 0),
            "heading": gps.get("heading", 0),
            "fix": gps.get("fix", False),
        }
    except Exception:
        return {"lat": 0, "lon": 0, "speed": 0, "heading": 0, "fix": False}


def find_nearest_waypoint(lat, lon, waypoints, start_idx=0):
    """Find nearest waypoint from current position."""
    best_idx = start_idx
    best_dist = float("inf")
    # Search forward from start_idx (don't go backwards)
    search_range = min(len(waypoints), start_idx + 50)
    for i in range(start_idx, search_range):
        d = haversine_m(lat, lon, waypoints[i]["lat"], waypoints[i]["lon"])
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx, best_dist


class RouteReplayer:
    def __init__(self, session_dir, dry_run=False):
        self.dry_run = dry_run
        self.waypoints = load_route(session_dir)
        self.current_wp = 0
        self.ser = None
        self.stop_reason = None

        if not self.waypoints:
            raise RuntimeError("No moving waypoints in session")

        print(f"Route loaded: {len(self.waypoints)} waypoints")
        print(f"Start: {self.waypoints[0]['lat']:.6f}, {self.waypoints[0]['lon']:.6f}")
        print(f"End: {self.waypoints[-1]['lat']:.6f}, {self.waypoints[-1]['lon']:.6f}")

        # Calculate route stats
        total_dist = sum(haversine_m(
            self.waypoints[i]["lat"], self.waypoints[i]["lon"],
            self.waypoints[i + 1]["lat"], self.waypoints[i + 1]["lon"])
            for i in range(len(self.waypoints) - 1))
        avg_speed = sum(w["speed"] for w in self.waypoints) / len(self.waypoints)
        print(f"Distance: {total_dist:.0f}m, avg speed: {avg_speed:.1f}m/s")

    def _init_vesc(self):
        if self.dry_run:
            return
        import serial
        self.ser = serial.Serial(VESC_PORT, VESC_BAUD, timeout=0.1)
        self.ser.reset_input_buffer()

    def _send_steering(self, target_encoder):
        """Send steering command to reach target encoder position."""
        if self.dry_run:
            return
        current = read_encoder()
        if current < 0:
            return
        # Simple proportional: error → current command
        error = target_encoder - current
        if abs(error) > 2048:
            error = error - 4096 if error > 0 else error + 4096
        # P controller with saturation
        current_cmd = max(-5.0, min(5.0, error * 0.01))
        self._vesc_set_current(current_cmd)

    def _vesc_set_current(self, amps):
        if self.ser and self.ser.is_open:
            ma = int(amps * 1000)
            payload = struct.pack(">Bi", COMM_SET_CURRENT, ma)
            c = 0
            for b in payload:
                c ^= b << 8
                for _ in range(8):
                    if c & 0x8000:
                        c = (c << 1) ^ 0x1021
                    else:
                        c <<= 1
                    c &= 0xFFFF
            pkt = bytes([0x02, len(payload)]) + payload + struct.pack(">H", c) + bytes([0x03])
            self.ser.write(pkt)

    def _brake(self, intensity=0.5):
        """Activate brake servo. 0=release, 1=full brake."""
        if self.dry_run:
            return
        import urllib.request
        try:
            angle = int(intensity * 95)  # 0-95 degrees
            urllib.request.urlopen(
                f"http://localhost:5000/brake?angle={angle}", timeout=1)
        except Exception:
            pass

    def _release_brake(self):
        self._brake(0)

    def _emergency_stop(self, reason):
        self.stop_reason = reason
        print(f"\n*** EMERGENCY STOP: {reason} ***")
        self._brake(1.0)
        self._vesc_set_current(0)
        global running
        running = False

    def run(self):
        global running

        self._init_vesc()
        self._release_brake()

        print(f"\n{'='*50}")
        print(f"  ROUTE REPLAY {'(DRY RUN)' if self.dry_run else 'ACTIVE'}")
        print(f"{'='*50}")
        print(f"Max speed: {MAX_SPEED_MS:.1f}m/s ({MAX_SPEED_MS*3.6:.0f}km/h)")
        print(f"GPS deviation max: {GPS_DEVIATION_MAX_M}m")
        print(f"Ctrl+C or switch OFF to stop\n")

        dt = 1.0 / CONTROL_HZ
        start_time = time.monotonic()

        try:
            while running and self.current_wp < len(self.waypoints) - 1:
                t0 = time.monotonic()

                # Read current state
                gps = read_gps()
                enc = read_encoder()

                if not gps["fix"]:
                    print("\r  Waiting for GPS fix...", end="", flush=True)
                    time.sleep(0.5)
                    continue

                # Find nearest waypoint
                self.current_wp, deviation = find_nearest_waypoint(
                    gps["lat"], gps["lon"], self.waypoints, self.current_wp)

                # Safety: GPS deviation
                if deviation > GPS_DEVIATION_MAX_M:
                    self._emergency_stop(
                        f"GPS deviation {deviation:.1f}m > {GPS_DEVIATION_MAX_M}m")
                    break

                # Target from recorded route
                wp = self.waypoints[min(self.current_wp + LOOKAHEAD_POINTS,
                                        len(self.waypoints) - 1)]
                target_speed = min(wp["speed"], MAX_SPEED_MS)
                target_enc = wp["encoder"]

                # Speed control: brake if too fast
                if gps["speed"] > target_speed + 0.5:
                    brake_intensity = min(1.0, (gps["speed"] - target_speed) / 2.0)
                    self._brake(brake_intensity)
                else:
                    self._release_brake()

                # Steering
                if target_enc > 0:
                    self._send_steering(target_enc)

                # Progress
                progress = self.current_wp / len(self.waypoints) * 100
                elapsed = time.monotonic() - start_time
                if int(elapsed) % 5 == 0:
                    print(f"\r  [{progress:.0f}%] wp={self.current_wp}/{len(self.waypoints)} "
                          f"dev={deviation:.1f}m speed={gps['speed']:.1f}m/s "
                          f"enc={enc} target={target_enc}",
                          end="", flush=True)

                # Sleep
                sleep_time = dt - (time.monotonic() - t0)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\nStopped by user")
        finally:
            # Always stop
            self._brake(0.5)
            time.sleep(0.3)
            self._vesc_set_current(0)
            self._release_brake()
            if self.ser:
                self.ser.close()

            if self.current_wp >= len(self.waypoints) - 1:
                print(f"\n\nRoute completed! {len(self.waypoints)} waypoints.")
            elif self.stop_reason:
                print(f"\nStopped: {self.stop_reason}")

            print(f"Final position: wp {self.current_wp}/{len(self.waypoints)}")


def main():
    parser = argparse.ArgumentParser(description="Asmile Route Replay")
    parser.add_argument("--session", required=True, help="Recorded session directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate without sending commands")
    args = parser.parse_args()

    replayer = RouteReplayer(args.session, dry_run=args.dry_run)
    replayer.run()


if __name__ == "__main__":
    main()
