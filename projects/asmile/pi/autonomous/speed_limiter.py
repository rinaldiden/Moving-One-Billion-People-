#!/usr/bin/env python3
"""
Asmile Speed Limiter — keeps speed below 12 km/h with progressive braking.

Runs as background service. Reads GPS speed, applies brake progressively
if speed exceeds target. Uses IMU to verify deceleration — if decel is
insufficient, increases brake force.

Braking profile learned from recorded sessions:
- Gentle: servo 0-40° → decel ~0.1g
- Medium: servo 40-70° → decel ~0.2g
- Hard: servo 70-95° → decel ~0.4g

Usage:
  python3 speed_limiter.py                    # default 12 km/h
  python3 speed_limiter.py --max-speed 10     # 10 km/h
  python3 speed_limiter.py --dry-run          # simulate only
"""

import json
import math
import os
import sys
import time
import signal
import argparse
from datetime import datetime

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Default config
DEFAULT_MAX_KMH = 10.0
CONTROL_HZ = 10
BRAKE_MIN_ANGLE = 0
BRAKE_MAX_ANGLE = 45

# Servo GPIO — direct PWM, no API
GPIO_CHIP = 4
SERVO_PIN = 12
SERVO_FREQ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ

# Braking PID
BRAKE_KP = 30.0     # degrees per m/s over limit
BRAKE_KI = 5.0      # integral term
BRAKE_KD = 10.0     # derivative term

# Decel check
MIN_EXPECTED_DECEL = 0.05  # g — if brake is on but decel < this, increase force
DECEL_BOOST_STEP = 5       # degrees to add if decel insufficient


def read_gps():
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:5000/stato", timeout=1)
        data = json.loads(resp.read())
        resp.close()
        gps = data.get("gps", {})
        return gps.get("speed_ms", 0), gps.get("fix", False)
    except Exception:
        return 0, False


def read_imu_accel_x():
    """Read longitudinal acceleration from IMU."""
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        h = bus.read_byte_data(0x68, 0x3B)
        l = bus.read_byte_data(0x68, 0x3C)
        v = (h << 8) | l
        if v >= 0x8000:
            v -= 0x10000
        return v / 16384.0  # ±2g scale
    except Exception:
        return 0


def _angle_to_duty(angle):
    """Convert servo angle (0-180°) to PWM duty cycle %."""
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


def set_brake(angle, dry_run=False, gpio_handle=None):
    """Set brake servo angle. GPIO direct — fast, no dependency."""
    angle = max(BRAKE_MIN_ANGLE, min(BRAKE_MAX_ANGLE, int(angle)))
    if dry_run:
        return angle

    if gpio_handle is not None:
        import lgpio
        if angle > 0:
            lgpio.tx_pwm(gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(angle))
        else:
            lgpio.tx_pwm(gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(0))
            time.sleep(0.3)
            lgpio.tx_pwm(gpio_handle, SERVO_PIN, 0, 0)
    return angle


