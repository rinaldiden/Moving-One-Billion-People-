#!/usr/bin/env python3
"""
Test buzzer KY-006 on GPIO 5 via Level Shifter #2 ch4.

If you don't hear anything:
1. Check HV of Level Shifter #2 has 5V (from Pololu F5 VOUT before Schottky)
2. Check LV4 → GPIO 5 (Pin 29)
3. Check HV4 → Buzzer S (signal)
4. Check Buzzer GND → common GND
5. Try different frequencies — the KY-006 resonates best at 2-4kHz

This script tests multiple frequencies and duty cycles to find what works.
"""

import lgpio
import time
import sys

GPIO_CHIP = 4
BUZZER_PIN = 5


def test_buzzer():
    h = lgpio.gpiochip_open(GPIO_CHIP)

    # Test 1: GPIO output check
    print("=== Test 1: GPIO 5 output ===")
    lgpio.gpio_claim_output(h, BUZZER_PIN, 1)
    time.sleep(0.1)
    lgpio.gpio_free(h, BUZZER_PIN)
    lgpio.gpio_claim_input(h, BUZZER_PIN)
    val = lgpio.gpio_read(h, BUZZER_PIN)
    lgpio.gpio_free(h, BUZZER_PIN)
    print(f"  GPIO 5 after HIGH: {val} ({'OK' if val == 1 else 'PROBLEM — pin not reaching header'})")

    # Test 2: PWM at different frequencies
    print("\n=== Test 2: Frequency sweep ===")
    print("  Listen for beeps at each frequency...")
    for freq in [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]:
        print(f"  {freq}Hz...", end=" ", flush=True)
        lgpio.tx_pwm(h, BUZZER_PIN, freq, 50)
        time.sleep(0.5)
        lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)
        time.sleep(0.2)
        print("done")

    # Test 3: Different duty cycles at 2kHz
    print("\n=== Test 3: Duty cycle sweep at 2kHz ===")
    for duty in [10, 25, 50, 75, 90]:
        print(f"  duty={duty}%...", end=" ", flush=True)
        lgpio.tx_pwm(h, BUZZER_PIN, 2000, duty)
        time.sleep(0.5)
        lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)
        time.sleep(0.2)
        print("done")

    # Test 4: Long beep at resonant frequency
    print("\n=== Test 4: Long beep 2.5kHz 3 seconds ===")
    lgpio.tx_pwm(h, BUZZER_PIN, 2500, 50)
    time.sleep(3)
    lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)
    print("  done")

    lgpio.gpiochip_close(h)
    print("\nIf you heard nothing, check level shifter wiring (HV needs 5V).")


if __name__ == "__main__":
    test_buzzer()
