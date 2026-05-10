#!/usr/bin/env python3
"""
Asmile Position Fusion — Kalman filter combining GPS + IMU + Encoder.

Estimates position, heading, and velocity at 50Hz by fusing:
- GPS: absolute position (1-10Hz, ±2-3m)
- IMU: acceleration + gyro rotation (100Hz, drifts)
- Encoder: steering angle → turn rate (200Hz, precise)

State vector: [x, y, heading, speed, yaw_rate]
- x, y: position in meters (local ENU frame, origin = first GPS fix)
- heading: radians from north (clockwise)
- speed: m/s
- yaw_rate: rad/s (from gyro_z, confirmed by encoder)

Bicycle model: the bike moves forward at speed along heading,
heading changes based on yaw_rate (from gyro + encoder).

Usage:
  # Standalone test
  python3 position_fusion.py --session ~/wip/recorder/session_20260508_205916/

  # As module
  from position_fusion import PositionFusion
  pf = PositionFusion()
  pf.update_gps(lat, lon, speed, heading)
  pf.update_imu(accel_x, accel_y, gyro_z)
  pf.update_encoder(encoder_pos)
  x, y, heading, speed = pf.get_position()
"""

import math
import time
import numpy as np
import json
import os
import csv
import argparse

# Earth radius
R_EARTH = 6371000.0

# Bicycle geometry
WHEELBASE_M = 1.2  # distance between front and rear axle
ENCODER_CENTER = 2824
ENCODER_STEPS_PER_REV = 4096
GEAR_RATIO = 5.0  # steering gear ratio

# Kalman filter tuning
PROCESS_NOISE_POS = 0.1       # m — position uncertainty growth per second
PROCESS_NOISE_HEADING = 0.02  # rad — heading uncertainty growth per second
PROCESS_NOISE_SPEED = 0.5     # m/s — speed uncertainty growth per second
PROCESS_NOISE_YAW = 0.1       # rad/s — yaw rate uncertainty growth per second

GPS_NOISE_POS = 2.5           # m — GPS position noise
GPS_NOISE_SPEED = 0.3         # m/s — GPS speed noise
GPS_NOISE_HEADING = 0.15      # rad — GPS heading noise (~8°)

IMU_NOISE_ACCEL = 0.1         # m/s² — accelerometer noise
IMU_NOISE_GYRO = 0.02         # rad/s — gyroscope noise

ENCODER_NOISE = 0.005         # rad — encoder angle noise


def gps_to_local(lat, lon, ref_lat, ref_lon):
    """Convert GPS to local ENU meters relative to reference point."""
    dlat = math.radians(lat - ref_lat)
    dlon = math.radians(lon - ref_lon)
    x = dlon * R_EARTH * math.cos(math.radians(ref_lat))
    y = dlat * R_EARTH
    return x, y


def local_to_gps(x, y, ref_lat, ref_lon):
    """Convert local ENU meters back to GPS."""
    lat = ref_lat + math.degrees(y / R_EARTH)
    lon = ref_lon + math.degrees(x / (R_EARTH * math.cos(math.radians(ref_lat))))
    return lat, lon


