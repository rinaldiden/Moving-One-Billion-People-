#!/usr/bin/env python3
"""
VESC return-to-center — SET_RPM mode (closed-loop velocità).

A differenza di vesc_return_to_center.py (che usa SET_CURRENT), qui
mandiamo COMM_SET_RPM con un target ERPM costante. Il VESC modula
internamente la corrente per mantenere quella RPM:
  - poca resistenza → poca corrente
  - resistenza alta (mano utente) → corrente sale fino al cap configurato
    in VESC (Motor Current Max, oggi 43A)

Vantaggio vs SET_CURRENT: niente overshoot violento da corrente costante,
velocità intrinsecamente limitata, coppia "on demand" fino al cap.

Direzione encoder vs RPM signed:
  - error > 0 (pos > centro) → vogliamo encoder decresca → RPM negativa
  - error < 0 (pos < centro) → vogliamo encoder cresca → RPM positiva
Il segno effettivo è governato da DIRECTION_SIGN (calibrato dopo
Detect Hall Sensors 2026-05-22, allineato con CURRENT_SIGN di
vesc_return_to_center.py).

Safety: stessi check dello script SET_CURRENT — fuori range, deadband,
zero-crossing, encoder lost.
"""
import csv
import os
import signal
import struct
import subprocess
import sys
import time
from datetime import datetime

import serial

# --- Hardware ---
UART = "/dev/ttyAMA0"
BAUD = 115200
ENC_FILE = "/tmp/encoder_position"

# --- Calibrazione (steering_limits.json) ---
CENTER = 3800
SX_MAX = 3565
DX_MAX = 4046
SAFETY_MARGIN = 20
DIRECTION_SIGN = +1   # 2026-05-22 Detect Hall Sensors: allineato a CURRENT_SIGN

# --- Controllo SET_RPM ---
LOOP_HZ = 50
DT = 1.0 / LOOP_HZ
DEADBAND = 10                # encoder step. |error| ≤ DEADBAND → STOP
TARGET_ERPM = 100            # ERPM (electrical RPM). Test 25A SET_CURRENT
                             # mostrava picchi a ~130 ERPM in movimento.
                             # 100 ERPM ≈ 60-70 step/s encoder ≈ 3-4s per
                             # corsa intera. Alzare per più velocità.
ABORT_TIMEOUT_S = 15.0       # se non arriva al centro in 15s → abort
TACH_CHECK_INTERVAL = 0.1    # poll telemetria VESC

# --- Logging ---
LOG_DIR = os.path.expanduser("~/wip/logging/vesc")

# --- VESC protocol ---
COMM_SET_DUTY = 5
COMM_SET_CURRENT = 6
COMM_SET_RPM = 8
COMM_GET_VALUES = 4


def crc16(data):
    c = 0
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def pkt(payload):
    return (bytes([0x02, len(payload)]) + payload
            + struct.pack(">H", crc16(payload)) + bytes([0x03]))


def send_rpm(ser, erpm):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_RPM, int(erpm))))
    except (serial.SerialException, OSError):
        pass


def send_current(ser, amps):
    """Fallback per stop sicuro."""
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_CURRENT, int(amps * 1000))))
    except (serial.SerialException, OSError):
        pass


def send_duty(ser, duty):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_DUTY, int(duty * 100000))))
    except (serial.SerialException, OSError):
        pass


def query_tach(ser):
    try:
        ser.reset_input_buffer()
        ser.write(pkt(bytes([COMM_GET_VALUES])))
        time.sleep(0.04)
        buf = ser.read(256)
    except (serial.SerialException, OSError):
        return None
    if not buf:
        return None
    start = buf.find(b"\x02")
    if start < 0 or len(buf) - start < 50:
        return None
    plen = buf[start + 1]
    payload = buf[start + 2:start + 2 + plen]
    if len(payload) < 50 or payload[0] != COMM_GET_VALUES:
        return None
    try:
        p = payload[1:]
        return {
            "i_motor": struct.unpack(">i", p[4:8])[0] / 100.0,
            "i_input": struct.unpack(">i", p[8:12])[0] / 100.0,
            "duty":    struct.unpack(">h", p[20:22])[0] / 1000.0,
            "rpm":     struct.unpack(">i", p[22:26])[0],
            "tach":    struct.unpack(">i", p[44:48])[0] if len(p) >= 48 else 0,
        }
    except struct.error:
        return None


