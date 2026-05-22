#!/usr/bin/env python3
"""
Asmile Speed Limiter v2 — GPS direct + 50Hz loop + slew rate + feed-forward.

Reads GPS directly from UART (no HTTP), IMU from I2C.
50Hz control loop for smooth servo response.
Slew rate limits servo movement for fluid braking.
Feed-forward estimates natural deceleration to avoid oscillation.

Usage:
  python3 speed_limiter.py                    # default 10 km/h
  python3 speed_limiter.py --max-speed 12     # 12 km/h
  python3 speed_limiter.py --dry-run          # simulate only
"""

import json
import os
import sys
import time
import signal
import argparse
import threading
from datetime import datetime

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Default config
DEFAULT_MAX_KMH = 10.0
HYSTERESIS_KMH = 3.0       # start monitoring at 7 km/h, limit at 10
CONTROL_HZ = 50             # 50Hz control loop (20ms per tick)
BRAKE_MIN_ANGLE = 0
BRAKE_MAX_ANGLE = 65

# Slew rate asimmetrico: engagement dolce, release pronto
MAX_SLEW_RATE_ENGAGE = 100.0   # deg/s — frenata che entra in ~0.6s (no inchioda)
MAX_SLEW_RATE_RELEASE = 400.0  # deg/s — rilascio rapido (< 0.2s)

# Servo GPIO — direct PWM (DFRobot SER0062: 6-8.4V, pulse 500-2500us, dead 1us)
# IMPORTANTE: 50Hz è lo standard servo. Il datasheet NON dichiara compatibilità
# con frequenze > 50Hz. 333Hz può causare jitter, corrente media alta, burnout
# (stall current = 5A @ 6V).
GPIO_CHIP = 4
SERVO_PIN = 12
SERVO_FREQ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ

# GPS UART direct
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400

# Bike BLE speed sensor (CooSpo BK467) — file scritto da bike_speed_reader.py
BIKE_SPEED_FILE = "/tmp/bike_speed"
BIKE_SPEED_MAX_AGE = 3.0   # secondi prima di considerare stale


# ═══════════════════════════════════════════════════════════
# GPS READER — direct UART, background thread
# ═══════════════════════════════════════════════════════════
GPS_STATE_FILE = "/tmp/gps_state.json"


class GPSDirectReader:
    """Reads GPS NMEA from UART directly. No HTTP.

    Publishes state to /tmp/gps_state.json so other processes
    (e.g. training_recorder) can consume GPS without UART contention.
    """

    def __init__(self):
        self.speed_ms = 0.0
        self.lat = 0.0
        self.lon = 0.0
        self.heading = 0.0
        self.fix = False
        self._lock = threading.Lock()
        self._running = False
        self._last_valid = 0
        self._last_publish = 0

    def _publish_state(self):
        # Throttle: publish at most 10Hz
        now = time.monotonic()
        if now - self._last_publish < 0.1:
            return
        self._last_publish = now
        state = {
            "lat": self.lat,
            "lon": self.lon,
            "speed_ms": self.speed_ms,
            "heading": self.heading,
            "fix": bool(self.fix),
            "ts": now,
        }
        try:
            tmp = GPS_STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, GPS_STATE_FILE)
        except OSError:
            pass

    def start(self):
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def get_speed(self):
        """Returns (speed_ms, fix). Non-blocking."""
        with self._lock:
            if time.monotonic() - self._last_valid > 3.0:
                return 0.0, False
            return self.speed_ms, self.fix

    def _nmea_to_decimal(self, value, direction):
        if not value:
            return 0.0
        d = int(float(value) / 100)
        m = float(value) - d * 100
        result = d + m / 60.0
        if direction in ('S', 'W'):
            result = -result
        return result

    def _run(self):
        import serial
        while self._running:
            try:
                ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.1)
                ser.reset_input_buffer()
                empty_count = 0

                while self._running:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    if not line:
                        empty_count += 1
                        if empty_count > 50:  # 5 seconds at 0.1s timeout
                            ser.close()
                            time.sleep(0.5)
                            ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.1)
                            ser.reset_input_buffer()
                            empty_count = 0
                        continue
                    empty_count = 0

                    if not line.startswith("$"):
                        continue

                    try:
                        if "RMC" in line:
                            parts = line.split(",")
                            if len(parts) >= 12:
                                if parts[2] == "A":
                                    speed_knots = float(parts[7]) if parts[7] else 0.0
                                    heading = float(parts[8]) if parts[8] else 0.0
                                    with self._lock:
                                        self.speed_ms = speed_knots * 0.514444
                                        self.heading = heading
                                        self.fix = True
                                        self._last_valid = time.monotonic()
                                        self._publish_state()
                                else:
                                    with self._lock:
                                        self.speed_ms = 0.0
                                        self.fix = False
                                        self._publish_state()

                        elif "GGA" in line:
                            parts = line.split(",")
                            if len(parts) >= 15 and parts[2] and parts[4]:
                                with self._lock:
                                    self.lat = self._nmea_to_decimal(parts[2], parts[3])
                                    self.lon = self._nmea_to_decimal(parts[4], parts[5])
                                    self.fix = int(parts[6]) > 0 if parts[6] else False
                                    self._publish_state()
                    except (ValueError, IndexError):
                        pass

                ser.close()
            except Exception as e:
                print(f"[GPS] Error: {e} — retrying in 1s")
                time.sleep(1)


