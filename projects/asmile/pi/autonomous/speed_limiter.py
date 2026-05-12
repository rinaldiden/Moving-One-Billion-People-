#!/usr/bin/env python3
"""
Asmile Speed Limiter — maintains speed at max 10 km/h with hysteresis braking.

Hysteresis band: 8-10 km/h
- Below 8 km/h: no braking, free ride
- 8-10 km/h: gentle progressive braking to prevent exceeding 10
- Above 10 km/h: stronger braking to bring speed back down
- Never locks the wheel — goal is to MAINTAIN 10 km/h, not stop

Reads GPS speed from servofreno API, controls servo via GPIO direct.

Usage:
  python3 speed_limiter.py                    # default 10 km/h
  python3 speed_limiter.py --max-speed 12     # 12 km/h
  python3 speed_limiter.py --dry-run          # simulate only
"""

import json
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
HYSTERESIS_KMH = 2.0      # start monitoring 2 km/h before limit
CONTROL_HZ = 10
BRAKE_MIN_ANGLE = 0
BRAKE_MAX_ANGLE = 45

# Servo GPIO — direct PWM
GPIO_CHIP = 4
SERVO_PIN = 12
SERVO_FREQ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ


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
    """Convert servo angle (0-180) to PWM duty cycle %."""
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
        self.max_kmh = max_kmh
        self.max_speed_ms = max_kmh / 3.6
        self.hyst_start_kmh = max_kmh - HYSTERESIS_KMH
        self.dry_run = dry_run

        # Brake state
        self.current_brake = 0
        self.brake_active = False
        self._emergency_was_active = False

        # Auto-calibration: learn how much brake angle produces how much decel
        self.brake_gain = 3.0   # initial guess: 3 degrees per km/h over limit
        self.last_speed_kmh = 0
        self.gain_learn_rate = 0.1

        # Speed smoothing (GPS is noisy)
        self.speed_history = []
        self.SMOOTH_WINDOW = 3  # median of last 3 readings

        # GPIO direct for servo
        self.gpio_handle = None
        if not dry_run:
            try:
                import lgpio
                self.gpio_handle = lgpio.gpiochip_open(GPIO_CHIP)
                lgpio.gpio_claim_output(self.gpio_handle, SERVO_PIN)
                set_brake(0, False, self.gpio_handle)
                print("Servo released to 0°")
            except Exception as e:
                print(f"WARNING: GPIO init failed: {e} — brake won't work")

        # Log
        self.log_file = None
        log_dir = os.path.expanduser("~/wip/logging/speed_limiter")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"limiter_{ts}.csv")
        self.log_file = open(log_path, "w")
        self.log_file.write("timestamp,speed_ms,speed_kmh,smoothed_kmh,"
                            "brake_angle,accel_x,zone,fix,brake_gain\n")
        print(f"Log: {log_path}")

    def _smooth_speed(self, speed_ms):
        """Median filter on GPS speed to reduce noise."""
        self.speed_history.append(speed_ms)
        if len(self.speed_history) > self.SMOOTH_WINDOW:
            self.speed_history.pop(0)
        import statistics
        return statistics.median(self.speed_history)

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
        speed_raw, fix = read_gps()
        accel_x = read_imu_accel_x()
        speed = self._smooth_speed(speed_raw)
        speed_kmh = speed * 3.6
        hyst_start_kmh = self.max_kmh - HYSTERESIS_KMH

        # Emergency brake from phone overrides everything
        emergency = self._check_emergency()
        if emergency > 0:
            self.current_brake = set_brake(emergency, self.dry_run, self.gpio_handle)
            self.brake_active = True
            self._emergency_was_active = True
            zone = "EMERGENCY"
            self._log(speed_raw, speed_kmh, accel_x, zone, fix)
            return speed, speed_kmh, self.current_brake

        # Emergency just released — snap to 0 immediately
        if self._emergency_was_active:
            self._emergency_was_active = False
            self.current_brake = set_brake(0, self.dry_run, self.gpio_handle)
            self.brake_active = False
            zone = "RELEASE"
            self._log(speed_raw, speed_kmh, accel_x, zone, fix)
            return speed, speed_kmh, self.current_brake

        # Auto-calibration: observe effect of braking on speed
        if self.brake_active and self.last_speed_kmh > 0:
            speed_delta = speed_kmh - self.last_speed_kmh  # negative = slowing
            if self.current_brake > 2:
                if speed_delta > 0.2:
                    # Braking but speed still rising → need more brake
                    self.brake_gain += self.gain_learn_rate
                elif speed_delta < -1.0:
                    # Braking too hard, slowing too fast → need less brake
                    self.brake_gain -= self.gain_learn_rate
                self.brake_gain = max(1.0, min(15.0, self.brake_gain))

        self.last_speed_kmh = speed_kmh

        # Hysteresis braking — auto-calibrated
        if speed_kmh > self.max_kmh:
            # OVER LIMIT — brake to bring speed back to max
            excess = speed_kmh - self.max_kmh
            brake_angle = excess * self.brake_gain
            brake_angle = max(2, min(BRAKE_MAX_ANGLE, brake_angle))
            self.current_brake = set_brake(brake_angle, self.dry_run, self.gpio_handle)
            self.brake_active = True
            zone = "OVER"

        elif speed_kmh > self.hyst_start_kmh:
            # HYSTERESIS ZONE (8-10 km/h) — gentle, proportional
            ratio = (speed_kmh - self.hyst_start_kmh) / HYSTERESIS_KMH
            brake_angle = ratio * self.brake_gain * 0.5  # half strength in zone
            if brake_angle > 1:
                self.current_brake = set_brake(brake_angle, self.dry_run, self.gpio_handle)
                self.brake_active = True
            else:
                if self.brake_active:
                    self.current_brake = set_brake(0, self.dry_run, self.gpio_handle)
                    self.brake_active = False
            zone = "HYST"

        else:
            # UNDER — release brake
            if self.brake_active:
                self.current_brake = set_brake(0, self.dry_run, self.gpio_handle)
                self.brake_active = False
            zone = "FREE"

        self._log(speed_raw, speed_kmh, accel_x, zone, fix)
        return speed, speed_kmh, self.current_brake

    def _log(self, speed_raw, speed_kmh, accel_x, zone, fix):
        if self.log_file:
            ts = datetime.now().isoformat(timespec="milliseconds")
            smoothed_kmh = speed_kmh
            self.log_file.write(
                f"{ts},{speed_raw:.2f},{speed_raw*3.6:.1f},{smoothed_kmh:.1f},"
                f"{self.current_brake:.0f},{accel_x:.3f},{zone},{1 if fix else 0},"
                f"{self.brake_gain:.2f}\n")
            self.log_file.flush()

    def run(self):
        global running
        hyst_start_kmh = self.max_kmh - HYSTERESIS_KMH

        print(f"{'='*50}")
        print(f"  ASMILE SPEED LIMITER")
        print(f"{'='*50}")
        print(f"Max speed: {self.max_kmh:.0f} km/h ({self.max_speed_ms:.1f} m/s)")
        print(f"Hysteresis: {self.hyst_start_kmh:.0f}-{self.max_kmh:.0f} km/h")
        print(f"Auto-calibration: gain starts at {self.brake_gain:.1f} deg/kmh")
        print(f"{'DRY RUN' if self.dry_run else 'ACTIVE'}")
        print(f"Ctrl+C to stop\n")

        while running:
            speed, kmh, brake = self.step()

            if self.brake_active:
                print(f"\r  {kmh:.1f} km/h | BRAKE {brake:.0f}°  ", end="", flush=True)
            elif speed > 0.3:
                print(f"\r  {kmh:.1f} km/h | OK           ", end="", flush=True)

            time.sleep(1.0 / CONTROL_HZ)

        # Do NOT release brake on exit — master_switch handles brake after stop
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
