#!/usr/bin/env python3
"""
Test isolato per verificare che il level shifter funzioni.

Fa toggle su GPIO 17 (clock) e chiede di misurare con multimetro
sul lato HV1 del level shifter.

Poi testa se GPIO 27 (data) riesce a vedere cambiamenti.

Run with: sudo python3 test_level_shifter.py
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
    print("TEST LEVEL SHIFTER + MAX485")
    print("=" * 50)

    # Test A: verificare che GPIO 17 esce dal Pi
    print("\n[A] GPIO 17 toggle lento — misura con multimetro")
    print("    Metti puntale su LV1 del level shifter")
    print("    Dovresti vedere alternare ~0V e ~3.3V")
    print("    Premi ENTER per iniziare...")
    input()

    for i in range(10):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        print(f"    GPIO 17 = LOW  (aspetto 2s...)")
        time.sleep(2)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        print(f"    GPIO 17 = HIGH (aspetto 2s...)")
        time.sleep(2)

    print("\n    Hai visto alternare la tensione su LV1? (s/n)")
    lv1_ok = input("    > ").strip().lower() == "s"

    if lv1_ok:
        print("\n    Ora metti il puntale su HV1 del level shifter")
        print("    Dovresti vedere alternare ~0V e ~5V")
        print("    Premi ENTER per iniziare...")
        input()

        for i in range(10):
            lgpio.gpio_write(h, PIN_CLOCK, 0)
            print(f"    GPIO 17 = LOW  (aspetto 2s...)")
            time.sleep(2)
            lgpio.gpio_write(h, PIN_CLOCK, 1)
            print(f"    GPIO 17 = HIGH (aspetto 2s...)")
            time.sleep(2)

        print("\n    Hai visto alternare la tensione su HV1? (s/n)")
        hv1_ok = input("    > ").strip().lower() == "s"
    else:
        hv1_ok = False

    # Test B: stato DI del MAX485 #1
    print("\n[B] Ora metti il puntale su DI del MAX485 #1 (clock)")
    print("    (il pin DI deve essere collegato a HV1)")
    print("    Premi ENTER per toggle...")
    input()

    for i in range(10):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        print(f"    GPIO 17 = LOW  (aspetto 2s...)")
        time.sleep(2)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        print(f"    GPIO 17 = HIGH (aspetto 2s...)")
        time.sleep(2)

    print("\n    Hai visto alternare la tensione su DI? (s/n)")
    di_ok = input("    > ").strip().lower() == "s"

    # Test C: uscita differenziale A/B del MAX485 #1
    print("\n[C] Metti il puntale tra A e B del MAX485 #1 (morsetti)")
    print("    Dovresti vedere alternare tensione differenziale")
    print("    Premi ENTER per toggle...")
    input()

    for i in range(5):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        print(f"    GPIO 17 = LOW  (aspetto 3s...)")
        time.sleep(3)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        print(f"    GPIO 17 = HIGH (aspetto 3s...)")
        time.sleep(3)

    # Test D: stato GPIO 27
    print("\n[D] Test GPIO 27 (data in) — stato attuale:")
    for i in range(10):
        val = lgpio.gpio_read(h, PIN_DATA)
        print(f"    Lettura {i+1}: GPIO 27 = {val}")
        time.sleep(0.5)

    # Riepilogo
    print("\n" + "=" * 50)
    print("RIEPILOGO")
    print("=" * 50)
    if not lv1_ok:
        print("  PROBLEMA: GPIO 17 non arriva a LV1")
        print("  → Controlla il filo tra Pin 11 e LV1 del level shifter")
    elif not hv1_ok:
        print("  PROBLEMA: Level shifter non converte LV1 → HV1")
        print("  → Controlla alimentazione: LV=3.3V, HV=5V, GND")
        print("  → Il level shifter potrebbe essere difettoso")
    elif not di_ok:
        print("  PROBLEMA: HV1 non arriva a DI del MAX485")
        print("  → Controlla il filo tra HV1 e DI")
    else:
        print("  Catena clock OK fino a DI del MAX485")
        print("  Se ancora non funziona, il problema e':")
        print("  → Uscita A/B del MAX485 #1 verso encoder")
        print("  → O i fili dell'encoder (Green/Brown) invertiti")

    lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
