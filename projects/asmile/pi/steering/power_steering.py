#!/usr/bin/env python3
"""
Asmile Power Steering v3 — SIMPLE

Encoder gira → motore gira. Proporzionale al delta encoder, basta.
COMM_SET_CURRENT: delta encoder * scala = corrente motore.
Gear ratio 5:1 (5 giri motore = 1 giro piantone).
"""

import serial
import struct
import time
import sys

# --- Config ---
UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"

LOOP_HZ = 50            # Match encoder daemon rate
SCALE = 1.0             # Amps per encoder step. THE tuning knob.
MAX_CURRENT = 15.0       # Safety clamp (Amps)
MIN_DELTA = 1            # Ignore noise below this

# VESC commands
COMM_SET_CURRENT = 6


# --- VESC Protocol ---

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
    crc = crc16(payload)
    return bytes([0x02, len(payload)]) + payload + struct.pack(">H", crc) + bytes([0x03])


def vesc_set_current(ser, amps: float):
    ma = int(amps * 1000)
    ser.write(vesc_packet(struct.pack(">Bi", COMM_SET_CURRENT, ma)))


# --- Encoder ---

def read_encoder() -> int:
    with open(POSITION_FILE, "r") as f:
        return int(f.read().strip())


def wrap_delta(d: int) -> int:
    if d > 2048:
        d -= 4096
    elif d < -2048:
        d += 4096
    return d


# --- Main ---

def main():
    try:
        read_encoder()
    except FileNotFoundError:
        print("ERROR: encoder daemon not running")
        sys.exit(1)

    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
    ser.reset_input_buffer()

    prev_pos = read_encoder()
    print(f"=== Power Steering v3 === SCALE={SCALE} MAX={MAX_CURRENT}A")
    print(f"Start pos: {prev_pos}")

    try:
        while True:
            pos = read_encoder()
            delta = wrap_delta(pos - prev_pos)
            prev_pos = pos

            if abs(delta) >= MIN_DELTA:
                current = delta * SCALE
                current = max(-MAX_CURRENT, min(MAX_CURRENT, current))
                vesc_set_current(ser, current)
                print(f"pos={pos:4d} d={delta:+3d} I={current:+.1f}A")
            else:
                vesc_set_current(ser, 0.0)

            time.sleep(1.0 / LOOP_HZ)

    except KeyboardInterrupt:
        print("\nStop")
        vesc_set_current(ser, 0.0)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
