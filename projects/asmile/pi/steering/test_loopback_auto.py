#!/usr/bin/env python3
"""
Test loopback RS-485 (non-interattivo).
Collega A↔A e B↔B tra i due moduli prima di lanciare.

Run with: sudo python3 test_loopback_auto.py
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

    print("=" * 50)
    print("TEST LOOPBACK RS-485 (auto)")
    print("=" * 50)
    print()

    print(f"  {'TX (GPIO 17)':>15} | {'RX (GPIO 27)':>15} | {'Match':>6}")
    print(f"  {'-'*15} | {'-'*15} | {'-'*6}")

    errors = 0
    total = 20

    for i in range(total):
        val = i % 2
        lgpio.gpio_write(h, PIN_CLOCK, val)
        time.sleep(0.05)
        read = lgpio.gpio_read(h, PIN_DATA)
        match = "OK" if read == val else "FAIL"
        if read != val:
            errors += 1
        print(f"  {val:>15} | {read:>15} | {match:>6}")
        time.sleep(0.05)

    print(f"\n  Risultato: {total - errors}/{total} corretti")
    print()

    if errors == 0:
        print("  LOOPBACK OK!")
        print("  Catena Pi -> RS-485 #1 -> RS-485 #2 -> Pi funziona.")
        print("  Problema nei fili encoder o nell'encoder stesso.")
    elif errors == total:
        print("  LOOPBACK FALLITO — nessun match")
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        time.sleep(0.05)
        r0 = lgpio.gpio_read(h, PIN_DATA)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(0.05)
        r1 = lgpio.gpio_read(h, PIN_DATA)
        print(f"  TX=0 -> RX={r0} | TX=1 -> RX={r1}")
        if r0 == 1 and r1 == 1:
            print("  RX sempre HIGH -> segnale non passa dai MAX485")
            print("    - Cavetti loopback A<->A / B<->B non collegati?")
            print("    - MAX485 #1 non trasmette (DE non HIGH?)")
            print("    - MAX485 #2 non riceve (RE non LOW?)")
            print("    - Moduli non funzionano a 3.3V? Provare 5V")
        elif r0 == 0 and r1 == 0:
            print("  RX sempre LOW -> MAX485 #2 bloccato basso")
        else:
            print("  RX invertito -> A/B invertiti nel loopback")
    else:
        print(f"  LOOPBACK PARZIALE — {errors} errori")
        print("  Contatto intermittente o problema di timing")

    lgpio.gpiochip_close(h)
    print("\nGPIO rilasciato.")


if __name__ == "__main__":
    main()
