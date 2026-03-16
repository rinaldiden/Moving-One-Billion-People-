#!/usr/bin/env python3
"""
Asmile Safe Shutdown — Raspberry Pi 5

Monitors a GPIO pin connected to the 48V battery line (via voltage divider).
When battery power is cut, the supercapacitor keeps the Raspi alive for ~5-10s,
during which this script detects the power loss and triggers a clean shutdown.

This prevents SD card corruption from sudden power loss.

How it works:
  1. GPIO pin reads HIGH when 48V battery is connected (via voltage divider)
  2. When battery switch is turned off, GPIO goes LOW
  3. Script detects LOW → triggers immediate 'shutdown -h now'
  4. Supercap provides enough energy to complete the shutdown (~5s)

Wiring:
  Battery 48V+ → 10kΩ → GPIO_PIN → 1kΩ → GND
  (voltage divider: ~4.36V when battery is at 48V, safe for 3.3V GPIO with clamping)
  NOTE: Use Raspi internal pull-down or external 1kΩ to GND

  Alternative (simpler, from 5V Pololu output):
  Pololu 5V VOUT → 10kΩ → GPIO_PIN → 10kΩ → GND  (gives ~2.5V = HIGH)

Supercap wiring:
  Pololu D24V55F5 VOUT (5V) → supercap + → Raspi 5V (Pin 2/4)
  Pololu D24V55F5 GND       → supercap − → Raspi GND

Dependencies:
  sudo apt install python3-lgpio

Install as service:
  sudo cp safe_shutdown.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now safe_shutdown.service
"""

import lgpio
import time
import subprocess
import sys

# --- Config ---
GPIO_CHIP = 4          # Pi 5 = gpiochip4
POWER_SENSE_PIN = 26   # GPIO 26 — change to your wiring
DEBOUNCE_MS = 500      # ignore glitches shorter than this
CHECK_INTERVAL = 0.2   # seconds between checks


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_input(h, POWER_SENSE_PIN, lgpio.SET_PULL_DOWN)

    print(f"[safe_shutdown] Monitoring GPIO {POWER_SENSE_PIN} for power loss...")

    low_since = None

    try:
        while True:
            level = lgpio.gpio_read(h, POWER_SENSE_PIN)

            if level == 0:
                if low_since is None:
                    low_since = time.monotonic()
                elif (time.monotonic() - low_since) * 1000 >= DEBOUNCE_MS:
                    print("[safe_shutdown] Power loss detected! Shutting down...")
                    subprocess.run(["sudo", "shutdown", "-h", "now"])
                    sys.exit(0)
            else:
                low_since = None

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("[safe_shutdown] Stopped.")
    finally:
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