def read_encoder():
    try:
        with open(ENC_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return -1


def find_recorder_pid():
    try:
        out = subprocess.check_output(["pgrep", "-f", "training_recorder.py"]).decode().strip()
        pids = [int(x) for x in out.split()]
        return pids[-1] if pids else None
    except subprocess.CalledProcessError:
        return None


def main():
    recorder_pid = find_recorder_pid()
    if recorder_pid:
        os.kill(recorder_pid, signal.SIGSTOP)
        time.sleep(0.3)
        print(f"[INFO] training_recorder PID {recorder_pid} sospeso (SIGSTOP)")

    ser = None
    log_f = None
    aborted = False
    abort_reason = ""
    try:
        ser = serial.Serial(UART, BAUD, timeout=0.2)
        ser.reset_input_buffer()

        pos = read_encoder()
        if pos < 0:
            print("[ERROR] encoder daemon non attivo (/tmp/encoder_position)")
            return

        print(f"[START] pos={pos}  center={CENTER}  error={pos - CENTER:+d}")
        print(f"        SX_MAX={SX_MAX}  DX_MAX={DX_MAX}  safety_margin={SAFETY_MARGIN}")
        print(f"        SET_RPM closed-loop: target_erpm={TARGET_ERPM}  loop={LOOP_HZ}Hz")
        print(f"        Limite corrente: configurato in VESC (Motor Current Max).")

        if abs(pos - CENTER) <= DEADBAND:
            print(f"[DONE] già al centro (|error|={abs(pos - CENTER)} ≤ {DEADBAND})")
            return

        t_start = time.monotonic()
        prev_error = None
        last_tach_check = 0.0
        telem = {"i_motor": 0.0, "i_input": 0.0, "duty": 0.0, "rpm": 0, "tach": 0}

        # Logging CSV
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f"return_rpm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        log_f = open(log_path, "w", newline="")
        log_csv = csv.writer(log_f)
        log_csv.writerow([
            "timestamp_iso", "t_rel", "pos", "error",
            "target_erpm", "actual_rpm",
            "i_motor", "i_input", "duty_real",
        ])
        print(f"[LOG] {log_path}")

        while True:
            t0 = time.monotonic()
            pos = read_encoder()
            if pos < 0:
                send_rpm(ser, 0); send_current(ser, 0)
                abort_reason = "encoder lost"
                aborted = True
                break

            # Safety: fuori finecorsa
            if pos < (SX_MAX - SAFETY_MARGIN) or pos > (DX_MAX + SAFETY_MARGIN):
                send_rpm(ser, 0); send_current(ser, 0)
                abort_reason = f"OUT OF RANGE pos={pos}"
                aborted = True
                break

            # Timeout globale
            if t0 - t_start > ABORT_TIMEOUT_S:
                send_rpm(ser, 0); send_current(ser, 0)
                abort_reason = f"TIMEOUT {ABORT_TIMEOUT_S}s"
                aborted = True
                break

            error = pos - CENTER

            # Zero-crossing: ha attraversato il centro per inerzia → STOP
            if prev_error is not None and (error * prev_error) < 0:
                send_rpm(ser, 0); send_current(ser, 0)
                time.sleep(0.02)
                send_rpm(ser, 0); send_current(ser, 0)
                print(f"[DONE] CROSSED center pos={pos} error={error:+d} "
                      f"(was {prev_error:+d}) in {t0 - t_start:.2f}s")
                break

            # Deadband: STOP MOTORE + EXIT
            if abs(error) <= DEADBAND:
                send_rpm(ser, 0); send_current(ser, 0)
                time.sleep(0.02)
                send_rpm(ser, 0); send_current(ser, 0)
                print(f"[DONE] ARRIVED at center pos={pos} error={error:+d} in {t0 - t_start:.2f}s")
                break

            prev_error = error

            # error > 0 → encoder deve decrescere → RPM negativa (con DIRECTION_SIGN=+1)
            # error < 0 → encoder deve crescere → RPM positiva
            direction = -1 if error > 0 else +1
            target_rpm = DIRECTION_SIGN * TARGET_ERPM * direction

            send_rpm(ser, target_rpm)

            # CSV row
            log_csv.writerow([
                datetime.now().isoformat(timespec="milliseconds"),
                f"{t0 - t_start:.3f}", pos, error,
                target_rpm, telem["rpm"],
                f"{telem['i_motor']:.2f}", f"{telem['i_input']:.2f}",
                f"{telem['duty']:.4f}",
            ])

            # Telemetria + stampa
            if t0 - last_tach_check >= TACH_CHECK_INTERVAL:
                last_tach_check = t0
                t = query_tach(ser)
                if t:
                    telem.update(t)
                    print(f"  pos={pos:4d} err={error:+4d} "
                          f"target_rpm={target_rpm:+5d} actual_rpm={t['rpm']:+5d} "
                          f"i_mot={t['i_motor']:+5.2f}A i_in={t['i_input']:+5.2f}A "
                          f"duty={t['duty']:+.3f}")

            elapsed = time.monotonic() - t0
            if elapsed < DT:
                time.sleep(DT - elapsed)

    except KeyboardInterrupt:
        print("\n[STOPPED] Ctrl-C")
        aborted = True
        abort_reason = "Ctrl-C"
    finally:
        if ser and ser.is_open:
            try:
                send_rpm(ser, 0)
                send_current(ser, 0)
                time.sleep(0.05)
                send_rpm(ser, 0)
                send_current(ser, 0)
                time.sleep(0.05)
                send_duty(ser, 0)
            except Exception:
                pass
            ser.close()
        if log_f:
            try:
                log_f.close()
            except Exception:
                pass
        if recorder_pid:
            try:
                os.kill(recorder_pid, signal.SIGCONT)
                print(f"[INFO] training_recorder PID {recorder_pid} ripreso (SIGCONT)")
            except ProcessLookupError:
                pass
        if aborted:
            print(f"[ABORT] {abort_reason}")
            sys.exit(1)


if __name__ == "__main__":
    main()
