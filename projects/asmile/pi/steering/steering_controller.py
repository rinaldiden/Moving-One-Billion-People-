#!/usr/bin/env python3
"""
Asmile Power Steering Controller

Il motore ASSISTE lo sterzo: legge il delta encoder (velocità di rotazione
manuale) e applica corrente proporzionale nella stessa direzione.

Encoder: 12-bit SSI (0-4095) sull'asse piantone sterzo (uscita gearbox 1:5).
Motor: Flipsky 6354 140KV, FOC + Hall, via VESC UART.

Telemetria VESC loggata in ~/wip/logging/vesc/
"""

import serial
import struct
import time
import threading
import sys
import os

# --- Hardware config ---
UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"
TELEMETRY_DIR = os.path.expanduser("~/wip/logging/vesc")
TELEMETRY_LATEST = "/tmp/steering_telemetry.csv"

# Encoder
ENCODER_STEPS_PER_REV = 4096
DEG_PER_STEP = 360.0 / ENCODER_STEPS_PER_REV  # 0.0879°

# Direzione assistenza (misurato dai log):
# Con config vesc_foc_ok.xml
ASSIST_DIRECTION = 1

# --- VESC protocol ---
COMM_GET_VALUES = 4
COMM_SET_CURRENT = 6


def crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def vesc_packet(payload: bytes) -> bytes:
    c = crc16(payload)
    return bytes([0x02, len(payload)]) + payload + struct.pack(">H", c) + bytes([0x03])


def parse_vesc_values(data: bytes):
    """Parse COMM_GET_VALUES response. Ritorna dict o None."""
    if len(data) < 10:
        return None
    idx = data.find(b'\x02')
    if idx < 0:
        return None
    if idx + 2 > len(data):
        return None
    plen = data[idx + 1]
    payload = data[idx + 2:idx + 2 + plen]

    if len(payload) < 56 or payload[0] != COMM_GET_VALUES:
        return None

    p = payload[1:]
    try:
        return {
            'temp_fet': struct.unpack(">h", p[0:2])[0] / 10.0,
            'temp_motor': struct.unpack(">h", p[2:4])[0] / 10.0,
            'i_motor': struct.unpack(">i", p[4:8])[0] / 100.0,
            'i_input': struct.unpack(">i", p[8:12])[0] / 100.0,
            'duty': struct.unpack(">h", p[20:22])[0] / 1000.0,
            'rpm': struct.unpack(">i", p[22:26])[0],
            'v_in': struct.unpack(">h", p[26:28])[0] / 10.0,
            'wh': struct.unpack(">i", p[36:40])[0] / 10000.0,
            'fault': p[52],
        }
    except (struct.error, IndexError):
        return None


