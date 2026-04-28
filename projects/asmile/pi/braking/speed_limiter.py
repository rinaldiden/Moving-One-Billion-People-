#!/usr/bin/env python3
"""
Asmile Speed Limiter — 15 km/h max

Reads GPS speed and applies progressive braking when speed exceeds limit.
Acts on the brake servo to physically slow down the bike.

Braking profile:
  15-17 km/h  → gentle braking (snap to 85°, contact pad)
  17-20 km/h  → medium braking (ramp to 90°)
  > 20 km/h   → full braking (ramp to 95°)
  < 15 km/h   → release brake

NOT EXECUTABLE — prepare only, deploy when ready.
"""

import lgpio
import serial
import time
import threading

# --- Config ---
SPEED_LIMIT_KMH = 15.0
SPEED_GENTLE = 17.0    # gentle brake threshold
SPEED_MEDIUM = 20.0    # medium brake threshold

GPIO_CHIP = 4
PIN_SERVO = 12
SERVO_FREQ = 330
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ

BRAKE_CONTACT = 85     # pad touches disc
BRAKE_GENTLE = 88
BRAKE_MEDIUM = 92
BRAKE_FULL = 95
BRAKE_RELEASE = 0

GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400

CHECK_INTERVAL = 0.2   # 5Hz speed check


def angle_to_duty(angle):
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


class SpeedLimiter:
    def __init__(self):
        self.h = lgpio.gpiochip_open(GPIO_CHIP)
        self.current_angle = 0.0
        self.speed_kmh = 0.0
        self._running = False
        self._gps_thread = None

    def _servo_write(self, angle):
        angle = max(0.0, min(180.0, angle))
        self.current_angle = angle
        lgpio.tx_pwm(self.h, PIN_SERVO, SERVO_FREQ, angle_to_duty(angle))

    def _servo_stop_pwm(self):
        lgpio.tx_pwm(self.h, PIN_SERVO, 0, 0)

    def _parse_rmc(self, sentence):
        parts = sentence.split(",")
        if len(parts) < 12 or parts[2] != "A":
            return None
        speed_knots = float(parts[7]) if parts[7] else 0.0
        return speed_knots * 1.852

    def _gps_reader(self):
        try:
            ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1.0)
        except Exception as e:
            print(f"[speed_limiter] GPS error: {e}")
            return

        while self._running:
            try:
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if "RMC" in line and line.startswith("$"):
                    speed = self._parse_rmc(line)
                    if speed is not None:
                        self.speed_kmh = speed
            except Exception:
                pass

    def _compute_brake_angle(self, speed):
        if speed <= SPEED_LIMIT_KMH:
            return BRAKE_RELEASE

        if speed <= SPEED_GENTLE:
            # Proportional between contact and gentle
            ratio = (speed - SPEED_LIMIT_KMH) / (SPEED_GENTLE - SPEED_LIMIT_KMH)
            return BRAKE_CONTACT + ratio * (BRAKE_GENTLE - BRAKE_CONTACT)

        if speed <= SPEED_MEDIUM:
            ratio = (speed - SPEED_GENTLE) / (SPEED_MEDIUM - SPEED_GENTLE)
            return BRAKE_GENTLE + ratio * (BRAKE_MEDIUM - BRAKE_GENTLE)

        return BRAKE_FULL

    def start(self):
        self._running = True
        self._gps_thread = threading.Thread(target=self._gps_reader, daemon=True)
        self._gps_thread.start()
        print(f"[speed_limiter] Active — limit {SPEED_LIMIT_KMH} km/h")

        try:
            while self._running:
                target = self._compute_brake_angle(self.speed_kmh)

                if target == BRAKE_RELEASE:
                    if self.current_angle > 0:
                        self._servo_write(BRAKE_RELEASE)
                        time.sleep(0.3)
                        self._servo_stop_pwm()
                else:
                    # Snap to contact first, then progressive
                    if self.current_angle < BRAKE_CONTACT:
                        self._servo_write(BRAKE_CONTACT)
                        time.sleep(0.1)
                    self._servo_write(target)

                if self.speed_kmh > SPEED_LIMIT_KMH:
                    print(f"[speed_limiter] {self.speed_kmh:.1f} km/h "
                          f"→ brake {target:.0f}°")

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self._servo_write(BRAKE_RELEASE)
        time.sleep(0.3)
        self._servo_stop_pwm()
        lgpio.gpiochip_close(self.h)
        print("[speed_limiter] Stopped, brake released.")


if __name__ == "__main__":
    limiter = SpeedLimiter()
    limiter.start()
