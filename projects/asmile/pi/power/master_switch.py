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
        """Switch turned ON — start servofreno (it releases the brake on startup)."""
        if self.active:
            return
        self.active = True
        print("[SWITCH] ON — starting servofreno")

        # Release servo GPIO if we were holding it
        if hasattr(self, 'servo_handle') and self.servo_handle:
            lgpio.tx_pwm(self.servo_handle, PIN_SERVO, 0, 0)
            lgpio.gpiochip_close(self.servo_handle)
            self.servo_handle = None
            time.sleep(0.3)

        subprocess.run(["systemctl", "start", "servofreno.service"])
        print("[SWITCH] servofreno started — brake released")

        # Start training recorder as asmile2 (not root — camera needs user access)
        recorder = "/home/asmile2/wip/Moving-One-Billion-People-/projects/asmile/pi/logging/training_recorder.py"
        subprocess.Popen(
            ["sudo", "-u", "asmile2",
             "env", "LD_PRELOAD=/home/asmile2/streaming/arducam_fix.so",
             "python3", "-u", recorder],
            stdout=open("/tmp/recorder.log", "w"),
            stderr=subprocess.STDOUT)
        print("[SWITCH] training recorder started")

    def deactivate(self):
        """Switch turned OFF — stop servofreno, lock brake."""
        if not self.active:
            return
        self.active = False
        print("[SWITCH] OFF — stopping servofreno, locking brake")

        # Stop training recorder
        subprocess.run(["pkill", "-f", "training_recorder.py"], capture_output=True)
        print("[SWITCH] training recorder stopped")

        # Stop servofreno (releases GPIO 12)
        subprocess.run(["systemctl", "stop", "servofreno.service"],
                        capture_output=True)
        time.sleep(0.5)

        # Now we can take GPIO 12 and lock brake
        h2 = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, angle_to_duty(BRAKE_ANGLE))
        print(f"[SWITCH] Brake locked at {BRAKE_ANGLE}°")
        # Keep h2 open so PWM stays active
        self.servo_handle = h2

    def cleanup(self):
        if hasattr(self, 'servo_handle') and self.servo_handle:
            lgpio.tx_pwm(self.servo_handle, PIN_SERVO, 0, 0)
            lgpio.gpiochip_close(self.servo_handle)
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