class SteeringController:
    """Power steering: corrente proporzionale alla velocità encoder."""

    def __init__(self,
                 scale=0.5,
                 max_current=5.0,
                 max_angle=50.0,
                 deadband_steps=2,
                 loop_hz=200,
                 smoothing=0.85,
                 telemetry_hz=10):
        # Tuning
        self.scale = scale
        self.max_current = min(max_current, 30.0)
        self.max_angle = max_angle
        self.deadband_steps = deadband_steps
        self.loop_hz = loop_hz
        self.dt = 1.0 / loop_hz
        self.smoothing = smoothing

        # Telemetria
        self.telemetry_hz = telemetry_hz
        self._telem_interval = loop_hz // telemetry_hz if telemetry_hz > 0 else 0
        self._telem_counter = 0
        self._telem_file = None
        self.telemetry = {}
        self.peak_i_motor = 0.0
        self.peak_i_input = 0.0

        # Velocity from inter-step timing
        self._last_step_time = 0.0   # quando è arrivato l'ultimo step
        self._last_step_dir = 0      # direzione ultimo step
        self._timeout = 0.3          # sec senza step → fermo (corrente 0)

        # State
        self.zero_offset = 0
        self.prev_raw = 0
        self.filtered_current = 0.0
        self.last_current = 0.0
        self.current_angle = 0.0

        # Safety
        self.encoder_ok = True
        self.running = False
        self._ser = None
        self._thread = None
        self._lock = threading.Lock()

        # Logging callback
        self.on_log = None

        self._enc_fail_count = 0
        self._MAX_ENC_FAILS = 5

    def _read_encoder_raw(self) -> int:
        try:
            with open(POSITION_FILE, "r") as f:
                val = int(f.read().strip())
            self._enc_fail_count = 0
            return val
        except (FileNotFoundError, ValueError, OSError):
            self._enc_fail_count += 1
            if self._enc_fail_count >= self._MAX_ENC_FAILS:
                self.encoder_ok = False
            return -1

    def _wrap_delta(self, delta: int) -> int:
        if delta > 2048:
            delta -= 4096
        elif delta < -2048:
            delta += 4096
        return delta

    def get_steering_angle(self) -> float:
        raw = self._read_encoder_raw()
        if raw < 0:
            return self.current_angle
        delta = self._wrap_delta(raw - self.zero_offset)
        self.current_angle = delta * DEG_PER_STEP
        return self.current_angle

    def zero_here(self):
        raw = self._read_encoder_raw()
        if raw >= 0:
            self.zero_offset = raw
            self.prev_raw = raw
            self.filtered_current = 0.0
            self.last_current = 0.0
            self.current_angle = 0.0
            self._last_step_time = 0.0
            self._last_step_dir = 0
            print(f"Zero impostato a encoder raw: {raw}")

    def _send_current(self, amps: float):
        if self._ser and self._ser.is_open:
            ma = int(amps * 1000)
            self._ser.write(vesc_packet(
                struct.pack(">Bi", COMM_SET_CURRENT, ma)))

    def _read_telemetry(self):
        if not self._ser or not self._ser.is_open:
            return None
        self._ser.reset_input_buffer()
        self._ser.write(vesc_packet(bytes([COMM_GET_VALUES])))
        time.sleep(0.01)
        resp = self._ser.read(self._ser.in_waiting or 128)
        if resp:
            time.sleep(0.005)
            resp += self._ser.read(self._ser.in_waiting or 64)
        vals = parse_vesc_values(resp)
        if vals:
            self.telemetry = vals
            self.peak_i_motor = max(self.peak_i_motor, abs(vals['i_motor']))
            self.peak_i_input = max(self.peak_i_input, abs(vals['i_input']))
            if self._telem_file:
                self._telem_file.write(
                    f"{time.time():.3f},"
                    f"{self.current_angle:.1f},"
                    f"{self.last_current:.2f},"
                    f"{vals['i_motor']:.2f},"
                    f"{vals['i_input']:.2f},"
                    f"{vals['v_in']:.1f},"
                    f"{vals['rpm']},"
                    f"{vals['duty']:.3f},"
                    f"{vals['temp_fet']:.1f},"
                    f"{vals['temp_motor']:.1f},"
                    f"{vals['fault']}\n"
                )
                self._telem_file.flush()
        return vals

    def _stop_motor(self):
        self._send_current(0.0)
        self.filtered_current = 0.0
        self.last_current = 0.0

    def _assist_step(self) -> float:
        raw = self._read_encoder_raw()
        if raw < 0:
            return 0.0

        now = time.monotonic()

        # Delta encoder dall'ultimo ciclo
        delta = self._wrap_delta(raw - self.prev_raw)
        self.prev_raw = raw

        # Aggiorna angolo
        angle_delta = self._wrap_delta(raw - self.zero_offset)
        self.current_angle = angle_delta * DEG_PER_STEP

        # Deadband
        if abs(delta) < self.deadband_steps:
            delta = 0

        with self._lock:
            scale = self.scale

        if delta != 0:
            # Step rilevato: calcola velocità dal tempo tra step
            dt_step = now - self._last_step_time if self._last_step_time > 0 else self.dt
            dt_step = max(dt_step, 0.001)  # evita div/0

            # Velocità in steps/sec
            velocity = abs(delta) / dt_step

            # Corrente proporzionale alla velocità
            # velocity in steps/sec, scale in A per step/ciclo
            # Normalizza: a 50 steps/sec (circa 4.4°/sec, lento) → scale * 1A
            raw_target = (velocity / 50.0) * scale * ASSIST_DIRECTION
            if delta < 0:
                raw_target = -raw_target

            self._last_step_time = now
            self._last_step_dir = 1 if delta > 0 else -1
        else:
            # Nessun step: quanto tempo è passato dall'ultimo?
            time_since = now - self._last_step_time if self._last_step_time > 0 else 999

            if time_since > self._timeout:
                # Fermo da troppo → corrente zero, subito
                raw_target = 0.0
            else:
                # Tra due step: mantieni corrente attuale (il filtro la tiene)
                raw_target = self.filtered_current

        # Filtro EMA — transizione fluida
        self.filtered_current = (
            self.smoothing * self.filtered_current +
            (1.0 - self.smoothing) * raw_target
        )

        target = self.filtered_current

        # Boost minimo: sotto 1.5A il VESC non muove il motore in una direzione
        # Se c'è un target non-zero, portalo almeno alla soglia minima
        min_effective = 1.5  # A — sotto questo il motore non risponde
        if 0 < abs(target) < min_effective and abs(target) > 0.05:
            target = min_effective if target > 0 else -min_effective

        # Safety: frena oltre i limiti angolari
        if self.current_angle > self.max_angle:
            over = self.current_angle - self.max_angle
            if target * ASSIST_DIRECTION > 0:
                target = 0.0
            if over > 5.0:
                target = 0.0
                self.filtered_current = 0.0
        elif self.current_angle < -self.max_angle:
            over = -self.max_angle - self.current_angle
            if target * ASSIST_DIRECTION < 0:
                target = 0.0
            if over > 5.0:
                target = 0.0
                self.filtered_current = 0.0

        output = max(-self.max_current, min(self.max_current, target))

        self.last_current = output
        return output

    def _control_loop(self):
        print(f"Power steering avviato @ {self.loop_hz}Hz")
        print(f"Scale={self.scale} A/step, max={self.max_current}A, "
              f"deadband={self.deadband_steps} steps, "
              f"smoothing={self.smoothing}")
        print(f"Limiti angolari: ±{self.max_angle}°")
        print(f"Telemetria: {self.telemetry_hz}Hz → {TELEMETRY_DIR}/")

        while self.running:
            t0 = time.monotonic()

            if not self.encoder_ok:
                self._stop_motor()
                if self.on_log:
                    self.on_log(time.time(), self.current_angle, 0, self.telemetry)
                time.sleep(0.1)
                self._read_encoder_raw()
                continue

            current = self._assist_step()
            self._send_current(current)

            # Telemetria periodica
            if self._telem_interval > 0:
                self._telem_counter += 1
                if self._telem_counter >= self._telem_interval:
                    self._telem_counter = 0
                    self._read_telemetry()

            if self.on_log:
                self.on_log(time.time(), self.current_angle,
                            current, self.telemetry)

            elapsed = time.monotonic() - t0
            sleep_time = self.dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._stop_motor()
        print("Power steering fermato")
        print(f"Picco corrente motore: {self.peak_i_motor:.1f}A")
        print(f"Picco corrente batteria: {self.peak_i_input:.1f}A")

    def start(self):
        if self.running:
            return True

        if self._read_encoder_raw() < 0:
            print("ERRORE: encoder daemon non attivo (/tmp/encoder_position)")
            print("Avvia: sudo systemctl start encoder-ssi")
            return False

        self._ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
        self._ser.reset_input_buffer()

        # Apri file telemetria
        os.makedirs(TELEMETRY_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(TELEMETRY_DIR, f"steering_{ts}.csv")
        self._telem_file = open(log_path, "w")
        self._telem_file.write(
            "timestamp,angle_deg,i_cmd,i_motor,i_input,"
            "v_in,rpm,duty,temp_fet,temp_motor,fault\n"
        )
        try:
            if os.path.islink(TELEMETRY_LATEST):
                os.unlink(TELEMETRY_LATEST)
            os.symlink(log_path, TELEMETRY_LATEST)
        except OSError:
            pass
        print(f"Telemetria: {log_path}")

        self.zero_here()

        self.running = True
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._stop_motor()
        if self._ser:
            self._ser.close()
            self._ser = None
        if self._telem_file:
            self._telem_file.close()
            self._telem_file = None
        print("Controller fermo, motore spento")

    def set_scale(self, scale):
        with self._lock:
            self.scale = scale
        print(f"Scale aggiornato: {self.scale} A/step")

    def set_max_current(self, amps):
        self.max_current = min(abs(amps), 30.0)
        print(f"Max current: {self.max_current}A")


if __name__ == "__main__":
    ctrl = SteeringController(scale=0.5, max_current=5.0)

    def log_fn(t, angle, current, telem):
        if abs(current) > 0.01 or telem:
            i_real = telem.get('i_motor', 0) if telem else 0
            v = telem.get('v_in', 0) if telem else 0
            print(f"  ang={angle:+6.1f}° I_cmd={current:+5.2f}A "
                  f"I_real={i_real:+6.1f}A V={v:.1f}V")

    ctrl.on_log = log_fn

    if not ctrl.start():
        sys.exit(1)

    print("\nGira lo sterzo a mano — il motore deve assistere.")
    print("Ctrl+C per fermare.\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        ctrl.stop()
