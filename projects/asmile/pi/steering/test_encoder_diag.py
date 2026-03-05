#!/usr/bin/env python3
"""
Diagnostic test for Briter 5V 12-bit SSI Encoder via RS-485 modules.

Tests each component step by step:
  1. GPIO chip access
  2. Clock output (GPIO 17)
  3. Enable pins (GPIO 22 HIGH, GPIO 23 LOW)
  4. Data input (GPIO 27) — check if stuck HIGH or LOW
  5. SSI read — try to clock out 12 bits
  6. Multiple reads — check if values change or are stuck

Run with: sudo python3 test_encoder_diag.py
"""

import lgpio
import time
import sys

GPIO_CHIP = 4
PIN_CLOCK = 17
PIN_DATA = 27
PIN_CLOCK_EN = 22
PIN_DATA_EN = 23
BITS = 12

PASS = "OK"
FAIL = "FAIL"


def test_gpio_access():
    """Test 1: Can we open gpiochip4?"""
    print("\n[TEST 1] Apertura gpiochip4...")
    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        print(f"  {PASS} — gpiochip{GPIO_CHIP} aperto (handle={h})")
        return h
    except Exception as e:
        print(f"  {FAIL} — Impossibile aprire gpiochip{GPIO_CHIP}: {e}")
        print("  Suggerimento: assicurati di eseguire con sudo")
        return None


def test_claim_pins(h):
    """Test 2: Claim all pins."""
    print("\n[TEST 2] Claim dei pin GPIO...")
    pins = [
        (PIN_CLOCK, "output", "CLOCK (GPIO 17)"),
        (PIN_CLOCK_EN, "output", "CLOCK_EN (GPIO 22)"),
        (PIN_DATA_EN, "output", "DATA_EN (GPIO 23)"),
        (PIN_DATA, "input", "DATA (GPIO 27)"),
    ]
    ok = True
    for pin, direction, name in pins:
        try:
            if direction == "output":
                lgpio.gpio_claim_output(h, pin, 1 if pin == PIN_CLOCK else 0)
            else:
                lgpio.gpio_claim_input(h, pin)
            print(f"  {PASS} — {name} claimed as {direction}")
        except Exception as e:
            print(f"  {FAIL} — {name}: {e}")
            ok = False
    return ok


def test_enable_pins(h):
    """Test 3: Set enable pins and verify."""
    print("\n[TEST 3] Enable pins (CLOCK_EN=HIGH, DATA_EN=LOW)...")
    try:
        lgpio.gpio_write(h, PIN_CLOCK_EN, 1)
        lgpio.gpio_write(h, PIN_DATA_EN, 0)
        print(f"  {PASS} — GPIO 22 (CLOCK_EN) = HIGH → RS-485 #1 in TX mode")
        print(f"  {PASS} — GPIO 23 (DATA_EN) = LOW  → RS-485 #2 in RX mode")
        return True
    except Exception as e:
        print(f"  {FAIL} — Errore impostazione enable: {e}")
        return False


def test_data_line_idle(h):
    """Test 4: Check data line state before clocking."""
    print("\n[TEST 4] Stato linea DATA a riposo (prima del clock)...")
    # Clock should be HIGH at idle for SSI
    lgpio.gpio_write(h, PIN_CLOCK, 1)
    time.sleep(0.001)

    readings = []
    for _ in range(10):
        readings.append(lgpio.gpio_read(h, PIN_DATA))
        time.sleep(0.0005)

    all_high = all(r == 1 for r in readings)
    all_low = all(r == 0 for r in readings)

    print(f"  10 letture DATA a riposo: {readings}")

    if all_high:
        print(f"  INFO — DATA sempre HIGH a riposo (normale per SSI — idle = 1)")
        return "high"
    elif all_low:
        print(f"  WARN — DATA sempre LOW a riposo!")
        print(f"         Possibili cause:")
        print(f"         - RS-485 #2 non alimentato o non funzionante")
        print(f"         - Cavi DATA+/DATA- invertiti o scollegati")
        print(f"         - Encoder non alimentato (controllare 5V su Pin 4)")
        print(f"         - Modulo RS-485 non funziona a 3.3V (provare 5V)")
        return "low"
    else:
        print(f"  INFO — DATA varia (potrebbe essere rumore o dati)")
        return "mixed"


