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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sensors"))
try:
    from actuator_log import log_cmd     # pulse freno all'ON/OFF nel log uscite (stesso ms del hub)
except Exception:                        # master_switch non deve MAI fermarsi per il log
    def log_cmd(*a, **k):
        return None

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
BRAKE_ANGLE = 50       # massimo freno (23/11: 50°, non più 60); all'OFF si usa OFF_ANGLE = 0
RELEASE_ANGLE = 0      # released when ON (gradi "logici" = raw 180°)
OFF_ANGLE = BRAKE_ANGLE     # 23/11 sera (Daniele): su 0 il freno va a 50° e il pin si libera: la bici resta ferma

# Buzzer (shared con safe_shutdown — GPIO 4 via 2N2222 driver)
BUZZER_PIN = 4


PARK_MAX_HOLD_A = 0.4      # stazionamento: corrente massima a pin libero (servo che non forza)
PARK_MIN_ANGLE = 30        # stazionamento: mai sotto questo angolo arretrando


def _corrente_servo_a():
    """INA219 0x40 (shunt 0,1 ohm): corrente dal registro shunt, 3 letture mediate. None se non risponde."""
    try:
        import smbus2
        b = smbus2.SMBus(1)
        tot = 0.0
        for _ in range(3):
            v = b.read_word_data(0x40, 0x01)
            v = ((v & 0xFF) << 8) | (v >> 8)
            v = v - 65536 if v > 32767 else v
            tot += v * 1e-5 / 0.1
            time.sleep(0.05)
        b.close()
        return abs(tot / 3)
    except Exception:
        return None


def buzzer_sweep(start_freq: int, end_freq: int, step: int = 50, step_time: float = 0.025):
    """Play a frequency sweep on BUZZER_PIN. Auto-detects ascending/descending."""
    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        s = -step if start_freq > end_freq else step
        for f in range(start_freq, end_freq, s):
            lgpio.tx_pwm(h, BUZZER_PIN, f, 50)
            time.sleep(step_time)
        lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)
        lgpio.gpiochip_close(h)
    except Exception:
        pass


