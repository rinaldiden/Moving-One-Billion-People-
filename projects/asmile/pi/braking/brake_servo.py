#!/usr/bin/env python3
"""
Asmile Braking — Raspberry Pi 5
Controls hydraulic disc brake servo with realistic braking profile.

Converted from: firmware/braking/brake_servo_test.ino

Raspi 5 Wiring:
  GPIO 12 (PWM0) → Servo signal (white/orange wire)
  GND (Pin 14)   → Servo GND + 6V power supply GND
  External 6V supply → Servo +V (red wire)

Dependencies:
  sudo apt install python3-lgpio
"""

import lgpio
import time

# --- Config ---
GPIO_CHIP = 4       # Pi 5 = gpiochip4
PIN_SERVO = 12      # GPIO 12 = hardware PWM0

# Servo timing
SERVO_FREQ = 50          # 50Hz = 20ms period
PULSE_MIN_US = 500       # 0°
PULSE_MAX_US = 2500      # 180°

# Braking parameters (same as Arduino sketch)
CENTER = 0
MEDIUM_TRAVEL = 85                         # Medium braking degrees
FAST_DEGREES = MEDIUM_TRAVEL - 29          # 56° fast phase
SUPER_FAST_DELAY = 0.001                   # 1 ms/degree
SOFT_BRAKE_DELAY = 0.060                   # 60 ms/degree
REPETITIONS = 500


def angle_to_duty(angle: int) -> float:
    """Convert angle (0-180) to duty cycle % for 50Hz servo."""
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / 20000.0) * 100.0


class Servo:
    """Servo wrapper on lgpio hardware PWM."""

    def __init__(self, h, pin):
        self.h = h
        self.pin = pin
        self.angle = 0

    def write(self, angle: int):
        self.angle = max(0, min(180, angle))
        lgpio.tx_pwm(self.h, self.pin, SERVO_FREQ, angle_to_duty(self.angle))

    def read(self) -> int:
        return self.angle

    def stop(self):
        lgpio.tx_pwm(self.h, self.pin, 0, 0)


def move_servo(servo, target: int, delay_per_deg: float):
    """Move servo degree by degree with constant delay."""
    current = servo.read()
    step = 1 if target > current else -1
    while current != target:
        current += step
        servo.write(current)
        time.sleep(delay_per_deg)


def realistic_braking(servo, target: int, fast_degrees: int, max_delay: float):
    """Two-phase braking: quick snap + progressive."""
    current = servo.read()
    direction = 1 if target > current else -1
    total_degrees = abs(target - current)
    fast_degrees = min(fast_degrees, total_degrees)

    # Phase 1: quick snap (mechanical play recovery)
    if fast_degrees > 0:
        fast_end = current + direction * fast_degrees
        print(f"  → Quick snap (first {fast_degrees}°)")
        while current != fast_end:
            current += direction
            servo.write(current)
            time.sleep(SUPER_FAST_DELAY)

    # Phase 2: progressive (modulated braking)
    brake_degrees = total_degrees - fast_degrees
    if brake_degrees > 0:
        print(f"  → Progressive ({brake_degrees}°)")
        for i in range(brake_degrees):
            progress = i / max(1, brake_degrees - 1)
            delay = SUPER_FAST_DELAY + progress * (max_delay - SUPER_FAST_DELAY)
            current += direction
            servo.write(current)
            time.sleep(delay)


def perform_brake(servo):
    """Execute a full cycle: brake + release."""
    target = CENTER + MEDIUM_TRAVEL
    print(f"MEDIUM BRAKE: +{MEDIUM_TRAVEL}°")
    realistic_braking(servo, target, FAST_DEGREES, SOFT_BRAKE_DELAY)
    print(f"Brake engaged ({target}°)")
    time.sleep(1.0)

    print("Quick release")
    move_servo(servo, CENTER, SUPER_FAST_DELAY)
    time.sleep(1.5)


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    servo = Servo(h, PIN_SERVO)

    print(f"=== BICYCLE BRAKE SYSTEM — {REPETITIONS}x MEDIUM BRAKING ===")

    # Zero position
    print("Finding ZERO...")
    servo.write(CENTER)
    time.sleep(1.0)
    print(f"Zero: {CENTER}°")
    time.sleep(2.0)
    print("Lever at ZERO position — Starting brake cycles")

    try:
        for i in range(1, REPETITIONS + 1):
            print(f"--- Brake {i}/{REPETITIONS} ---")
            perform_brake(servo)

        print(f"=== {REPETITIONS} BRAKE CYCLES COMPLETED ===")

    except KeyboardInterrupt:
        print("\nStop — servo at zero position")
        servo.write(CENTER)
        time.sleep(0.5)
    finally:
        servo.stop()
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
