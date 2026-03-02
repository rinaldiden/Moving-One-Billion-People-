# Complete Wiring Diagram — Raspberry Pi 5

Full setup for the Asmile project: steering, braking, GPS, IMU.

## Devices

| Device | Protocol | Port |
|---|---|---|
| VESC (steering) | UART0 | /dev/ttyAMA0 |
| Briter 5V 12-bit SSI Encoder | GPIO bit-bang (via 2x RS-485) | GPIO 17/27 |
| GPS NEO-M10 | UART3 | /dev/ttyAMA3 |
| MPU6050 IMU | I2C1 | 0x68 |
| Brake servo | Hardware PWM0 | GPIO 12 |

## Complete Pin Map

| GPIO | Header Pin | Device | Function | Direction |
|---|---|---|---|---|
| GPIO 2 | Pin 3 | MPU6050 | I2C1 SDA | I/O |
| GPIO 3 | Pin 5 | MPU6050 | I2C1 SCL | OUT |
| GPIO 8 | Pin 24 | GPS NEO-M10 | UART3 TX | OUT |
| GPIO 9 | Pin 21 | GPS NEO-M10 | UART3 RX | IN |
| GPIO 12 | Pin 32 | Brake servo | PWM0 signal | OUT |
| GPIO 14 | Pin 8 | VESC | UART0 TX | OUT |
| GPIO 15 | Pin 10 | VESC | UART0 RX | IN |
| GPIO 17 | Pin 11 | SSI Encoder | CLOCK (via RS-485 #1) | OUT |
| GPIO 22 | Pin 15 | SSI Encoder | CLOCK_ENABLE (HIGH) | OUT |
| GPIO 23 | Pin 16 | SSI Encoder | DATA_ENABLE (LOW) | OUT |
| GPIO 27 | Pin 13 | SSI Encoder | DATA (via RS-485 #2) | IN |

## 40-Pin Header — Final View

```
         Raspberry Pi 5 — GPIO Header
    ╔═══════════════════════════════════════════════╗
    ║  3V3              [ 1] [ 2]  5V               ║
    ║  GPIO 2  I2C SDA  [ 3] [ 4]  5V               ║  ← MPU6050 SDA + Encoder VCC
    ║  GPIO 3  I2C SCL  [ 5] [ 6]  GND              ║  ← MPU6050 SCL + Common GND
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
    ║  GPIO 6           [31] [32]  GPIO 12 SERVO    ║  ← Brake servo PWM
    ║  GPIO 13          [33] [34]  GND              ║
    ║  GPIO 19          [35] [36]  GPIO 16          ║
    ║  GPIO 26          [37] [38]  GPIO 20          ║
    ║  GND              [39] [40]  GPIO 21          ║
    ╚═══════════════════════════════════════════════╝
```

## Detailed Wiring Per Device

### 1. VESC (Steering) — UART0

```
Raspi GPIO 14 (Pin 8)  TX ──→ VESC RX
Raspi GPIO 15 (Pin 10) RX ←── VESC TX
Raspi GND     (Pin 6)     ─── VESC GND
```

### 2. Briter 5V 12-bit SSI Encoder — via 2x TTL-RS485 Modules

The encoder uses RS-485 differential signals. Two modules are needed:
- Module #1 for CLOCK (Raspi transmits → Encoder receives)
- Module #2 for DATA (Encoder transmits → Raspi receives)

**RS-485 Module #1 — CLOCK (transmit)**

```
Raspi GPIO 17 (Pin 11) ──→ DI
Raspi 3.3V    (Pin 1)  ──→ DE (HIGH = transmit)
Raspi 3.3V    (Pin 1)  ──→ RE (HIGH = disable receive)
Raspi 3.3V    (Pin 1)  ──→ VCC
Raspi GND     (Pin 6)  ──→ GND
                            A  ──→ Encoder CLK+
                            B  ──→ Encoder CLK-
```

**RS-485 Module #2 — DATA (receive)**

```
Raspi GPIO 27 (Pin 13) ←── RO
GND                     ──→ DE (LOW = disable transmit)
GND                     ──→ RE (LOW = receive)
Raspi 3.3V    (Pin 1)  ──→ VCC
Raspi GND     (Pin 6)  ──→ GND
                            A  ←── Encoder DATA+
                            B  ←── Encoder DATA-
```

**Briter Encoder**

```
VCC (red)    ←── Raspi Pin 2 (5V)
GND (black)  ─── Common GND
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
                                MPU6050 AD0 ─── GND (address 0x68)
```

### 5. Brake Servo — Direct PWM + External 6V Power

```
Raspi GPIO 12 (Pin 32) PWM ──→ Servo signal wire (white/orange)
Raspi GND     (Pin 14)     ─── Servo GND + Power supply GND
External 6V power supply   ──→ Servo +V (red wire)
```

> **IMPORTANT:** GND must be common between Raspi, servo, and 6V power supply.

## Power Wiring

```
┌─────────────┐
│  Raspi 5V   │──→ Briter Encoder VCC (5V)
│  (Pin 2)    │
├─────────────┤
│  Raspi 3.3V │──→ GPS NEO-M10 VCC
│  (Pin 1)    │──→ MPU6050 VCC
│             │──→ RS-485 #1 VCC
│             │──→ RS-485 #2 VCC
├─────────────┤
│  Ext. 6V    │──→ Brake servo +V (red)
│  supply     │
├─────────────┤
│  Common GND │─── Raspi GND
│             │─── VESC GND
│             │─── Encoder GND
│             │─── GPS GND
│             │─── MPU6050 GND
│             │─── RS-485 #1 GND
│             │─── RS-485 #2 GND
│             │─── Servo GND
│             │─── 6V supply GND
└─────────────┘
```

## Raspi Configuration

Add to `/boot/firmware/config.txt`:

```
dtoverlay=uart3
dtparam=i2c_arm=on
```

Disable serial console (for UART0 → VESC):

```bash
sudo raspi-config
# → Interface Options → Serial Port
# → Login shell over serial: NO
# → Serial port hardware: YES
```

## Software Dependencies

```bash
sudo apt install python3-lgpio python3-smbus
pip install pyserial
```

## Python Scripts

| Script | Path | Function |
|---|---|---|
| Steering | `pi/steering/steering_vesc_encoder.py` | SSI Encoder → VESC UART duty |
| Braking | `pi/braking/brake_servo.py` | Servo PWM realistic braking profile |
| GPS | `pi/sensors/gps_neo_m10.py` | NMEA parser lat/lon/speed |
| IMU | `pi/sensors/imu_mpu6050.py` | Accelerometer + gyroscope braking feedback |
