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
              │ (5V/5A)   │ │PDI-6221 │ │  (48V)     │
              │           │ │  (6V)   │ │            │
              │ ┌───────┐ │ │         │ │ ┌────────┐ │
              │ │Encoder│ │ │         │ │ │Flipsky │ │
              │ │GPS    │ │ │         │ │ │ 6354   │ │
              │ │MPU6050│ │ │         │ │ │steering│ │
              │ │RS-485 │ │ │         │ │ │ motor  │ │
              │ │Camera │ │ │         │ │ └────────┘ │
              │ └───────┘ │ │         │ │            │
              └───────────┘ └─────────┘ └────────────┘
                   5V           6V          48V direct
```

## Detailed Wiring

### Battery 48V → Pololu D24V55F5 (5V for Raspi)

| Pololu D24V55F5 | Connect to |
|---|---|
| VIN | Battery 48V + |
| GND | Battery 48V − (common GND) |
| VOUT (5V) | Raspi Pin 2 and Pin 4 (5V) via USB-C cable or GPIO header |
| GND | Raspi GND |

> **Raspi Power:** The Pi 5 requires stable 5V/5A.
> Connect via USB-C PD or directly to GPIO header 5V pins
> (Pin 2 + Pin 4 in parallel to distribute current).

### Battery 48V → Pololu D24V55F6 (6V for Servo)

| Pololu D24V55F6 | Connect to |
|---|---|
| VIN | Battery 48V + |
| GND | Battery 48V − (common GND) |
| VOUT (6V) | Servo PDI-6221MG red wire (+V) |
| GND | Servo PDI-6221MG black wire (GND) |

### Battery 48V → VESC (direct)

| VESC | Connect to |
|---|---|
| BAT+ | Battery 48V + |
| BAT− | Battery 48V − |
| Motor U/V/W | Flipsky 6354 BLDC steering motor (3 phases) |

## Physical Connection Diagram

```
48V BATTERY (13S Li-ion)
    │(+)                    │(−)
    │                       │
    ├───────────────────────┤ COMMON GND
    │         │         │   │      │         │          │
    │    ┌────┴───┐ ┌───┴───┴─┐    │    ┌────┴───┐ ┌───┴────┐
    │    │POLOLU  │ │ POLOLU  │    │    │POLOLU  │ │POLOLU  │
    │    │D24V55F5│ │D24V55F6 │    │    │D24V55F5│ │D24V55F6│
    │    │VIN     │ │VIN      │    │    │GND     │ │GND     │
    │    └───┬────┘ └───┬─────┘    │    └───┬────┘ └───┬────┘
    │    VOUT│5V    VOUT│6V        │    GND │      GND │
    │        │          │          │        │          │
    │   ┌────┴────┐  ┌──┴──────┐  │   ┌────┴────┐  ┌──┴──────┐
    │   │RASPI 5  │  │SERVO    │  │   │RASPI 5  │  │SERVO    │
    │   │Pin 2 +4 │  │+V red   │  │   │GND Pin 6│  │GND black│
    │   └─────────┘  └─────────┘  │   └────┬────┘  └─────────┘
    │                              │        │
  ┌─┴──────┐                    ┌──┴────┐   │
  │ VESC   │                    │ VESC  │   ├── Encoder GND
  │ BAT+   │                    │ BAT−  │   ├── GPS GND
  └────────┘                    └───────┘   ├── MPU6050 GND
                                            ├── RS-485 #1 GND
                                            └── RS-485 #2 GND
