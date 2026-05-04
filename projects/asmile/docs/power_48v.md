# 48V Power Wiring Diagram — Asmile

The entire system is powered by a single 48V battery mounted on the bicycle.

## Source

```
13S Li-ion Battery
├── Nominal: 48V
├── Full charge: ~54.6V
├── Min discharge: ~42V
└── Powers the entire system
```

## Power Distribution

```
                        ┌─────────────────────────────────┐
                        │       48V BATTERY (13S)          │
                        │          + ─── −                 │
                        └──────┬───────────┬───────────────┘
                               │           │
                    ┌──────────┴──┐        │
                    │             │        │
              ┌─────┴─────┐ ┌────┴────┐   │
              │  Pololu    │ │ Pololu  │   │
              │ D24V55F5   │ │D24V55F6 │   │
              │  48V → 5V  │ │48V → 6V │   │
              └─────┬──────┘ └────┬────┘   │
                    │             │        │
              ┌─────┴─────┐ ┌────┴────┐ ┌─┴──────────┐
              │           │ │         │ │            │
              │ Raspi 5   │ │ Servo   │ │   VESC     │
              │ (5V/5A)   │ │Miuzei   │ │  (48V)     │
              │           │ │M S69    │ │            │
              │ ┌───────┐ │ │ (6V)    │ │ ┌────────┐ │
              │ │Encoder│ │ │         │ │ │Flipsky │ │
              │ │GPS    │ │ │         │ │ │ 6354   │ │
              │ │MPU6050│ │ │         │ │ │steering│ │
              │ │RS-485 │ │ │         │ │ │ motor  │ │
              │ │Camera │ │ │         │ │ └────────┘ │
              │ └───────┘ │ │         │ │            │
              └───────────┘ └─────────┘ └────────────┘
                   5V           6V          48V direct
```

## Safe Shutdown — LM74700 Ideal Diode + Supercap 2.2F

When the 48V battery switch is turned off, the Raspi needs time to shut down cleanly
to avoid SD card corruption. A supercapacitor on the 5V rail provides power while
the Pi shuts down. An ideal diode (LM74700 + MOSFET) prevents backfeed with
near-zero voltage drop.

### Complete Circuit

```
48V BATTERY
    │(+)                                        │(−)
    │                                           │
    ▼                                           ▼
┌────────────────┐                        ┌─────────────┐
│ Pololu D24V55F5│                        │ Pololu GND  │
│ VIN            │                        │             │
└───────┬────────┘                        └──────┬──────┘
        │ VOUT (5V)                              │ GND
        │                                        │
        ├──→ Level Shifter HV (power)            │
        │    Level Shifter HV3 ← jumper to HV    │
        │    Level Shifter LV3 → GPIO 26 Pin 37  │  ← power sense
        │                                        │
        ├──→ LM74700 ANODE (pin 1)               │
        ├──→ LM74700 EN (pin 3)                  │
        │                                        │
        └──→ MOSFET Source                        │
                │                                │
            LM74700 GATE (pin 2) → MOSFET Gate   │
            LM74700 VCAP (pin 5) ─┐              │
                                  │ 100nF        │
            LM74700 CATHODE (pin 4)┘              │
                │                                │
            MOSFET Drain                          │
                │                                │
                ├──── Supercap (+) 2.2F ─────────┤── Supercap (−)
                │                                │
                ├──── Raspi Pin 2 (5V) ──────────┤── Raspi Pin 6 (GND)
                ├──── Raspi Pin 4 (5V)           │
                │                                │
                ├──── 22Ω ──→ Drain IRL540N      │
                │             (discharge)  Source─┤
                │                                │
                │     Gate ──┬── pull-up 10kΩ ───┤ (a Supercap +)
                │            └── GPIO 6 Pin 31   │ (LOW=Pi on, off)
                │                                │
            LM74700 GND (pin 6) ─────────────────┤
                                                 │
                └────────────────────────────────┘
                          all GNDs connected
```

### MOSFET Versions

| Phase | MOSFET | Rdson | Drop @3A | Pi vede |
|---|---|---|---|---|
| 1 (ora) | IRL540N | 44mΩ | 132mV | 4.87V |
| 2 (IRF3205) | IRF3205 | 8mΩ | 24mV | 4.98V |

Il cablaggio è **identico** — cambia solo il MOSFET fisico.

### Come funziona

```
Batteria ON:
  Pololu VOUT = 5V
  → Level Shifter HV = 5V → LV3 = 3.3V → GPIO 26 = HIGH (armed)
  → LM74700 apre MOSFET → corrente passa → Supercap si carica + Pi alimentato
  → Pi vede: 5V - drop MOSFET = 4.87V (IRL540N) o 4.98V (IRF3205)

Batteria OFF:
  Pololu VOUT = 0V (istantaneo)
  → Level Shifter HV = 0V → shifter muore → LV3 = 0V → GPIO 26 = LOW
  → safe_shutdown.py rileva LOW per >500ms → shutdown -h now
  → LM74700 chiude MOSFET → blocca backfeed dal supercap al Pololu
  → Supercap tiene Pi vivo (~1.8s a 1.2A) per completare shutdown

Dopo shutdown:
  Pi OFF → GPIO 6 flotta → pull-up 10kΩ tira gate IRL540N HIGH
  → IRL540N ON → supercap si scarica via 22Ω
  → τ = 22 × 2.2 = ~48s per scaricare completamente
  → Pronto per prossimo ciclo
```

