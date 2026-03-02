#!/usr/bin/env python3
"""
IMU Asmile — Raspberry Pi 5
Legge accelerometro e giroscopio MPU6050 via I2C per feedback frenata.

Cablaggio Raspi 5:
  GPIO 2 (Pin 3) SDA ↔ MPU6050 SDA
  GPIO 3 (Pin 5) SCL → MPU6050 SCL
  3.3V   (Pin 1)     → MPU6050 VCC
  GND    (Pin 6)     → MPU6050 GND
  MPU6050 AD0        → GND (indirizzo 0x68)

Config.txt richiesto:
  dtparam=i2c_arm=on

Dipendenze:
  sudo apt install python3-smbus
"""

import smbus2
import struct
import time
import math

# --- Config ---
I2C_BUS = 1
MPU6050_ADDR = 0x68

# Registri MPU6050
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
ACCEL_CONFIG = 0x1C
GYRO_CONFIG = 0x1B

# Scale (default ±2g, ±250°/s)
ACCEL_SCALE = 16384.0  # LSB/g
GYRO_SCALE = 131.0     # LSB/(°/s)

# Soglia decelerazione per feedback frenata (in g)
DECEL_THRESHOLD = 0.3


def init_mpu6050(bus) -> None:
    """Inizializza MPU6050: sveglia + config scale."""
    bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0x00)   # Sveglia
    time.sleep(0.1)
    bus.write_byte_data(MPU6050_ADDR, ACCEL_CONFIG, 0x00)  # ±2g
    bus.write_byte_data(MPU6050_ADDR, GYRO_CONFIG, 0x00)   # ±250°/s


def read_raw(bus, reg: int) -> int:
    """Legge valore 16-bit signed da due registri consecutivi."""
    high = bus.read_byte_data(MPU6050_ADDR, reg)
    low = bus.read_byte_data(MPU6050_ADDR, reg + 1)
    value = (high << 8) | low
    if value >= 0x8000:
        value -= 0x10000
    return value


def read_accel(bus) -> tuple:
    """Legge accelerometro (ax, ay, az) in g."""
    ax = read_raw(bus, ACCEL_XOUT_H) / ACCEL_SCALE
    ay = read_raw(bus, ACCEL_XOUT_H + 2) / ACCEL_SCALE
    az = read_raw(bus, ACCEL_XOUT_H + 4) / ACCEL_SCALE
    return ax, ay, az


def read_gyro(bus) -> tuple:
    """Legge giroscopio (gx, gy, gz) in °/s."""
    gx = read_raw(bus, GYRO_XOUT_H) / GYRO_SCALE
    gy = read_raw(bus, GYRO_XOUT_H + 2) / GYRO_SCALE
    gz = read_raw(bus, GYRO_XOUT_H + 4) / GYRO_SCALE
    return gx, gy, gz


def main():
    bus = smbus2.SMBus(I2C_BUS)
    init_mpu6050(bus)
    print("MPU6050 inizializzato su I2C1 (0x68)")
    print(f"Soglia decelerazione: {DECEL_THRESHOLD}g")

    try:
        while True:
            ax, ay, az = read_accel(bus)
            gx, gy, gz = read_gyro(bus)

            # Decelerazione longitudinale (asse X, negativo = frenata)
            decel = -ax

            status = ""
            if decel > DECEL_THRESHOLD:
                status = f" *** FRENATA {decel:.2f}g ***"

            print(f"Acc: X={ax:+.2f} Y={ay:+.2f} Z={az:+.2f}g | "
                  f"Gyro: X={gx:+.1f} Y={gy:+.1f} Z={gz:+.1f}°/s{status}")

            time.sleep(0.02)  # ~50Hz

    except KeyboardInterrupt:
        print("\nIMU stop")
    finally:
        bus.close()


if __name__ == "__main__":
    main()
