#!/usr/bin/env python3
"""
Asmile Safe Shutdown — Raspberry Pi 5

Monitors GPIO 26 (power-sense via level shifter from Pololu VOUT).
When battery is cut, GPIO transitions HIGH→LOW. Detection uses
hardware edge events (lgpio alert + callback) — more robust than
polling, because the BCM2712 event-detect register latches the edge
even if the CPU is briefly throttled during brownout.

Wiring:
  Pololu VOUT → HV3 of level shifter
  LV3 of level shifter → GPIO 26 (Pin 37)
  Pi 3.3V → LV of level shifter
  Recommended: bleed resistor 1kΩ on Pololu VOUT → GND so the
  shifter input drops within ms when battery is removed (otherwise
  the Pololu output cap can keep HV3 alive for seconds).

  Pololu VOUT → LM74700 → supercap+ = Pi 5V (Pin 2/4)
  Pololu GND  → supercap− = Pi GND
"""

import lgpio
import time
import subprocess
import sys
import os
import threading
from datetime import datetime

# --- Config ---
GPIO_CHIP = 4
POWER_SENSE_PIN = 26
BUZZER_PIN = 4
DEBOUNCE_MS = 200       # confirm POWER LOSS only if LOW persists for this long
POLL_INTERVAL = 0.05    # backup poll cadence (edge callback is primary)
HEALTH_LOG = "/tmp/asmile_health.csv"
HEALTH_INTERVAL = 5     # log Pi health to CSV every Ns
LOG_FILE = "/var/log/safe_shutdown.log"
TOMBSTONE = "/var/lib/asmile/last_shutdown.txt"


# ---- Shared state (between callback thread and main loop) ----
_lock = threading.Lock()
_armed = False
_low_since = None       # set when falling edge or LOW poll → time.monotonic()
_glitch_count = 0


def log(msg):
    """Print (flushed) + append to persistent log file."""
    ts = datetime.now().isoformat(timespec="milliseconds")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_tombstone(event, extra=""):
    """Append to tombstone file — survives reboot, post-mortem record."""
    try:
        os.makedirs(os.path.dirname(TOMBSTONE), exist_ok=True)
        ts = datetime.now().isoformat(timespec="milliseconds")
        with open(TOMBSTONE, "a") as f:
            f.write(f"{ts} {event} {extra}\n")
    except Exception:
        pass


def short_beep(freq=2500, duration=0.08):
    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.tx_pwm(h, BUZZER_PIN, freq, 50)
        time.sleep(duration)
        lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)
        lgpio.gpiochip_close(h)
    except Exception:
        pass


