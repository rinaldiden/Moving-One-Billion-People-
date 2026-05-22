#!/usr/bin/env python3
"""
Force brake release — emergency utility to push servo to release position.

Same gesture master_switch.py does at switch_on:
  - GPIO 12 PWM @ 330Hz, duty for angle=0 (max release) for ~2s
  - then PWM off + gpio_free → pin hi-Z, servo "libero"

Usage:
  sudo systemctl stop speed_limiter? (no, not a service — kill via master switch OFF)
  Switch fisico OFF (master_switch farà 60° pulse poi pwm off → servo a 60° meccanico),
  poi lancia:    sudo python3 release_brake.py

Per il setup idraulico: questo da solo NON garantisce di sbloccare il caliper se
l'olio è in lock. In quel caso serve intervento manuale (apertura bleed nut o
tiraggio leva).
"""
import os
import sys
import time

GPIO_CHIP = 0
SERVO_PIN = 12
SERVO_FREQ = 330  # Hz
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
PERIOD_US = 1_000_000 / SERVO_FREQ
RELEASE_ANGLE = 0    # gradi "logici" → raw 180° (servo invertito)


def angle_to_duty(angle: float) -> float:
    """Convert angle (0=release, 180=full brake) to duty cycle for tx_pwm."""
    raw = 180.0 - angle
    pulse_us = PULSE_MIN_US + (raw / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / PERIOD_US) * 100.0


def main():
    if os.geteuid() != 0:
        print("Run as root (sudo).", file=sys.stderr)
        return 1
    try:
        import lgpio
    except ImportError:
        print("lgpio not installed", file=sys.stderr)
        return 1

    h = lgpio.gpiochip_open(GPIO_CHIP)
    try:
        lgpio.gpio_claim_output(h, SERVO_PIN)
    except Exception as e:
        # already claimed by another process?
        print(f"[WARN] claim failed ({e}). Trying to free first...")
        try:
            lgpio.gpio_free(h, SERVO_PIN)
        except Exception:
            pass
        lgpio.gpio_claim_output(h, SERVO_PIN)

    duty = angle_to_duty(RELEASE_ANGLE)
    print(f"[RELEASE] PWM {SERVO_FREQ}Hz duty={duty:.2f}% (angle {RELEASE_ANGLE}° release)")
    lgpio.tx_pwm(h, SERVO_PIN, SERVO_FREQ, duty)
    time.sleep(2.0)
    lgpio.gpio_write(h, SERVO_PIN, 0)
    lgpio.gpio_free(h, SERVO_PIN)
    lgpio.gpiochip_close(h)
    print("[DONE] PWM off, pin freed. Servo dovrebbe essere in posizione release.")
    print("SE il freno resta tirato → idraulico bloccato, serve intervento manuale "
          "(tirare leva freno a mano, o aprire bleed nut).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
