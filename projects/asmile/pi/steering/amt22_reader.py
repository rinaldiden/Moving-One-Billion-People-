#!/usr/bin/env python3
"""
AMT222A-V Absolute Encoder Reader — SPI direct on Raspberry Pi 5.

No RS-485 modules, no level shifter needed!
Output HIGH = 3.3V, directly compatible with Pi GPIO.

Pinout:
  Pin 1 (Vdd)  → Pi Pin 2 (5V)
  Pin 2 (SCLK) → Pi Pin 40 (GPIO 21, SPI1_SCLK)
  Pin 3 (MOSI) → Pi Pin 38 (GPIO 20, SPI1_MOSI)
  Pin 4 (GND)  → Pi Pin 39 (GND)
  Pin 5 (MISO) → Pi Pin 35 (GPIO 19, SPI1_MISO)
  Pin 6 (CS)   → Pi Pin 12 (GPIO 18, SPI1_CE0)

SPI Mode 0 (CPOL=0, CPHA=0), max 2MHz.

Usage:
  python3 amt22_reader.py           # continuous reading
  python3 amt22_reader.py --test    # quick test
  python3 amt22_reader.py --daemon  # write to /tmp/encoder_position
"""

import spidev
import time
import sys
import os

SPI_BUS = 1
SPI_DEV = 0
SPI_SPEED_HZ = 500_000  # 500kHz safe, max 2MHz
SPI_MODE = 0b00         # Mode 0: CPOL=0, CPHA=0

POSITION_FILE = "/tmp/encoder_position"
POLL_INTERVAL = 0.005   # 200Hz
BITS = 12               # AMT222A = 12-bit

# Commands
CMD_READ_POSITION = [0x00, 0x00]
CMD_RESET = [0x00, 0x60]
CMD_SET_ZERO = [0x00, 0x70]


def read_position(spi):
    """Read 12-bit absolute position from AMT222A-V.

    Returns (position, valid) tuple.
    Position is 0-4095 for 12-bit encoder.
    Valid is True if checkbits pass.
    """
    # CS goes LOW automatically via spidev
    # Send two bytes with required delay between them

    # Byte 1: send 0x00, receive high byte [K1 K0 D13..D8]
    high = spi.xfer2([0x00])[0]
    time.sleep(3e-6)  # T_B >= 2.5µs between bytes

    # Byte 2: send 0x00, receive low byte [D7..D0]
    low = spi.xfer2([0x00])[0]

    # Combine
    raw = (high << 8) | low

    # Verify checkbits (bit 15 = K1 odd, bit 14 = K0 even)
    k1 = (raw >> 15) & 1
    k0 = (raw >> 14) & 1

    # Calculate expected parity
    odd_parity = 0
    even_parity = 0
    for i in range(14):
        bit = (raw >> i) & 1
        if i % 2 == 0:
            even_parity ^= bit
        else:
            odd_parity ^= bit

    expected_k1 = (~odd_parity) & 1
    expected_k0 = (~even_parity) & 1

    valid = (k1 == expected_k1) and (k0 == expected_k0)

    # Extract position (lower 14 bits)
    position_14bit = raw & 0x3FFF

    # For 12-bit encoder, shift right 2
    if BITS == 12:
        position = position_14bit >> 2
    else:
        position = position_14bit

    return position, valid


def read_position_single_transfer(spi):
    """Alternative: read both bytes in single SPI transfer.

    Some setups work better with a single xfer2 call.
    The 2.5µs delay between bytes is handled by the SPI hardware
    at lower clock speeds.
    """
    raw_bytes = spi.xfer2([0x00, 0x00])
    raw = (raw_bytes[0] << 8) | raw_bytes[1]

    position_14bit = raw & 0x3FFF
    if BITS == 12:
        position = position_14bit >> 2
    else:
        position = position_14bit

    return position, True  # skip checkbit for speed


def test_encoder(spi):
    """Quick test: read 20 times and show results."""
    print("=== AMT222A-V Test ===")
    print(f"SPI{SPI_BUS}.{SPI_DEV}, Mode {SPI_MODE}, Speed {SPI_SPEED_HZ}Hz")
    print()

    # Method 1: two separate transfers
    print("Method 1 (split transfers, 2.5µs delay):")
    for i in range(10):
        pos, valid = read_position(spi)
        check = "OK" if valid else "FAIL"
        print(f"  {i}: position={pos:4d}  checkbit={check}")
        time.sleep(0.1)

    print()

    # Method 2: single transfer
    print("Method 2 (single transfer):")
    for i in range(10):
        pos, valid = read_position_single_transfer(spi)
        print(f"  {i}: position={pos:4d}")
        time.sleep(0.1)

    print()
    print("Ruota l'encoder e verifica che i valori cambiano!")
    print("Range: 0-4095 per 360 gradi")


def daemon_mode(spi):
    """Continuous reading, write to /tmp/encoder_position."""
    print(f"AMT22 daemon started (SPI{SPI_BUS}.{SPI_DEV}, {SPI_SPEED_HZ}Hz)")
    print(f"Position file: {POSITION_FILE}")

    last_pos = None
    quiet = "--quiet" in sys.argv

    try:
        while True:
            pos, valid = read_position(spi)

            if valid:
                tmp = POSITION_FILE + ".tmp"
                with open(tmp, "w") as f:
                    f.write(str(pos))
                os.replace(tmp, POSITION_FILE)

                if not quiet and pos != last_pos:
                    print(f"Position: {pos:4d}")
                    last_pos = pos

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def main():
    spi = spidev.SpiDev()
    try:
        spi.open(SPI_BUS, SPI_DEV)
    except FileNotFoundError:
        print(f"ERROR: /dev/spidev{SPI_BUS}.{SPI_DEV} not found")
        print("Add to /boot/firmware/config.txt: dtoverlay=spi1-1cs")
        sys.exit(1)

    spi.mode = SPI_MODE
    spi.max_speed_hz = SPI_SPEED_HZ
    spi.bits_per_word = 8

    if "--test" in sys.argv:
        test_encoder(spi)
    elif "--daemon" in sys.argv or "--quiet" in sys.argv:
        daemon_mode(spi)
    else:
        # Default: continuous reading with output
        print(f"AMT222A-V on SPI{SPI_BUS}.{SPI_DEV} @ {SPI_SPEED_HZ}Hz")
        print("Ctrl+C to stop\n")
        try:
            while True:
                pos, valid = read_position(spi)
                check = "OK" if valid else "FAIL"
                print(f"\rPosition: {pos:4d}  [{check}]", end="", flush=True)
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nDone.")

    spi.close()


if __name__ == "__main__":
    main()