def fast_shutdown():
    log("FAST_SHUTDOWN — morente beep + spawn detached buzzer + shutdown -h")
    write_tombstone("FAST_SHUTDOWN_BEGIN")

    # 5 beep morenti (~700ms) — eseguiti nel processo principale prima di
    # qualsiasi cosa che possa essere uccisa.
    try:
        h_buzz = lgpio.gpiochip_open(GPIO_CHIP)
        for f in (1500, 1200, 900, 600, 400):
            lgpio.tx_pwm(h_buzz, BUZZER_PIN, f, 50)
            time.sleep(0.10)
            lgpio.tx_pwm(h_buzz, BUZZER_PIN, 0, 0)
            time.sleep(0.04)
        lgpio.gpiochip_close(h_buzz)
    except Exception:
        pass

    # Buzzer detached: nuovo session ID + ignora SIGTERM, sopravvive al kill
    # di safe_shutdown.service e suona finché systemd-shutdown manda SIGKILL
    # finale (giusto prima dell'halt). Effetto: tono continuo fino allo spegnimento.
    buzz_code = (
        "import lgpio, signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "try:\n"
        "    h = lgpio.gpiochip_open(4)\n"
        "    lgpio.tx_pwm(h, 4, 1500, 50)\n"
        "    time.sleep(120)\n"
        "except Exception: pass\n"
    )
    try:
        subprocess.Popen(
            [sys.executable, "-c", buzz_code],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

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

    subprocess.run(["sync"], timeout=1)
    log("services killed + sync done — calling shutdown -h now")
    write_tombstone("SHUTDOWN_HALT_CALLED")
    subprocess.Popen(["shutdown", "-h", "now"])


def gpio_edge_callback(chip, gpio, level, tick):
    """Called by lgpio thread on any edge of GPIO 26.

    level: 0 = falling, 1 = rising, 2 = watchdog (ignored).
    The BCM2712 latches edges in hardware so events queued during
    a brief CPU throttle event are still delivered.
    """
    global _armed, _low_since, _glitch_count

    if level == 2:
        return

    now = time.monotonic()
    with _lock:
        if level == 1:  # RISING — went HIGH
            if not _armed:
                _armed = True
                log("ARMED — rising edge")
                write_tombstone("ARMED")
            else:
                if _low_since is not None:
                    dur = (now - _low_since) * 1000
                    log(f"GPIO_BACK_HIGH after {dur:.0f}ms (glitch, edge)")
                _low_since = None
            return

        # level == 0 → FALLING
        if not _armed:
            return  # ignore until we've seen at least one HIGH

        if _low_since is None:
            _low_since = now
            _glitch_count += 1
            log(f"GPIO_LOW_DETECTED #{_glitch_count} (edge)")
            write_tombstone(f"LOW_EDGE_{_glitch_count}")
            short_beep(freq=2500, duration=0.08)


def health_logger(h, stop_event):
    """Background thread: write health row every HEALTH_INTERVAL seconds."""
    ina219 = None
    try:
        import smbus2
        ina_bus = smbus2.SMBus(1)
        ina_bus.write_word_data(0x40, 0x05, 0x1000)
        ina219 = ina_bus
        log("INA219 detected")
    except Exception:
        log("INA219 not found")

    with open(HEALTH_LOG, "w") as f:
        f.write("timestamp,temp_c,throttled,voltage_ok,current_mA,gpio26,glitches\n")

    while not stop_event.is_set():
        try:
            level = lgpio.gpio_read(h, POWER_SENSE_PIN)
            temp = subprocess.run(["vcgencmd", "measure_temp"],
                                  capture_output=True, text=True, timeout=2)
            temp_c = temp.stdout.strip().replace("temp=", "").replace("'C", "")
            throt = subprocess.run(["vcgencmd", "get_throttled"],
                                   capture_output=True, text=True, timeout=2)
            throt_val = throt.stdout.strip().split("=")[1] if "=" in throt.stdout else "?"
            volt_ok = "1" if throt_val == "0x0" else "0"
            current_mA = -1
            if ina219:
                try:
                    raw = ina219.read_word_data(0x40, 0x04)
                    raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
                    if raw > 32767:
                        raw -= 65536
                    current_mA = raw * 0.1
                except Exception:
                    current_mA = -1
            ts = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(HEALTH_LOG, "a") as f:
                f.write(f"{ts},{temp_c},{throt_val},{volt_ok},{current_mA:.1f},{level},{_glitch_count}\n")
        except Exception:
            pass
        stop_event.wait(HEALTH_INTERVAL)


def main():
    global _armed, _low_since

    log("=" * 50)
    log(f"safe_shutdown START — DEBOUNCE_MS={DEBOUNCE_MS} POLL={POLL_INTERVAL}s edge+poll")
    write_tombstone("SERVICE_START")

    h = lgpio.gpiochip_open(GPIO_CHIP)
    # Claim as input with pull-down AND alert on both edges
    lgpio.gpio_claim_alert(h, POWER_SENSE_PIN, lgpio.BOTH_EDGES, lgpio.SET_PULL_DOWN)
    cb = lgpio.callback(h, POWER_SENSE_PIN, lgpio.BOTH_EDGES, gpio_edge_callback)
    log(f"Edge callback registered on GPIO {POWER_SENSE_PIN}")

    # Prime armed state from current level (in case we're already HIGH)
    initial = lgpio.gpio_read(h, POWER_SENSE_PIN)
    if initial == 1:
        with _lock:
            _armed = True
        log("ARMED — initial GPIO HIGH at startup")
        write_tombstone("ARMED_AT_STARTUP")
    else:
        log("Waiting for GPIO HIGH to arm...")

    # Start health logger in background
    stop_event = threading.Event()
    hl_thread = threading.Thread(target=health_logger, args=(h, stop_event), daemon=True)
    hl_thread.start()

    try:
        while True:
            now = time.monotonic()

            # Backup poll — in case edge callback missed an event
            current = lgpio.gpio_read(h, POWER_SENSE_PIN)
            with _lock:
                if not _armed and current == 1:
                    _armed = True
                    log("ARMED — rising via poll")
                    write_tombstone("ARMED_VIA_POLL")
                if _armed and current == 0 and _low_since is None:
                    _low_since = now
                    _glitch_count_local = _glitch_count + 1
                    # Use a separate inc so we don't conflict with callback
                    log(f"GPIO_LOW_DETECTED via poll (backup, callback may have missed)")
                    write_tombstone("LOW_VIA_POLL")
                    short_beep(freq=2500, duration=0.08)
                if _armed and current == 1 and _low_since is not None:
                    dur = (now - _low_since) * 1000
                    log(f"GPIO_BACK_HIGH via poll after {dur:.0f}ms (glitch)")
                    _low_since = None

                # Confirm power loss after debounce
                if _low_since is not None and (now - _low_since) * 1000 >= DEBOUNCE_MS:
                    log(f"POWER_LOSS_CONFIRMED after {DEBOUNCE_MS}ms — fast_shutdown()")
                    write_tombstone("POWER_LOSS_CONFIRMED")
                    # Release lock before triggering shutdown
                    confirm_shutdown = True
                else:
                    confirm_shutdown = False

            if confirm_shutdown:
                fast_shutdown()
                stop_event.set()
                sys.exit(0)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log("Stopped (KeyboardInterrupt)")
    finally:
        stop_event.set()
        try:
            cb.cancel()
        except Exception:
            pass
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
