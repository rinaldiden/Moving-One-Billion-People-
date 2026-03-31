#!/usr/bin/env python3
"""
Test motore VESC — prova a farlo girare con COMM_SET_CURRENT.
Sequenza: 2A, 5A, 8A, 10A (1.5s ciascuno), poi stop.
Monitora encoder per verificare movimento.
"""

import serial
import struct
import time
import sys

UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"

# VESC commands
COMM_FW_VERSION = 0
COMM_SET_DUTY = 5
COMM_SET_CURRENT = 6
COMM_ALIVE = 30


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


def vesc_set_current(ser, amps: float):
    """Send COMM_SET_CURRENT. Amps as float, converted to milliamps int32."""
    ma = int(amps * 1000)
    ser.write(vesc_packet(struct.pack(">Bi", COMM_SET_CURRENT, ma)))


def vesc_set_duty(ser, duty: float):
    """Send COMM_SET_DUTY. Duty as float -1.0 to +1.0."""
    duty_int = int(duty * 100000)
    ser.write(vesc_packet(struct.pack(">Bi", COMM_SET_DUTY, duty_int)))


def vesc_alive(ser):
    """Send COMM_ALIVE keepalive."""
    ser.write(vesc_packet(bytes([COMM_ALIVE])))


def vesc_get_fw(ser):
    """Request FW version and read response."""
    ser.reset_input_buffer()
    ser.write(vesc_packet(bytes([COMM_FW_VERSION])))
    time.sleep(0.1)
    resp = ser.read(ser.in_waiting or 64)
    return resp


def read_encoder() -> int:
    try:
        with open(POSITION_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


def main():
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
    ser.reset_input_buffer()

    # Step 1: verify FW communication
    print("=== Test Motor Spin ===")
    print()
    print("[1] Verifica comunicazione FW...")
    fw = vesc_get_fw(ser)
    if len(fw) > 3:
        print(f"    VESC risponde: {fw.hex()} ({len(fw)} bytes) — OK")
    else:
        print(f"    VESC non risponde! ({fw.hex() if fw else 'nessun dato'})")
        print("    Controlla: VESC acceso? UART collegato? Baud rate?")
        ser.close()
        sys.exit(1)

    # Step 2: read initial encoder
    enc_start = read_encoder()
    print(f"[2] Encoder posizione iniziale: {enc_start}")
    print()

    # Step 3: test corrente crescente
    test_currents = [2.0, 5.0, 8.0, 10.0]
    duration = 1.5  # secondi per ogni step

    print("[3] Test COMM_SET_CURRENT (corrente crescente)...")
    print(f"    Sequenza: {test_currents} A, {duration}s ciascuno")
    print()
    print(f"    {'Corrente':>10s}  {'Enc start':>10s}  {'Enc end':>10s}  {'Delta':>8s}  {'Movimento':>10s}")
    print(f"    {'--------':>10s}  {'---------':>10s}  {'-------':>10s}  {'-----':>8s}  {'---------':>10s}")

    for amps in test_currents:
        enc_before = read_encoder()

        # Send current command repeatedly for duration
        t0 = time.time()
        while time.time() - t0 < duration:
            vesc_set_current(ser, amps)
            time.sleep(0.02)  # 50Hz

        enc_after = read_encoder()
        delta = enc_after - enc_before
        if delta > 2048:
            delta -= 4096
        elif delta < -2048:
            delta += 4096

        moved = "SI!" if abs(delta) > 2 else "no"
        print(f"    {amps:>8.1f} A  {enc_before:>10d}  {enc_after:>10d}  {delta:>+8d}  {moved:>10s}")

        # Brief pause between steps
        vesc_set_current(ser, 0.0)
        time.sleep(0.5)

    # Step 4: test con duty (per confronto)
    print()
    print("[4] Test COMM_SET_DUTY (per confronto)...")
    test_duties = [0.05, 0.1, 0.2, 0.3]
    print(f"    Sequenza: {test_duties} duty, {duration}s ciascuno")
    print()
    print(f"    {'Duty':>10s}  {'Enc start':>10s}  {'Enc end':>10s}  {'Delta':>8s}  {'Movimento':>10s}")
    print(f"    {'----':>10s}  {'---------':>10s}  {'-------':>10s}  {'-----':>8s}  {'---------':>10s}")

    for duty in test_duties:
        enc_before = read_encoder()

        t0 = time.time()
        while time.time() - t0 < duration:
            vesc_set_duty(ser, duty)
            time.sleep(0.02)

        enc_after = read_encoder()
        delta = enc_after - enc_before
        if delta > 2048:
            delta -= 4096
        elif delta < -2048:
            delta += 4096

        moved = "SI!" if abs(delta) > 2 else "no"
        print(f"    {duty:>8.2f}    {enc_before:>10d}  {enc_after:>10d}  {delta:>+8d}  {moved:>10s}")

        vesc_set_duty(ser, 0.0)
        time.sleep(0.5)

    # Stop
    vesc_set_current(ser, 0.0)
    vesc_set_duty(ser, 0.0)

    enc_end = read_encoder()
    total_delta = enc_end - enc_start
    if total_delta > 2048:
        total_delta -= 4096
    elif total_delta < -2048:
        total_delta += 4096

    print()
    print(f"[5] Riepilogo:")
    print(f"    Encoder inizio: {enc_start}, fine: {enc_end}, delta totale: {total_delta:+d}")
    print(f"    Delta in gradi: {total_delta * 360.0 / 4096.0:+.1f}°")
    print()

    if abs(total_delta) > 2:
        print("    >>> MOTORE SI MUOVE! Possiamo procedere col servo loop.")
    else:
        print("    >>> MOTORE NON SI MUOVE.")
        print("    Possibili cause:")
        print("    - APP VESC non configurata su UART (serve VESC Tool)")
        print("    - Motor detection non fatta su questo setup")
        print("    - Cavi motore/Hall scollegati")
        print("    - VESC in fault (LED rosso lampeggiante?)")

    ser.close()


if __name__ == "__main__":
    main()
