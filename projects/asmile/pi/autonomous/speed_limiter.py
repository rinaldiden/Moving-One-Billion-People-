#!/usr/bin/env python3
"""
Speed limiter — mantiene 8-10 km/h via servofreno DFRobot SER0062.

Lanciato da master_switch quando switch va su 1, killato quando va a 0.

Architettura:
  - GPS in thread: legge NMEA da /dev/ttyAMA3, mantiene (speed, fix) shared.
  - IMU sync: legge accel_x da MPU6050 (0x68) ad ogni tick.
  - Loop 50Hz: fonde GPS+IMU, calcola PID + feed-forward, applica slew,
    pilota servo a 50Hz (DFRobot SER0062, pulse-and-free pattern).
  - Anti-spike GPS: rifiuta delta > 2.5 m/s tra due tick.
  - Feed-forward sulla decel naturale (stimata online quando freno è OFF).
  - CSV log a 10Hz in ~/wip/logging/speed_limiter/.

Costanti tunables in cima al file.
"""
import csv
import math
import os
import signal
import struct
import sys
import threading
import time
from collections import deque
from datetime import datetime

import lgpio
import serial
import smbus2

# ─── Target ───────────────────────────────────────────────────────────
TARGET_KMH = 10.0       # ceiling: sopra → adattivo per riportare a target
ACTIVATE_KMH = 7.0      # sotto → FREE, brake rilasciato

# ─── Controller adattivo (no mappa fissa angolo) ─────────────────────
# Brake_cmd cresce/cala in base alla decelerazione MISURATA dall'IMU.
STEP_UP_DEG_S = 12.0    # quanto cresce il brake/sec se NON sto decelerando
STEP_DOWN_DEG_S = 25.0  # quanto rilascio il brake/sec se decel OK o speed cala
DECEL_OK_MS2 = 0.30     # decel "sufficiente" (m/s² positivi)
DECEL_EWMA = 0.20       # smoothing accel_x dell'IMU (alpha)

# ─── Servo (DFRobot SER0062, 50Hz pulse-and-free) ────────────────────
GPIO_CHIP = 0
SERVO_PIN = 12
SERVO_FREQ = 50
PWM_PULSE_MIN_US = 500
PWM_PULSE_MAX_US = 2500
PWM_PERIOD_US = 1_000_000 / SERVO_FREQ
BRAKE_MAX_ANGLE = 60    # mai oltre: idraulico inchioda
BRAKE_PWM_ON_THRESHOLD = 2.0   # sotto questo angolo → free pin (hi-Z), risparmio

# ─── Loop ─────────────────────────────────────────────────────────────
CONTROL_HZ = 50
DT = 1.0 / CONTROL_HZ
LOG_HZ = 10
LOG_EVERY = CONTROL_HZ // LOG_HZ

# ─── PID (su error in m/s, output in gradi) ───────────────────────────
KP = 12.0
KI = 4.0
KD = 1.5
INTEGRAL_LIMIT = 15.0   # anti-windup (in unità di output, gradi)

# ─── Feed-forward ─────────────────────────────────────────────────────
FF_GAIN = 30.0          # gradi per m/s² di decel extra richiesta
FF_HORIZON_S = 1.0      # tempo "obiettivo" in cui tornare a target

# ─── Slew rate ────────────────────────────────────────────────────────
SLEW_MAX_DEG_PER_S = 200.0   # 4° per tick a 50Hz

# ─── GPS ──────────────────────────────────────────────────────────────
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400
GPS_STATE_FILE = "/tmp/gps_state.json"   # condiviso con altri consumer
GPS_FIX_TIMEOUT_S = 3.0
GPS_SPIKE_MAX_DELTA_MS = 2.5

# ─── BLE Coospo (solo logging, non controllo) ─────────────────────────
BLE_SPEED_FILE = "/tmp/bike_speed"
BLE_FRESH_S = 3.0

# ─── IMU ──────────────────────────────────────────────────────────────
IMU_BUS = 1
IMU_ADDR = 0x68
IMU_PWR_MGMT_1 = 0x6B
IMU_ACCEL_XOUT_H = 0x3B
IMU_ACCEL_SCALE = 16384.0   # ±2g range LSB/g

