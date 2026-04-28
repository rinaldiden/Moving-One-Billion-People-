#!/usr/bin/env python3
"""
Asmile Servofreno Server — Raspberry Pi 5

Flask server on 0.0.0.0:5000 with:
  - HTML page with FRENA button (hold to brake, release to stop)
  - POST /frena  → start brake loop
  - POST /rilascia → release brake
  - Background training data logging at 10Hz (continuous from boot)

Uses exact parameters from brake_servo.py, imu_mpu6050.py, gps_neo_m10.py.
"""

import lgpio
import smbus2
import serial
import time
import threading
import os
import sys
from datetime import datetime, date
from flask import Flask, jsonify, request

# ═══════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
LOG_DIR = os.path.join(PROJECT_DIR, "pi", "logging")
LOG_SERVO_DIR = os.path.join(LOG_DIR, "servofreno")
LOG_TRAINING_DIR = os.path.join(LOG_DIR, "training_data")

os.makedirs(LOG_SERVO_DIR, exist_ok=True)
os.makedirs(LOG_TRAINING_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# SERVO CONFIG — from brake_servo.py (exact values)
# ═══════════════════════════════════════════════════════════
GPIO_CHIP = 4
PIN_SERVO = 12          # GPIO 12 = hardware PWM0
SERVO_FREQ = 330        # PDI-6221MG native frequency
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ  # ~3030us

CENTER = 0              # release angle
MEDIUM_TRAVEL = 95      # max braking angle

# ═══════════════════════════════════════════════════════════
# IMU CONFIG — from imu_mpu6050.py (exact values)
# ═══════════════════════════════════════════════════════════
I2C_BUS = 1
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
ACCEL_CONFIG = 0x1C
GYRO_CONFIG = 0x1B
ACCEL_SCALE = 16384.0   # LSB/g at ±2g
GYRO_SCALE = 131.0      # LSB/(°/s) at ±250°/s

# ═══════════════════════════════════════════════════════════
# GPS CONFIG — from gps_neo_m10.py (exact values)
# ═══════════════════════════════════════════════════════════
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400

# ═══════════════════════════════════════════════════════════
# INA219 — servo current sensor on I2C1
# ═══════════════════════════════════════════════════════════
INA219_ADDR = 0x40
INA219_REG_CONFIG = 0x00
INA219_REG_SHUNT = 0x01
INA219_REG_BUS = 0x02
INA219_REG_CURRENT = 0x04
INA219_SHUNT_RESISTANCE = 0.1  # default shunt on most breakout boards

ina219_available = False


def init_ina219(bus):
    """Initialize INA219 with default config (32V, 2A range)."""
    global ina219_available
    try:
        # Config: 32V bus range, 320mV shunt range, 12-bit, continuous
        bus.write_word_data(INA219_ADDR, INA219_REG_CONFIG, 0x399F)
        # Calibration for 0.1Ω shunt: CAL = 0.04096 / (current_LSB * R_shunt)
        # current_LSB = 0.1mA → CAL = 0.04096 / (0.0001 * 0.1) = 4096
        bus.write_word_data(INA219_ADDR, 0x05, _swap_bytes(4096))
        ina219_available = True
        print("[INA219] Initialized at 0x40")
    except Exception as e:
        print(f"[INA219] Not available: {e}")
        ina219_available = False


def _swap_bytes(val):
    """Swap bytes for I2C word (big-endian)."""
    return ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)


def read_ina219(bus) -> dict:
    """Read voltage (V) and current (mA) from INA219."""
    if not ina219_available or bus is None:
        return {"servo_voltage": 0.0, "servo_current_ma": 0.0}
    try:
        raw_bus = bus.read_word_data(INA219_ADDR, INA219_REG_BUS)
        raw_bus = _swap_bytes(raw_bus)
        voltage = (raw_bus >> 3) * 0.004  # 4mV per LSB

        raw_shunt = bus.read_word_data(INA219_ADDR, INA219_REG_SHUNT)
        raw_shunt = _swap_bytes(raw_shunt)
        if raw_shunt >= 0x8000:
            raw_shunt -= 0x10000
        current_ma = raw_shunt * 0.01 / INA219_SHUNT_RESISTANCE  # 10uV per LSB

        return {"servo_voltage": voltage, "servo_current_ma": current_ma}
    except Exception:
        return {"servo_voltage": 0.0, "servo_current_ma": 0.0}


