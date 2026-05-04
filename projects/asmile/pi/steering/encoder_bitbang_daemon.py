#!/usr/bin/env python3
"""
SSI encoder reader via GPIO bit-bang — no SPI hardware needed.

Works on any GPIO pins. Default: GPIO 17 (CLK) + GPIO 27 (DATA).
Compatible with Briter BRT38 SSI encoder via RS-485 + level shifter.

SSI protocol:
  1. Clock and data both HIGH when idle
  2. First falling edge of clock latches current position
  3. Data clocked out on rising edge, MSB first
  4. 12-bit = 4096 positions
  5. t4 > 20us monoflop time between reads

Usage:
  python3 encoder_bitbang_daemon.py              # GPIO 17/27, prints values
  python3 encoder_bitbang_daemon.py --quiet       # no output
  python3 encoder_bitbang_daemon.py --clk 21 --data 19  # custom pins (SPI1 pins)

Position written to /tmp/encoder_position (same as SPI daemon).
"""

import lgpio
import time
import sys
import os
import argparse

GPIO_CHIP = 4          # Pi 5 = gpiochip4
POSITION_FILE = "/tmp/encoder_position"
POLL_INTERVAL = 0.005  # 200Hz polling
BITS = 12              # 12-bit encoder
CLOCK_DELAY = 0.000002 # 2us per half-clock (T=4us, 250kHz effective)
MONOFLOP_DELAY = 0.00005  # 50us between reads (t4 > 20us)


def read_encoder_ssi(h, clk_pin, data_pin):
    """Read SSI encoder via bit-bang GPIO."""
    # SSI: first falling edge latches current value
    lgpio.gpio_write(h, clk_pin, 0)  # falling edge = latch
    time.sleep(CLOCK_DELAY)

    bits = 0
    for i in range(BITS):
        lgpio.gpio_write(h, clk_pin, 1)  # rising edge = data valid
        time.sleep(CLOCK_DELAY)
        bit = lgpio.gpio_read(h, data_pin)
        bits = (bits << 1) | bit
        lgpio.gpio_write(h, clk_pin, 0)  # falling edge
        time.sleep(CLOCK_DELAY)

    # Return clock to idle HIGH
    lgpio.gpio_write(h, clk_pin, 1)
    time.sleep(MONOFLOP_DELAY)  # t4 > 20us

    return bits


def main():
    parser = argparse.ArgumentParser(description="SSI encoder bit-bang daemon")
    parser.add_argument("--clk", type=int, default=17, help="GPIO pin for clock (default: 17)")
    parser.add_argument("--data", type=int, default=27, help="GPIO pin for data (default: 27)")
    parser.add_argument("--quiet", action="store_true", help="No output")
    args = parser.parse_args()

    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, args.clk, 1)  # CLK idle HIGH
    lgpio.gpio_claim_input(h, args.data, lgpio.SET_PULL_UP)  # DATA idle HIGH

    if not args.quiet:
        print(f"Encoder bit-bang daemon started (CLK=GPIO{args.clk}, DATA=GPIO{args.data})")
        print(f"Position file: {POSITION_FILE}")

    last_pos = None
    try:
        while True:
            pos = read_encoder_ssi(h, args.clk, args.data)

            # Write to file for other scripts
            tmp = POSITION_FILE + ".tmp"
            with open(tmp, "w") as f:
                f.write(str(pos))
            os.replace(tmp, POSITION_FILE)

            if not args.quiet and pos != last_pos:
                print(f"Position: {pos:4d}")
                last_pos = pos

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        if not args.quiet:
            print("\nStopped.")
    finally:
        lgpio.gpio_write(h, args.clk, 1)  # leave clock HIGH (idle)
        lgpio.gpiochip_close(h)
        try:
            os.remove(POSITION_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
