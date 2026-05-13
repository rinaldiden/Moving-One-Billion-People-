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
HYSTERESIS_KMH = 3.0      # start monitoring at 7 km/h, limit at 10
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


_last_angle = -1  # track last sent angle to avoid re-sending

# INA219 servo current sensor (I2C 0x40) — checks servo is powered before sending PWM
INA219_ADDR = 0x40
_ina219_bus = None
_servo_powered = True  # assume powered if no INA219


def _check_servo_power():
    """Read INA219 to verify servo has voltage. Returns True if powered or no sensor."""
    global _ina219_bus, _servo_powered
    try:
        if _ina219_bus is None:
            import smbus2
            _ina219_bus = smbus2.SMBus(1)
            # Init INA219: calibration register
            _ina219_bus.write_word_data(INA219_ADDR, 0x05, 0x1000)
        # Read bus voltage register (reg 0x02)
        raw = _ina219_bus.read_word_data(INA219_ADDR, 0x02)
        raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
        voltage = (raw >> 3) * 0.004  # 4mV per LSB
        _servo_powered = voltage > 3.0  # servo should be at ~6V
        return _servo_powered
    except Exception:
        _servo_powered = True  # no INA219 = assume powered
        return True


def set_brake(angle, dry_run=False, gpio_handle=None):
    """Set brake servo angle. GPIO direct — only sends PWM when angle changes.
    Checks INA219 first: no PWM if servo not powered."""
    global _last_angle
    angle = max(BRAKE_MIN_ANGLE, min(BRAKE_MAX_ANGLE, int(angle)))
    if dry_run:
        return angle

    if gpio_handle is not None and angle != _last_angle:
        import lgpio
        if angle > 0:
            if _check_servo_power():
                lgpio.tx_pwm(gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(angle))
            else:
                lgpio.tx_pwm(gpio_handle, SERVO_PIN, 0, 0)  # no power = no PWM
                print("WARNING: servo not powered (INA219 < 3V), PWM blocked")
                angle = 0
        else:
            lgpio.tx_pwm(gpio_handle, SERVO_PIN, 0, 0)
        _last_angle = angle
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

        # Adaptive controller state
        self.brake_angle = 0.0  # current commanded angle (float for smooth increments)

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
                # Go to 0°, hold 1.5s for servo to arrive, then cut PWM
                lgpio.tx_pwm(self.gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(0))
                time.sleep(1.5)
                lgpio.tx_pwm(self.gpio_handle, SERVO_PIN, 0, 0)
                print("Servo released to 0°, PWM off")
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
                            "brake_angle,accel_x,zone,fix\n")
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

        # IMU-integrated speed as backup when GPS is down
        dt = 1.0 / CONTROL_HZ
        if not hasattr(self, '_imu_speed'):
            self._imu_speed = 0.0
        # Integrate acceleration (accel_x negative = forward accel on this bike)
        self._imu_speed += -accel_x * 9.81 * dt
        self._imu_speed = max(0, self._imu_speed)  # can't go negative
        # Decay IMU speed slowly (drift correction)
        self._imu_speed *= 0.98

        if fix and speed_raw > 0.1:
            # GPS available: use GPS, sync IMU estimate
            speed = self._smooth_speed(speed_raw)
            self._imu_speed = speed  # reset IMU to GPS
        elif self._imu_speed > 1.0:
            # No GPS fix but IMU says we're moving
            speed = self._imu_speed
        else:
            speed = self._smooth_speed(speed_raw)

        speed_kmh = speed * 3.6

        # IMU boost: if accelerating and already in zone, predict higher
        if accel_x < -0.05 and speed_kmh > 6:
            speed_kmh += abs(accel_x) * 9.81 * 0.5 * 3.6

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

        dt = 1.0 / CONTROL_HZ

        # Adaptive controller: adjusts brake_angle based on speed feedback
        # - Speed too high → increase angle
        # - Speed dropping → hold or decrease angle
        # - Speed OK → decrease angle
        # No fixed mapping — learns from the effect of braking

        if speed_kmh > self.max_kmh:
            # OVER LIMIT — increase brake until speed drops
            self.brake_angle += 2.0  # +2° every 100ms until it works
            self.brake_angle = min(self.brake_angle, BRAKE_MAX_ANGLE)
            self.current_brake = set_brake(int(self.brake_angle), self.dry_run, self.gpio_handle)
            self.brake_active = True
            zone = "OVER"

        elif speed_kmh > self.hyst_start_kmh:
            # HYSTERESIS ZONE — adjust based on trend
            if accel_x < -0.05:
                # Accelerating hard — increase brake
                self.brake_angle += 1.0
            elif accel_x < -0.02:
                # Accelerating slightly — small increase
                self.brake_angle += 0.3
            elif accel_x > 0.05:
                # Decelerating — release faster
                self.brake_angle -= 2.0
            elif accel_x > 0.02:
                # Slowing slightly or stable — release
                self.brake_angle -= 1.0
            else:
                # Steady speed — ease off slowly
                self.brake_angle -= 0.5

            self.brake_angle = max(1, min(BRAKE_MAX_ANGLE, self.brake_angle))
            self.current_brake = set_brake(int(self.brake_angle), self.dry_run, self.gpio_handle)
            self.brake_active = True
            zone = "HYST"

        else:
            # UNDER — reduce brake
            if self.brake_angle > 0:
                self.brake_angle -= 1.0
                self.brake_angle = max(0, self.brake_angle)
                self.current_brake = set_brake(int(self.brake_angle), self.dry_run, self.gpio_handle)
                if self.brake_angle <= 0:
                    self.brake_active = False
            else:
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
                f"{self.current_brake:.0f},{accel_x:.3f},{zone},{1 if fix else 0}\n")
            self.log_file.flush()

    def run(self):
        global running
        hyst_start_kmh = self.max_kmh - HYSTERESIS_KMH

        print(f"{'='*50}")
        print(f"  ASMILE SPEED LIMITER")
        print(f"{'='*50}")
        print(f"Max speed: {self.max_kmh:.0f} km/h ({self.max_speed_ms:.1f} m/s)")
        print(f"Hysteresis: {self.hyst_start_kmh:.0f}-{self.max_kmh:.0f} km/h")
        print(f"Adaptive controller: adjusts brake from GPS+IMU feedback")
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