# ═══════════════════════════════════════════════════════════
# ENCODER — read from daemon shared file
# ═══════════════════════════════════════════════════════════
ENCODER_FILE = "/tmp/encoder_position"

# ═══════════════════════════════════════════════════════════
# BRAKE LOOP PARAMETERS
# ═══════════════════════════════════════════════════════════
RAMP_DURATION = 2.0       # seconds of gentle ramp
RAMP_START_ANGLE = 40     # initial angle during ramp
LOOP_INTERVAL = 0.1       # 100ms per iteration
ANGLE_INCREMENT_SLOW = 2  # degrees per step during ramp
ANGLE_INCREMENT_FAST = 5  # degrees per step after ramp
EXPECTED_DECEL_G = 0.15   # expected deceleration in g
SPEED_STOP_MS = 0.1       # speed threshold to consider stopped


# ═══════════════════════════════════════════════════════════
# SERVO
# ═══════════════════════════════════════════════════════════
def angle_to_duty(angle: float) -> float:
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


class Servo:
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


# ═══════════════════════════════════════════════════════════
# IMU
# ═══════════════════════════════════════════════════════════
def init_mpu6050(bus):
    bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0x00)
    time.sleep(0.1)
    bus.write_byte_data(MPU6050_ADDR, ACCEL_CONFIG, 0x00)  # ±2g
    bus.write_byte_data(MPU6050_ADDR, GYRO_CONFIG, 0x00)   # ±250°/s


def read_raw(bus, reg: int) -> int:
    high = bus.read_byte_data(MPU6050_ADDR, reg)
    low = bus.read_byte_data(MPU6050_ADDR, reg + 1)
    value = (high << 8) | low
    if value >= 0x8000:
        value -= 0x10000
    return value


IMU_ZERO = {"ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}


def read_imu(bus) -> dict:
    if bus is None:
        return IMU_ZERO
    ax = read_raw(bus, ACCEL_XOUT_H) / ACCEL_SCALE
    ay = read_raw(bus, ACCEL_XOUT_H + 2) / ACCEL_SCALE
    az = read_raw(bus, ACCEL_XOUT_H + 4) / ACCEL_SCALE
    gx = read_raw(bus, GYRO_XOUT_H) / GYRO_SCALE
    gy = read_raw(bus, GYRO_XOUT_H + 2) / GYRO_SCALE
    gz = read_raw(bus, GYRO_XOUT_H + 4) / GYRO_SCALE
    return {"ax": ax, "ay": ay, "az": az, "gx": gx, "gy": gy, "gz": gz}


# ═══════════════════════════════════════════════════════════
# GPS
# ═══════════════════════════════════════════════════════════
def nmea_to_decimal(coord: str, direction: str) -> float:
    if len(coord) < 4:
        return 0.0
    dot = coord.index(".")
    degrees = int(coord[:dot - 2])
    minutes = float(coord[dot - 2:])
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


class GPSReader:
    """Background thread that continuously parses NMEA and exposes latest values."""

    def __init__(self):
        self.lat = 0.0
        self.lon = 0.0
        self.speed_ms = 0.0
        self.heading = 0.0
        self.fix = False
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def get(self) -> dict:
        with self._lock:
            return {
                "lat": self.lat, "lon": self.lon,
                "speed_ms": self.speed_ms, "heading": self.heading,
                "fix": self.fix,
            }

    def _run(self):
        try:
            ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1.0)
        except Exception as e:
            print(f"[GPS] Cannot open {GPS_PORT}: {e}")
            return

        print(f"[GPS] Reading on {GPS_PORT} @ {GPS_BAUD} baud")
        try:
            while self._running:
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if not line.startswith("$"):
                    continue

                if "GGA" in line:
                    parts = line.split(",")
                    if len(parts) >= 15 and parts[2] and parts[4]:
                        with self._lock:
                            self.lat = nmea_to_decimal(parts[2], parts[3])
                            self.lon = nmea_to_decimal(parts[4], parts[5])
                            self.fix = int(parts[6]) > 0 if parts[6] else False

                elif "RMC" in line:
                    parts = line.split(",")
                    if len(parts) >= 12 and parts[2] == "A":
                        speed_knots = float(parts[7]) if parts[7] else 0.0
                        heading = float(parts[8]) if parts[8] else 0.0
                        with self._lock:
                            self.speed_ms = speed_knots * 1.852 / 3.6  # knots → m/s
                            self.heading = heading
                            self.fix = True
        except Exception as e:
            print(f"[GPS] Error: {e}")
        finally:
            ser.close()


