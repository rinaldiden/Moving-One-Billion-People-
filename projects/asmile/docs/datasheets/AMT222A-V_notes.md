# AMT222A-V — Encoder Assoluto SPI (sostituisce Briter BRT38)

Datasheet salvato: AMT22_V_datasheet.pdf

## Specifiche elettriche (dal datasheet)

| Parametro | Min | Typ | Max | Unità |
|-----------|-----|-----|-----|-------|
| Alimentazione (Vdd) | 3.8 | 5 | 5.5 | V |
| Start-up time | | 200 | | ms |
| Corrente | | 16 | | mA |
| Input LOW | | | 0.8 | V |
| Input HIGH | 2.0 | | 5.5 | V |
| Output LOW | | | 0.8 | V |
| Output HIGH | 3.3 | | | V |

**Output HIGH = 3.3V** → compatibile diretto con GPIO Raspberry Pi! Niente level shifter!

## SPI Interface (dal datasheet)

| Parametro | Min | Typ | Max | Unità |
|-----------|-----|-----|-----|-------|
| Protocollo | SPI Mode 0 | | | |
| Frame size | | 8 | | bit |
| Data rate | | | 2 | MHz |
| T_CLK (data to buffer) | 2.5 | | | µs |
| T_B (tra i byte) | 2.5 | | | µs |
| T_CS (tra le letture) | 40 | | | µs |
| T_R (prima di rilasciare CS) | 3 | | | µs |

**SPI Mode 0** (CPOL=0, CPHA=0)

## Sequenza lettura posizione

```
Comando: 0x00 0x00

1. CS → LOW
2. Invia byte 0x00 → ricevi byte alto [K1 K0 D13 D12 D11 D10 D9 D8]
3. Attendi ≥ 2.5µs (T_B)
4. Invia byte 0x00 → ricevi byte basso [D7 D6 D5 D4 D3 D2 D1 D0]
5. Attendi ≥ 3µs (T_R)
6. CS → HIGH
7. Attendi ≥ 40µs (T_CS) prima della prossima lettura

Risultato 16 bit:
  Bit 15 (K1): checkbit odd parity
  Bit 14 (K0): checkbit even parity
  Bit 13-0: posizione (14 bit)

Per 12-bit (AMT222A): bit 1-0 sempre 0 → shift right 2 → posizione 0-4095
```

## Comandi

| Comando | Hex | Descrizione |
|---------|-----|-------------|
| Read Position | 0x00 0x00 | Legge posizione corrente |
| Reset Encoder | 0x00 0x60 | Reset completo |
| Set Zero Point | 0x00 0x70 | Imposta zero (solo single-turn) |

## Checkbit (verifica integrità)

```
K1 (odd):  !(H5^H3^H1^H7^L5^L3^L1) = deve essere 1
K0 (even): !(H4^H2^H0^L6^L4^L2^L0) = deve essere 1

Esempio: 0x61AB
  K1=0, K0=0 → verifica:
  Odd:  !(1^0^0^1^1^1^1) = 0 ✓
  Even: !(0^0^1^0^0^0^1) = 1 ✓
```

## Switch Run/Program

L'encoder ha uno switch sotto:
- **Run Mode** (destra) = modalità SPI normale
- **Program Mode** (sinistra) = per AMT Viewpoint software

**IMPORTANTE**: switch deve essere in **Run Mode** prima di collegare!

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

Output HIGH = 3.3V → diretto al Pi, nessun level shifter!

## Differenze dal Briter BRT38

| | Briter BRT38 | AMT222A-V |
|--|---|---|
| Interfaccia | SSI via RS-485 | SPI Mode 0 diretto |
| Moduli extra | 2x RS-485 + level shifter | NESSUNO |
| Tensione output | 5V (serve shifter) | 3.3V (diretto al Pi) |
| Fili | 8 (6 usati) | 6 |
| SPI Mode | Mode 2 (CPOL=1) | Mode 0 (CPOL=0) |
| Clock idle | HIGH | LOW |
| Timing tra byte | nessuno | 2.5µs minimo |
| Checksum | nessuno | 2 bit parity |
| Complessità | Alta | Minima |
