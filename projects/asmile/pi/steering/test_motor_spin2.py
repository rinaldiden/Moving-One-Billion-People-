#!/usr/bin/env python3
"""
Test motore v2 — 10A per 5 secondi, log encoder real-time.
Poi inverte a -10A per 5 secondi. Poi stop.
"""

import serial
import struct
import time

UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"
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


def vesc_set_current(ser, amps: float):
    ma = int(amps * 1000)
    ser.write(vesc_packet(struct.pack(">Bi", COMM_SET_CURRENT, ma)))


def read_encoder() -> int:
    try:
        with open(POSITION_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


def run_phase(ser, label, amps, duration):
    print(f"\n--- {label}: {amps:+.0f}A per {duration}s ---")
    enc_start = read_encoder()
    print(f"Encoder start: {enc_start}")

    t0 = time.time()
    last_print = t0
    last_enc = enc_start
    while time.time() - t0 < duration:
        vesc_set_current(ser, amps)
        enc = read_encoder()

        # Print every 0.25s or on change
        now = time.time()
        if enc != last_enc or now - last_print >= 0.25:
            elapsed = now - t0
            delta = enc - enc_start
            if delta > 2048: delta -= 4096
            elif delta < -2048: delta += 4096
            deg = delta * 360.0 / 4096.0
            print(f"  t={elapsed:5.2f}s  enc={enc:4d}  delta={delta:+5d}  ({deg:+6.1f}°)")
            last_print = now
            last_enc = enc

        time.sleep(0.02)

    enc_end = read_encoder()
    total = enc_end - enc_start
    if total > 2048: total -= 4096
    elif total < -2048: total += 4096
    print(f"  FINE: delta={total:+d} steps ({total*360.0/4096.0:+.1f}°)")
    return total


def main():
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
    ser.reset_input_buffer()

    print("=== Test Motor Spin v2 ===")
    print("10A avanti 5s, poi -10A indietro 5s")

    d1 = run_phase(ser, "AVANTI", 10.0, 5.0)
    vesc_set_current(ser, 0.0)
    time.sleep(1.0)

    d2 = run_phase(ser, "INDIETRO", -10.0, 5.0)
    vesc_set_current(ser, 0.0)

    print(f"\n=== Riepilogo ===")
    print(f"Avanti:  {d1:+d} steps ({d1*360.0/4096.0:+.1f}°)")
    print(f"Indietro: {d2:+d} steps ({d2*360.0/4096.0:+.1f}°)")

    if abs(d1) > 2 or abs(d2) > 2:
        print("\n>>> Encoder rileva movimento! Pronti per servo loop.")
    else:
        print("\n>>> Encoder ancora fermo.")
        print("    L'encoder è accoppiato all'asse uscita gearbox?")
        print("    Prova a girare l'asse a mano e controlla /tmp/encoder_position")

    ser.close()


if __name__ == "__main__":
    main()
