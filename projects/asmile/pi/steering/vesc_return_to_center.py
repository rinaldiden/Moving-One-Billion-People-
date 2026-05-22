#!/usr/bin/env python3
"""
VESC return-to-center — closed-loop encoder → centro 3800.

Algoritmo:
  - Pausa training_recorder per liberare UART
  - Loop 50Hz: legge encoder, target_duty proporzionale all'errore
  - Duty parte basso (0.02), sale gradualmente se il motore non si muove
    finché vede movimento nella direzione corretta (risolve lo stallo
    osservato il 2026-05-18 a corrente fissa)
  - Tach VESC double-check: se direzione tach opposta a direzione encoder → abort
  - Safety cut hardware ai finecorsa SX_MAX/DX_MAX

Costanti da projects/asmile/config/steering_limits.json.
Lancia con switch OFF preferibilmente, ma gestisce anche switch ON
sospendendo solo training_recorder (speed_limiter non tocca la UART VESC).
"""
import os
import signal
import struct
import subprocess
import sys
import time

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
CURRENT_SIGN = +1   # 2026-05-22 dopo Detect Hall Sensors: invertito (era -1)

# --- Controllo (CURRENT mode) ---
LOOP_HZ = 50
DT = 1.0 / LOOP_HZ
DEADBAND = 10           # step encoder. |error| ≤ DEADBAND → STOP IMMEDIATO + exit
CURRENT_MIN = 8.0       # A — coppia minima (vince attrito statico)
CURRENT_MAX = 18.0      # A — cap per condizioni reali (motor limit 43A, ample margin)
KP = 0.06               # A/step. error 200 → 12A. error 50 → 3A (floor a CURRENT_MIN).
STALL_TIMEOUT = 0.5     # s senza movimento prima di iniziare ramp-up
ABORT_TIMEOUT = 3.0     # s a CURRENT_MAX senza movimento → abort
TACH_CHECK_INTERVAL = 0.2

# --- VESC protocol ---
COMM_SET_CURRENT = 6
COMM_SET_DUTY = 5
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


def send_duty(ser, duty):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_DUTY, int(duty * 100000))))
    except (serial.SerialException, OSError):
        pass


def send_current(ser, amps):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_CURRENT, int(amps * 1000))))
    except (serial.SerialException, OSError):
        pass


def query_tach(ser):
    """Read VESC telemetry, return dict or None."""
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
        # primo pid è il sudo wrapper, prendiamo l'ultimo (figlio python)
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
        print(f"        CURRENT mode: KP={KP}A/step  range {CURRENT_MIN}→{CURRENT_MAX}A  loop={LOOP_HZ}Hz")

        if abs(pos - CENTER) <= DEADBAND:
            print(f"[DONE] già al centro (|error|={abs(pos - CENTER)} ≤ {DEADBAND})")
            return

        pos_prev = pos
        t_last_motion = time.monotonic()
        t_at_max = None
        tach_prev = None
        pos_at_tach = pos
        last_tach_check = 0.0
        t_start = time.monotonic()

        while True:
            t0 = time.monotonic()
            pos = read_encoder()
            if pos < 0:
                send_current(ser, 0)
                abort_reason = "encoder lost"
                aborted = True
                break

            # Safety: fuori finecorsa
            if pos < (SX_MAX - SAFETY_MARGIN) or pos > (DX_MAX + SAFETY_MARGIN):
                send_current(ser, 0)
                abort_reason = f"OUT OF RANGE pos={pos}"
                aborted = True
                break

            error = pos - CENTER

            # Deadband: target raggiunto, STOP MOTORE + EXIT (no oscillation)
            if abs(error) <= DEADBAND:
                send_current(ser, 0)
                time.sleep(0.02)
                send_current(ser, 0)   # ridondanza, garantisce stop
                print(f"[DONE] ARRIVED at center pos={pos} error={error:+d} in {t0 - t_start:.2f}s")
                break

            direction = -1 if error > 0 else 1  # +1 = vogliamo encoder aumenti
            delta = pos - pos_prev
            moving_correct = (delta * direction) > 0 and abs(delta) >= 1

            # P-controller in CURRENT: scala con errore, floor + cap
            target_mag = max(CURRENT_MIN, min(CURRENT_MAX, KP * abs(error)))

            # Detect stallo per abort safety
            if moving_correct:
                t_last_motion = t0
                t_at_max = None
            elif t0 - t_last_motion > STALL_TIMEOUT:
                if target_mag >= CURRENT_MAX - 0.1:
                    if t_at_max is None:
                        t_at_max = t0
                    elif t0 - t_at_max > ABORT_TIMEOUT:
                        send_current(ser, 0)
                        abort_reason = f"STALL: current_max={CURRENT_MAX}A per {ABORT_TIMEOUT}s senza movimento"
                        aborted = True
                        break

            target_current = CURRENT_SIGN * target_mag * direction
            send_current(ser, target_current)

            # Tach double-check periodico
            if t0 - last_tach_check >= TACH_CHECK_INTERVAL:
                last_tach_check = t0
                t = query_tach(ser)
                if t:
                    tach_now = t["tach"]
                    if tach_prev is not None:
                        d_tach = tach_now - tach_prev
                        d_enc = pos - pos_at_tach
                        # Validazione direzione solo se entrambi muovono significativamente
                        if abs(d_enc) > 8 and abs(d_tach) > 3:
                            if (d_tach > 0) != (d_enc > 0):
                                send_current(ser, 0)
                                abort_reason = f"TACH/ENC MISMATCH: d_tach={d_tach} d_enc={d_enc}"
                                aborted = True
                                break
                    tach_prev = tach_now
                    pos_at_tach = pos
                    print(f"  pos={pos:4d} err={error:+4d} i_set={target_current:+5.2f}A "
                          f"i_mot={t['i_motor']:+5.2f}A i_in={t['i_input']:+5.2f}A "
                          f"duty={t['duty']:+.3f} tach={tach_now} rpm={t['rpm']}")

            pos_prev = pos
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
                send_current(ser, 0)
                time.sleep(0.05)
                send_current(ser, 0)
                time.sleep(0.05)
                send_duty(ser, 0)   # ridondanza finale: forza duty 0 anche se in CURRENT mode
            except Exception:
                pass
            ser.close()
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
