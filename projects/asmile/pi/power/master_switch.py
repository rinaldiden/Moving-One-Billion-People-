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
import pwd

# --- Config ---
GPIO_CHIP = 4          # Pi 5 = gpiochip4
SWITCH_PIN = 17        # GPIO 17, Pin 11
DEBOUNCE_MS = 300      # debounce time
CHECK_INTERVAL = 0.1   # 100ms poll
WATCHDOG_INTERVAL = 10 # seconds between recorder health checks
RECORDER_MAX_RETRIES = 5
RECORDER_STARTUP_WAIT = 5  # seconds to wait before checking if recorder is alive

# Detect username (asmile or asmile2)
ASMILE_USER = None
for u in ("asmile", "asmile2"):
    try:
        pwd.getpwnam(u)
        ASMILE_USER = u
        break
    except KeyError:
        continue
if not ASMILE_USER:
    ASMILE_USER = "asmile"
HOME_DIR = f"/home/{ASMILE_USER}"

# Servo (for brake lock)
PIN_SERVO = 12
SERVO_FREQ = 330
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ
BRAKE_ANGLE = 95       # full brake when OFF
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
        self.recorder_proc = None
        self.recorder_retries = 0
        self.last_watchdog = 0

    def read_switch(self) -> bool:
        """Returns True if switch is ON (closed, LOW)."""
        return lgpio.gpio_read(self.h, SWITCH_PIN) == 0

    def _kill_camera_zombies(self):
        """Kill any leftover camera processes before starting recorder."""
        subprocess.run(["pkill", "-9", "-f", "training_recorder.py"], capture_output=True)
        subprocess.run(["killall", "-9", "rpicam-vid"], capture_output=True)
        subprocess.run(["killall", "-9", "gst-launch-1.0"], capture_output=True)
        subprocess.run(["fuser", "-k", "/dev/video0"], capture_output=True)
        time.sleep(1.0)
        print("[SWITCH] camera zombies cleaned")

    def _start_recorder(self):
        """Start dual camera recorder, return the Popen object."""
        recorder = f"{HOME_DIR}/wip/Moving-One-Billion-People-/projects/asmile/pi/camera/dual_cam_recorder.py"
        proc = subprocess.Popen(
            ["sudo", "-u", ASMILE_USER,
             "python3", "-u", recorder],
            stdout=open("/tmp/recorder.log", "w"),
            stderr=subprocess.STDOUT)
        return proc

    def _recorder_is_alive(self):
        """Check if recorder process is still running."""
        if self.recorder_proc is None:
            return False
        return self.recorder_proc.poll() is None

    def watchdog_check(self):
        """Called from main loop — restart recorder if it died while switch is ON."""
        if not self.active:
            return
        now = time.monotonic()
        if now - self.last_watchdog < WATCHDOG_INTERVAL:
            return
        self.last_watchdog = now

        if self._recorder_is_alive():
            self.recorder_retries = 0  # healthy, reset counter
            return

        # Recorder is dead
        self.recorder_retries += 1
        if self.recorder_retries > RECORDER_MAX_RETRIES:
            print(f"[WATCHDOG] recorder failed {RECORDER_MAX_RETRIES} times, giving up until next switch cycle")
            return

        print(f"[WATCHDOG] recorder died! Restarting (attempt {self.recorder_retries}/{RECORDER_MAX_RETRIES})")
        self._kill_camera_zombies()
        self.recorder_proc = self._start_recorder()
        time.sleep(RECORDER_STARTUP_WAIT)
        if self._recorder_is_alive():
            print("[WATCHDOG] recorder restarted OK")
        else:
            print("[WATCHDOG] recorder failed to start")

    def activate(self, follow_me=False):
        """Switch turned ON — start servofreno and logging.
        If follow_me=True, also start follow-me cone tracking."""
        if self.active:
            return
        self.active = True
        self.follow_me = follow_me
        self.recorder_retries = 0

        # Release servo GPIO if we were holding it
        if hasattr(self, 'servo_handle') and self.servo_handle:
            lgpio.tx_pwm(self.servo_handle, PIN_SERVO, 0, 0)
            lgpio.gpiochip_close(self.servo_handle)
            self.servo_handle = None
            time.sleep(0.3)

        subprocess.run(["systemctl", "start", "servofreno.service"])
        print("[SWITCH] servofreno started — brake released")

        # Clean up any zombie camera processes
        self._kill_camera_zombies()

        # Start training recorder
        self.recorder_proc = self._start_recorder()
        time.sleep(RECORDER_STARTUP_WAIT)
        if self._recorder_is_alive():
            print("[SWITCH] training recorder started OK")
        else:
            print("[SWITCH] training recorder failed on first try, watchdog will retry")

        self.last_watchdog = time.monotonic()

        if follow_me:
            follow_me_main = f"{HOME_DIR}/wip/Moving-One-Billion-People-/projects/asmile/follow_me/main.py"
            arducam = f"{HOME_DIR}/streaming/arducam_fix.so"
            subprocess.Popen(
                ["sudo", "-u", ASMILE_USER,
                 "env", f"LD_PRELOAD={arducam}",
                 "python3", "-u", follow_me_main],
                stdout=open("/tmp/follow_me.log", "w"),
                stderr=subprocess.STDOUT)
            print("[SWITCH] FOLLOW-ME mode activated!")
        else:
            print("[SWITCH] Normal logging mode")

    def deactivate(self):
        """Switch turned OFF — stop servofreno, lock brake."""
        if not self.active:
            return
        self.active = False
        self.recorder_proc = None
        print("[SWITCH] OFF — stopping servofreno, locking brake")

        # Stop follow-me if running
        subprocess.run(["pkill", "-f", "follow_me/main.py"], capture_output=True)
        # Stop training recorder and ALL video processes
        self._kill_camera_zombies()
        print("[SWITCH] services stopped")

        # Stop servofreno (releases GPIO 12)
        subprocess.run(["systemctl", "stop", "servofreno.service"],
                        capture_output=True)
        time.sleep(0.5)

        # Now we can take GPIO 12 and lock brake
        h2 = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, angle_to_duty(BRAKE_ANGLE))
        print(f"[SWITCH] Brake locked at {BRAKE_ANGLE}°")
        # Wait for servo to reach position, then cut PWM to avoid burnout
        time.sleep(0.5)
        lgpio.tx_pwm(h2, PIN_SERVO, 0, 0)
        lgpio.gpiochip_close(h2)
        self.servo_handle = None
        print("[SWITCH] Servo PWM off (holds mechanically)")

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
    print(f"ON         = brake released, logging active")
    print(f"ON-OFF-ON  = follow-me mode (within 1s)")
    print(f"OFF        = brake locked at {BRAKE_ANGLE}°, all stopped")

    DOUBLE_TAP_WINDOW = 1.0  # seconds to detect ON-OFF-ON

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
                        # ON detected — wait to see if it's a double-tap
                        # (ON now, need to see OFF then ON within DOUBLE_TAP_WINDOW)
                        double_tap = False
                        deadline = time.monotonic() + DOUBLE_TAP_WINDOW
                        while time.monotonic() < deadline:
                            time.sleep(CHECK_INTERVAL)
                            s = sw.read_switch()
                            if not s:
                                # OFF detected — now wait for second ON
                                while time.monotonic() < deadline:
                                    time.sleep(CHECK_INTERVAL)
                                    s2 = sw.read_switch()
                                    if s2:
                                        double_tap = True
                                        break
                                break

                        if double_tap:
                            sw.activate(follow_me=True)
                        else:
                            # Check switch is still ON after the wait
                            if sw.read_switch():
                                sw.activate(follow_me=False)
                            # else: switch went OFF during wait, deactivate
                            else:
                                sw.deactivate()
                        last_state = sw.read_switch()
                        last_change = time.monotonic()
                    else:
                        sw.deactivate()

            # Watchdog: check recorder is alive while switch is ON
            sw.watchdog_check()

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n[SWITCH] Stopped")
    finally:
        sw.cleanup()


if __name__ == "__main__":
    main()
