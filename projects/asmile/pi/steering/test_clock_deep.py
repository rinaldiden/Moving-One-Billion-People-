#!/usr/bin/env python3
"""
Deep clock debug for Briter SSI encoder.

Tests:
  A) Loopback (con encoder collegato) — il segnale passa ancora tra i MAX485?
  B) Timing lento — clock con pause lunghe (100us, 1ms, 10ms)
  C) Più bit — prova a leggere 13, 16, 25 bit (magari non è 12-bit)
  D) Clock invertito — prova partendo da LOW invece che HIGH
  E) Monitoring continuo — mostra lo stato di DATA in tempo reale

Run with: sudo python3 test_clock_deep.py
"""

import lgpio
import time
import sys

GPIO_CHIP = 4
PIN_CLOCK = 17
PIN_DATA = 27
PIN_CLOCK_EN = 22
PIN_DATA_EN = 23


def setup(h):
    lgpio.gpio_claim_output(h, PIN_CLOCK, 1)
    lgpio.gpio_claim_input(h, PIN_DATA)
    lgpio.gpio_claim_output(h, PIN_CLOCK_EN, 1)
    lgpio.gpio_claim_output(h, PIN_DATA_EN, 0)


def read_ssi(h, bits, half_period_us, idle_high=True):
    """Read SSI with configurable timing and polarity."""
    idle = 1 if idle_high else 0
    active = 0 if idle_high else 1

    lgpio.gpio_write(h, PIN_CLOCK, idle)
    time.sleep(50e-6)  # monoflop recovery

    result_bits = []
    for _ in range(bits):
        lgpio.gpio_write(h, PIN_CLOCK, active)
        time.sleep(half_period_us * 1e-6)
        lgpio.gpio_write(h, PIN_CLOCK, idle)
        time.sleep(half_period_us * 1e-6)
        bit = lgpio.gpio_read(h, PIN_DATA)
        result_bits.append(bit)

    lgpio.gpio_write(h, PIN_CLOCK, idle)
    time.sleep(50e-6)

    val = 0
    for b in result_bits:
        val = (val << 1) | b
    return val, result_bits


def test_a_loopback_with_encoder(h):
    """Test A: Does the RS-485 loopback still work with encoder wires on?"""
    print("\n[A] LOOPBACK CON ENCODER COLLEGATO")
    print("    (questo verifica se i moduli RS-485 vedono ancora il segnale)")
    errors = 0
    for i in range(10):
        val = i % 2
        lgpio.gpio_write(h, PIN_CLOCK, val)
        time.sleep(0.01)
        read = lgpio.gpio_read(h, PIN_DATA)
        match = "OK" if read == val else "FAIL"
        if read != val:
            errors += 1
    if errors == 0:
        print("    NOTA: loopback funziona — ma questo NON testa l'encoder,")
        print("    testa solo che il segnale passa tra i 2 MAX485.")
        print("    Con l'encoder collegato, DATA dipende dall'encoder, non dal clock.")
    print(f"    Risultato: GPIO17→GPIO27 match {10-errors}/10")
    print(f"    DATA segue TX: {'SI' if errors == 0 else 'NO'}")
    # Reset clock to idle HIGH
    lgpio.gpio_write(h, PIN_CLOCK, 1)
    time.sleep(0.01)
    return errors


def test_b_timing(h):
    """Test B: Try different clock speeds."""
    print("\n[B] TIMING — clock a velocità diverse")
    speeds = [
        (1, "1us (veloce)"),
        (10, "10us"),
        (100, "100us"),
        (1000, "1ms (lento)"),
        (10000, "10ms (molto lento)"),
    ]
    for half_period, label in speeds:
        val, bits = read_ssi(h, 12, half_period)
        all_same = len(set(bits)) == 1
        print(f"    {label:25s} → {bits} = {val:4d} (0x{val:03X}) {'*** DATI!' if not all_same else ''}")


def test_c_more_bits(h):
    """Test C: Try reading more bits."""
    print("\n[C] PIU' BIT — forse non è 12-bit")
    for nbits in [12, 13, 16, 24, 25]:
        val, bits = read_ssi(h, nbits, 10)
        all_same = len(set(bits)) == 1
        summary = f"tutti {'1' if bits[0] == 1 else '0'}" if all_same else "VARIABILI!"
        print(f"    {nbits:2d} bit: {bits} = {val} ({summary})")