# ═══════════════════════════════════════════════════════════
# BIKE BLE SPEED READER — file polling (daemon writes /tmp/bike_speed)
# ═══════════════════════════════════════════════════════════
def read_bike_ble_speed():
    """Returns (speed_ms, ok). Non-blocking. ok=False se file mancante/stale/illeggibile."""
    try:
        st = os.stat(BIKE_SPEED_FILE)
        if time.time() - st.st_mtime > BIKE_SPEED_MAX_AGE:
            return 0.0, False
        with open(BIKE_SPEED_FILE) as f:
            line = f.readline().strip()
        speed_ms = float(line.split()[0])
        return speed_ms, True
    except (FileNotFoundError, ValueError, IndexError, OSError):
        return 0.0, False


# ═══════════════════════════════════════════════════════════
# IMU READER — direct I2C
# ═══════════════════════════════════════════════════════════
_imu_bus = None


def read_imu_accel_x():
    """Read longitudinal acceleration from IMU. Direct I2C."""
    global _imu_bus
    try:
        if _imu_bus is None:
            import smbus2
            _imu_bus = smbus2.SMBus(1)
            _imu_bus.write_byte_data(0x68, 0x6B, 0x00)
            time.sleep(0.01)
        h = _imu_bus.read_byte_data(0x68, 0x3B)
        l = _imu_bus.read_byte_data(0x68, 0x3C)
        v = (h << 8) | l
        if v >= 0x8000:
            v -= 0x10000
        return v / 16384.0
    except Exception:
        _imu_bus = None
        return 0


