#!/usr/bin/env python3
"""
Asmile Power Steering — Raspberry Pi 5

Servo-sterzo elettrico: l'encoder rileva la rotazione del volante,
il motore VESC assiste nella stessa direzione.

Rapporto meccanico 1:5 (motore:sterzo) → il motore gira 5x per ogni giro sterzo.
GAIN controlla quanta assistenza dare: 1.0 = pari angolo, >1.0 = sovra-assistenza.

Encoder: /tmp/encoder_position (daemon SPI)
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

# Steering tuning
GAIN = 1.2          # 1.0 = pari angolo, 1.2 = 20% sovra-assistenza (servo feel)
MAX_DUTY = 0.8      # Limite sicurezza (80%)
MIN_DUTY = 0.08     # Sotto questo il motore non si muove (attrito statico)
MIN_CHANGE = 3      # Soglia rumore encoder (counts)
DECAY_RATE = 0.85   # Rampa discesa quando encoder fermo (0-1, più basso = più rapido)
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
    print(f"GAIN={GAIN}  MAX_DUTY={MAX_DUTY}  MIN_DUTY={MIN_DUTY}")
    print(f"Rapporto 1:5 — encoder counts → duty con gain")
    print()

    vesc_set_duty(ser, 0.0)
    last_pos = read_encoder_position()
    current_duty = 0.0
    idle_cycles = 0

    try:
        while True:
            current_pos = read_encoder_position()

            # Wrap-around 12-bit (4095↔0)
            delta = current_pos - last_pos
            if delta > 2048:
                delta -= 4096
            elif delta < -2048:
                delta += 4096

            if abs(delta) >= MIN_CHANGE:
                # Rapporto 1:5: per ogni count encoder, il motore deve fare 5x
                # Con encoder 12bit (4096/giro), delta tipico 20-80 a 50Hz
                # duty = delta * 5 * GAIN / 4096
                #   delta=20 → 0.029 * GAIN, delta=50 → 0.073
                # Troppo basso ancora. Usiamo una scala pratica:
                # Il motore deve assistere con forza, quindi mappiamo
                # il range utile di delta (3-100) su duty (MIN_DUTY-MAX_DUTY)
                raw_duty = (abs(delta) / 60.0) * GAIN  # delta=60 → 100% di GAIN
                raw_duty = max(MIN_DUTY, min(MAX_DUTY, raw_duty))

                # Direzione dal segno del delta
                if delta < 0:
                    raw_duty = -raw_duty

                current_duty = raw_duty
                idle_cycles = 0
                last_pos = current_pos

                print(f"Pos: {current_pos:4d} | Delta: {delta:+4d} | Duty: {current_duty:+.3f}")
            else:
                # Encoder fermo → rampa a zero
                idle_cycles += 1
                if abs(current_duty) > 0.01:
                    current_duty *= DECAY_RATE
                    if abs(current_duty) < 0.01:
                        current_duty = 0.0
                elif current_duty != 0.0:
                    current_duty = 0.0

            vesc_set_duty(ser, current_duty)
            time.sleep(1.0 / LOOP_HZ)

    except KeyboardInterrupt:
        print("\nStop — motor idle")
        vesc_set_duty(ser, 0.0)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