# ─── Logging ──────────────────────────────────────────────────────────
LOG_DIR = os.path.expanduser("~/wip/logging/speed_limiter")


# ══════════════════════════════════════════════════════════════════════
# GPS reader (thread)
# ══════════════════════════════════════════════════════════════════════
class GPSReader:
    def __init__(self):
        self._lock = threading.Lock()
        self._speed_ms = 0.0
        self._fix = False
        self._last_update = 0.0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = True

    def start(self):
        self._thread.start()

    def stop(self):
        self._running = False

    def get(self):
        """Returns (speed_ms, fix_valid). fix_valid=False se sample > 3s."""
        with self._lock:
            stale = (time.monotonic() - self._last_update) > GPS_FIX_TIMEOUT_S
            if stale:
                return 0.0, False
            return self._speed_ms, self._fix

    def _publish_json(self):
        """Scrivi state condiviso per consumer esterni (es. training_recorder)."""
        try:
            import json
            tmp = GPS_STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump({
                    "speed_ms": self._speed_ms,
                    "fix": self._fix,
                    "ts": self._last_update,
                }, f)
            os.replace(tmp, GPS_STATE_FILE)
        except OSError:
            pass

    def _run(self):
        ser = None
        while self._running:
            try:
                if ser is None:
                    ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.1)
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if not line.startswith("$") or "RMC" not in line:
                    continue
                parts = line.split(",")
                if len(parts) < 8:
                    continue
                status = parts[2]   # A=valid, V=void
                fix = (status == "A")
                speed_knots = float(parts[7]) if parts[7] else 0.0
                speed_ms = speed_knots * 0.514444
                with self._lock:
                    self._fix = fix
                    self._speed_ms = speed_ms if fix else 0.0
                    self._last_update = time.monotonic()
                self._publish_json()
            except (serial.SerialException, OSError, ValueError):
                if ser:
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                time.sleep(0.5)


# ══════════════════════════════════════════════════════════════════════
# BLE Coospo speed reader (file polling, log-only)
# ══════════════════════════════════════════════════════════════════════
def _read_ble_speed():
    """Returns (speed_ms, fresh_bool). False se file mancante o stale."""
    try:
        st = os.stat(BLE_SPEED_FILE)
        if time.time() - st.st_mtime > BLE_FRESH_S:
            return 0.0, False
        with open(BLE_SPEED_FILE) as f:
            return float(f.readline().strip().split()[0]), True
    except (FileNotFoundError, ValueError, IndexError, OSError):
        return 0.0, False


# ══════════════════════════════════════════════════════════════════════
# IMU (sync)
# ══════════════════════════════════════════════════════════════════════
class IMU:
    def __init__(self):
        self._bus = smbus2.SMBus(IMU_BUS)
        self._bus.write_byte_data(IMU_ADDR, IMU_PWR_MGMT_1, 0x00)  # wake
        time.sleep(0.02)

    def accel_x(self):
        """Returns longitudinal accel in g. Asse X = direzione marcia (-decel)."""
        try:
            h = self._bus.read_byte_data(IMU_ADDR, IMU_ACCEL_XOUT_H)
            l = self._bus.read_byte_data(IMU_ADDR, IMU_ACCEL_XOUT_H + 1)
            raw = struct.unpack(">h", bytes([h, l]))[0]
            return raw / IMU_ACCEL_SCALE
        except OSError:
            return 0.0


# ══════════════════════════════════════════════════════════════════════
# Servo (DFRobot SER0062, 50Hz pulse-and-free)
# ══════════════════════════════════════════════════════════════════════
def angle_to_duty(angle: float) -> float:
    """0° logico = release massimo (raw 180°). 60° = freno (raw 120°)."""
    raw = 180.0 - angle
    pulse_us = PWM_PULSE_MIN_US + (raw / 180.0) * (PWM_PULSE_MAX_US - PWM_PULSE_MIN_US)
    return (pulse_us / PWM_PERIOD_US) * 100.0