```

## Peripherals Powered by Raspi

The Raspi 5 in turn powers the low-consumption peripherals:

| Peripheral | Voltage | Raspi Source | Typical Current |
|---|---|---|---|
| Briter Encoder | 5V | Pin 2 (5V) | ~50mA |
| GPS NEO-M10 | 3.3V | Pin 1 (3.3V) | ~30mA |
| MPU6050 | 3.3V | Pin 1 (3.3V) | ~5mA |
| RS-485 module #1 | 3.3V | Pin 1 (3.3V) | ~10mA |
| RS-485 module #2 | 3.3V | Pin 1 (3.3V) | ~10mA |
| Arducam Camarray HAT | 5V | via GPIO header | ~300mA |

**Total peripherals:** ~400mA + Raspi itself (~2-3A under load) = **~3.5A max on 5V Pololu**

## Safe Shutdown (Supercapacitor)

When the 48V battery switch is turned off, the Raspi needs time to shut down cleanly
to avoid SD card corruption. A **supercapacitor** on the 5V rail provides ~5-6 seconds
of power after the battery is disconnected.

### Supercap Specs

| Parameter | Value |
|---|---|
| Part | Abracon ADCM-S05R5SA106RB |
| Digikey | 535-ADCM-S05R5SA106RB-ND |
| Capacitance | **2.2F** |
| Voltage | 5.5V (max) |
| Mount | Through-hole |
| Holdup time | ~1.8s at 1.2A (from 4.7V down to 3.8V cutoff) |

### How it works

```
48V Battery ON:   Battery → Pololu 5V → Raspi + Supercap (charging)
48V Battery OFF:  Supercap → Raspi (discharging, ~5.7s of power)
                  GPIO sense pin goes LOW → safe_shutdown.py → shutdown -h now
```

The key: the supercap sits **between** the Pololu 5V output and the Raspi.
When the battery is cut, the Pololu stops outputting 5V instantly, but the
supercap has stored enough energy to keep the Raspi powered while it shuts down.

An ideal diode (LM74700 + MOSFET) prevents the supercap from back-feeding
into the Pololu (which would drain it faster). Unlike a Schottky diode
(~300mV drop), the ideal diode has near-zero voltage drop:
- Phase 1: LM74700 + IRL540N (Rdson 44mΩ) → ~130mV drop → Pi sees 4.87V
- Phase 2: LM74700 + IRF3205 (Rdson 8mΩ) → ~24mV drop → Pi sees 4.98V

### Wiring Diagram

```
                    BATTERY ON                         BATTERY OFF
               ┌──────────────────┐              ┌──────────────────┐
               │ Pololu charges   │              │ Supercap powers  │
               │ Raspi + supercap │              │ Raspi for ~5.7s  │
               └──────────────────┘              └──────────────────┘

48V Battery ──→ Pololu D24V55F5 (5V out)
                      │
                      │ VOUT (5V)
                      │
                      ├────── Schottky diode (1N5822) ──→ Supercap (+)
                      │       (anode=Pololu, cathode=cap)      │
                      │                                        │
                      │       ┌────────────────────────────────┤
                      │       │                                │
                      │  Supercap 10F 5.5V              Raspi 5V
                      │  (Abracon ADCM-S05R5SA106RB)   (Pin 2 + Pin 4)
                      │       │                                │
                      │       │                                │
                      GND ────┴──────────────── GND ───────────┘
                                              (Pin 6)
```

### Physical wiring step-by-step

| Step | From | To | Notes |
|------|------|----|-------|
| 1 | Pololu D24V55F5 **VOUT** | Schottky diode **anode** (band away from Pololu) | 1N5822 or similar, ≥3A rated |
| 2 | Schottky diode **cathode** (band side) | Supercap **+** pin | Respect polarity! |
| 3 | Supercap **+** pin | Raspi **Pin 2 + Pin 4** (5V) | This is the Raspi power input |
| 4 | Supercap **−** pin | Raspi **Pin 6** (GND) | Common ground |
| 5 | Pololu D24V55F5 **GND** | Same GND rail | All GNDs together |

> **Why the Schottky diode?** When the battery is cut, the Pololu output drops
> to 0V. Without the diode, the supercap would discharge back through the Pololu
> output, wasting energy. The Schottky blocks reverse current with minimal forward
> voltage drop (~0.3V), so the Raspi sees ~4.7V — still enough for stable operation.

### Power sense (GPIO for shutdown detection)

To detect when the battery is cut, tap the **Pololu VOUT** side (before the diode)
via **Level Shifter #2 channel 3** (the same shifter used for the encoder):

```
Pololu VOUT (5V, before diode) ──→ Level Shifter #2 HV (power)
                                    Level Shifter #2 HV3 ← jumper to HV
                                    Level Shifter #2 LV3 ──→ GPIO 26 (Pin 37)

