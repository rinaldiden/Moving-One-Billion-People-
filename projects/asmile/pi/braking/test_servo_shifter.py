#!/usr/bin/env python3
"""
Quick test: servo via level shifter on GPIO 12.
Moves to 0, then 90, then 0. If the servo moves, the shifter works.
"""

import lgpio
import time

GPIO_CHIP = 4
PIN_SERVO = 12
SERVO_FREQ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500


def angle_to_duty(angle: int) -> float:
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / 20000.0) * 100.0


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)

    print("=== TEST SERVO + LEVEL SHIFTER ===")

    print("1) Posizione 0...")
    lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, angle_to_duty(0))
    time.sleep(2.0)

    print("2) Posizione 90...")
    lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, angle_to_duty(90))
    time.sleep(2.0)

    print("3) Ritorno a 0...")
    lgpio.tx_pwm(h, PIN_SERVO, SERVO_FREQ, angle_to_duty(0))
    time.sleep(2.0)

    print("4) Stop PWM")
    lgpio.tx_pwm(h, PIN_SERVO, 0, 0)
    lgpio.gpiochip_close(h)

    print("=== FINE TEST ===")
    print("Se il servo si e' mosso a 90 e tornato a 0, il level shifter funziona!")


if __name__ == "__main__":
    main()