class Servo:
    """
    Pilota DFRobot SER0062 con pattern PULSE-AND-FREE corretto:

      - Quando l'angolo target CAMBIA di >= PULSE_TRIGGER_DEG → invia un nuovo pulse
        (claim_output se necessario + tx_pwm @ 50Hz con la nuova duty)
      - Mantiene il PWM attivo per PULSE_HOLD_S (tempo per il servo di raggiungere
        la posizione comandata)
      - Poi tx_pwm(0) + gpio_free → pin hi-Z. Il servo brushless ha pulse-lock
        interno e mantiene meccanicamente la posizione.
      - Se l'angolo cambia ancora prima dei 150ms, ri-tira il pulse con la
        nuova duty (non blocca, NO time.sleep nel loop).

    Logga su stdout OGNI azione GPIO: claim, tx_pwm (con duty/angle/freq), free.
    """

    PULSE_TRIGGER_DEG = 1.0    # delta angolo che fa scattare nuovo pulse
    PULSE_HOLD_S = 0.15        # quanto tengo il PWM attivo (servo raggiunge target)
    # NIENTE refresh periodico: il SER0062 ha pulse-lock interno,
    # ri-pulsare a parità di angolo lo fa "twitchare" inutilmente

    def __init__(self):
        self._chip = lgpio.gpiochip_open(GPIO_CHIP)
        self._log(f"chip_open(chip={GPIO_CHIP})")
        self._claimed = False
        self._pulse_start = 0.0
        self._last_pulsed_angle = -999.0

    def _log(self, msg):
        print(f"[SERVO {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}",
              flush=True)

    def tick(self, angle: float):
        """Chiamato dal control loop a 50Hz con l'angolo TARGET.
        Decide se serve un nuovo pulse o se rilasciare il pin."""
        angle = max(0.0, min(BRAKE_MAX_ANGLE, angle))
        now = time.monotonic()

        delta = abs(angle - self._last_pulsed_angle)

        # 1) Trigger nuovo pulse SOLO se l'angolo cambia significativamente
        if delta >= self.PULSE_TRIGGER_DEG:
            if not self._claimed:
                try:
                    lgpio.gpio_free(self._chip, SERVO_PIN)
                except lgpio.error:
                    pass
                lgpio.gpio_claim_output(self._chip, SERVO_PIN)
                self._claimed = True
                self._log(f"claim_output(pin={SERVO_PIN})")
            duty = angle_to_duty(angle)
            lgpio.tx_pwm(self._chip, SERVO_PIN, SERVO_FREQ, duty)
            self._log(f"tx_pwm(pin={SERVO_PIN}, freq={SERVO_FREQ}Hz, "
                      f"duty={duty:.2f}%, angle={angle:.2f}°) [Δ{delta:+.1f}°]")
            self._last_pulsed_angle = angle
            self._pulse_start = now
            return

        # 2) Se sto ancora pulsando ma il tempo di hold è scaduto → free pin
        if self._claimed and (now - self._pulse_start) >= self.PULSE_HOLD_S:
            lgpio.tx_pwm(self._chip, SERVO_PIN, SERVO_FREQ, 0.0)
            self._log(f"tx_pwm(pin={SERVO_PIN}, duty=0%) — stop PWM (hold done @ {angle:.2f}°)")
            lgpio.gpio_free(self._chip, SERVO_PIN)
            self._claimed = False
            self._log(f"gpio_free(pin={SERVO_PIN}) — pin hi-Z, servo mantiene posizione")

    def shutdown(self):
        if self._chip is not None:
            try:
                if self._claimed:
                    lgpio.tx_pwm(self._chip, SERVO_PIN, SERVO_FREQ, 0.0)
                    time.sleep(0.02)
                    lgpio.gpio_free(self._chip, SERVO_PIN)
                lgpio.gpiochip_close(self._chip)
            except Exception:
                pass
            self._chip = None
            self._claimed = False


