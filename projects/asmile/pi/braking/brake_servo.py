#!/usr/bin/env python3
"""
Asmile Braking — Raspberry Pi 5
Controls hydraulic disc brake servo (JX PDI-6221MG) with realistic braking profile.

PDI-6221MG specs:
  - Working frequency: 330Hz (NOT 50Hz)
  - Pulse range: 500-2500us (180°)
  - Dead band: 2us
  - Speed at 6V: 0.16 sec/60°
  - Stall torque at 6V: 20.32 kg.cm

Raspi 5 Wiring (via level shifter 3.3V→6V):
  GPIO 12 (PWM0) → Level Shifter LV1 → HV1 → Servo signal (orange)
  GND (Pin 34)   → Level Shifter GND → Servo GND + Pololu F6 GND
  Pololu F6 6V   → Level Shifter HV  + Servo +V (red)
  Raspi 3.3V     → Level Shifter LV

Dependencies:
  sudo apt install python3-lgpio
"""

import lgpio
import time

# --- Config ---
GPIO_CHIP = 4       # Pi 5 = gpiochip4
PIN_SERVO = 12      # GPIO 12 = hardware PWM0

# PDI-6221MG servo timing
SERVO_FREQ = 330         # 330Hz native frequency
PULSE_MIN_US = 500       # 0°
PULSE_MAX_US = 2500      # 180°
PERIOD_US = 1_000_000 / SERVO_FREQ  # ~3030us

# Braking parameters
CENTER = 0
MEDIUM_TRAVEL = 85                         # Medium braking degrees
FAST_DEGREES = MEDIUM_TRAVEL - 29          # 56° fast phase
PROGRESSIVE_STEPS = 6                      # number of steps in progressive phase
HOLD_TIME = 1.0                            # seconds holding brake
RELEASE_TIME = 0.3                         # seconds for full release
PAUSE_TIME = 1.5                           # seconds between cycles
REPETITIONS = 10                           # tuning mode


def angle_to_duty(angle: float) -> float:
    """Convert angle (0-180) to duty cycle % for PDI-6221MG at 330Hz."""
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


class Servo:
    """Servo wrapper on lgpio hardware PWM for PDI-6221MG."""

    def __init__(self, h, pin):
        self.h = h
        self.pin = pin
        self.angle = 0.0

    def write(self, angle: float):
        self.angle = max(0.0, min(180.0, angle))
        lgpio.tx_pwm(self.h, self.pin, SERVO_FREQ, angle_to_duty(self.angle))

    def read(self) -> float:
        return self.angle

    def stop(self):
        lgpio.tx_pwm(self.h, self.pin, 0, 0)


def move_smooth(servo, target: float, duration: float):
    """Move servo smoothly from current to target over duration (seconds).
    Lets the servo interpolate using its native speed, sending position
    updates every servo period (~3ms at 330Hz)."""
    current = servo.read()
    if abs(target - current) < 0.5:
        servo.write(target)
        return

    steps = max(1, int(duration * SERVO_FREQ))
    for i in range(1, steps + 1):
        t = i / steps
        # ease-out cubic: decelerates at end
        t_ease = 1.0 - (1.0 - t) ** 3
        pos = current + (target - current) * t_ease
        servo.write(pos)
        time.sleep(duration / steps)


def perform_brake(servo):
    """Execute a full brake cycle: snap + progressive + hold + release."""
    snap_target = CENTER + FAST_DEGREES
    final_target = CENTER + MEDIUM_TRAVEL

    # Full speed to target — single command, servo runs at max speed
    print(f"  → Full speed to {final_target}°")
    servo.write(final_target)
    # servo speed: 0.16s/60° at 6V → 85° takes ~0.23s
    time.sleep(0.30)

    print(f"  Brake engaged ({final_target}°)")
    time.sleep(HOLD_TIME)

    # Phase 3: release — smooth ease-out back to center
    print(f"  → Release")
    move_smooth(servo, CENTER, RELEASE_TIME)
    time.sleep(PAUSE_TIME)


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    servo = Servo(h, PIN_SERVO)

    print(f"=== BRAKE SYSTEM PDI-6221MG — {REPETITIONS}x MEDIUM BRAKING ===")

    print("Finding ZERO...")
    servo.write(CENTER)
    time.sleep(1.0)
    print(f"Zero: {CENTER}°")
    time.sleep(2.0)
    print("Starting brake cycles")

    try:
        for i in range(1, REPETITIONS + 1):
            print(f"--- Brake {i}/{REPETITIONS} ---")
            perform_brake(servo)

        print(f"=== {REPETITIONS} BRAKE CYCLES COMPLETED ===")

    except KeyboardInterrupt:
        print("\nStop — returning to zero")
        servo.write(CENTER)
        time.sleep(0.5)
    finally:
        servo.stop()
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
