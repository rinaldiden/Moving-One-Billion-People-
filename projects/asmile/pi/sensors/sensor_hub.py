#!/usr/bin/env python3
"""
sensor_hub.py — UN solo registratore per tutti i sensori del Pi, uguale su tutta la flotta
(asmile #001, asmile2, asmile-logger). Metodo deciso da Daniele 2026-11-07.

  - una riga ogni 20 ms ESATTI (50 Hz a scadenza fissa, niente deriva)
  - t_ms = CLOCK_MONOTONIC in ms: lo STESSO orologio dei frame camera (SensorTimestamp di
    libcamera, in frames_*.csv del recorder) e dei campioni encoder (bridge Arduino);
    wall = ora reale, solo per leggerla
  - GPS a 10 Hz (configurato all'avvio): i campi gps_* sono pieni solo nella riga in cui arriva
    un fix nuovo, cioè ogni ~5 righe; vuoti nelle altre
  - STESSE colonne su ogni unità: un sensore assente lascia la colonna vuota
  - fsync ogni secondo: uno spegnimento perde al massimo l'ultimo secondo, mai buchi di byte nulli

File:  /data/logging/sensors/sensors_<AAAAMMGG_hhmmss>.csv (+ .json con orologi e dispositivi),
       nuovo file ogni ora.  Stato live: /dev/shm/asmile_hub.json (lo leggono limiter e server freno).
Attivazione per unità: SENSOR_HUB=1 in ~/asmile_id.conf (HUB_VESC=1 se va letto anche il VESC).
"""
import json
import os
import signal
import struct
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hub_client import (HUB_STATE_FILE, LIMITER_STATE_FILE, now_ms, unit_conf,  # noqa: E402
                        write_json_atomic)

SCHEMA = "asmile_sensors_v1"
PERIOD_MS = 20
ROTATE_S = 3600
FSYNC_EVERY = 50
OUT_DIR = "/data/logging/sensors" if os.path.isdir("/data") else os.path.expanduser("~/logging/sensors")

COLUMNS = [
    "t_ms", "wall",
    "imu_ax_g", "imu_ay_g", "imu_az_g", "imu_gx_dps", "imu_gy_dps", "imu_gz_dps",
    "enc_t_ms", "enc_wheel_cum", "enc_wheel_raw", "enc_steer_raw",
    "servo_v", "servo_ma",
    "lim_t_ms", "lim_source", "lim_zone", "lim_speed_ms", "lim_accel_ms2", "lim_error_ms",
    "brake_target_deg", "brake_cmd_deg",
    "vesc_rpm", "vesc_duty", "vesc_i_motor", "vesc_i_in", "vesc_v_in", "vesc_tach", "vesc_fault",
    "gps_t_ms", "gps_utc", "gps_fix", "gps_lat", "gps_lon", "gps_speed_ms", "gps_heading",
    "gps_sats", "gps_hdop", "gps_alt_m",
    "evento",
]

# ─── IMU MPU6050 ───────────────────────────────────────────────────────
I2C_BUS = 1
MPU_ADDR = 0x68
MPU_DLPF = 4            # reg 0x1A: banda ~21 Hz (ritardo ~8.5 ms) = anti-aliasing per i 50 Hz

# ─── INA219 (corrente servo freno) ─────────────────────────────────────
INA_ADDR = 0x40

# ─── encoder (bridge Arduino) ──────────────────────────────────────────
ENC_CUM_FILE = "/tmp/encoder_wheel_cum"      # "<cum> <t_mono_s> <sterzo> <ruota>"
ENC_STEER_FILE = "/tmp/encoder_steer"
ENC_FW_FILE = "/tmp/encoder_fw_version"
ENC_FRESH_MS = 500

# ─── GPS NEO-M10 ───────────────────────────────────────────────────────
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400
GPS_RATE_MS = 100       # 10 Hz
# UBX-CFG-VALSET (strato RAM: si rimanda a ogni avvio, la config salvata del modulo non cambia)
GPS_KEYS = [
    (0x30210001, "<H", GPS_RATE_MS),   # CFG-RATE-MEAS
    (0x209100C5, "<B", 0),             # CFG-MSGOUT-NMEA_ID_GSV_UART1 off (alleggerisce la seriale)
    (0x209100C0, "<B", 0),             # ..._GSA_UART1 off
    (0x209100CA, "<B", 0),             # ..._GLL_UART1 off
    (0x209100B1, "<B", 0),             # ..._VTG_UART1 off   (restano RMC + GGA)
]

