#!/usr/bin/env python3
"""
Test SSI encoder reading via SPI1 hardware on Raspberry Pi 5.

Wiring:
  SPI1_SCLK (GPIO 21, Pin 40) → Level Shifter → RS-485 #1 DI → Encoder CLK
  SPI1_MISO (GPIO 19, Pin 35) ← Level Shifter ← RS-485 #2 RO ← Encoder DATA
  SPI1_CE0  (GPIO 18, Pin 12) → not connected (but claimed by SPI driver)

SSI protocol:
  - Clock idles HIGH, data is clocked out on falling edge
  - 12-bit position data, MSB first
  - After 12 bits, encoder outputs zeros or repeats

SPI mode 2 (CPOL=1, CPHA=0) matches SSI timing:
  - Clock idles HIGH
  - Data sampled on leading (falling) edge
"""

import spidev
import time
import sys

SPI_BUS = 1
SPI_DEV = 0
SPI_SPEED_HZ = 500_000  # 500 kHz - safe for SSI via RS-485
SSI_BITS = 12

def read_encoder(spi):
    """Read 12-bit SSI position via SPI."""
    # Read 2 bytes (16 bits) - we need at least 12
    raw = spi.xfer2([0x00, 0x00])
    # Combine bytes: MSB first
    value_16 = (raw[0] << 8) | raw[1]
    # Extract top 12 bits (SSI sends MSB first, first bit after clock start)
    position = (value_16 >> 4) & 0x0FFF
    return position, raw

def main():
    spi = spidev.SpiDev()
    try:
        spi.open(SPI_BUS, SPI_DEV)
    except FileNotFoundError:
        print(f"ERROR: /dev/spidev{SPI_BUS}.{SPI_DEV} not found")
        print("Run: sudo dtoverlay spi1-1cs")
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied on /dev/spidev{SPI_BUS}.{SPI_DEV}")
        print("Run with sudo or add user to 'spi' group")
        sys.exit(1)

    # SPI Mode 2: CPOL=1 (idle HIGH), CPHA=0 (sample on leading/falling edge)
    spi.mode = 0b10
    spi.max_speed_hz = SPI_SPEED_HZ
    spi.bits_per_word = 8

    print(f"SPI{SPI_BUS}.{SPI_DEV} opened, mode={spi.mode}, speed={spi.max_speed_hz}Hz")
    print(f"Reading {SSI_BITS}-bit SSI encoder... (Ctrl+C to stop)")
    print(f"{'Position':>10} {'Raw hex':>12} {'Raw bin':>20}")
    print("-" * 46)

    last_pos = None
    try:
        while True:
            pos, raw = read_encoder(spi)
            raw_hex = f"0x{raw[0]:02X}{raw[1]:02X}"
            raw_bin = f"{raw[0]:08b} {raw[1]:08b}"

            # Only print if changed (or first reading)
            if pos != last_pos:
                print(f"{pos:>10} ({pos:>4}) {raw_hex:>12} {raw_bin:>20}")
                last_pos = pos

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        spi.close()

if __name__ == "__main__":
    main()