class SpeedLimiter:
    def __init__(self, max_kmh=DEFAULT_MAX_KMH, dry_run=False):
        self.max_speed_ms = max_kmh / 3.6
        self.max_kmh = max_kmh
        self.dry_run = dry_run

        # PID state
        self.integral = 0
        self.prev_error = 0
        self.current_brake = 0
        self.brake_active = False

        # Decel monitor
        self.decel_boost = 0

        # GPIO direct for servo — fast, no API dependency
        self.gpio_handle = None
        if not dry_run:
            try:
                import lgpio
                self.gpio_handle = lgpio.gpiochip_open(GPIO_CHIP)
                lgpio.gpio_claim_output(self.gpio_handle, SERVO_PIN)
                # Release brake on startup
                set_brake(0, False, self.gpio_handle)
                print("Servo released to 0°")
            except Exception as e:
                print(f"WARNING: GPIO init failed: {e} — brake won't work")

        # Log
        self.log_file = None
        log_dir = os.path.expanduser("~/wip/logging/speed_limiter")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = open(os.path.join(log_dir, f"limiter_{ts}.csv"), "w")
        self.log_file.write("timestamp,speed_ms,speed_kmh,error_ms,"
                            "brake_angle,accel_x,decel_boost\n")

    def _check_emergency(self):
        """Check if phone requested emergency brake via flag file."""
        if not os.path.exists("/tmp/emergency_brake"):
            return 0
        try:
            with open("/tmp/emergency_brake") as f:
                angle = int(f.read().strip())
                return max(0, min(BRAKE_MAX_ANGLE, angle))
        except (ValueError, OSError):
            return 0

    def step(self):
        speed, fix = read_gps()
        accel_x = read_imu_accel_x()
        speed_kmh = speed * 3.6

        # Emergency brake from phone overrides everything
        emergency = self._check_emergency()
        if emergency > 0:
            self.current_brake = set_brake(emergency, self.dry_run, self.gpio_handle)
            self.brake_active = True
            self._emergency_was_active = True
            return speed, speed_kmh, self.current_brake

        # Emergency just released — snap to 0 immediately
        if getattr(self, '_emergency_was_active', False):
            self._emergency_was_active = False
            self.current_brake = set_brake(0, self.dry_run, self.gpio_handle)
            self.brake_active = False
            self.integral = 0
            self.decel_boost = 0
            return speed, speed_kmh, self.current_brake

        # Speed error: positive = over limit
        error = speed - self.max_speed_ms
        dt = 1.0 / CONTROL_HZ

        if error > 0:
            # Over speed — apply brake
            self.integral += error * dt
            self.integral = min(self.integral, 20)  # anti-windup
            derivative = (error - self.prev_error) / dt

            # PID output
            brake_angle = (BRAKE_KP * error +
                           BRAKE_KI * self.integral +
                           BRAKE_KD * derivative +
                           self.decel_boost)

            # Check if decel is happening
            if self.brake_active and accel_x < MIN_EXPECTED_DECEL:
                # Brake is on but not decelerating enough — boost
                self.decel_boost += DECEL_BOOST_STEP * dt
                self.decel_boost = min(self.decel_boost, 30)

            self.current_brake = set_brake(brake_angle, self.dry_run, self.gpio_handle)
            self.brake_active = True

        elif error < -0.5:
            # Well under limit — release brake gradually
            if self.brake_active:
                self.current_brake = max(0, self.current_brake - 10 * dt)
                set_brake(self.current_brake, self.dry_run, self.gpio_handle)
                if self.current_brake <= 0:
                    self.brake_active = False
                    self.integral = 0
                    self.decel_boost = 0

        self.prev_error = error

        # Log
        if self.log_file:
            ts = datetime.now().isoformat(timespec="milliseconds")
            self.log_file.write(
                f"{ts},{speed:.2f},{speed_kmh:.1f},{error:.2f},"
                f"{self.current_brake:.0f},{accel_x:.3f},{self.decel_boost:.1f}\n")
            self.log_file.flush()

        return speed, speed_kmh, self.current_brake

    def run(self):
        global running

        print(f"{'='*50}")
        print(f"  ASMILE SPEED LIMITER")
        print(f"{'='*50}")
        print(f"Max speed: {self.max_kmh:.0f} km/h ({self.max_speed_ms:.1f} m/s)")
        print(f"{'DRY RUN' if self.dry_run else 'ACTIVE'}")
        print(f"Ctrl+C to stop\n")

        while running:
            speed, kmh, brake = self.step()

            if self.brake_active:
                print(f"\r  {kmh:.1f} km/h | BRAKE {brake:.0f}°  ", end="", flush=True)
            elif speed > 0.3:
                print(f"\r  {kmh:.1f} km/h | OK           ", end="", flush=True)

            time.sleep(1.0 / CONTROL_HZ)

        # Release brake on exit
        set_brake(0, self.dry_run, self.gpio_handle)
        if self.log_file:
            self.log_file.close()
        print(f"\n\nSpeed limiter stopped.")

    def __del__(self):
        if self.log_file:
            self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Asmile Speed Limiter")
    parser.add_argument("--max-speed", type=float, default=DEFAULT_MAX_KMH,
                        help=f"Max speed in km/h (default: {DEFAULT_MAX_KMH})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    limiter = SpeedLimiter(max_kmh=args.max_speed, dry_run=args.dry_run)
    limiter.run()


if __name__ == "__main__":
    main()