class PositionFusion:
    """Extended Kalman Filter for bicycle position estimation."""

    def __init__(self):
        # State: [x, y, heading, speed, yaw_rate]
        self.state = np.zeros(5)
        self.P = np.diag([10.0, 10.0, 1.0, 1.0, 0.5])  # initial uncertainty

        # Reference GPS point (set on first fix)
        self.ref_lat = None
        self.ref_lon = None
        self.initialized = False

        # Timing
        self.last_update = None
        self.update_count = 0

        # Encoder state
        self.last_encoder = -1
        self.encoder_steer_angle = 0.0  # radians

    def _predict(self, dt):
        """Predict step: bicycle model forward."""
        x, y, heading, speed, yaw_rate = self.state

        # Bicycle kinematics
        x += speed * math.sin(heading) * dt
        y += speed * math.cos(heading) * dt
        heading += yaw_rate * dt
        # Normalize heading to [0, 2π]
        heading = heading % (2 * math.pi)

        self.state = np.array([x, y, heading, speed, yaw_rate])

        # Jacobian of state transition
        F = np.eye(5)
        F[0, 2] = speed * math.cos(heading) * dt
        F[0, 3] = math.sin(heading) * dt
        F[1, 2] = -speed * math.sin(heading) * dt
        F[1, 3] = math.cos(heading) * dt
        F[2, 4] = dt

        # Process noise
        Q = np.diag([
            PROCESS_NOISE_POS * dt,
            PROCESS_NOISE_POS * dt,
            PROCESS_NOISE_HEADING * dt,
            PROCESS_NOISE_SPEED * dt,
            PROCESS_NOISE_YAW * dt,
        ]) ** 2

        self.P = F @ self.P @ F.T + Q

    def _kalman_update(self, z, H, R):
        """Standard Kalman update."""
        y = z - H @ self.state
        # Normalize heading difference
        if H.shape[0] >= 3 and H[2, 2] != 0:
            y[2] = (y[2] + math.pi) % (2 * math.pi) - math.pi
        S = H @ self.P @ H.T + R
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return  # skip update if singular
        self.state = self.state + K @ y
        self.state[2] = self.state[2] % (2 * math.pi)
        self.P = (np.eye(5) - K @ H) @ self.P

    def update_gps(self, lat, lon, speed_ms, heading_deg):
        """Update with GPS measurement."""
        if lat == 0 or lon == 0:
            return

        now = time.monotonic()
        if self.last_update is not None:
            dt = now - self.last_update
            if dt > 0:
                self._predict(dt)
        self.last_update = now

        # Set reference on first fix
        if self.ref_lat is None:
            self.ref_lat = lat
            self.ref_lon = lon
            heading_rad = math.radians(heading_deg) if heading_deg > 0 else 0
            self.state = np.array([0, 0, heading_rad, speed_ms, 0])
            self.initialized = True
            return

        # Convert to local
        x, y = gps_to_local(lat, lon, self.ref_lat, self.ref_lon)
        heading_rad = math.radians(heading_deg)

        # Measurement
        z = np.array([x, y, heading_rad, speed_ms])
        H = np.zeros((4, 5))
        H[0, 0] = 1  # x
        H[1, 1] = 1  # y
        H[2, 2] = 1  # heading
        H[3, 3] = 1  # speed

        R = np.diag([
            GPS_NOISE_POS ** 2,
            GPS_NOISE_POS ** 2,
            GPS_NOISE_HEADING ** 2,
            GPS_NOISE_SPEED ** 2,
        ])

        # If speed is very low, GPS heading is unreliable
        if speed_ms < 0.5:
            R[2, 2] = 100  # ignore GPS heading when slow

        self._kalman_update(z, H, R)
        self.update_count += 1

    def update_imu(self, accel_x, gyro_z_deg_s):
        """Update with IMU measurement. accel_x in g, gyro_z in deg/s."""
        now = time.monotonic()
        if self.last_update is not None:
            dt = now - self.last_update
            if dt > 0:
                self._predict(dt)
        self.last_update = now

        if not self.initialized:
            return

        # Convert units
        accel_ms2 = accel_x * 9.81  # g → m/s²
        gyro_rad_s = math.radians(gyro_z_deg_s)

        # Update speed from acceleration (integrate)
        # z = current_speed + accel * dt (but we don't have dt here, use as observation)
        # Actually: use accel to refine speed change
        # For now: use gyro_z as yaw_rate measurement

        z = np.array([gyro_rad_s])
        H = np.zeros((1, 5))
        H[0, 4] = 1  # yaw_rate
        R = np.array([[IMU_NOISE_GYRO ** 2]])

        self._kalman_update(z, H, R)

    def update_encoder(self, encoder_pos):
        """Update with encoder position. Converts to steering angle → yaw rate."""
        if encoder_pos <= 0:
            return

        if self.last_encoder < 0:
            self.last_encoder = encoder_pos
            return

        # Encoder delta → steering angle
        delta = encoder_pos - ENCODER_CENTER
        if delta > 2048:
            delta -= 4096
        elif delta < -2048:
            delta += 4096

        # Steering angle in radians (encoder → wheel via gear ratio)
        steer_angle = (delta / ENCODER_STEPS_PER_REV) * 2 * math.pi / GEAR_RATIO
        self.encoder_steer_angle = steer_angle

        # Bicycle model: yaw_rate = speed * tan(steer_angle) / wheelbase
        speed = max(self.state[3], 0.1)
        yaw_rate_from_encoder = speed * math.tan(steer_angle) / WHEELBASE_M

        # Clamp to reasonable values
        yaw_rate_from_encoder = max(-2.0, min(2.0, yaw_rate_from_encoder))

        z = np.array([yaw_rate_from_encoder])
        H = np.zeros((1, 5))
        H[0, 4] = 1  # yaw_rate
        R = np.array([[ENCODER_NOISE ** 2]])

        self._kalman_update(z, H, R)
        self.last_encoder = encoder_pos

    def get_position(self):
        """Return current estimated position."""
        x, y, heading, speed, yaw_rate = self.state
        if self.ref_lat is not None:
            lat, lon = local_to_gps(x, y, self.ref_lat, self.ref_lon)
        else:
            lat, lon = 0, 0
        return {
            "lat": lat,
            "lon": lon,
            "x": x,
            "y": y,
            "heading_deg": math.degrees(heading) % 360,
            "speed_ms": max(0, speed),
            "yaw_rate_deg_s": math.degrees(yaw_rate),
            "steer_angle_deg": math.degrees(self.encoder_steer_angle),
            "uncertainty_m": math.sqrt(self.P[0, 0] + self.P[1, 1]),
        }