def _pin_in_ingresso():
    """24/11: su Pi 5 gpio_free lascia GPIO12 in OUTPUT LOW ('op dl'); il SER0062 vuole il pin davvero libero."""
    subprocess.run(["pinctrl", "set", str(PIN_SERVO), "ip", "pn"], timeout=1, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
        self._limiter_check()
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

    def _limiter_check(self):
        """24/11 (rollback-guardian): se il limiter muore col freno tirato nessuno lo riapre (la guardia di rilascio sta
        dentro il limiter). Limiter morto con master ON -> freno a 0 per 1,5 s, pin in ingresso, avviso. NON lo riavvia
        (Restart=no per scelta: si riaccende col master)."""
        p = getattr(self, "speed_limiter_proc", None)
        if p is None or p.poll() is None:
            return
        print(f"[WATCHDOG] speed_limiter MORTO (codice {p.returncode}): freno a {RELEASE_ANGLE}° e pin libero", flush=True)
        self.speed_limiter_proc = None
        try:
            h = lgpio.gpiochip_open(GPIO_CHIP)
            try:
                lgpio.gpio_free(h, PIN_SERVO)
            except lgpio.error:
                pass
            lgpio.gpio_claim_output(h, PIN_SERVO)
            lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, angle_to_duty(RELEASE_ANGLE))
            time.sleep(1.5)
            lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, 0)
            lgpio.gpio_free(h, PIN_SERVO)
            _pin_in_ingresso()
            lgpio.gpiochip_close(h)
            log_cmd("brake", "pwm", RELEASE_ANGLE, "watchdog: speed_limiter morto, rilascio")
        except Exception as e:
            print(f"[WATCHDOG] rilascio freno fallito: {e!r}", flush=True)
        try:
            with open("/run/speed_limiter_v3.state", "w") as f:
                f.write('{"stato": "CADUTO", "avvisi": ["LIMITER MORTO: freno rilasciato dal master, nessun limite dei 15 km/h"]}')
        except OSError:
            pass
        buzzer_sweep(1500, 600)

    def activate(self, follow_me=False):
        """Switch turned ON — release servo + logging. No speed_limiter (deleted 2026-05-22)."""
        if self.active and self._recorder_is_alive():
            return  # already running and healthy
        # If active but recorder dead, force restart
        self.active = True
        self.follow_me = follow_me
        self.recorder_retries = 0

        # Audio cue: switch ON → sweep ascendente 800→1500Hz
        buzzer_sweep(800, 1500)

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
        log_cmd("brake", "pwm", RELEASE_ANGLE, "master_switch ON: rilascio")
        print(f"[SWITCH] Servo → {RELEASE_ANGLE}° (release, 1.5s di pulse @ {SERVO_FREQ}Hz)")
        time.sleep(1.5)
        lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, 0)  # ferma PWM (duty 0)
        lgpio.gpio_free(h, PIN_SERVO)              # rilascia pin
        _pin_in_ingresso()                          # davvero hi-Z (Pi 5: gpio_free lascia LOW)
        log_cmd("brake", "free", RELEASE_ANGLE, "master_switch ON")
        lgpio.gpiochip_close(h)
        self.servo_handle = None
        print("[SWITCH] PWM stopped, pin freed (hi-Z) — servo libero")

        # 23/11 sera (Daniele): speed_limiter v3 ATTIVO (comanda il freno, max 50°, anti-impuntata) e registra ogni ciclo in
        # /data/logging/limiter_v3/attivo_*.csv. Il vecchio speed_limiter.py NON parte più.
        sl_dir = f"{HOME_DIR}/wip/Moving-One-Billion-People-/projects/asmile/pi/autonomous"
        self.speed_limiter_proc = subprocess.Popen(
            ["python3", "-u", "-m", "speed_limiter_v3.hw"],
            cwd=sl_dir,
            stdout=open("/tmp/speed_limiter_v3.log", "w"),
            stderr=subprocess.STDOUT,
        )
        print(f"[SWITCH] speed_limiter v3 ATTIVO started PID={self.speed_limiter_proc.pid}")

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

        # Audio cue: switch OFF → sweep discendente 1500→800Hz
        buzzer_sweep(1500, 800)
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

        # Switch OFF: freno a 50° (OFF_ANGLE) per tenere ferma la bici, pulse 1.5s, poi pin libero (hi-Z). A 50° il servo
        # tiene 0,03-0,16 A a pin libero (misura INA 23/11); a 60 andava in stallo >3,2 A. Niente LOW continuo.
        h2 = lgpio.gpiochip_open(GPIO_CHIP)
        try:
            lgpio.gpio_free(h2, PIN_SERVO)
        except lgpio.error:
            pass
        lgpio.gpio_claim_output(h2, PIN_SERVO)
        lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, angle_to_duty(OFF_ANGLE))
        log_cmd("brake", "pwm", OFF_ANGLE, "master_switch OFF: freno di stazionamento")
        print(f"[SWITCH] Freno → {OFF_ANGLE}° (stazionamento, 1.5s di pulse @ {SERVO_FREQ}Hz), poi pin libero")
        time.sleep(1.5)
        lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, 0)
        time.sleep(0.05)
        lgpio.gpio_free(h2, PIN_SERVO)
        _pin_in_ingresso()
        log_cmd("brake", "free", OFF_ANGLE, "master_switch OFF")
        # 23/11: a pin libero il SER0062 tiene la posizione da solo; se spinge contro l'olio resta in stallo per ore
        # (misura INA: a 50° a volte 0,03 A, a volte 1,3 A). Guardia: finché la corrente a pin libero è sopra 0,4 A,
        # arretra di 2° (mai sotto PARK_MIN_ANGLE). Senza INA si resta a OFF_ANGLE.
        ang = OFF_ANGLE
        for _ in range(12):
            i_a = _corrente_servo_a()
            if i_a is None or i_a < PARK_MAX_HOLD_A or ang - 2 < PARK_MIN_ANGLE:
                break
            ang -= 2
            lgpio.gpio_claim_output(h2, PIN_SERVO)
            lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, angle_to_duty(ang))
            time.sleep(0.5)
            lgpio.tx_pwm(h2, PIN_SERVO, SERVO_FREQ, 0)
            time.sleep(0.05)
            lgpio.gpio_free(h2, PIN_SERVO)
            _pin_in_ingresso()
            time.sleep(0.3)
            log_cmd("brake", "free", ang, "master_switch OFF: arretro (corrente %.2f A)" % i_a)
            print(f"[SWITCH] stazionamento: corrente {i_a:.2f} A a pin libero -> arretro a {ang}°")
        lgpio.gpiochip_close(h2)
        self.servo_handle = None
        print("[SWITCH] PWM stopped, pin freed (hi-Z) — servo libero, niente segnale")

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
    print(f"OFF        = freno a {OFF_ANGLE}° (stazionamento) e pin libero, all stopped")

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
