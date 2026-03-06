#!/usr/bin/env python3
"""
Asmile Steering — Raspberry Pi 5
Reads SSI encoder position (from daemon), sends duty to VESC via UART.

Encoder position is read from /tmp/encoder_position (written by encoder_spi_daemon.py).
VESC is connected on UART0: GPIO 14 (TX) → VESC RX, GPIO 15 (RX) → VESC TX.

Dependencies:
  pip install pyserial
"""

import serial
import struct
import time
import sys

# --- Config ---
UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"

MIN_CHANGE = 5
MAX_DUTY = 0.8

# VESC UART protocol
COMM_SET_DUTY = 5


# --- VESC UART ---

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


def vesc_set_duty(ser, duty: float):
    duty_int = int(duty * 100000)
    payload = struct.pack(">Bi", COMM_SET_DUTY, duty_int)
    crc = crc16(payload)
    packet = (
        bytes([0x02, len(payload)])
        + payload
        + struct.pack(">H", crc)
        + bytes([0x03])
    )
    ser.write(packet)


# --- Encoder ---

def read_encoder_position() -> int:
    with open(POSITION_FILE, "r") as f:
        return int(f.read().strip())


# --- Main loop ---

def main():
    # Check encoder daemon is running
    try:
        read_encoder_position()
    except FileNotFoundError:
        print("ERROR: encoder daemon not running (/tmp/encoder_position not found)")
        print("Start it: sudo systemctl start encoder-ssi")
        sys.exit(1)

    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)

    print("Encoder → VESC — Motor spins proportional to steering rotation")
    vesc_set_duty(ser, 0.0)
    last_pos = read_encoder_position()

    try:
        while True:
            current_pos = read_encoder_position()

            # Wrap-around at 12-bit boundary (4095↔0)
            delta = current_pos - last_pos
            if delta > 2048:
                delta -= 4096
            elif delta < -2048:
                delta += 4096

            if abs(delta) >= MIN_CHANGE:
                duty = max(-MAX_DUTY, min(MAX_DUTY, delta / 2048.0))
                vesc_set_duty(ser, duty)
                print(f"Pos: {current_pos} | Delta: {delta:+d} | Duty: {duty:+.3f}")
                last_pos = current_pos

            time.sleep(0.02)  # ~50Hz

    except KeyboardInterrupt:
        print("\nStop — motor idle")
        vesc_set_duty(ser, 0.0)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
