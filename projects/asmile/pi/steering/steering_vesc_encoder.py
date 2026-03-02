#!/usr/bin/env python3
"""
Sterzo Asmile — Raspberry Pi 5
Legge encoder SSI 12-bit, calcola delta, invia duty al VESC via UART.

Convertito da: firmware/steering/steering_vesc_encoder.ino

Cablaggio Raspi 5 (pin aggiornati per compatibilità con GPS + IMU):
  UART0:  GPIO 14 (TX) → VESC RX  |  GPIO 15 (RX) → VESC TX
  Encoder SSI (via 2x moduli RS-485):
    GPIO 17 (Pin 11) → CLOCK  (RS-485 #1 DI → encoder CLK+/CLK-)
    GPIO 27 (Pin 13) → DATA   (RS-485 #2 RO ← encoder DATA+/DATA-)
    GPIO 22 (Pin 15) → CLOCK_ENABLE (tenere HIGH)
    GPIO 23 (Pin 16) → DATA_ENABLE  (tenere LOW)

  Altri dispositivi sullo stesso Raspi:
    UART3 GPIO 8/9   → GPS NEO-M10
    I2C1  GPIO 2/3   → MPU6050 IMU
    PWM0  GPIO 12    → Servo freno

Dipendenze:
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

# GPIO (BCM) — Pi 5 usa gpiochip4
# Pin riassegnati per evitare conflitto con I2C1 (MPU6050) e UART3 (GPS)
GPIO_CHIP = 4
PIN_CLOCK = 17      # Pin 11 — era GPIO 4
PIN_DATA = 27       # Pin 13 — era GPIO 3 (ora libero per I2C1 SCL)
PIN_CLOCK_EN = 22   # Pin 15 — era GPIO 5
PIN_DATA_EN = 23    # Pin 16 — era GPIO 6

# Encoder SSI
BITS = 12
SAMPLES = 5
MIN_CHANGE = 5
MAX_DUTY = 0.8

# VESC UART protocol
COMM_SET_DUTY = 5


# --- VESC UART ---

def crc16(data: bytes) -> int:
    """CRC16-CCITT per protocollo VESC."""
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
    """Invia comando SET_DUTY al VESC via UART."""
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


# --- Encoder SSI ---

def read_ssi_single(h) -> int:
    """Legge una singola posizione dall'encoder SSI (bit-bang)."""
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
    """Legge encoder SSI con median filter (5 campioni)."""
    readings = sorted(read_ssi_single(h) for _ in range(SAMPLES))
    return readings[SAMPLES // 2]


# --- Main loop ---

def main():
    # Init GPIO
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, PIN_CLOCK, 1)
    lgpio.gpio_claim_input(h, PIN_DATA)
    lgpio.gpio_claim_output(h, PIN_CLOCK_EN, 1)  # HIGH sempre
    lgpio.gpio_claim_output(h, PIN_DATA_EN, 0)   # LOW sempre

    # Init UART
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)

    print("Encoder → VESC — Motore gira solo con rotazione (orario/antiorario)")
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
        print("\nStop — motore fermo")
        vesc_set_duty(ser, 0.0)
    finally:
        ser.close()
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
