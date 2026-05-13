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
import os

# --- Config ---
GPIO_CHIP = 4          # Pi 5 = gpiochip4
POWER_SENSE_PIN = 26   # GPIO 26 — change to your wiring
# SUPERCAP_DISCHARGE_PIN removed — discharge circuit not used
DEBOUNCE_MS = 500      # ignore glitches shorter than this
CHECK_INTERVAL = 0.2   # seconds between checks
HEALTH_LOG = "/tmp/asmile_health.csv"
HEALTH_INTERVAL = 10   # log health every 10s


def fast_shutdown():
    """Kill all Asmile services first, then shutdown.
    With 2.2F supercap we have ~1.3s — every ms counts."""
    print("[safe_shutdown] Fast shutdown — killing services...")

    # Kill heavy processes first (video, recorder, flask)
    kills = [
        ["killall", "-9", "gst-launch-1.0"],
        ["pkill", "-9", "-f", "training_recorder.py"],
        ["pkill", "-9", "-f", "follow_me/main.py"],
        ["systemctl", "stop", "servofreno.service"],
        ["systemctl", "stop", "master_switch.service"],
        ["systemctl", "stop", "encoder-ssi.service"],
    ]
    for cmd in kills:
        subprocess.run(cmd, capture_output=True, timeout=1)

    # Sync filesystem
    subprocess.run(["sync"], timeout=1)

    print("[safe_shutdown] Services killed. Shutting down NOW.")
    subprocess.Popen(["shutdown", "-h", "now"])

    # Buzzer shutdown sound — beeps that die (plays DURING shutdown)
    try:
        h_buzz = lgpio.gpiochip_open(GPIO_CHIP)
        freq = 500
        on_t = 0.15
        off_t = 0.15
        while freq > 100:
            lgpio.tx_pwm(h_buzz, 4, freq, 50)
            time.sleep(on_t)
            lgpio.tx_pwm(h_buzz, 4, 0, 0)
            time.sleep(off_t)
            freq -= 50
            on_t += 0.03
            off_t += 0.05
        lgpio.gpiochip_close(h_buzz)
    except Exception:
        pass


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_input(h, POWER_SENSE_PIN, lgpio.SET_PULL_DOWN)

    print(f"[safe_shutdown] Monitoring GPIO {POWER_SENSE_PIN} for power loss...")
    print(f"[safe_shutdown] Waiting for battery HIGH signal before arming...")

    # Safety: do NOT trigger shutdown until we've seen the pin HIGH at least once.
    # This prevents spurious shutdowns when hardware is not yet connected
    # (pin floats LOW with pull-down → would immediately trigger shutdown).
    armed = False
    low_since = None
    last_health = 0
    glitch_count = 0

    # Try to init INA219 for current monitoring
    ina219 = None
    try:
        import smbus2
        ina_bus = smbus2.SMBus(1)
        ina_bus.write_word_data(0x40, 0x05, 0x1000)  # calibration register
        ina219 = ina_bus
        print("[safe_shutdown] INA219 current sensor detected")
    except Exception:
        print("[safe_shutdown] INA219 not found, logging without current")

    # Init health log
    with open(HEALTH_LOG, "w") as f:
        f.write("timestamp,temp_c,throttled,voltage_ok,current_mA,gpio26,glitches\n")

    try:
        while True:
            level = lgpio.gpio_read(h, POWER_SENSE_PIN)
            now = time.monotonic()

            # Health logging
            if now - last_health >= HEALTH_INTERVAL:
                last_health = now
                try:
                    temp = subprocess.run(["vcgencmd", "measure_temp"],
                                         capture_output=True, text=True, timeout=2)
                    temp_c = temp.stdout.strip().replace("temp=", "").replace("'C", "")
                    throt = subprocess.run(["vcgencmd", "get_throttled"],
                                          capture_output=True, text=True, timeout=2)
                    throt_val = throt.stdout.strip().split("=")[1] if "=" in throt.stdout else "?"
                    volt_ok = "1" if throt_val == "0x0" else "0"
                    # Read current from INA219 if available
                    current_mA = -1
                    if ina219:
                        try:
                            raw = ina219.read_word_data(0x40, 0x04)
                            raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
                            if raw > 32767:
                                raw -= 65536
                            current_mA = raw * 0.1  # 0.1mA per LSB
                        except Exception:
                            current_mA = -1
                    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
                    with open(HEALTH_LOG, "a") as f:
                        f.write(f"{ts},{temp_c},{throt_val},{volt_ok},{current_mA:.1f},{level},{glitch_count}\n")
                except Exception:
                    pass

            if not armed:
                if level == 1:
                    armed = True
                    print("[safe_shutdown] Battery detected (GPIO HIGH). Armed.")
                else:
                    time.sleep(CHECK_INTERVAL)
                    continue

            if level == 0:
                if low_since is None:
                    low_since = now
                    glitch_count += 1
                    print(f"[safe_shutdown] GPIO LOW detected (glitch #{glitch_count})")
                elif (now - low_since) * 1000 >= DEBOUNCE_MS:
                    print(f"[safe_shutdown] Power loss confirmed after {DEBOUNCE_MS}ms!")
                    fast_shutdown()
                    sys.exit(0)
            else:
                if low_since is not None:
                    duration = (now - low_since) * 1000
                    print(f"[safe_shutdown] GPIO back HIGH after {duration:.0f}ms (glitch)")
                low_since = None

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("[safe_shutdown] Stopped.")
    finally:
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