def read_ssi_raw(h):
    """Clock out 12 bits from SSI encoder."""
    # SSI protocol: clock idle HIGH, data sampled on rising edge
    raw = 0
    time.sleep(25e-6)  # Monoflop time
    for _ in range(BITS):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        time.sleep(1e-6)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(2e-6)
        bit = lgpio.gpio_read(h, PIN_DATA)
        raw = (raw << 1) | bit
    time.sleep(25e-6)
    return raw


def test_ssi_read(h):
    """Test 5: Try to read SSI data."""
    print("\n[TEST 5] Lettura SSI (12 bit, singola)...")

    # Read raw bits one by one for debugging
    lgpio.gpio_write(h, PIN_CLOCK, 1)
    time.sleep(0.001)

    bits = []
    time.sleep(25e-6)
    for i in range(BITS):
        lgpio.gpio_write(h, PIN_CLOCK, 0)
        time.sleep(1e-6)
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(2e-6)
        bit = lgpio.gpio_read(h, PIN_DATA)
        bits.append(bit)
    time.sleep(25e-6)

    raw = 0
    for b in bits:
        raw = (raw << 1) | b

    print(f"  Bit individuali: {bits}")
    print(f"  Valore raw: {raw} (0x{raw:03X})")

    all_ones = all(b == 1 for b in bits)
    all_zeros = all(b == 0 for b in bits)

    if all_ones:
        print(f"  WARN — Tutti 1 (4095) — DATA bloccato HIGH")
        print(f"         Il clock potrebbe non arrivare all'encoder")
        print(f"         Controllare: RS-485 #1 (clock) collegamento e alimentazione")
    elif all_zeros:
        print(f"  WARN — Tutti 0 — DATA bloccato LOW")
        print(f"         Il modulo RS-485 #2 potrebbe non ricevere")
    else:
        print(f"  {PASS} — Dati variabili ricevuti, encoder risponde!")

    return raw, bits


def test_multiple_reads(h):
    """Test 6: Multiple reads to check consistency."""
    print("\n[TEST 6] Letture multiple (20 campioni)...")
    values = []
    for i in range(20):
        lgpio.gpio_write(h, PIN_CLOCK, 1)
        time.sleep(0.005)
        val = read_ssi_raw(h)
        values.append(val)
        time.sleep(0.02)

    unique = set(values)
    print(f"  Valori: {values}")
    print(f"  Valori unici: {len(unique)} — {sorted(unique)}")

    if len(unique) == 1:
        v = values[0]
        if v == 4095:
            print(f"  WARN — Sempre 4095: clock non arriva all'encoder")
        elif v == 0:
            print(f"  WARN — Sempre 0: data line morta")
        else:
            print(f"  INFO — Valore costante {v} — encoder fermo ma funzionante!")
            print(f"         Prova a ruotare l'encoder manualmente")
    elif len(unique) <= 3:
        print(f"  INFO — Pochi valori diversi, potrebbe essere rumore o micro-movimento")
    else:
        print(f"  {PASS} — Valori variabili, encoder funziona!")


def test_clock_toggle(h):
    """Test 7: Verify clock pin toggles correctly."""
    print("\n[TEST 7] Verifica toggle del clock (GPIO 17)...")
    try:
        for i in range(5):
            lgpio.gpio_write(h, PIN_CLOCK, 0)
            time.sleep(0.001)
            lgpio.gpio_write(h, PIN_CLOCK, 1)
            time.sleep(0.001)
        print(f"  {PASS} — Clock toggle completato senza errori")
        print(f"  Suggerimento: con un multimetro/oscilloscopio verificare")
        print(f"  che il segnale arrivi al pin A/B del morsetto RS-485 #1")
        return True
    except Exception as e:
        print(f"  {FAIL} — {e}")
        return False


