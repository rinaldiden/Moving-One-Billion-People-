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
TARGET_KMH = 10.0       # ceiling: sopra → PID + FF + base ramp
ACTIVATE_KMH = 7.0      # sotto → FREE. Sopra → rampa lineare fino a HYST_MAX_DEG
HYST_MAX_DEG = 10.0     # angolo del freno raggiunto a TARGET_KMH (rampa lineare)

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

        # PID state
        self.integral = 0.0
        self.prev_speed_for_d = 0.0   # derivative on measurement (no setpoint kick)

        # Feed-forward natural decel estimator
        self.natural_decel = 0.15   # m/s² start (piano, no pendenza)
        self.natural_decel_buf = deque(maxlen=50)   # ~1s a 50Hz

        # Slew rate state
        self.brake_cmd = 0.0   # gradi applicati

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

    # ─── Stima decel naturale (online) ────────────────────────────────
    def _update_natural_decel(self, speed):
        if self.brake_cmd < 0.5 and speed > 1.0:
            d = (self.prev_speed - speed) / DT
            if 0.0 < d < 2.0:   # range sano (no spike, no accel positiva)
                self.natural_decel_buf.append(d)
                self.natural_decel = sum(self.natural_decel_buf) / len(self.natural_decel_buf)

    # ─── Soft ramp + PID + FF ─────────────────────────────────────────
    def _compute_target(self, speed):
        # Zona FREE: sotto activate, nessun comando
        if speed < self.activate_ms:
            self.integral *= 0.9   # decadimento integratore
            self.prev_speed_for_d = speed
            return 0.0, 0.0, (0.0, 0.0, 0.0), "FREE"

        # Rampa lineare 0→HYST_MAX_DEG da ACTIVATE a TARGET (sempre attiva sopra activate)
        ramp_progress = min(1.0, (speed - self.activate_ms) / max(0.001, self.target_ms - self.activate_ms))
        soft_brake = HYST_MAX_DEG * ramp_progress

        # Sotto target: solo rampa soft, niente PID/FF
        if speed <= self.target_ms:
            self.integral *= 0.95   # integratore lento decadimento
            self.prev_speed_for_d = speed
            target = max(0.0, min(BRAKE_MAX_ANGLE, soft_brake))
            return target, 0.0, (0.0, 0.0, 0.0), "HYST"

        # OVER: rampa soft (saturata a HYST_MAX_DEG) + PID + FF
        error = speed - self.target_ms

        self.integral += error * DT
        self.integral = max(-INTEGRAL_LIMIT, min(INTEGRAL_LIMIT, self.integral))
        d_meas = (speed - self.prev_speed_for_d) / DT
        self.prev_speed_for_d = speed

        p = KP * error
        i = KI * self.integral
        d = KD * d_meas
        pid_out = max(0.0, p + i + d)

        # Feed-forward: extra decel richiesta per tornare a target in FF_HORIZON_S
        needed_decel = (speed - self.target_ms) / FF_HORIZON_S
        extra = max(0.0, needed_decel - self.natural_decel)
        ff = FF_GAIN * extra

        target = soft_brake + pid_out + ff
        target = max(0.0, min(BRAKE_MAX_ANGLE, target))
        return target, error, (p, i, d), "OVER"

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
                speed, source = self._fuse(gps_speed, fix, accel_x)

                self._update_natural_decel(speed)
                target, error, (p, i, d), zone = self._compute_target(speed)
                ff_brake = max(0.0, target - max(0.0, p + i + d))
                self._slew(target)
                self.servo.tick(self.brake_cmd)

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