# ══════════════════════════════════════════════════════════════════════
# Controller
# ══════════════════════════════════════════════════════════════════════
class SpeedLimiter:
    def __init__(self):
        self.gps = GPSReader()
        self.imu = IMU()
        self.servo = Servo()

        self.target_ms = TARGET_KMH / 3.6
        self.activate_ms = ACTIVATE_KMH / 3.6

        self.prev_gps_speed = 0.0
        self.imu_speed = 0.0   # integratore IMU per fallback senza fix
        self.speed_history = deque(maxlen=5)   # median smoothing

        # Stato controller adattivo
        self.brake_cmd = 0.0       # gradi attualmente comandati al servo
        self.decel_filtered = 0.0  # m/s² (positivo = sto rallentando), EWMA da IMU
        self.natural_decel = 0.0   # placeholder, non più usato in controllo

        # Loop state
        self.prev_speed = 0.0
        self.tick = 0

        # Log
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f"limiter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self.log_f = open(log_path, "w", newline="")
        self.log = csv.writer(self.log_f)
        self.log.writerow([
            "timestamp_iso", "gps_speed_ms", "imu_speed_ms", "fused_speed_ms",
            "fix", "source", "accel_x_g", "natural_decel_ms2",
            "error_ms", "pid_p", "pid_i", "pid_d", "ff_brake_deg",
            "target_brake_deg", "brake_cmd_deg", "zone",
            "ble_speed_ms", "ble_fresh",
        ])
        print(f"[LIMITER] log: {log_path}", flush=True)

        # Stop flag
        self.running = True
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

    def _on_signal(self, *_):
        self.running = False

    # ─── Fusione velocità ─────────────────────────────────────────────
    def _read_speed(self):
        gps_raw, fix = self.gps.get()

        # Anti-spike GPS
        if fix:
            if abs(gps_raw - self.prev_gps_speed) > GPS_SPIKE_MAX_DELTA_MS:
                gps_raw = self.prev_gps_speed   # rigetta spike
            else:
                self.prev_gps_speed = gps_raw

        return gps_raw, fix

    def _fuse(self, gps_speed, fix, accel_x):
        # Integrazione IMU come backup
        self.imu_speed += -accel_x * 9.81 * DT
        self.imu_speed = max(0.0, self.imu_speed * 0.995)   # damping leggero

        if fix:
            self.imu_speed = gps_speed   # ri-sincronizza
            self.speed_history.append(gps_speed)
            source = "gps"
        elif self.imu_speed > 0.5:
            self.speed_history.append(self.imu_speed)
            source = "imu"
        else:
            self.speed_history.append(0.0)
            source = "zero"

        # Median smoothing (5 sample = 100ms a 50Hz)
        smoothed = sorted(self.speed_history)[len(self.speed_history) // 2]
        return smoothed, source

    # ─── Controller adattivo ──────────────────────────────────────────
    def _compute_target(self, speed, accel_x):
        """Aggiorna brake_cmd in base a velocità + decel misurata.
        PRIORITÀ: appena la bici sta rallentando (decel positiva O velocità
        in calo) → rilascia veloce. Solo se non rallenta E sono sopra target
        → costruisce il freno."""
        imu_decel = -accel_x * 9.81  # m/s² positivo = sto rallentando
        self.decel_filtered = (1.0 - DECEL_EWMA) * self.decel_filtered + DECEL_EWMA * imu_decel

        # Trend velocità tra tick (m/s²)
        speed_trend = (speed - self.prev_speed) / DT   # negativo = sto calando

        step_up = STEP_UP_DEG_S * DT
        step_down = STEP_DOWN_DEG_S * DT
        speed_kmh = speed * 3.6

        speed_dropping = speed_trend < -0.05      # 0.05 m/s² in 20ms = ~0.5 km/h al secondo
        decel_positive = self.decel_filtered > 0.10   # decel sensibile su IMU

        if speed_kmh < ACTIVATE_KMH:
            # FREE: rilascia velocemente
            new = max(0.0, self.brake_cmd - step_down * 2.0)
            zone = "FREE"
        elif speed_dropping or decel_positive:
            # PRIORITÀ ASSOLUTA: la bici sta già rallentando → rilascia
            # (più aggressivo se decel più forte)
            release_scale = 1.0 + max(0.0, self.decel_filtered / DECEL_OK_MS2)
            new = max(0.0, self.brake_cmd - step_down * release_scale)
            zone = "RELEASE"
        elif speed_kmh > TARGET_KMH:
            # Sopra target E NON sta rallentando → costruisci freno
            scale = min(3.0, 1.0 + (speed_kmh - TARGET_KMH) / 2.0)
            new = self.brake_cmd + step_up * scale
            zone = "OVER"
        else:
            # HYST band 7-10 km/h, non sta rallentando → un pochino di freno
            new = self.brake_cmd + step_up * 0.5
            zone = "HYST"

        new = max(0.0, min(BRAKE_MAX_ANGLE, new))
        return new, self.decel_filtered, (self.decel_filtered, speed_trend, 0.0), zone

    # ─── Slew rate sul comando servo ──────────────────────────────────
    def _slew(self, target):
        delta = target - self.brake_cmd
        max_delta = SLEW_MAX_DEG_PER_S * DT
        delta = max(-max_delta, min(max_delta, delta))
        self.brake_cmd += delta
        self.brake_cmd = max(0.0, min(BRAKE_MAX_ANGLE, self.brake_cmd))

    # ─── Main loop ────────────────────────────────────────────────────
    def run(self):
        self.gps.start()
        print(f"[LIMITER] running. target={TARGET_KMH}km/h activate={ACTIVATE_KMH}km/h "
              f"brake_max={BRAKE_MAX_ANGLE}° slew={SLEW_MAX_DEG_PER_S}°/s",
              flush=True)

        next_tick = time.monotonic()
        try:
            while self.running:
                t0 = time.monotonic()

                gps_speed, fix = self._read_speed()
                accel_x = self.imu.accel_x()
                ble_speed, ble_fresh = _read_ble_speed()
                speed, source = self._fuse(gps_speed, fix, accel_x)

                # Controller adattivo: aggiorna brake_cmd direttamente
                # (no slew separato — il rate limiting è dentro al controller)
                new_brake, decel_meas, (df, _, _), zone = self._compute_target(speed, accel_x)
                self.brake_cmd = new_brake
                self.servo.tick(self.brake_cmd)
                # Alias per log (riusa colonne esistenti)
                target = new_brake
                p = i = d = 0.0
                ff_brake = 0.0
                error = decel_meas

                # Log a 10Hz
                if self.tick % LOG_EVERY == 0:
                    self.log.writerow([
                        datetime.now().isoformat(timespec="milliseconds"),
                        f"{gps_speed:.3f}", f"{self.imu_speed:.3f}", f"{speed:.3f}",
                        1 if fix else 0, source,
                        f"{accel_x:.4f}", f"{self.natural_decel:.3f}",
                        f"{error:.3f}", f"{p:.2f}", f"{i:.2f}", f"{d:.2f}",
                        f"{ff_brake:.2f}",
                        f"{target:.2f}", f"{self.brake_cmd:.2f}", zone,
                        f"{ble_speed:.3f}", 1 if ble_fresh else 0,
                    ])
                    self.log_f.flush()

                self.prev_speed = speed
                self.tick += 1

                # Sleep al prossimo tick
                next_tick += DT
                sleep = next_tick - time.monotonic()
                if sleep > 0:
                    time.sleep(sleep)
                else:
                    next_tick = time.monotonic()   # we slipped, resync
        finally:
            self.shutdown()

    def shutdown(self):
        print("[LIMITER] shutdown", flush=True)
        self.gps.stop()
        # rilascia il freno prima di uscire (un pulse a 0° = release massimo)
        try:
            self.servo.tick(0.0)
            time.sleep(self.servo.PULSE_HOLD_S + 0.05)
            self.servo.tick(0.0)   # secondo tick → trigger free pin
            self.servo.shutdown()
        except Exception:
            pass
        try:
            self.log_f.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
def main():
    SpeedLimiter().run()


if __name__ == "__main__":
    main()
