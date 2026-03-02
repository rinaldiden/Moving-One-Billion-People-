# Schema Collegamento Completo — Raspberry Pi 5

Setup completo per il progetto Asmile: sterzo, freno, GPS, IMU.

## Dispositivi

| Dispositivo | Protocollo | Porta |
|---|---|---|
| VESC (sterzo) | UART0 | /dev/ttyAMA0 |
| Encoder Briter 5V 12-bit SSI | GPIO bit-bang (via 2x RS-485) | GPIO 17/27 |
| GPS NEO-M10 | UART3 | /dev/ttyAMA3 |
| MPU6050 IMU | I2C1 | 0x68 |
| Servo freno | PWM0 hardware | GPIO 12 |

## Mappa Pin Completa

| GPIO | Pin header | Dispositivo | Funzione | Direzione |
|---|---|---|---|---|
| GPIO 2 | Pin 3 | MPU6050 | I2C1 SDA | I/O |
| GPIO 3 | Pin 5 | MPU6050 | I2C1 SCL | OUT |
| GPIO 8 | Pin 24 | GPS NEO-M10 | UART3 TX | OUT |
| GPIO 9 | Pin 21 | GPS NEO-M10 | UART3 RX | IN |
| GPIO 12 | Pin 32 | Servo freno | PWM0 segnale | OUT |
| GPIO 14 | Pin 8 | VESC | UART0 TX | OUT |
| GPIO 15 | Pin 10 | VESC | UART0 RX | IN |
| GPIO 17 | Pin 11 | Encoder SSI | CLOCK (via RS-485 #1) | OUT |
| GPIO 22 | Pin 15 | Encoder SSI | CLOCK_ENABLE (HIGH) | OUT |
| GPIO 23 | Pin 16 | Encoder SSI | DATA_ENABLE (LOW) | OUT |
| GPIO 27 | Pin 13 | Encoder SSI | DATA (via RS-485 #2) | IN |

## Header 40 Pin — Vista Finale

```
         Raspberry Pi 5 — GPIO Header
    ╔═══════════════════════════════════════════════╗
    ║  3V3              [ 1] [ 2]  5V               ║
    ║  GPIO 2  I2C SDA  [ 3] [ 4]  5V               ║  ← MPU6050 SDA + Encoder VCC
    ║  GPIO 3  I2C SCL  [ 5] [ 6]  GND              ║  ← MPU6050 SCL + GND comune
    ║  GPIO 4           [ 7] [ 8]  GPIO 14 UART TX  ║  ← VESC TX
    ║  GND              [ 9] [10]  GPIO 15 UART RX  ║  ← VESC RX
    ║  GPIO 17 ENC CLK  [11] [12]  GPIO 18          ║  ← Encoder CLOCK
    ║  GPIO 27 ENC DAT  [13] [14]  GND              ║  ← Encoder DATA
    ║  GPIO 22 CLK_EN   [15] [16]  GPIO 23 DAT_EN   ║  ← Encoder enable pins
    ║  3V3              [17] [18]  GPIO 24          ║
    ║  GPIO 10          [19] [20]  GND              ║
    ║  GPIO 9  GPS RX   [21] [22]  GPIO 25          ║  ← GPS UART3 RX
    ║  GPIO 11          [23] [24]  GPIO 8  GPS TX   ║  ← GPS UART3 TX
    ║  GND              [25] [26]  GPIO 7           ║
    ║  GPIO 0           [27] [28]  GPIO 1           ║
    ║  GPIO 5           [29] [30]  GND              ║
    ║  GPIO 6           [31] [32]  GPIO 12 SERVO    ║  ← Servo freno PWM
    ║  GPIO 13          [33] [34]  GND              ║
    ║  GPIO 19          [35] [36]  GPIO 16          ║
    ║  GPIO 26          [37] [38]  GPIO 20          ║
    ║  GND              [39] [40]  GPIO 21          ║
    ╚═══════════════════════════════════════════════╝
```

## Cablaggi Dettagliati

### 1. VESC (Sterzo) — UART0

```
Raspi GPIO 14 (Pin 8)  TX ──→ VESC RX
Raspi GPIO 15 (Pin 10) RX ←── VESC TX
Raspi GND     (Pin 6)     ─── VESC GND
```

### 2. Encoder Briter 5V 12-bit SSI — via 2x Moduli TTL-RS485

L'encoder usa segnali differenziali RS-485. Servono 2 moduli:
- Modulo #1 per CLOCK (Raspi trasmette → Encoder riceve)
- Modulo #2 per DATA (Encoder trasmette → Raspi riceve)

**Modulo RS-485 #1 — CLOCK (trasmissione)**

```
Raspi GPIO 17 (Pin 11) ──→ DI
Raspi 3.3V    (Pin 1)  ──→ DE (HIGH = trasmetti)
Raspi 3.3V    (Pin 1)  ──→ RE (HIGH = disabilita ricezione)
Raspi 3.3V    (Pin 1)  ──→ VCC
Raspi GND     (Pin 6)  ──→ GND
                            A  ──→ Encoder CLK+
                            B  ──→ Encoder CLK-
```

**Modulo RS-485 #2 — DATA (ricezione)**

```
Raspi GPIO 27 (Pin 13) ←── RO
GND                     ──→ DE (LOW = disabilita trasmissione)
GND                     ──→ RE (LOW = ricevi)
Raspi 3.3V    (Pin 1)  ──→ VCC
Raspi GND     (Pin 6)  ──→ GND
                            A  ←── Encoder DATA+
                            B  ←── Encoder DATA-
```

**Encoder Briter**

```
VCC (rosso)  ←── Raspi Pin 2 (5V)
GND (nero)   ─── GND comune
CLK+         ─── RS-485 #1 pin A
CLK-         ─── RS-485 #1 pin B
DATA+        ─── RS-485 #2 pin A
DATA-        ─── RS-485 #2 pin B
```

### 3. GPS NEO-M10 — UART3

```
Raspi GPIO 8  (Pin 24) TX ──→ GPS RX
Raspi GPIO 9  (Pin 21) RX ←── GPS TX
Raspi 3.3V    (Pin 1)     ──→ GPS VCC
Raspi GND     (Pin 6)     ─── GPS GND
```

### 4. MPU6050 IMU — I2C1

```
Raspi GPIO 2  (Pin 3)  SDA ↔── MPU6050 SDA
Raspi GPIO 3  (Pin 5)  SCL ──→ MPU6050 SCL
Raspi 3.3V    (Pin 1)      ──→ MPU6050 VCC
Raspi GND     (Pin 6)      ─── MPU6050 GND
                                MPU6050 AD0 ─── GND (indirizzo 0x68)
```

### 5. Servo Freno — PWM Diretto + Alimentazione 6V Esterna

```
Raspi GPIO 12 (Pin 32) PWM ──→ Servo segnale (filo bianco/arancione)
Raspi GND     (Pin 14)     ─── Servo GND + Alimentatore GND
Alimentatore 6V esterno    ──→ Servo +V (filo rosso)
```

> **IMPORTANTE:** Il GND deve essere comune tra Raspi, servo e alimentatore 6V.

## Schema Alimentazione

```
┌─────────────┐
│  Raspi 5V   │──→ Encoder Briter VCC (5V)
│  (Pin 2)    │
├─────────────┤
│  Raspi 3.3V │──→ GPS NEO-M10 VCC
│  (Pin 1)    │──→ MPU6050 VCC
│             │──→ RS-485 #1 VCC
│             │──→ RS-485 #2 VCC
├─────────────┤
│  Alim. 6V   │──→ Servo freno +V (rosso)
│  esterno     │
├─────────────┤
│  GND comune │─── Raspi GND
│             │─── VESC GND
│             │─── Encoder GND
│             │─── GPS GND
│             │─── MPU6050 GND
│             │─── RS-485 #1 GND
│             │─── RS-485 #2 GND
│             │─── Servo GND
│             │─── Alimentatore 6V GND
└─────────────┘
```

## Configurazione Raspi

Aggiungere a `/boot/firmware/config.txt`:

```
dtoverlay=uart3
dtparam=i2c_arm=on
```

Disabilitare console seriale (per UART0 → VESC):

```bash
sudo raspi-config
# → Interface Options → Serial Port
# → Login shell over serial: NO
# → Serial port hardware: YES
```

## Dipendenze Software

```bash
sudo apt install python3-lgpio python3-smbus
pip install pyserial
```

## Script Python

| Script | Percorso | Funzione |
|---|---|---|
| Sterzo | `pi/steering/steering_vesc_encoder.py` | Encoder SSI → VESC UART duty |
| Freno | `pi/braking/brake_servo.py` | Servo PWM profilo frenata |
| GPS | `pi/sensors/gps_neo_m10.py` | NMEA parser lat/lon/vel |
| IMU | `pi/sensors/imu_mpu6050.py` | Accelerometro + giroscopio feedback frenata |
