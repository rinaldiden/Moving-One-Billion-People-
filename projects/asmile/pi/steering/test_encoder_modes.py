#!/usr/bin/env python3
"""
Test SSI encoder with all SPI modes and speeds.
Finds the right combination that reads valid data.

If all modes read 4095 (0xFFF) or 0, the problem is hardware/wiring.
If one mode reads changing values when you rotate the encoder, that's the right one.
"""

import spidev
import time
import sys

SPI_BUS = 1
SPI_DEV = 0

MODES = [0, 1, 2, 3]
SPEEDS = [100_000, 250_000, 500_000, 1_000_000]


def read_encoder(spi, shift=4):
    raw = spi.xfer2([0x00, 0x00])
    val16 = (raw[0] << 8) | raw[1]
    pos = (val16 >> shift) & 0x0FFF
    return pos, raw


def test_mode_speed(mode, speed):
    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.mode = mode
    spi.max_speed_hz = speed
    spi.bits_per_word = 8

    readings = []
    for _ in range(10):
        pos, raw = read_encoder(spi)
        readings.append(pos)
        time.sleep(0.02)

    spi.close()

    unique = len(set(readings))
    all_fff = all(r == 4095 for r in readings)
    all_zero = all(r == 0 for r in readings)

    return readings, unique, all_fff, all_zero


def main():
    print("=== SSI Encoder Mode/Speed Scanner ===")
    print("Rotate the encoder shaft during this test!\n")

    results = []

    for mode in MODES:
        cpol = (mode >> 1) & 1
        cpha = mode & 1
        for speed in SPEEDS:
            try:
                readings, unique, all_fff, all_zero = test_mode_speed(mode, speed)

                status = "STUCK 4095" if all_fff else "STUCK 0" if all_zero else f"VARIES ({unique} unique)"
                flag = " <<<" if not all_fff and not all_zero and unique > 1 else ""

                print(f"Mode {mode} (CPOL={cpol} CPHA={cpha}) @ {speed//1000:>4}kHz: "
                      f"{status:>20}  samples={readings[:5]}{flag}")

                results.append((mode, speed, unique, all_fff, all_zero))
            except Exception as e:
                print(f"Mode {mode} @ {speed//1000:>4}kHz: ERROR {e}")

    # Also test different bit shifts
    print("\n=== Bit shift test (mode 2, 100kHz) ===")
    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.mode = 2
    spi.max_speed_hz = 100_000
    spi.bits_per_word = 8

    for shift in range(0, 8):
        readings = []
        for _ in range(5):
            raw = spi.xfer2([0x00, 0x00])
            val16 = (raw[0] << 8) | raw[1]
            pos = (val16 >> shift) & 0x0FFF
            readings.append(pos)
            time.sleep(0.02)
        print(f"  Shift {shift}: {readings}")

    # Try 3 bytes for more bits
    print("\n=== 3-byte read (mode 2, 100kHz) ===")
    for _ in range(5):
        raw = spi.xfer2([0x00, 0x00, 0x00])
        val24 = (raw[0] << 16) | (raw[1] << 8) | raw[2]
        print(f"  Raw: 0x{raw[0]:02X}{raw[1]:02X}{raw[2]:02X} = "
              f"{raw[0]:08b} {raw[1]:08b} {raw[2]:08b}  "
              f">>4={((val24>>12)&0xFFF):4d}  >>8={((val24>>8)&0xFFF):4d}")
        time.sleep(0.1)

    spi.close()

    # Summary
    print("\n=== Summary ===")
    good = [(m, s) for m, s, u, f, z in results if not f and not z and u > 1]
    if good:
        print(f"Working combinations: {good}")
    else:
        print("No working combination found — check hardware/wiring")
        print("  - Is encoder LED green? (blue = wrong mode, needs reset)")
        print("  - Are Yellow/Orange wires disconnected?")
        print("  - Is RS-485 #2 powered (VCC 5V)?")
        print("  - RO of RS-485 #2 → HV2 of level shifter → LV2 → GPIO 19?")


if __name__ == "__main__":
    main()
