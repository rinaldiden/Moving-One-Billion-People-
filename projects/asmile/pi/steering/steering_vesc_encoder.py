#!/usr/bin/env python3
"""
Asmile Power Steering — Raspberry Pi 5

Porta Python dello sketch Arduino steering_vesc_encoder.ino.
Stessa logica: duty = delta / 2048.0, comando SOLO quando c'è movimento.
Il VESC mantiene l'ultimo duty finché non riceve un nuovo comando.

Encoder: /tmp/encoder_position (daemon SPI, 50Hz)
VESC: UART0 GPIO14/15, 115200 baud
"""

import serial
import struct
import time
import sys

# --- Config ---
UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
POSITION_FILE = "/tmp/encoder_position"

# Stesso dello sketch Arduino
MIN_CHANGE = 5      # Min cambio per inviare comando (~mezzo grado)
MAX_DUTY = 0.3      # Limite sicurezza (0.8 nello sketch, 0.3 per test)
SENSITIVITY = 2048.0  # Divisore: delta/2048 = duty. Abbassare = più reattivo
LOOP_HZ = 50

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
    try:
        read_encoder_position()
    except FileNotFoundError:
        print("ERROR: encoder daemon not running (/tmp/encoder_position not found)")
        print("Start it: sudo systemctl start encoder-ssi")
        sys.exit(1)

    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)

    print(f"=== Asmile Power Steering ===")
    print(f"MIN_CHANGE={MIN_CHANGE}  MAX_DUTY={MAX_DUTY}  SENSITIVITY={SENSITIVITY}")
    print(f"Logica Arduino: duty = delta/{SENSITIVITY}, comando solo su movimento.")
    print()

    vesc_set_duty(ser, 0.0)
    last_pos = read_encoder_position()

    try:
        while True:
            current_pos = read_encoder_position()

            # Wrap-around come nello sketch Arduino
            delta = current_pos - last_pos
            if delta > 2048:
                delta -= 4096
            elif delta < -2048:
                delta += 4096

            # Comando SOLO se c'è movimento significativo (come Arduino)
            if abs(delta) >= MIN_CHANGE:
                duty = delta / SENSITIVITY
                duty = max(-MAX_DUTY, min(MAX_DUTY, duty))

                vesc_set_duty(ser, duty)
                last_pos = current_pos

                print(f"Pos: {current_pos:4d} | Delta: {delta:+4d} | Duty: {duty:+.3f}")

            # Se encoder fermo: NON manda nulla, VESC mantiene ultimo duty

            time.sleep(1.0 / LOOP_HZ)

    except KeyboardInterrupt:
        print("\nStop — motor idle")
        vesc_set_duty(ser, 0.0)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