def print_summary(data_idle, raw_val, bits):
    """Print diagnostic summary."""
    print("\n" + "=" * 60)
    print("RIEPILOGO DIAGNOSTICA")
    print("=" * 60)

    all_ones = all(b == 1 for b in bits)
    all_zeros = all(b == 0 for b in bits)

    if not all_ones and not all_zeros:
        print("  L'encoder risponde! Se i valori sembrano sensati,")
        print("  il problema potrebbe essere nel software, non nel wiring.")
        return

    print("\nPossibili problemi in ordine di probabilita':")
    print()

    if data_idle == "low" and all_zeros:
        print("  1. ENCODER NON ALIMENTATO")
        print("     → Verificare 5V su filo rosso con multimetro")
        print("     → Verificare GND su filo nero")
        print()
        print("  2. MODULO RS-485 #2 (DATA) NON FUNZIONA A 3.3V")
        print("     → Provare ad alimentare RS-485 #2 a 5V (Pin 4)")
        print("     → ATTENZIONE: se RO va a 5V serve un partitore")
        print("     → per proteggere GPIO 27 (max 3.3V)")
        print()
        print("  3. CAVI DATA SCOLLEGATI O INVERTITI")
        print("     → Controllare White=DATA+, Gray=DATA-")
        print("     → Verificare che arrivino ai morsetti A/B di RS-485 #2")

    elif data_idle == "high" and all_ones:
        print("  1. CLOCK NON ARRIVA ALL'ENCODER")
        print("     → Il modulo RS-485 #1 (clock) potrebbe non funzionare a 3.3V")
        print("     → Provare ad alimentare RS-485 #1 a 5V (Pin 4)")
        print("     → Verificare Green=CLK+, Brown=CLK- ai morsetti A/B")
        print()
        print("  2. CAVI CLOCK SCOLLEGATI O INVERTITI")
        print("     → Controllare collegamento tra RS-485 #1 e encoder")
        print()
        print("  3. RS-485 #1 DE/RE NON CORRETTI")
        print("     → DE e RE devono essere entrambi a 3.3V (o VCC)")
        print("     → per mettere il modulo in modalita' TX")

    print()
    print("  NOTA SUL 3.3V vs 5V:")
    print("  I moduli RS-485 basati su MAX485 funzionano da 4.75V a 5.25V.")
    print("  Se usi MAX485 originali, NON funzionano a 3.3V.")
    print("  Moduli basati su MAX3485 o SP3485 funzionano a 3.3V.")
    print("  → Controlla il chip sul modulo RS-485!")


def main():
    print("=" * 60)
    print("DIAGNOSTICA ENCODER BRITER SSI — Raspberry Pi 5")
    print("=" * 60)
    print(f"  Clock: GPIO {PIN_CLOCK} (Pin 11)")
    print(f"  Data:  GPIO {PIN_DATA} (Pin 13)")
    print(f"  CLK_EN: GPIO {PIN_CLOCK_EN} (Pin 15) → HIGH")
    print(f"  DAT_EN: GPIO {PIN_DATA_EN} (Pin 16) → LOW")

    h = test_gpio_access()
    if h is None:
        sys.exit(1)

    try:
        if not test_claim_pins(h):
            sys.exit(1)

        test_enable_pins(h)
        test_clock_toggle(h)
        data_idle = test_data_line_idle(h)
        raw, bits = test_ssi_read(h)
        test_multiple_reads(h)
        print_summary(data_idle, raw, bits)

    finally:
        lgpio.gpiochip_close(h)
        print("\nGPIO rilasciato.")


if __name__ == "__main__":
    main()
