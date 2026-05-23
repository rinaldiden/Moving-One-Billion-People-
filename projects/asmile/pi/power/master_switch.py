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
from datetime import datetime

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

# Servo (for brake lock) — DFRobot SER0062 brushless waterproof, 6-8.4V
# 50Hz è lo standard servo. Pulse 500-2500us, dead zone 1us. Stall 5A.
PIN_SERVO = 12
SERVO_FREQ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ
BRAKE_ANGLE = 60       # brake lock when OFF (gradi "logici")
RELEASE_ANGLE = 0      # released when ON (gradi "logici" = raw 180°)


def angle_to_duty(angle: float) -> float:
    # Servo montato invertito: raw 180° = rilasciato, raw 0° = freno pieno.
    # angle "logico": 0 = release, +N = N° di frenata.
    raw = 180.0 - angle
    pulse_us = PULSE_MIN_US + (raw / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
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
        """Start recorder. Uses training_recorder (Camarray) or dual_cam_recorder
        depending on which exists. training_recorder is the default for asmile2."""
        base = f"{HOME_DIR}/wip/Moving-One-Billion-People-/projects/asmile/pi"
        # Camarray HAT (asmile2): training_recorder with LD_PRELOAD
        camarray_recorder = f"{base}/logging/training_recorder.py"
        # Dual separate cams (asmile ID001): dual_cam_recorder
        dualcam_recorder = f"{base}/camera/dual_cam_recorder.py"

        # Check if arducam_fix.so exists = Camarray HAT present
        arducam_fix = f"{HOME_DIR}/streaming/arducam_fix.so"
        if os.path.isfile(arducam_fix):
            recorder = camarray_recorder
            cmd = ["sudo", "-u", ASMILE_USER,
                   "env", f"LD_PRELOAD={arducam_fix}",
                   "python3", "-u", recorder]
        else:
            recorder = dualcam_recorder
            cmd = ["sudo", "-u", ASMILE_USER,
                   "python3", "-u", recorder]

        proc = subprocess.Popen(cmd,
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
        """Switch turned ON — release servo + logging. No speed_limiter (deleted 2026-05-22)."""
        if self.active and self._recorder_is_alive():
            return  # already running and healthy
        # If active but recorder dead, force restart
        self.active = True
        self.follow_me = follow_me
        self.recorder_retries = 0

        # Release: pulse a 0° per 1.5s, poi PWM stop + gpio_free → pin hi-Z.
        # SER0062 brushless: MAI gpio_write LOW continuo dopo PWM (memory:
        # feedback_dfrobot_pulse_lock). Solo pulse-and-free.
        h = lgpio.gpiochip_open(GPIO_CHIP)
        try:
            lgpio.gpio_free(h, PIN_SERVO)   # pulisci stato precedente
        except lgpio.error:
            pass
        lgpio.gpio_claim_output(h, PIN_SERVO)
        lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, angle_to_duty(RELEASE_ANGLE))
        print(f"[SWITCH] Servo → {RELEASE_ANGLE}° (release, 1.5s di pulse @ {SERVO_FREQ}Hz)")
        time.sleep(1.5)
        lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, 0)  # ferma PWM (duty 0)
        lgpio.gpio_free(h, PIN_SERVO)              # rilascia pin → hi-Z
        lgpio.gpiochip_close(h)
        self.servo_handle = None
        print("[SWITCH] PWM stopped, pin freed (hi-Z) — servo libero")

        # Lancia speed_limiter (subprocess root) DOPO il release del servo.
        sl_path = f"{HOME_DIR}/wip/Moving-One-Billion-People-/projects/asmile/pi/autonomous/speed_limiter.py"
        self.speed_limiter_proc = subprocess.Popen(
            ["python3", "-u", sl_path],
            stdout=open("/tmp/speed_limiter.log", "w"),
            stderr=subprocess.STDOUT,
        )
        print(f"[SWITCH] speed_limiter started PID={self.speed_limiter_proc.pid}")

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

    def deactivate(self, force=False):
        """Switch turned OFF — BRAKE FIRST, then stop services."""
        if not self.active and not force:
            return
        self.active = False
        self.recorder_proc = None

        # Ferma speed_limiter PRIMA del pulse di parking (gli evita di combattere col servo)
        if hasattr(self, "speed_limiter_proc") and self.speed_limiter_proc is not None:
            try:
                self.speed_limiter_proc.terminate()
                self.speed_limiter_proc.wait(timeout=2)
            except Exception:
                try:
                    self.speed_limiter_proc.kill()
                except Exception:
                    pass
            self.speed_limiter_proc = None
            print("[SWITCH] speed_limiter stopped")

        # Switch OFF: chiudi il freno, tieni 1.5s, poi PWM off (servo
        # mantiene la posizione meccanicamente). Comportamento originale.
        h2 = lgpio.gpiochip_open(GPIO_CHIP)
        try:
            lgpio.gpio_claim_output(h2, PIN_SERVO)
        except lgpio.error:
            pass
        lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, angle_to_duty(BRAKE_ANGLE))
        print(f"[SWITCH] Brake → {BRAKE_ANGLE}° (1.5s di pulse)")
        time.sleep(1.5)
        lgpio.gpio_write(h2, PIN_SERVO, 0)
        lgpio.gpiochip_close(h2)
        self.servo_handle = None
        print("[SWITCH] PWM off, servo tenuto da attrito meccanico")

        # Clean up the rest
        subprocess.run(["pkill", "-f", "follow_me/main.py"], capture_output=True)
        self._kill_camera_zombies()
        print("[SWITCH] services stopped")

    def cleanup(self):
        if hasattr(self, 'servo_handle') and self.servo_handle:
            try:
                lgpio.gpiochip_close(self.servo_handle)
            except Exception:
                pass
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

    # Switch state log
    SWITCH_LOG = "/tmp/asmile_switch.csv"
    with open(SWITCH_LOG, "a") as f:
        if os.path.getsize(SWITCH_LOG) == 0:
            f.write("timestamp,event,state\n")

    def log_switch(event, state):
        ts = datetime.now().isoformat(timespec="milliseconds")
        with open(SWITCH_LOG, "a") as f:
            f.write(f"{ts},{event},{state}\n")
        print(f"[SWITCH] {ts} {event} → {state}")

    # Read initial state and act
    initial = sw.read_switch()
    log_switch("boot", "ON" if initial else "OFF")

    if initial:
        sw.activate()
    else:
        sw.deactivate(force=True)

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
                        log_switch("switch_on", "ON")
                        sw.activate(follow_me=False)
                        last_state = True
                        last_change = time.monotonic()
                    else:
                        log_switch("switch_off", "OFF")
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