def test_d_inverted_clock(h):
    """Test D: SSI with inverted clock polarity."""
    print("\n[D] CLOCK INVERTITO — idle LOW, sample su fronte discendente")
    print("    (se CLK+/CLK- sono scambiati, questo potrebbe funzionare)")
    val_normal, bits_normal = read_ssi(h, 12, 10, idle_high=True)
    val_invert, bits_invert = read_ssi(h, 12, 10, idle_high=False)
    print(f"    Normale  (idle HIGH): {bits_normal} = {val_normal}")
    print(f"    Invertito(idle LOW):  {bits_invert} = {val_invert}")
    if bits_normal != bits_invert:
        print("    *** DIFFERENZA! Prova a scambiare Green/Brown sui morsetti RS-485 #1")


def test_e_data_monitor(h):
    """Test E: Monitor DATA line while toggling clock slowly."""
    print("\n[E] MONITOR DATA — toggle clock lento e osserva DATA")
    print("    CLK  DATA")
    lgpio.gpio_write(h, PIN_CLOCK, 1)
    time.sleep(0.01)
    for i in range(24):
        val = i % 2
        lgpio.gpio_write(h, PIN_CLOCK, val)
        time.sleep(0.005)
        data = lgpio.gpio_read(h, PIN_DATA)
        marker = " <<<" if data != 1 else ""
        print(f"     {val}    {data}{marker}")
        time.sleep(0.005)
    lgpio.gpio_write(h, PIN_CLOCK, 1)


def test_f_power_check(h):
    """Test F: Check if encoder is powered by reading DATA with no clock."""
    print("\n[F] VERIFICA ALIMENTAZIONE ENCODER")
    print("    Clock fermo HIGH, leggo DATA 20 volte in 2 secondi")
    lgpio.gpio_write(h, PIN_CLOCK, 1)
    time.sleep(0.1)
    readings = []
    for _ in range(20):
        readings.append(lgpio.gpio_read(h, PIN_DATA))
        time.sleep(0.1)
    unique = set(readings)
    print(f"    Letture: {readings}")
    if len(unique) == 1 and 1 in unique:
        print("    DATA sempre HIGH a riposo — NORMALE per SSI")
        print("    (l'encoder alimentato tiene DATA HIGH quando non cloccato)")
        print("    Ma potrebbe anche essere pull-up del modulo RS-485 senza segnale...")
    elif len(unique) == 1 and 0 in unique:
        print("    DATA sempre LOW — encoder probabilmente non alimentato")
    else:
        print("    DATA varia — possibile rumore o encoder attivo")


def main():
    print("=" * 60)
    print("DEEP CLOCK DEBUG — Briter SSI Encoder")
    print("=" * 60)

    h = lgpio.gpiochip_open(GPIO_CHIP)
    try:
        setup(h)
        test_f_power_check(h)
        test_a_loopback_with_encoder(h)
        test_b_timing(h)
        test_c_more_bits(h)
        test_d_inverted_clock(h)
        test_e_data_monitor(h)

        print("\n" + "=" * 60)
        print("CONCLUSIONI")
        print("=" * 60)
        print("""
Se DATA e' SEMPRE 1 in tutti i test:
  1. Prova a SCAMBIARE Green/Brown (CLK+/CLK-) sui morsetti RS-485 #1
  2. Se ancora 4095, verifica con multimetro:
     - 5V tra Red e Black dell'encoder?
     - Tensione su A/B di RS-485 #1 quando clock togla?
  3. Controlla che il level shifter converta:
     - LV1 deve alternare 0-3.3V
     - HV1 deve alternare 0-5V

Se DATA cambia con clock INVERTITO (test D):
  → I fili Green/Brown sono scambiati, inverti A↔B su RS-485 #1

Se DATA cambia con timing LENTO (test B):
  → Il clock via RS-485 e' troppo lento, prova SPI hardware
""")
    finally:
        lgpio.gpiochip_close(h)
        print("GPIO rilasciato.")


if __name__ == "__main__":
    main()
