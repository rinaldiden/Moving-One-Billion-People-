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

## Safety Notes

- **COMMON GND:** All GNDs (battery, Pololu x2, VESC, Raspi, servo, sensors) must be connected together
- **Fuse:** Inline fuse recommended on the 48V+ line before distribution
- **Main switch:** A switch/kill switch on the 48V+ line to shut down everything
- **Reverse protection:** Pololu regulators have built-in reverse polarity protection
- **Heat dissipation:** Pololu regulators may heat up under load — mount with ventilation or on a heatsink