# ═══════════════════════════════════════════════════════════
# ENCODER
# ═══════════════════════════════════════════════════════════
def read_encoder() -> int:
    try:
        with open(ENCODER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


# ═══════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════
def servo_log_path() -> str:
    return os.path.join(LOG_SERVO_DIR, f"servofreno_{date.today():%Y%m%d}.csv")


def training_log_path() -> str:
    return os.path.join(LOG_TRAINING_DIR, f"training_{date.today():%Y%m%d}.csv")


def log_servo(evento: str, speed_ms: float, accel_g: float, angle: float, note: str = ""):
    path = servo_log_path()
    write_header = not os.path.exists(path)
    with open(path, "a") as f:
        if write_header:
            f.write("timestamp,evento,velocita_ms,accel_ms2,angolo_servo_deg,note\n")
        ts = datetime.now().isoformat(timespec="milliseconds")
        accel_ms2 = accel_g * 9.81
        f.write(f"{ts},{evento},{speed_ms:.3f},{accel_ms2:.3f},{angle:.1f},{note}\n")


def log_training(gps: dict, imu: dict, ina: dict, evento: str = ""):
    path = training_log_path()
    write_header = not os.path.exists(path)
    with open(path, "a") as f:
        if write_header:
            f.write("timestamp,gps_lat,gps_lon,gps_speed_ms,gps_heading,"
                    "imu_accel_x,imu_accel_y,imu_accel_z,"
                    "imu_gyro_x,imu_gyro_y,imu_gyro_z,encoder_pos,"
                    "servo_voltage,servo_current_ma,evento\n")
        ts = datetime.now().isoformat(timespec="milliseconds")
        enc = read_encoder()
        f.write(f"{ts},{gps['lat']:.7f},{gps['lon']:.7f},{gps['speed_ms']:.3f},"
                f"{gps['heading']:.1f},{imu['ax']:.4f},{imu['ay']:.4f},{imu['az']:.4f},"
                f"{imu['gx']:.2f},{imu['gy']:.2f},{imu['gz']:.2f},{enc},"
                f"{ina['servo_voltage']:.3f},{ina['servo_current_ma']:.1f},{evento}\n")


# ═══════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════
gpio_handle = None
servo = None
i2c_bus = None
gps_reader = None

braking = False          # True while brake loop is active
brake_event = ""         # "FRENATA" during braking, "" otherwise
brake_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
# TRAINING DATA LOGGER — 10Hz continuous
# ═══════════════════════════════════════════════════════════
def training_logger_thread():
    global i2c_bus, gps_reader, brake_event
    print("[TRAINING] Logging at 10Hz")
    while True:
        try:
            imu = read_imu(i2c_bus)
            gps = gps_reader.get()
            ina = read_ina219(i2c_bus)
            log_training(gps, imu, ina, brake_event)
        except Exception as e:
            print(f"[TRAINING] Error: {e}")
        time.sleep(0.1)


# ═══════════════════════════════════════════════════════════
# BRAKE LOOP
# ═══════════════════════════════════════════════════════════
def brake_loop():
    global braking, brake_event, servo, i2c_bus, gps_reader

    with brake_lock:
        if braking:
            return
        braking = True
        brake_event = "FRENATA"

    SNAP_ANGLE = 85       # fast phase: grab the disc
    PROGRESSIVE_STEP = 1  # degrees per step in progressive phase
    PROGRESSIVE_DELAY = 0.05  # 50ms between steps

    print(f"[BRAKE] Start — snap to {SNAP_ANGLE}° then progressive to {MEDIUM_TRAVEL}°")
    log_servo("INIZIO_FRENATA", 0, 0, SNAP_ANGLE)

    try:
        # Phase 1: fast snap to grab the disc
        servo.write(SNAP_ANGLE)
        time.sleep(0.1)

        # Phase 2: progressive from SNAP to MEDIUM_TRAVEL
        angle = SNAP_ANGLE
        while angle < MEDIUM_TRAVEL and braking:
            angle = min(angle + PROGRESSIVE_STEP, MEDIUM_TRAVEL)
            servo.write(angle)
            time.sleep(PROGRESSIVE_DELAY)

        while braking:
            imu = read_imu(i2c_bus)
            gps = gps_reader.get()
            decel_g = -imu["ax"]
            speed_ms = gps["speed_ms"]

            log_servo("LOOP", speed_ms, decel_g, angle)
            time.sleep(LOOP_INTERVAL)

    except Exception as e:
        log_servo("ERRORE", 0, 0, angle, str(e))
        print(f"[BRAKE] Error: {e}")
    finally:
        release_servo()


def release_servo():
    global braking, brake_event, servo
    was_braking = braking
    braking = False
    brake_event = ""

    if servo:
        servo.write(CENTER)
        if was_braking:
            log_servo("FINE_FRENATA", 0, 0, CENTER, "rilascio")
            print(f"[BRAKE] Released → {CENTER}°")


# ═══════════════════════════════════════════════════════════
# FLASK APP
# ═══════════════════════════════════════════════════════════
app = Flask(__name__)

HTML_PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Asmile Freno</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #1a1a2e; color: #eee; font-family: -apple-system, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; height: 100vh; user-select: none;
    -webkit-user-select: none;
  }
  h1 { font-size: 1.5rem; margin-bottom: 1rem; color: #888; }
  #status {
    font-size: 1.2rem; margin-bottom: 2rem; min-height: 1.5em;
    color: #0f0; font-family: monospace;
  }
  #status.braking { color: #f44; }
  #btn-brake {
    width: 250px; height: 250px; border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, #e74c3c, #8b0000);
    border: 6px solid #600; color: white; font-size: 2.5rem;
    font-weight: bold; cursor: pointer; outline: none;
    box-shadow: 0 8px 30px rgba(231,76,60,0.4);
    transition: transform 0.1s, box-shadow 0.1s;
    -webkit-tap-highlight-color: transparent;
  }
  #btn-brake:active, #btn-brake.active {
    transform: scale(0.92);
    box-shadow: 0 2px 10px rgba(231,76,60,0.6);
    background: radial-gradient(circle at 30% 30%, #ff6b6b, #c0392b);
  }
  .info {
    margin-top: 2rem; font-size: 0.85rem; color: #555;
    text-align: center; line-height: 1.6;
  }