Wiring: HV and HV3 jumpered on the board. GND pins jumpered, one wire to
common GND terminal block. Shifter powered from Pololu F5 VOUT (before diode).

  Battery ON:  Pololu outputs 5V → shifter alive → LV3 = 3.3V → GPIO HIGH
  Battery OFF: Pololu drops to 0V → shifter dies → LV3 = 0V → GPIO LOW
```

Previous design used a 2x 10kΩ resistor divider — replaced with level shifter
for reliability (no voltage to verify, cleaner signal).

The supercap is on the OTHER side of the diode, so it does NOT keep GPIO high.
This is what triggers the safe shutdown script.

### Complete circuit

```
48V BATTERY
    │(+)                              │(−)
    │                                 │
    ▼                                 ▼
┌────────────────┐              ┌─────────────┐
│ Pololu D24V55F5│              │ Pololu GND  │
│ VIN            │              │             │
└───────┬────────┘              └──────┬──────┘
        │ VOUT (5V)                    │ GND
        │                              │
        ├──→ Level Shifter #2 HV3      │  ← power sense
        │    (LV3 → GPIO 26 Pin 37)   │
        │                              │
        ▼
   ┌──────────────────────┐            │
   │ LM74700 + MOSFET     │            │
   │ (ideal diode)        │            │
   │                      │            │
   │ Phase 1: IRL540N     │            │
   │   Rdson=44mΩ         │            │
   │   drop ~130mV @3A    │            │
   │   Pi sees ~4.87V     │            │
   │                      │            │
   │ Phase 2 (mercoledì): │            │
   │   IRF3205            │            │
   │   Rdson=8mΩ          │            │
   │   drop ~24mV @3A     │            │
   │   Pi sees ~4.98V     │            │
   └──────────┬───────────┘            │
              │                        │
        │                              │
        ├──── Supercap (+) ────────────┤── Supercap (−)
        │     2.2F / 5.5V             │
        │                              │
        ├──── Raspi Pin 2 (5V) ────────┤── Raspi Pin 6 (GND)
        ├──── Raspi Pin 4 (5V)        │
        │                              │
        ├──── Resistenza 22Ω ──→ Drain │
        │     (bleed discharge)  IRL540N│
        │                        Source─┤
        │                              │
        │     Gate ──┬── pull-up 10kΩ ─┤ (a Supercap +)
        │            └── GPIO 6 Pin 31 │ (LOW=Pi on, MOSFET off)
        │                              │
        └──────────────────────────────┘
              all GNDs connected

Auto-discharge after shutdown:
  Pi ON:  GPIO 6 = LOW → Gate LOW → MOSFET off → no drain
  Pi OFF: GPIO floats → pull-up pulls Gate to supercap V → MOSFET on → discharge via 22Ω
  Discharge time: τ = 22 × 2.2 = ~48s from 4.7V to ~0V
```

### Software

A systemd service runs `safe_shutdown.py` which monitors GPIO 26:
- **HIGH** = battery connected, all good
- **LOW** for >500ms = power loss detected → `shutdown -h now`

Install:
```bash
sudo cp safe_shutdown.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now safe_shutdown.service
```

Quick manual shutdown (alias in .bashrc):
```bash
alias off='sudo shutdown -h now'
```

## Safety Notes

- **COMMON GND:** All GNDs (battery, Pololu x2, VESC, Raspi, servo, sensors) must be connected together
- **Fuse:** Inline fuse recommended on the 48V+ line before distribution
- **Main switch:** A switch/kill switch on the 48V+ line to shut down everything
- **Safe shutdown:** Supercap + GPIO sense ensures clean Raspi shutdown when battery is cut
- **Reverse protection:** Pololu regulators have built-in reverse polarity protection
- **Heat dissipation:** Pololu regulators may heat up under load — mount with ventilation or on a heatsink
