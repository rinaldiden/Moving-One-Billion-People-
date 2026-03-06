#!/usr/bin/env python3
"""
SSI encoder continuous reader via SPI1.
Keeps the clock active so the encoder LED stays green.
Exposes current position via shared memory file.

Usage:
  python3 encoder_spi_daemon.py          # foreground, prints values
  python3 encoder_spi_daemon.py --quiet  # foreground, no output

Position is written to /tmp/encoder_position (plain text integer).
Other scripts can read it at any time.
"""

import spidev
import time
import sys
import os

SPI_BUS = 1
SPI_DEV = 0
SPI_SPEED_HZ = 500_000
POSITION_FILE = "/tmp/encoder_position"
POLL_INTERVAL = 0.02  # 50Hz polling = continuous clock activity

def read_encoder(spi):
    raw = spi.xfer2([0x00, 0x00])
    value_16 = (raw[0] << 8) | raw[1]
    position = (value_16 >> 4) & 0x0FFF
    return position

def main():
    quiet = "--quiet" in sys.argv

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.mode = 0b10
    spi.max_speed_hz = SPI_SPEED_HZ
    spi.bits_per_word = 8

    if not quiet:
        print(f"Encoder daemon started (SPI{SPI_BUS}.{SPI_DEV}, {SPI_SPEED_HZ}Hz)")
        print(f"Position file: {POSITION_FILE}")

    last_pos = None
    try:
        while True:
            pos = read_encoder(spi)

            # Write to file for other scripts
            tmp = POSITION_FILE + ".tmp"
            with open(tmp, "w") as f:
                f.write(str(pos))
            os.replace(tmp, POSITION_FILE)

            if not quiet and pos != last_pos:
                print(f"Position: {pos:4d}")
                last_pos = pos

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        if not quiet:
            print("\nStopped.")
    finally:
        spi.close()
        try:
            os.remove(POSITION_FILE)
        except OSError:
            pass

if __name__ == "__main__":
    main()