</style>
</head>
<body>
  <h1>ASMILE FRENO</h1>
  <div id="status">Pronto</div>
  <button id="btn-brake">FRENA</button>
  <div class="info">
    Tieni premuto per frenare<br>Rilascia per rilasciare
  </div>
<script>
const btn = document.getElementById('btn-brake');
const st = document.getElementById('status');
let braking = false;
let useTouch = false;

function startBrake() {
  if (braking) return;
  braking = true;
  btn.classList.add('active');
  st.textContent = 'FRENATA IN CORSO';
  st.className = 'braking';
  fetch('/frena', {method: 'POST'});
}

function stopBrake() {
  if (!braking) return;
  braking = false;
  btn.classList.remove('active');
  st.textContent = 'Rilasciato';
  st.className = '';
  fetch('/rilascia', {method: 'POST'});
}

// Touch events — block mouse events once touch is detected
btn.addEventListener('touchstart', (e) => { e.preventDefault(); useTouch = true; startBrake(); });
btn.addEventListener('touchend', (e) => { e.preventDefault(); stopBrake(); });
btn.addEventListener('touchcancel', stopBrake);

// Mouse events — only fire if no touch detected
btn.addEventListener('mousedown', () => { if (!useTouch) startBrake(); });
btn.addEventListener('mouseup', () => { if (!useTouch) stopBrake(); });
btn.addEventListener('mouseleave', () => { if (!useTouch) stopBrake(); });
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/frena", methods=["POST"])
def frena():
    if not braking:
        threading.Thread(target=brake_loop, daemon=True).start()
    return jsonify({"status": "braking"})