def test_with_session(session_dir):
    """Replay a recorded session through the fusion filter."""
    csv_path = os.path.join(session_dir, "sensors.csv")
    if not os.path.exists(csv_path):
        print(f"No sensors.csv in {session_dir}")
        return

    pf = PositionFusion()
    results = []

    with open(csv_path, errors="replace") as f:
        clean = (line.replace("\x00", "") for line in f)
        reader = csv.DictReader(clean)
        for row in reader:
            try:
                lat = float(row.get("gps_lat", 0))
                lon = float(row.get("gps_lon", 0))
                speed = float(row.get("gps_speed_ms", 0))
                heading = float(row.get("gps_heading", 0))
                accel_x = float(row.get("imu_accel_x", 0))
                gyro_z = float(row.get("imu_gyro_z", 0))
                enc = int(row.get("encoder_pos", -1))
            except (ValueError, KeyError):
                continue

            # Simulate sensor updates (in real-time these come at different rates)
            if lat > 0:
                pf.update_gps(lat, lon, speed, heading)
            pf.update_imu(accel_x, gyro_z)
            pf.update_encoder(enc)

            pos = pf.get_position()
            pos["gps_lat"] = lat
            pos["gps_lon"] = lon
            pos["gps_speed"] = speed
            pos["timestamp"] = row.get("timestamp", "")
            results.append(pos)

    # Analyze accuracy: compare fused position vs GPS
    errors = []
    for r in results:
        if r["gps_lat"] > 0 and r["lat"] > 0:
            err = math.sqrt(
                (gps_to_local(r["lat"], r["lon"], r["gps_lat"], r["gps_lon"])[0]) ** 2 +
                (gps_to_local(r["lat"], r["lon"], r["gps_lat"], r["gps_lon"])[1]) ** 2
            )
            errors.append(err)

    if errors:
        print(f"\nFusion vs GPS:")
        print(f"  Mean error: {np.mean(errors):.2f}m")
        print(f"  Max error:  {np.max(errors):.2f}m")
        print(f"  p95 error:  {np.percentile(errors, 95):.2f}m")
        print(f"  Uncertainty: {results[-1]['uncertainty_m']:.2f}m")
        print(f"  Updates: {pf.update_count}")
        print(f"  Samples: {len(results)}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Asmile Position Fusion")
    parser.add_argument("--session", required=True, help="Recorded session directory")
    args = parser.parse_args()

    print(f"{'='*50}")
    print(f"  ASMILE POSITION FUSION TEST")
    print(f"{'='*50}")
    print(f"Session: {args.session}\n")

    test_with_session(args.session)


if __name__ == "__main__":
    main()