# ═══════════════════════════════════════════════════════════
# SERVO CONTROL
# ═══════════════════════════════════════════════════════════
def _angle_to_duty(angle):
    # Servo montato invertito: raw 180° = rilasciato, raw 0° = freno pieno.
    # angle "logico": 0 = release, +N = N° di frenata.
    raw = 180.0 - angle
    pulse_us = PULSE_MIN_US + (raw / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


_last_sent_angle = -1   # sentinel: nessun comando inviato ancora

# INA219 servo current sensor
INA219_ADDR = 0x40
_ina219_bus = None


def _check_servo_power():
    global _ina219_bus
    try:
        if _ina219_bus is None:
            import smbus2
            _ina219_bus = smbus2.SMBus(1)
            _ina219_bus.write_word_data(INA219_ADDR, 0x05, 0x1000)
        raw = _ina219_bus.read_word_data(INA219_ADDR, 0x02)
        raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
        voltage = (raw >> 3) * 0.004
        return voltage > 3.0
    except Exception:
        return True  # no INA219 = assume powered


def send_servo(angle, gpio_handle):
    """Pattern pulse-and-free: PWM solo quando serve coppia.

    - angle > 0 (frena): claim pin + tx_pwm continuo → servo tiene posizione
    - angle = 0 (release): gpio_write(0) + gpio_free → pin in hi-Z, servo
      non riceve nessun signal e resta fermo (zero corrente, zero microagg).

    NB: il SER0062 con signal LOW continuo (pin claimed output LOW) NON va
    in free-wheel — interpreta LOW come "pulse 0µs" e fa microaggiustamenti
    cercando posizione di fail-safe. Solo con pin hi-Z (free) è davvero libero.
    """
    global _last_sent_angle
    angle = max(BRAKE_MIN_ANGLE, min(BRAKE_MAX_ANGLE, int(angle)))

    if gpio_handle is None or angle == _last_sent_angle:
        return angle

    import lgpio
    if angle > 0 and _check_servo_power():
        # Claim pin if currently released (gpio_free'd)
        try:
            lgpio.gpio_claim_output(gpio_handle, SERVO_PIN)
        except lgpio.error:
            pass  # already claimed
        lgpio.tx_pwm(gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(angle))
    else:
        # Release: cut PWM, free the pin (hi-Z = servo davvero scollegato)
        try:
            lgpio.gpio_write(gpio_handle, SERVO_PIN, 0)
            lgpio.gpio_free(gpio_handle, SERVO_PIN)
        except lgpio.error:
            pass
        angle = 0
    _last_sent_angle = angle
    return angle


# ═══════════════════════════════════════════════════════════
# SPEED LIMITER
# ═══════════════════════════════════════════════════════════
class SpeedLimiter:
    def __init__(self, max_kmh=DEFAULT_MAX_KMH, dry_run=False):
        self.max_kmh = max_kmh
        self.max_speed_ms = max_kmh / 3.6
        self.hyst_start_kmh = max_kmh - HYSTERESIS_KMH
        self.dry_run = dry_run

        # Brake state
        self.brake_cmd = 0.0        # commanded angle (float, smooth)
        self.brake_active = False
        self._emergency_was_active = False

        # Speed smoothing
        self.speed_history = []
        self.SMOOTH_WINDOW = 5      # median of last 5 at 50Hz

        # Feed-forward: estimate natural deceleration
        self.natural_decel = 0.0    # m/s² deceleration without brake
        self.prev_speed = 0.0
        self.decel_samples = []     # collect decel when brake=0

        # IMU speed backup
        self._imu_speed = 0.0

        # Per logging: ultima fonte velocità + raw values
        self._last_chosen_source = "init"
        self._last_gps_speed = 0.0
        self._last_ble_speed = 0.0
        self._last_ble_ok = False

        # GPS direct reader
        self.gps = GPSDirectReader()
        self.gps.start()

        # GPIO
        self.gpio_handle = None
        if not dry_run:
            try:
                import lgpio
                self.gpio_handle = lgpio.gpiochip_open(GPIO_CHIP)
                lgpio.gpio_claim_output(self.gpio_handle, SERVO_PIN)
                # Pulse 0° per 1.5s (porta il servo a release anche da 60°),
                # poi PWM off + gpio_free → pin hi-Z, servo davvero libero.
                lgpio.tx_pwm(self.gpio_handle, SERVO_PIN, SERVO_FREQ, _angle_to_duty(0))
                time.sleep(1.5)
                lgpio.gpio_write(self.gpio_handle, SERVO_PIN, 0)
                lgpio.gpio_free(self.gpio_handle, SERVO_PIN)
                print("Servo @ 0° release (PWM off, pin free, servo davvero libero)")
            except Exception as e:
                print(f"WARNING: GPIO init failed: {e}")

        # Log
        self.log_file = None
        log_dir = os.path.expanduser("~/wip/logging/speed_limiter")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"limiter_{ts}.csv")
        self.log_file = open(log_path, "w")
        self.log_file.write("timestamp,speed_ms,speed_kmh,"
                            "brake_cmd,accel_x,zone,fix,natural_decel,"
                            "gps_speed_ms,ble_speed_ms,ble_ok,chosen_source\n")
        self._log_counter = 0  # log every 5th tick (10Hz logging at 50Hz loop)
        print(f"Log: {log_path}")

    def _smooth_speed(self, speed_ms):
        self.speed_history.append(speed_ms)
        if len(self.speed_history) > self.SMOOTH_WINDOW:
            self.speed_history.pop(0)
        import statistics
        return statistics.median(self.speed_history)

    def _check_emergency(self):
        if not os.path.exists("/tmp/emergency_brake"):
            return 0
        try:
            with open("/tmp/emergency_brake") as f:
                angle = int(f.read().strip())
                return max(0, min(BRAKE_MAX_ANGLE, angle))
        except (ValueError, OSError):
            return 0

    def _update_natural_decel(self, speed_ms, accel_x, dt):
        """Estimate natural deceleration when brake is not active."""
        if self.brake_cmd < 1 and speed_ms > 1.0:
            # No brake applied and moving — measure natural decel
            decel = (self.prev_speed - speed_ms) / dt if dt > 0 else 0
            if 0 < decel < 2.0:  # sane range
                self.decel_samples.append(decel)
                if len(self.decel_samples) > 50:
                    self.decel_samples.pop(0)
                self.natural_decel = sum(self.decel_samples) / len(self.decel_samples)

    def _apply_slew_rate(self, target, dt):
        """Limit how fast brake_cmd can change. Asymmetric: engage slow, release fast."""
        delta = target - self.brake_cmd
        if delta > 0:
            max_delta = MAX_SLEW_RATE_ENGAGE * dt
            if delta > max_delta:
                delta = max_delta
        else:
            max_delta = MAX_SLEW_RATE_RELEASE * dt
            if delta < -max_delta:
                delta = -max_delta
        self.brake_cmd += delta
        self.brake_cmd = max(0, min(BRAKE_MAX_ANGLE, self.brake_cmd))

    def step(self):
        speed_raw, fix = self.gps.get_speed()
        bike_ble_speed, bike_ble_ok = read_bike_ble_speed()
        accel_x = read_imu_accel_x()
        dt = 1.0 / CONTROL_HZ

        # IMU backup speed
        self._imu_speed += -accel_x * 9.81 * dt
        self._imu_speed = max(0, self._imu_speed)
        self._imu_speed *= 0.99

        # Priorità: GPS (con fix) > BLE bike sensor > IMU integration > smoothed GPS=0
        if fix and speed_raw > 0.1:
            speed = self._smooth_speed(speed_raw)
            self._imu_speed = speed
            chosen_source = "gps"
        elif bike_ble_ok:
            speed = self._smooth_speed(bike_ble_speed)
            self._imu_speed = speed   # resetta IMU per evitare drift
            chosen_source = "ble"
        elif self._imu_speed > 1.0:
            speed = self._imu_speed
            chosen_source = "imu"
        else:
            speed = self._smooth_speed(speed_raw)
            chosen_source = "gps_zero"
        self._last_chosen_source = chosen_source
        self._last_gps_speed = speed_raw
        self._last_ble_speed = bike_ble_speed
        self._last_ble_ok = bike_ble_ok

        speed_kmh = speed * 3.6

        # Update natural deceleration estimate
        self._update_natural_decel(speed, accel_x, dt)

        # Emergency brake
        emergency = self._check_emergency()
        if emergency > 0:
            self._apply_slew_rate(emergency, dt)
            send_servo(int(self.brake_cmd), self.gpio_handle)
            self.brake_active = True
            self._emergency_was_active = True
            zone = "EMERGENCY"
            self._maybe_log(speed_raw, speed_kmh, accel_x, zone, fix)
            self.prev_speed = speed
            return speed, speed_kmh, self.brake_cmd

        if self._emergency_was_active:
            self._emergency_was_active = False
            self._apply_slew_rate(0, dt)
            send_servo(int(self.brake_cmd), self.gpio_handle)
            self.brake_active = False
            zone = "RELEASE"
            self._maybe_log(speed_raw, speed_kmh, accel_x, zone, fix)
            self.prev_speed = speed
            return speed, speed_kmh, self.brake_cmd

        # Feed-forward: how much is the bike already decelerating naturally?
        # If natural decel is enough to bring speed down, reduce brake demand
        natural_brake_effect = self.natural_decel * 3.6  # convert to km/h/s
        speed_trend = speed_kmh - self.prev_speed * 3.6  # positive = accelerating

        # Controller
        if speed_kmh > self.max_kmh:
            # OVER — target proportional to excess, minus natural decel
            excess = speed_kmh - self.max_kmh
            target = 5.0 + excess * 8.0  # base 5° + 8° per km/h over
            # Feed-forward: reduce if already decelerating
            if speed_trend < -0.1:
                target *= 0.5  # halve if already slowing
            self._apply_slew_rate(target, dt)
            self.brake_active = True
            zone = "OVER"

        elif speed_kmh > self.hyst_start_kmh:
            # HYSTERESIS — gentle, with feed-forward
            ratio = (speed_kmh - self.hyst_start_kmh) / HYSTERESIS_KMH
            target = ratio * 10.0  # 0° at 7, 10° at 10

            # Feed-forward: if decelerating naturally, reduce or skip brake
            if speed_trend < -0.05:
                target = max(0, target - natural_brake_effect * 2)

            # If accelerating in zone, increase
            if accel_x < -0.03:
                target += 3.0

            self._apply_slew_rate(target, dt)
            self.brake_active = True if self.brake_cmd > 0.5 else False
            zone = "HYST"

        else:
            # FREE — release
            self._apply_slew_rate(0, dt)
            if self.brake_cmd < 0.5:
                self.brake_active = False
            zone = "FREE"

        send_servo(int(self.brake_cmd), self.gpio_handle)

        self._maybe_log(speed_raw, speed_kmh, accel_x, zone, fix)
        self.prev_speed = speed
        return speed, speed_kmh, self.brake_cmd

    def _maybe_log(self, speed_raw, speed_kmh, accel_x, zone, fix):
        """Log at 10Hz (every 5th tick at 50Hz loop)."""
        self._log_counter += 1
        if self._log_counter < 5:
            return
        self._log_counter = 0
        if self.log_file:
            ts = datetime.now().isoformat(timespec="milliseconds")
            self.log_file.write(
                f"{ts},{speed_raw:.2f},{speed_kmh:.1f},"
                f"{self.brake_cmd:.1f},{accel_x:.3f},{zone},"
                f"{1 if fix else 0},{self.natural_decel:.3f},"
                f"{self._last_gps_speed:.3f},{self._last_ble_speed:.3f},"
                f"{1 if self._last_ble_ok else 0},{self._last_chosen_source}\n")
            self.log_file.flush()

    def run(self):
        global running

        print(f"{'='*50}")
        print(f"  ASMILE SPEED LIMITER v2")
        print(f"{'='*50}")
        print(f"Max speed: {self.max_kmh:.0f} km/h")
        print(f"Hysteresis: {self.hyst_start_kmh:.0f}-{self.max_kmh:.0f} km/h")
        print(f"Loop: {CONTROL_HZ} Hz, slew engage: {MAX_SLEW_RATE_ENGAGE}°/s, release: {MAX_SLEW_RATE_RELEASE}°/s")
        print(f"GPS: direct UART {GPS_PORT}")
        print(f"Feed-forward: natural decel estimation")
        print(f"{'DRY RUN' if self.dry_run else 'ACTIVE'}")
        print(f"Ctrl+C to stop\n")

        while running:
            t0 = time.monotonic()
            speed, kmh, brake = self.step()

            if self.brake_active:
                print(f"\r  {kmh:.1f} km/h | BRAKE {brake:.0f}°  ", end="", flush=True)
            elif speed > 0.3:
                print(f"\r  {kmh:.1f} km/h | OK           ", end="", flush=True)

            # Precise timing for 50Hz
            elapsed = time.monotonic() - t0
            sleep_time = (1.0 / CONTROL_HZ) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.gps.stop()
        if self.log_file:
            self.log_file.close()
        # Cleanup GPIO: rilascia il chip così master_switch può subentrare
        # rapidamente. NON metto LOW: master_switch riprende con PWM continuo.
        if self.gpio_handle is not None:
            try:
                import lgpio
                lgpio.gpiochip_close(self.gpio_handle)
            except Exception as e:
                print(f"[CLEANUP] GPIO close error: {e}")
        print(f"\n\nSpeed limiter stopped.")

    def __del__(self):
        if hasattr(self, 'log_file') and self.log_file:
            self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Asmile Speed Limiter v2")
    parser.add_argument("--max-speed", type=float, default=DEFAULT_MAX_KMH,
                        help=f"Max speed in km/h (default: {DEFAULT_MAX_KMH})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    limiter = SpeedLimiter(max_kmh=args.max_speed, dry_run=args.dry_run)
    limiter.run()


if __name__ == "__main__":
    main()