### LM74700 Collegamento Passo Passo

```
LM74700 (SOT-23-6, visto dall'alto con scritta dritta):

        ┌─────┐
  Pin 1 │     │ Pin 6
  Pin 2 │     │ Pin 5
  Pin 3 │     │ Pin 4
        └─────┘

Pin 1 (ANODE)   → Pololu 5V VOUT
Pin 2 (GATE)    → MOSFET Gate
Pin 3 (EN)      → Pololu 5V VOUT (jumper a Pin 1)
Pin 4 (CATHODE) → MOSFET Drain (lato uscita: supercap + Pi)
Pin 5 (VCAP)    → condensatore 100nF → Pin 4 (CATHODE)
Pin 6 (GND)     → GND comune

MOSFET (IRL540N o IRF3205, TO-220, visto da davanti):

     ┌───────────┐
     │  MOSFET   │
     │           │
     └─┬───┬───┬─┘
       G   D   S
       │   │   │
       │   │   └── Pololu 5V VOUT (ingresso, = ANODE)
       │   └────── Supercap + Raspi 5V (uscita, = CATHODE)
       └────────── LM74700 pin 2 (GATE)
```

### Componenti necessari

| # | Componente | Valore | Quantità |
|---|---|---|---|
| 1 | LM74700 | SOT-23-6 | 1 |
| 2 | IRL540N (fase 1) o IRF3205 (fase 2) | TO-220 | 1 |
| 3 | Condensatore ceramico | 100nF (0.1uF) | 1 |
| 4 | Supercap | 2.2F 5.5V | 1 |
| 5 | IRL540N (discharge) | TO-220 | 1 (già montato) |
| 6 | Resistenza | 120Ω (discharge, più tempo per shutdown) | 1 |
| 7 | Resistenza | 10kΩ (pull-up gate discharge) | 1 (già montata) |

### Power Sense (GPIO 26)

Il level shifter è alimentato dal **Pololu VOUT** (PRIMA dell'ideal diode).
Quando la batteria si stacca, il Pololu va a 0V, il level shifter muore,
GPIO 26 va LOW. Il supercap è DOPO l'ideal diode, quindi NON tiene alto
il power sense — esattamente come con il vecchio diodo Schottky.

```
Level Shifter canali usati:
  Canale 1: CLK encoder    GPIO 21 → LV1 → HV1 → RS-485 #1 DI
  Canale 2: DATA encoder   GPIO 19 ← LV2 ← HV2 ← RS-485 #2 RO
  Canale 3: Power sense    GPIO 26 ← LV3 ← HV3 ← Pololu VOUT (prima ideal diode)
  Canale 4: LIBERO
```

## Buzzer — KY-006 via 2N2222A

Il buzzer non passa più dal level shifter. Pilotato da transistor NPN:

```
GPIO 4 (Pin 7) ──→ Resistenza 1kΩ ──→ Base 2N2222A
                                       Emitter → GND
                                       Collector → Buzzer KY-006 (S)
                                       Buzzer KY-006 (+) → 5V
                                       Buzzer KY-006 (−) → GND
```

> GPIO 4 manda PWM → 2N2222A amplifica → buzzer suona a 5V.
> Resistenza 1kΩ alla base limita la corrente dal GPIO (~3mA).

## Peripherals Powered by Raspi

| Peripheral | Voltage | Raspi Source | Typical Current |
|---|---|---|---|
| Briter Encoder | 5V | Pin 2 (5V) | ~50mA |
| GPS NEO-M10 | 3.3V | Pin 1 (3.3V) | ~30mA |
| MPU6050 | 3.3V | Pin 1 (3.3V) | ~5mA |
| RS-485 module #1 | 5V | Pin 2 (5V) | ~10mA |
| RS-485 module #2 | 5V | Pin 2 (5V) | ~10mA |
| Buzzer KY-006 | 5V via 2N2222A | Pin 2 (5V) | ~20mA |
| Cameras OV9281 x2 | via CSI | Camera ports | ~300mA |

**Total peripherals:** ~425mA + Raspi itself (~2-3A under load) = **~3.5A max on 5V Pololu**

## Safety Notes

- **COMMON GND:** All GNDs (battery, Pololu x2, VESC, Raspi, servo, sensors) must be connected together
- **Fuse:** Inline fuse recommended on the 48V+ line before distribution
- **Main switch:** A switch/kill switch on the 48V+ line to shut down everything
- **Safe shutdown:** LM74700 ideal diode + supercap + GPIO 26 sense ensures clean Raspi shutdown
- **Reverse protection:** Pololu regulators have built-in reverse polarity protection
- **Heat dissipation:** Pololu regulators may heat up under load — mount with ventilation or on a heatsink
