# Schema Alimentazione 48V — Asmile

Tutto il sistema è alimentato da una singola batteria 48V montata sulla bici.

## Sorgente

```
Batteria 13S Li-ion
├── Nominale: 48V
├── Carica completa: ~54.6V
├── Scarica minima: ~42V
└── Alimenta tutto il sistema
```

## Distribuzione Potenza

```
                        ┌─────────────────────────────────┐
                        │      BATTERIA 48V (13S)          │
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
              │ (5V/5A)   │ │ PDI-6221MG  │ │  (48V)     │
              │           │ │ (6V)    │ │            │
              │ ┌───────┐ │ │         │ │ ┌────────┐ │
              │ │Encoder│ │ │         │ │ │Motore  │ │
              │ │GPS    │ │ │         │ │ │BLDC    │ │
              │ │MPU6050│ │ │         │ │ │sterzo  │ │
              │ │RS-485 │ │ │         │ │ └────────┘ │
              │ │Camera │ │ │         │ │            │
              │ └───────┘ │ │         │ │            │
              └───────────┘ └─────────┘ └────────────┘
                   5V           6V          48V diretto
```

## Cablaggi Dettagliati

### Batteria 48V → Pololu D24V55F5 (5V per Raspi)

| Pololu D24V55F5 | Collega a |
|---|---|
| VIN | Batteria 48V + |
| GND | Batteria 48V − (GND comune) |
| VOUT (5V) | Raspi Pin 2 e Pin 4 (5V) via cavo USB-C o header GPIO |
| GND | Raspi GND |

> **Alimentazione Raspi:** Il Pi 5 richiede 5V/5A stabili.
> Collegare via USB-C PD oppure direttamente ai pin 5V del GPIO header
> (Pin 2 + Pin 4 in parallelo per distribuire corrente).

### Batteria 48V → Pololu D24V55F6 (6V per Servo)

| Pololu D24V55F6 | Collega a |
|---|---|
| VIN | Batteria 48V + |
| GND | Batteria 48V − (GND comune) |
| VOUT (6V) | Servo PDI-6221MG filo rosso (+V) |
| GND | Servo PDI-6221MG filo nero (GND) |

### Batteria 48V → VESC (diretto)

| VESC | Collega a |
|---|---|
| BAT+ | Batteria 48V + |
| BAT− | Batteria 48V − |
| Motore U/V/W | Motore BLDC sterzo (3 fasi) |

## Schema Fisico Connessioni

```
BATTERIA 48V (13S Li-ion)
    │(+)                    │(−)
    │                       │
    ├───────────────────────┤ GND COMUNE
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
    │   │Pin 2 +4 │  │+V rosso │  │   │GND Pin 6│  │GND nero │
    │   └─────────┘  └─────────┘  │   └────┬────┘  └─────────┘
    │                              │        │
  ┌─┴──────┐                    ┌──┴────┐   │
  │ VESC   │                    │ VESC  │   ├── Encoder GND
  │ BAT+   │                    │ BAT−  │   ├── GPS GND
  └────────┘                    └───────┘   ├── MPU6050 GND
                                            ├── RS-485 #1 GND
                                            └── RS-485 #2 GND
```

## Periferiche alimentate dal Raspi

Il Raspi 5 a sua volta alimenta le periferiche a basso consumo:

| Periferica | Tensione | Fonte Raspi | Corrente tipica |
|---|---|---|---|
| Encoder Briter | 5V | Pin 2 (5V) | ~50mA |
| GPS NEO-M10 | 3.3V | Pin 1 (3.3V) | ~30mA |
| MPU6050 | 3.3V | Pin 1 (3.3V) | ~5mA |
| RS-485 modulo #1 | 3.3V | Pin 1 (3.3V) | ~10mA |
| RS-485 modulo #2 | 3.3V | Pin 1 (3.3V) | ~10mA |
| Arducam Camarray HAT | 5V | via header GPIO | ~300mA |

**Totale periferiche:** ~400mA + Raspi stesso (~2-3A sotto carico) = **~3.5A max sul Pololu 5V**

## Note Sicurezza

- **GND COMUNE:** Tutti i GND (batteria, Pololu x2, VESC, Raspi, servo, sensori) devono essere collegati insieme
- **Fusibile:** Consigliato fusibile inline sulla linea 48V+ prima della distribuzione
- **Interruttore generale:** Un interruttore/kill switch sulla linea 48V+ per spegnere tutto
- **Protezione inversione:** I Pololu hanno protezione da inversione di polarità integrata
- **Dissipazione:** I Pololu possono scaldare sotto carico — montarli con ventilazione o su dissipatore