# ─── VESC (solo con HUB_VESC=1) ────────────────────────────────────────
VESC_PORT = "/dev/ttyAMA0"
VESC_BAUD = 115200

# ─── eventi da file flag ───────────────────────────────────────────────
FLAG_EVENTS = {"/tmp/emergency_brake": "FRENATA_TELEFONO"}

running = True


def _swap16(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)


class I2CSensors:
    def __init__(self):
        self.bus = None
        self.imu_ok = self.ina_ok = False
        try:
            import smbus2
            self.bus = smbus2.SMBus(I2C_BUS)
        except Exception as e:
            print(f"[HUB] I2C non disponibile: {e}", flush=True)
            return
        try:
            self.bus.write_byte_data(MPU_ADDR, 0x6B, 0x00)      # sveglia
            self.bus.write_byte_data(MPU_ADDR, 0x1A, MPU_DLPF)  # filtro passa-basso
            self.bus.write_byte_data(MPU_ADDR, 0x1C, 0x00)      # ±2 g
            self.bus.write_byte_data(MPU_ADDR, 0x1B, 0x00)      # ±250 °/s
            self.imu_ok = True
        except OSError as e:
            print(f"[HUB] IMU assente: {e}", flush=True)
        try:
            self.bus.write_word_data(INA_ADDR, 0x00, 0x399F)
            self.bus.write_word_data(INA_ADDR, 0x05, _swap16(4096))
            self.ina_ok = True
        except OSError:
            pass

    def imu(self):
        if not self.imu_ok:
            return None
        try:
            b = self.bus.read_i2c_block_data(MPU_ADDR, 0x3B, 14)   # una transazione: accel+temp+gyro
        except OSError:
            return None
        v = struct.unpack(">7h", bytes(b))
        return (v[0] / 16384.0, v[1] / 16384.0, v[2] / 16384.0,
                v[4] / 131.0, v[5] / 131.0, v[6] / 131.0)

    def ina(self):
        if not self.ina_ok:
            return None
        try:
            vb = (_swap16(self.bus.read_word_data(INA_ADDR, 0x02)) >> 3) * 0.004
            sh = _swap16(self.bus.read_word_data(INA_ADDR, 0x01))
            if sh >= 0x8000:
                sh -= 0x10000
            return vb, sh * 0.01 / 0.1
        except OSError:
            return None


def _nmea_deg(v, hemi):
    if not v:
        return None
    d = int(float(v) / 100)
    x = d + (float(v) - d * 100) / 60.0
    return -x if hemi in ("S", "W") else x


def _ubx(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in body:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


class GPS(threading.Thread):
    """Legge NMEA da UART3, raggruppa GGA+RMC della stessa epoca (stesso orario UTC)."""

    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.epoch = {}
        self.latest = None          # ultimo fix completo
        self.seq = 0
        self.config_ack = None
        self.present = False

    def _configure(self, ser):
        payload = bytes([0, 0x01, 0, 0])
        for key, fmt, val in GPS_KEYS:
            payload += struct.pack("<I", key) + struct.pack(fmt, val)
        ser.write(_ubx(0x06, 0x8A, payload))
        t0, buf = time.monotonic(), b""
        while time.monotonic() - t0 < 1.5:
            buf += ser.read(256)
            if b"\xb5\x62\x05\x01" in buf:
                return "ACK"
            if b"\xb5\x62\x05\x00" in buf:
                return "NAK"
        return "nessuna risposta"

    def run(self):
        try:
            import serial
            ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.2)
        except Exception as e:
            print(f"[HUB] GPS assente: {e}", flush=True)
            return
        self.present = True
        self.config_ack = self._configure(ser)
        print(f"[HUB] GPS {GPS_PORT}: config 10 Hz → {self.config_ack}", flush=True)
        while running:
            try:
                raw = ser.readline()
            except Exception:
                time.sleep(0.5)
                continue
            t_rx = now_ms()
            line = raw.decode("ascii", "ignore").strip()
            if not line.startswith("$") or "*" not in line:
                continue
            p = line.split("*")[0].split(",")
            kind = p[0][3:]
            if kind not in ("GGA", "RMC") or len(p) < 10:
                continue
            utc = p[1]
            if self.epoch.get("utc") != utc:
                self.epoch = {"utc": utc, "t_ms": t_rx}
            e = self.epoch
            try:
                if kind == "RMC":
                    e["rmc"] = True
                    e["fix_rmc"] = p[2] == "A"
                    e["lat"], e["lon"] = _nmea_deg(p[3], p[4]), _nmea_deg(p[5], p[6])
                    e["speed"] = float(p[7]) * 0.514444 if p[7] else None
                    e["heading"] = float(p[8]) if p[8] else None
                else:
                    e["gga"] = True
                    e["quality"] = int(p[6] or 0)
                    e["sats"] = int(p[7] or 0)
                    e["hdop"] = float(p[8]) if p[8] else None
                    e["alt"] = float(p[9]) if p[9] else None
                    if e.get("lat") is None:
                        e["lat"], e["lon"] = _nmea_deg(p[2], p[3]), _nmea_deg(p[4], p[5])
            except ValueError:
                continue
            if e.get("rmc") and e.get("gga") and not e.get("done"):
                e["done"] = True
                with self.lock:
                    self.latest = dict(e)
                    self.seq += 1


