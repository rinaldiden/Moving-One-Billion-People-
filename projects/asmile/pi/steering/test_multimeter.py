#!/usr/bin/env python3
"""
Toggle clock lentamente per misure col multimetro.
Ogni stato dura 3 secondi — abbastanza per leggere il tester.

Run with: sudo python3 test_multimeter.py
"""

import lgpio
import time

GPIO_CHIP = 4
PIN_CLOCK = 17
PIN_DATA = 27
PIN_CLOCK_EN = 22
PIN_DATA_EN = 23


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, PIN_CLOCK, 1)
    lgpio.gpio_claim_input(h, PIN_DATA)
    lgpio.gpio_claim_output(h, PIN_CLOCK_EN, 1)
    lgpio.gpio_claim_output(h, PIN_DATA_EN, 0)

    print("=" * 55)
    print("MISURE COL MULTIMETRO — 3 punti da verificare")
    print("=" * 55)

    # Misura 1: alimentazione encoder
    print("\n[1] ALIMENTAZIONE ENCODER")
    print("    Multimetro in DC Volt tra:")
    print("    + Red wire encoder (o Pin 4 del Raspi)")
    print("    - Black wire encoder (o Pin 30 GND)")
    print("    Deve leggere ~5V")
    print()

    # Misura 2: uscita level shifter HV1
    print("[2] USCITA LEVEL SHIFTER → DI del MAX485 #1")
    print("    Multimetro tra HV1 e GND")
    print("    Vedrai alternare ~0V e ~5V ogni 3 secondi")
    print()

    # Misura 3: uscita differenziale RS-485 #1
    print("[3] USCITA RS-485 #1 (morsetti A-B)")
    print("    Multimetro tra A e B del modulo RS-485 #1")
    print("    Deve alternare tra ~+1.5V e ~-1.5V")
    print()

    print("Toggle clock... (Ctrl+C per uscire)")
    print()

    try:
        cycle = 0
        while True:
            lgpio.gpio_write(h, PIN_CLOCK, 0)
            data = lgpio.gpio_read(h, PIN_DATA)
            print(f"  CLK=LOW   DATA={data}   (3s...)")
            time.sleep(3)

            lgpio.gpio_write(h, PIN_CLOCK, 1)
            data = lgpio.gpio_read(h, PIN_DATA)
            print(f"  CLK=HIGH  DATA={data}   (3s...)")
            time.sleep(3)

            cycle += 1
            if cycle >= 20:
                break
    except KeyboardInterrupt:
        print("\nInterrotto.")
    finally:
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        lgpio.gpiochip_close(h)
        print("GPIO rilasciato.")


if __name__ == "__main__":
    main()
