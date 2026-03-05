#!/usr/bin/env python3
"""
Test loopback RS-485: collega A↔A e B↔B tra i due moduli MAX485.
Quello che scrivi su GPIO 17 (clock/TX) deve tornare su GPIO 27 (data/RX).

Scollega i fili dell'encoder dai morsetti prima di lanciare!

Run with: sudo python3 test_loopback.py
"""

import lgpio
import time

GPIO_CHIP = 4
PIN_CLOCK = 17   # TX via RS-485 #1
PIN_DATA = 27    # RX via RS-485 #2
PIN_CLOCK_EN = 22
PIN_DATA_EN = 23


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, PIN_CLOCK, 1)
    lgpio.gpio_claim_input(h, PIN_DATA)
    lgpio.gpio_claim_output(h, PIN_CLOCK_EN, 1)
    lgpio.gpio_claim_output(h, PIN_DATA_EN, 0)

    print("=" * 50)
    print("TEST LOOPBACK RS-485")
    print("=" * 50)
    print()
    print("Prerequisiti:")
    print("  1. Scollega i 4 fili encoder dai morsetti RS-485")
    print("  2. Collega un cavetto tra A di RS-485 #1 e A di RS-485 #2")
    print("  3. Collega un cavetto tra B di RS-485 #1 e B di RS-485 #2")
    print()
    print("Premi ENTER quando pronto...")
    input()

    print("\nInvio pattern e lettura risposta:\n")
    print(f"  {'TX (GPIO 17)':>15} | {'RX (GPIO 27)':>15} | {'Match':>6}")
    print(f"  {'-'*15} | {'-'*15} | {'-'*6}")

    errors = 0
    total = 20

    for i in range(total):
        val = i % 2  # alterna 0 e 1
        lgpio.gpio_write(h, PIN_CLOCK, val)
        time.sleep(0.05)  # 50ms per stabilizzare
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
        print("  La catena Pi → LevelShifter → MAX485 #1 → MAX485 #2 → LevelShifter → Pi funziona.")
        print("  Il problema e' nei fili dell'encoder o nell'encoder stesso.")
    elif errors == total:
        print("  LOOPBACK FALLITO — nessun match")
        print()
        # Test extra: vediamo se data e' sempre fisso
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        time.sleep(0.05)
        r0 = lgpio.gpio_read(h, PIN_DATA)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(0.05)
        r1 = lgpio.gpio_read(h, PIN_DATA)
        print(f"  TX=0 → RX={r0} | TX=1 → RX={r1}")
        if r0 == 1 and r1 == 1:
            print("  RX sempre HIGH → il segnale non passa dai MAX485")
            print("  Possibili cause:")
            print("    - Cavetti loopback A↔A / B↔B non collegati bene")
            print("    - MAX485 #1 non trasmette (controlla DE=HIGH, DI collegato a HV1)")
            print("    - MAX485 #2 non riceve (controlla RE=LOW, RO collegato a HV2)")
        elif r0 == 0 and r1 == 0:
            print("  RX sempre LOW → MAX485 #2 riceve ma e' bloccato basso")
            print("    - Controlla VCC del MAX485 #2")
        else:
            print("  RX invertito rispetto a TX → possibile A/B invertiti nel loopback")
    else:
        print(f"  LOOPBACK PARZIALE — {errors} errori")
        print("  Possibile problema di timing o contatto intermittente")

    lgpio.gpiochip_close(h)
    print("\nGPIO rilasciato.")


if __name__ == "__main__":
    main()
