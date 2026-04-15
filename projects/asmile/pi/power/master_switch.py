#!/usr/bin/env python3
"""
Asmile Master Switch — GPIO toggle controls system state.

Physical switch between GPIO 17 (Pin 11) and GND (Pin 9).
  - Switch ON  (closed, GPIO LOW):  unlock brake, start logging/recording
  - Switch OFF (open, GPIO HIGH):   lock brake (full braking), stop logging

Wiring:
  GPIO 17 (Pin 11) ──── switch ──── GND (Pin 9)
  Internal pull-up: pin reads HIGH when switch open, LOW when closed.

Future: same switch will toggle autonomous driving instead of logging.

Install as service:
  sudo cp master_switch.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now master_switch.service
"""

import lgpio
import time
import subprocess
import sys
import os

# --- Config ---
GPIO_CHIP = 4          # Pi 5 = gpiochip4
SWITCH_PIN = 17        # GPIO 17, Pin 11
DEBOUNCE_MS = 300      # debounce time
CHECK_INTERVAL = 0.1   # 100ms poll

# Servo (for brake lock)
PIN_SERVO = 12
SERVO_FREQ = 330
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ
BRAKE_ANGLE = 88       # full brake when OFF
RELEASE_ANGLE = 0      # released when ON


def angle_to_duty(angle: float) -> float:
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


class MasterSwitch:
    def __init__(self):
        self.h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_input(self.h, SWITCH_PIN, lgpio.SET_PULL_UP)
        self.active = False  # current state: True = ON
        self.servofreno_was_running = False

    def read_switch(self) -> bool:
        """Returns True if switch is ON (closed, LOW)."""
        return lgpio.gpio_read(self.h, SWITCH_PIN) == 0

    def activate(self):
        """Switch turned ON — unlock brake, start logging."""
        if self.active:
            return
        self.active = True
        print("[SWITCH] ON — unlocking brake, starting services")

        # Release brake servo
        lgpio.tx_pwm(self.h, PIN_SERVO, SERVO_FREQ, angle_to_duty(RELEASE_ANGLE))
        time.sleep(0.5)
        lgpio.tx_pwm(self.h, PIN_SERVO, 0, 0)  # stop PWM, let servofreno take over

        # Start servofreno server (if not running)
        result = subprocess.run(["systemctl", "is-active", "servofreno.service"],
                                capture_output=True, text=True)
        if result.stdout.strip() != "active":
            subprocess.run(["systemctl", "start", "servofreno.service"])
            print("[SWITCH] servofreno started")
        else:
            print("[SWITCH] servofreno already running")

    def deactivate(self):
        """Switch turned OFF — lock brake, stop logging."""
        if not self.active:
            return
        self.active = False
        print("[SWITCH] OFF — locking brake, stopping services")

        # Stop servofreno server
        subprocess.run(["systemctl", "stop", "servofreno.service"],
                        capture_output=True)
        print("[SWITCH] servofreno stopped")

        # Lock brake at full angle
        lgpio.tx_pwm(self.h, PIN_SERVO, SERVO_FREQ, angle_to_duty(BRAKE_ANGLE))
        print(f"[SWITCH] Brake locked at {BRAKE_ANGLE}°")

    def cleanup(self):
        lgpio.tx_pwm(self.h, PIN_SERVO, 0, 0)
        lgpio.gpiochip_close(self.h)


def main():
    sw = MasterSwitch()

    print("=" * 50)
    print("  ASMILE MASTER SWITCH")
    print("=" * 50)
    print(f"GPIO {SWITCH_PIN} (Pin 11) — pull-up, switch to GND (Pin 9)")
    print(f"ON  = brake released, servofreno active")
    print(f"OFF = brake locked at {BRAKE_ANGLE}°, servofreno stopped")

    # Read initial state
    initial = sw.read_switch()
    print(f"Initial state: {'ON' if initial else 'OFF'}")

    if initial:
        sw.activate()
    else:
        sw.deactivate()

    last_state = initial
    last_change = time.monotonic()

    try:
        while True:
            current = sw.read_switch()

            if current != last_state:
                now = time.monotonic()
                if (now - last_change) * 1000 >= DEBOUNCE_MS:
                    last_state = current
                    last_change = now
                    if current:
                        sw.activate()
                    else:
                        sw.deactivate()

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n[SWITCH] Stopped")
    finally:
        sw.cleanup()


if __name__ == "__main__":
    main()