@app.route("/rilascia", methods=["POST"])
def rilascia():
    release_servo()
    return jsonify({"status": "released"})


@app.route("/stato", methods=["GET"])
def stato():
    gps = gps_reader.get() if gps_reader else {}
    imu_data = {}
    try:
        imu_data = read_imu(i2c_bus) if i2c_bus else {}
    except Exception:
        pass
    ina_data = read_ina219(i2c_bus) if i2c_bus else {}
    return jsonify({
        "braking": braking,
        "servo_angle": servo.read() if servo else 0,
        "gps": gps,
        "imu": imu_data,
        "encoder": read_encoder(),
        "ina219": ina_data,
    })


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    global gpio_handle, servo, i2c_bus, gps_reader

    print("=" * 50)
    print("  ASMILE SERVOFRENO SERVER")
    print("=" * 50)

    # GPIO + Servo
    gpio_handle = lgpio.gpiochip_open(GPIO_CHIP)
    servo = Servo(gpio_handle, PIN_SERVO)
    servo.write(CENTER)
    print(f"[SERVO] GPIO {PIN_SERVO}, freq {SERVO_FREQ}Hz")
    print(f"[SERVO] CENTER={CENTER}°, MAX_BRAKE={MEDIUM_TRAVEL}°")

    # IMU
    try:
        i2c_bus = smbus2.SMBus(I2C_BUS)
        init_mpu6050(i2c_bus)
        imu_test = read_imu(i2c_bus)
        print(f"[IMU] MPU6050 on I2C{I2C_BUS} @ 0x{MPU6050_ADDR:02X}")
        print(f"[IMU] Test read: ax={imu_test['ax']:.2f} ay={imu_test['ay']:.2f} az={imu_test['az']:.2f}g")
    except Exception as e:
        i2c_bus = None
        print(f"[IMU] Not available: {e}")
        print(f"[IMU] (needs reboot to enable I2C — will work without)")

    # INA219
    if i2c_bus:
        init_ina219(i2c_bus)

    # GPS
    gps_reader = GPSReader()
    gps_reader.start()

    # Encoder
    enc = read_encoder()
    print(f"[ENCODER] Position: {enc}" if enc >= 0 else "[ENCODER] Daemon not running (ok)")

    # Logging
    print(f"[LOG] Servofreno: {LOG_SERVO_DIR}/")
    print(f"[LOG] Training:   {LOG_TRAINING_DIR}/")

    # Training logger — 10Hz continuous
    threading.Thread(target=training_logger_thread, daemon=True).start()

    # Flask
    print()
    print(f"[SERVER] http://192.168.1.119:5000")
    print(f"[SERVER] Apri nel browser per il tasto FRENA")
    print()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