class Vesc(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.data = None

    @staticmethod
    def _crc16(data):
        crc = 0
        for x in data:
            crc ^= x << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
                crc &= 0xFFFF
        return crc

    def run(self):
        try:
            import serial
            ser = serial.Serial(VESC_PORT, VESC_BAUD, timeout=0.05)
        except Exception as e:
            print(f"[HUB] VESC assente: {e}", flush=True)
            return
        pkt = bytes([0x02, 1, 4]) + struct.pack(">H", self._crc16(bytes([4]))) + b"\x03"
        while running:
            try:
                ser.reset_input_buffer()
                ser.write(pkt)
                time.sleep(0.03)
                r = ser.read(ser.in_waiting or 80)
                i = r.find(b"\x02")
                pl = r[i + 2:i + 2 + r[i + 1]] if i >= 0 and i + 2 <= len(r) else b""
                if len(pl) >= 56 and pl[0] == 4:
                    q = pl[1:]
                    self.data = (struct.unpack(">i", q[22:26])[0], struct.unpack(">h", q[20:22])[0] / 1000,
                                 struct.unpack(">i", q[4:8])[0] / 100, struct.unpack(">i", q[8:12])[0] / 100,
                                 struct.unpack(">h", q[26:28])[0] / 10, struct.unpack(">i", q[44:48])[0], q[52])
            except Exception:
                pass
            time.sleep(0.02)


def read_encoders():
    try:
        with open(ENC_CUM_FILE) as f:
            c, t, s, w = f.readline().split()[:4]
        t_ms = int(float(t) * 1000)
        if now_ms() - t_ms <= ENC_FRESH_MS:
            return t_ms, int(c), int(w), int(s)
    except (OSError, ValueError):
        pass
    try:                                        # bridge vecchio: solo sterzo, senza istante
        with open(ENC_STEER_FILE) as f:
            return None, None, None, int(f.readline())
    except (OSError, ValueError):
        return None


def read_limiter():
    try:
        with open(LIMITER_STATE_FILE) as f:
            st = json.load(f)
        if now_ms() - st.get("t_ms", 0) <= 500:
            return st
    except (OSError, ValueError):
        pass
    return None


def fmt(v, nd):
    return "" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def clocks():
    c = {"wall_minus_monotonic_s": time.time() - time.monotonic()}
    if hasattr(time, "CLOCK_BOOTTIME"):        # Linux: deve restare ~0 (il Pi non va mai in sospensione)
        c["boottime_minus_monotonic_s"] = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
    return c


class Writer:
    def __init__(self, info):
        self.info, self.f, self.opened = info, None, 0
        os.makedirs(OUT_DIR, exist_ok=True)

    def _open(self):
        self.close()
        name = f"sensors_{datetime.now():%Y%m%d_%H%M%S}"
        self.path = os.path.join(OUT_DIR, name + ".csv")
        self.f = open(self.path, "w")
        self.f.write(",".join(COLUMNS) + "\n")
        self.opened, self.n = time.monotonic(), 0
        meta = dict(self.info, file=name + ".csv", schema=SCHEMA, columns=COLUMNS,
                    clocks_start=clocks(), started=datetime.now().isoformat(timespec="milliseconds"))
        write_json_atomic(os.path.join(OUT_DIR, name + ".json"), meta)
        print(f"[HUB] scrivo {self.path}", flush=True)

    def row(self, line):
        if self.f is None or time.monotonic() - self.opened > ROTATE_S:
            self._open()
        self.f.write(line)
        self.n += 1
        if self.n % FSYNC_EVERY == 0:
            self.f.flush()
            os.fsync(self.f.fileno())

    def close(self):
        if self.f:
            self.f.flush()
            os.fsync(self.f.fileno())
            self.f.close()
            meta_p = self.path[:-4] + ".json"
            try:
                meta = json.load(open(meta_p))
                meta.update(clocks_end=clocks(), rows=self.n)
                write_json_atomic(meta_p, meta)
            except (OSError, ValueError):
                pass
            self.f = None


def main():
    global running
    conf = unit_conf()
    i2c = I2CSensors()
    gps = GPS()
    gps.start()
    vesc = None
    if conf.get("HUB_VESC") == "1":
        vesc = Vesc()
        vesc.start()
    time.sleep(2.0)                             # lascia arrivare config GPS e banner encoder
    try:
        fw = open(ENC_FW_FILE).read().strip()
    except OSError:
        fw = None
    info = {"unit": conf.get("ASMILE_NAME"), "unit_id": conf.get("ASMILE_ID"),
            "period_ms": PERIOD_MS, "clock": "CLOCK_MONOTONIC ms (= frame camera, = encoder)",
            "imu": i2c.imu_ok, "imu_dlpf_reg": MPU_DLPF, "ina219": i2c.ina_ok,
            "gps": gps.present, "gps_rate_ms": GPS_RATE_MS, "gps_config": gps.config_ack,
            "vesc": vesc is not None, "encoder_fw": fw}
    w = Writer(info)

    def stop(*_):
        global running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    last_gps_seq, flags = 0, {k: False for k in FLAG_EVENTS}
    nxt = time.monotonic()
    late = 0
    while running:
        nxt += PERIOD_MS / 1000.0
        d = nxt - time.monotonic()
        if d > 0:
            time.sleep(d)
        elif d < -PERIOD_MS / 1000.0:          # in ritardo di oltre un periodo: riallinea, non recuperare a raffica
            late += 1
            nxt = time.monotonic()
        t_ms = now_ms()
        imu = i2c.imu()
        enc = read_encoders()
        ina = i2c.ina()
        lim = read_limiter()
        with gps.lock:
            g = gps.latest if gps.seq != last_gps_seq else None
            last_gps_seq = gps.seq
        ev = []
        for path, name in FLAG_EVENTS.items():
            on = os.path.exists(path)
            if on != flags[path]:
                ev.append(name + ("_ON" if on else "_OFF"))
                flags[path] = on
        vals = [t_ms, datetime.now().isoformat(timespec="milliseconds")]
        vals += [fmt(x, 4) for x in imu[:3]] + [fmt(x, 2) for x in imu[3:]] if imu else [""] * 6
        vals += [fmt(x, 0) for x in enc] if enc else [""] * 4
        vals += [fmt(ina[0], 3), fmt(ina[1], 1)] if ina else ["", ""]
        if lim:
            vals += [lim.get("t_ms", ""), lim.get("source", ""), lim.get("zone", ""),
                     fmt(lim.get("speed_ms"), 3), fmt(lim.get("accel_ms2"), 3), fmt(lim.get("error_ms"), 3),
                     fmt(lim.get("target_deg"), 2), fmt(lim.get("cmd_deg"), 2)]
        else:
            vals += [""] * 8
        vd = vesc.data if vesc else None
        vals += [fmt(vd[0], 0), fmt(vd[1], 3), fmt(vd[2], 2), fmt(vd[3], 2), fmt(vd[4], 1),
                 fmt(vd[5], 0), fmt(vd[6], 0)] if vd else [""] * 7
        if g:
            vals += [g["t_ms"], g["utc"], g.get("quality", 0) if g.get("fix_rmc") else 0,
                     fmt(g.get("lat"), 7), fmt(g.get("lon"), 7), fmt(g.get("speed"), 3),
                     fmt(g.get("heading"), 1), fmt(g.get("sats"), 0), fmt(g.get("hdop"), 2), fmt(g.get("alt"), 1)]
        else:
            vals += [""] * 10
        vals.append("|".join(ev))
        w.row(",".join(str(v) for v in vals) + "\n")

        state = dict(zip(COLUMNS, vals))
        with gps.lock:
            gl = gps.latest
        if gl:                                  # nello stato live il GPS resta sempre l'ultimo
            state.update(gps_t_ms=gl["t_ms"], gps_fix=bool(gl.get("fix_rmc")), gps_lat=gl.get("lat"),
                         gps_lon=gl.get("lon"), gps_speed_ms=gl.get("speed") or 0.0,
                         gps_heading=gl.get("heading") or 0.0)
        state["t_ms"] = t_ms
        state["late_ticks"] = late
        write_json_atomic(HUB_STATE_FILE, state)
    w.close()
    print(f"[HUB] fermo (tick in ritardo: {late})", flush=True)


if __name__ == "__main__":
    main()
