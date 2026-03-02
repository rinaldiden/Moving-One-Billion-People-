#!/usr/bin/env python3
"""
Asmile Steering — Raspberry Pi 5
Reads 12-bit SSI encoder, calculates delta, sends duty to VESC via UART.

Converted from: firmware/steering/steering_vesc_encoder.ino

Raspi 5 Wiring (pins updated for GPS + IMU compatibility):
  UART0:  GPIO 14 (TX) → VESC RX  |  GPIO 15 (RX) → VESC TX
  SSI Encoder (via 2x RS-485 modules):
    GPIO 17 (Pin 11) → CLOCK  (RS-485 #1 DI → encoder CLK+/CLK-)
    GPIO 27 (Pin 13) → DATA   (RS-485 #2 RO ← encoder DATA+/DATA-)
    GPIO 22 (Pin 15) → CLOCK_ENABLE (keep HIGH)
    GPIO 23 (Pin 16) → DATA_ENABLE  (keep LOW)

  Other devices on the same Raspi:
    UART3 GPIO 8/9   → GPS NEO-M10
    I2C1  GPIO 2/3   → MPU6050 IMU
    PWM0  GPIO 12    → Brake servo

Dependencies:
  sudo apt install python3-lgpio
  pip install pyserial
"""

import lgpio
import serial
import struct
import time

# --- Config ---
UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200

# GPIO (BCM) — Pi 5 uses gpiochip4
# Pins reassigned to avoid conflict with I2C1 (MPU6050) and UART3 (GPS)
GPIO_CHIP = 4
PIN_CLOCK = 17      # Pin 11 — was GPIO 4
PIN_DATA = 27       # Pin 13 — was GPIO 3 (now free for I2C1 SCL)
PIN_CLOCK_EN = 22   # Pin 15 — was GPIO 5
PIN_DATA_EN = 23    # Pin 16 — was GPIO 6

# SSI Encoder
BITS = 12
SAMPLES = 5
MIN_CHANGE = 5
MAX_DUTY = 0.8

# VESC UART protocol
COMM_SET_DUTY = 5


# --- VESC UART ---

def crc16(data: bytes) -> int:
    """CRC16-CCITT for VESC protocol."""
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
    """Send SET_DUTY command to VESC via UART."""
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


# --- SSI Encoder ---

def read_ssi_single(h) -> int:
    """Read a single position from SSI encoder (bit-bang)."""
    raw = 0
    time.sleep(25e-6)
    for _ in range(BITS):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        time.sleep(1e-6)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(2e-6)
        raw = (raw << 1) | lgpio.gpio_read(h, PIN_DATA)
    time.sleep(25e-6)
    return raw


def read_ssi(h) -> int:
    """Read SSI encoder with median filter (5 samples)."""
    readings = sorted(read_ssi_single(h) for _ in range(SAMPLES))
    return readings[SAMPLES // 2]


# --- Main loop ---

def main():
    # Init GPIO
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, PIN_CLOCK, 1)
    lgpio.gpio_claim_input(h, PIN_DATA)
    lgpio.gpio_claim_output(h, PIN_CLOCK_EN, 1)  # Always HIGH
    lgpio.gpio_claim_output(h, PIN_DATA_EN, 0)   # Always LOW

    # Init UART
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)

    print("Encoder → VESC — Motor spins only with rotation (CW/CCW)")
    vesc_set_duty(ser, 0.0)
    last_pos = 0

    try:
        while True:
            current_pos = read_ssi(h)

            # Wrap-around 4095↔0
            if last_pos >= 4090 and current_pos <= 5:
                delta = 1
            elif last_pos <= 5 and current_pos >= 4090:
                delta = -1
            else:
                delta = current_pos - last_pos

            if abs(delta) >= MIN_CHANGE:
                duty = max(-MAX_DUTY, min(MAX_DUTY, delta / 2048.0))
                vesc_set_duty(ser, duty)
                print(f"Pos: {current_pos} | Delta: {delta} | Duty: {duty:.3f}")
                last_pos = current_pos

            time.sleep(0.02)  # ~50Hz

    except KeyboardInterrupt:
        print("\nStop — motor idle")
        vesc_set_duty(ser, 0.0)
    finally:
        ser.close()
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
