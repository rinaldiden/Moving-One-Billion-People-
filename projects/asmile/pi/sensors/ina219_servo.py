#!/usr/bin/env python3
"""
Asmile INA219 — Servo brake current sensor

Reads voltage and current from INA219 on I2C1 to monitor
brake servo PDI-6221MG power consumption in real time.

Raspi 5 Wiring:
  GPIO 2 (Pin 3) SDA ↔ INA219 SDA (shared I2C bus with MPU6050)
  GPIO 3 (Pin 5) SCL → INA219 SCL
  3.3V   (Pin 1)     → INA219 VCC
  GND    (Pin 6)     → INA219 GND

  INA219 VIN+ ← servo power supply (6V from Pololu)
  INA219 VIN- → servo power pin
  (shunt resistor 0.1Ω onboard)

Address: 0x40 (A0=GND, A1=GND)

Dependencies:
  sudo apt install python3-smbus
"""

import smbus2
import struct
import time

# --- Config ---
I2C_BUS = 1
INA219_ADDR = 0x40

# INA219 registers
REG_CONFIG = 0x00
REG_SHUNT_VOLTAGE = 0x01
REG_BUS_VOLTAGE = 0x02
REG_POWER = 0x03
REG_CURRENT = 0x04
REG_CALIBRATION = 0x05

# Shunt resistor (standard breakout board = 0.1Ω)
SHUNT_OHMS = 0.1

# Calibration for 0.1Ω shunt, max ~3.2A
# Cal = trunc(0.04096 / (current_LSB * R_shunt))
# current_LSB = max_expected_current / 2^15 = 3.2 / 32768 ≈ 0.0001 A
CURRENT_LSB = 0.0001  # 0.1 mA per bit
CAL_VALUE = int(0.04096 / (CURRENT_LSB * SHUNT_OHMS))  # = 4096
POWER_LSB = CURRENT_LSB * 20  # per INA219 datasheet


def _write_reg(bus, reg: int, value: int):
    """Write 16-bit register (big-endian)."""
    data = struct.pack(">H", value & 0xFFFF)
    bus.write_i2c_block_data(INA219_ADDR, reg, list(data))


def _read_reg_signed(bus, reg: int) -> int:
    """Read 16-bit signed register."""
    data = bus.read_i2c_block_data(INA219_ADDR, reg, 2)
    value = struct.unpack(">h", bytes(data))[0]
    return value


def _read_reg_unsigned(bus, reg: int) -> int:
    """Read 16-bit unsigned register."""
    data = bus.read_i2c_block_data(INA219_ADDR, reg, 2)
    value = struct.unpack(">H", bytes(data))[0]
    return value


def init_ina219(bus) -> None:
    """Initialize INA219: configure + calibrate."""
    # Config: 32V bus range, ±320mV shunt range, 12-bit, continuous
    # BRNG=1 (32V), PG=11 (±320mV), BADC=0011 (12-bit), SADC=0011 (12-bit)
    # Mode=111 (continuous shunt+bus)
    config = (0b0 << 15 |   # RST
              0b1 << 13 |   # BRNG = 32V
              0b11 << 11 |  # PG = ±320mV (enough for 3.2A × 0.1Ω = 320mV)
              0b0011 << 7 | # BADC = 12-bit
              0b0011 << 3 | # SADC = 12-bit
              0b111)        # Mode = continuous shunt+bus
    _write_reg(bus, REG_CONFIG, config)
    time.sleep(0.01)

    # Calibration
    _write_reg(bus, REG_CALIBRATION, CAL_VALUE)
    time.sleep(0.01)


def read_bus_voltage(bus) -> float:
    """Read bus voltage in volts (load side)."""
    raw = _read_reg_unsigned(bus, REG_BUS_VOLTAGE)
    # Bits [15:3] = voltage, bit 1 = CNVR, bit 0 = OVF
    return (raw >> 3) * 0.004  # 4mV per LSB


def read_shunt_voltage(bus) -> float:
    """Read shunt voltage in millivolts."""
    raw = _read_reg_signed(bus, REG_SHUNT_VOLTAGE)
    return raw * 0.01  # 10μV per LSB → mV


def read_current(bus) -> float:
    """Read current in amps."""
    raw = _read_reg_signed(bus, REG_CURRENT)
    return raw * CURRENT_LSB


def read_power(bus) -> float:
    """Read power in watts."""
    raw = _read_reg_unsigned(bus, REG_POWER)
    return raw * POWER_LSB


def read_all(bus) -> dict:
    """Read all INA219 values at once."""
    return {
        "voltage_v": read_bus_voltage(bus),
        "current_a": read_current(bus),
        "power_w": read_power(bus),
        "shunt_mv": read_shunt_voltage(bus),
    }


def main():
    bus = smbus2.SMBus(I2C_BUS)
    init_ina219(bus)
    print(f"INA219 initialized on I2C{I2C_BUS} @ 0x{INA219_ADDR:02X}")
    print(f"Shunt: {SHUNT_OHMS}Ω, Cal: {CAL_VALUE}")
    print(f"Monitoring servo brake current...\n")

    peak_current = 0.0
    peak_power = 0.0

    try:
        while True:
            d = read_all(bus)
            peak_current = max(peak_current, abs(d["current_a"]))
            peak_power = max(peak_power, d["power_w"])

            status = ""
            if abs(d["current_a"]) > 0.5:
                status = " *** SERVO ACTIVE ***"
            elif abs(d["current_a"]) > 0.05:
                status = " (idle draw)"

            print(f"\rV={d['voltage_v']:.2f}V "
                  f"I={d['current_a']:+.3f}A "
                  f"P={d['power_w']:.3f}W "
                  f"Vshunt={d['shunt_mv']:+.2f}mV "
                  f"| PEAK: {peak_current:.3f}A {peak_power:.3f}W"
                  f"{status}    ", end="", flush=True)

            time.sleep(0.05)  # 20Hz

    except KeyboardInterrupt:
        print(f"\n\nPeak current: {peak_current:.3f}A")
        print(f"Peak power:   {peak_power:.3f}W")
    finally:
        bus.close()


if __name__ == "__main__":
    main()
