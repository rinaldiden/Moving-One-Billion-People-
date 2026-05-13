# AMT222A-V — Encoder Assoluto SPI (sostituisce Briter BRT38)

Datasheet: https://www.mouser.it/datasheet/3/6118/1/amt22_v.pdf

## Specifiche
- **Tipo**: Capacitivo, assoluto, single-turn
- **Risoluzione**: 12 bit (4096 posizioni) — modello A
- **Interfaccia**: SPI nativo (NO RS-485, NO level shifter!)
- **Alimentazione**: 3.8V - 5.5V
- **Clock SPI**: fino a 2MHz (usare 500kHz per prototipazione)
- **Precisione**: ±0.2° meccanici
- **Temperatura**: -40°C a +125°C

## Pinout (connettore 6 pin)

| Pin | Segnale | Descrizione |
|-----|---------|-------------|
| 1 | Vdd | Alimentazione 3.8-5.5V |
| 2 | SCLK | SPI Clock |
| 3 | MOSI | SPI Master Out Slave In |
| 4 | GND | Ground |
| 5 | MISO | SPI Master In Slave Out |
| 6 | CS | Chip Select (active LOW) |

## Collegamento a Raspberry Pi 5 — SPI1

```
AMT222A-V          Raspberry Pi (SPI1)
Pin 1 (Vdd)    →   Pin 2 (5V)
Pin 2 (SCLK)   →   Pin 40 (GPIO 21, SPI1_SCLK)
Pin 3 (MOSI)   →   Pin 38 (GPIO 20, SPI1_MOSI)
Pin 4 (GND)    →   Pin 39 (GND)
Pin 5 (MISO)   →   Pin 35 (GPIO 19, SPI1_MISO)
Pin 6 (CS)     →   Pin 12 (GPIO 18, SPI1_CE0)
```

## Protocollo SPI — sequenza di lettura

```
1. CS → LOW
2. Invia 0x00 (NOP), ricevi byte alto
3. Attendi 3µs
4. Invia 0x00, ricevi byte basso
5. CS → HIGH

Risultato: 16 bit
  - Bit 15-14: checkbit (verifica integrità)
  - Bit 13-2: posizione 12 bit (0-4095)
  - Bit 1-0: sempre 0 (per 12 bit, shift right 2)
```

## Validazione checksum

```python
# XOR dei bit pari e dispari per verificare integrità
odd_check = 0
even_check = 0
for i in range(16):
    if i % 2 == 0:
        even_check ^= (raw >> i) & 1
    else:
        odd_check ^= (raw >> i) & 1
valid = (odd_check == 1) and (even_check == 1)
```

## Differenze dal Briter BRT38

| | Briter BRT38 | AMT222A-V |
|--|---|---|
| Interfaccia | SSI via RS-485 | SPI diretto |
| Moduli extra | 2x RS-485 + level shifter | Nessuno |
| Tensione segnale | 5V (serve shifter) | 3.3V-5V compatibile |
| Fili | 6 (+ 2 da non collegare) | 6 |
| Complessità | Alta | Bassa |

## Vantaggi
- Collegamento diretto al Pi senza moduli intermediari
- Niente conflitti con RS-485/level shifter
- SPI nativo = più affidabile e veloce
- Compatibile 3.3V = niente level shifter
