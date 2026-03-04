# Complete Wiring Diagram — Raspberry Pi 5

Full setup for the Asmile project: steering, braking, GPS, IMU.

> **Note:** Arducam Camarray HAT is mounted on the GPIO header with stacking (pass-through) headers. All connections are made from the top of the HAT.

## Devices

| Device | Protocol | Port |
|---|---|---|
| VESC (steering) | UART0 | /dev/ttyAMA0 |
| Briter 5V 12-bit SSI Encoder | GPIO bit-bang (via 2x RS-485) | GPIO 17/27 |
| GPS NEO-M10 | UART3 | /dev/ttyAMA3 |
| MPU6050 IMU | I2C1 | 0x68 |
| Brake servo | Hardware PWM0 | GPIO 12 |
| Arducam Camarray HAT | CSI + I2C1 | Camera port |

## Complete Pin Map

| GPIO | Header Pin | Device | Function | Direction |
|---|---|---|---|---|
| GPIO 2 | Pin 3 | MPU6050 + Camarray | I2C1 SDA (shared bus) | I/O |
| GPIO 3 | Pin 5 | MPU6050 + Camarray | I2C1 SCL (shared bus) | OUT |
| GPIO 8 | Pin 24 | GPS NEO-M10 | UART3 TX | OUT |
| GPIO 9 | Pin 21 | GPS NEO-M10 | UART3 RX | IN |
| GPIO 12 | Pin 32 | Brake servo | PWM0 signal | OUT |
| GPIO 14 | Pin 8 | VESC | UART0 TX | OUT |
| GPIO 15 | Pin 10 | VESC | UART0 RX | IN |
| GPIO 17 | Pin 11 | SSI Encoder | CLOCK (via RS-485 #1) | OUT |
| GPIO 22 | Pin 15 | SSI Encoder | CLOCK_ENABLE (HIGH) | OUT |
| GPIO 23 | Pin 16 | SSI Encoder | DATA_ENABLE (LOW) | OUT |
| GPIO 27 | Pin 13 | SSI Encoder | DATA (via RS-485 #2) | IN |

## 40-Pin Header — Final View (from top of Camarray HAT)

```
         Raspberry Pi 5 — GPIO Header
         (accessed from top of Camarray HAT stacking header)
    ╔═══════════════════════════════════════════════════════════╗
    ║  3V3  RS485+GPS+IMU  [ 1] [ 2]  5V   Pololu F5 + HAT    ║
    ║  GPIO 2  I2C SDA     [ 3] [ 4]  5V   Encoder VCC        ║
    ║  GPIO 3  I2C SCL     [ 5] [ 6]  GND  HAT                ║
    ║  (free)              [ 7] [ 8]  GPIO 14 TX → VESC       ║
    ║  GND  VESC           [ 9] [10]  GPIO 15 RX ← VESC       ║
    ║  GPIO 17 ENC CLOCK   [11] [12]  (free)                   ║
    ║  GPIO 27 ENC DATA    [13] [14]  GND                      ║
    ║  GPIO 22 CLK_EN HIGH [15] [16]  GPIO 23 DAT_EN LOW       ║
    ║  3V3                 [17] [18]  (free)                    ║
    ║  (free)              [19] [20]  GND  GPS                  ║
    ║  GPIO 9  GPS RX      [21] [22]  (free)                   ║
    ║  (free)              [23] [24]  GPIO 8  GPS TX            ║
    ║  GND  MPU6050        [25] [26]  (free)                   ║
    ║  (free)              [27] [28]  (free)                    ║
    ║  (free)              [29] [30]  GND  RS485+Encoder        ║
    ║  (free)              [31] [32]  GPIO 12 SERVO PWM         ║
    ║  (free)              [33] [34]  GND  Servo                ║
    ║  (free)              [35] [36]  (free)                    ║
    ║  (free)              [37] [38]  (free)                    ║
    ║  GND                 [39] [40]  (free)                    ║
    ╚═══════════════════════════════════════════════════════════╝
```

## Detailed Wiring Per Device

### 1. Power — 48V Battery → Pololu → Raspi

```
Pololu D24V55F5:
  VIN  ← Battery 48V+
  GND  ← Battery 48V−
  VOUT (5V) ──→ Raspi Pin 2 (5V) via HAT stacking header
  GND       ──→ Raspi GND

  EN, PG, VRP → leave unconnected
```

> Raspi and Camarray HAT are powered together from the same 5V rail.

### 2. VESC (Steering) — UART0

```
Raspi GPIO 14 (Pin 8)  TX ──→ VESC RX
Raspi GPIO 15 (Pin 10) RX ←── VESC TX
Raspi GND     (Pin 9)     ─── VESC GND
```

> VESC is powered directly from 48V battery. Do NOT connect VESC 5V pin to Raspi.

### 3. Briter 5V 12-bit SSI Encoder — via 2x TTL-RS485 Modules

The encoder uses RS-485 differential signals. Two modules are needed:
- Module #1 for CLOCK (Raspi transmits → Encoder receives)
- Module #2 for DATA (Encoder transmits → Raspi receives)

**Briter Encoder Wire Colors (⚠️ TO BE VERIFIED when encoder arrives):**

| Wire Color | Signal |
|---|---|
| **Red** | VCC (5V) |
| **Black** | GND |
| **Green** | CLK+ |
| **Brown** | CLK- |
| **White** | DATA+ |
| **Gray** | DATA- |

**RS-485 Module #1 — CLOCK (transmit)**

```
Raspi side (TTL):              Encoder side (screw terminal):
  VCC ← Raspi Pin 17 (3.3V)     A ──→ Green wire  (CLK+)
  DI  ← Raspi Pin 11 (GPIO 17)  B ──→ Brown wire  (CLK-)
  DE  ← Raspi Pin 17 (3.3V)
  RE  ← Raspi Pin 17 (3.3V)
  GND ← Raspi Pin 30 (GND)
```

**RS-485 Module #2 — DATA (receive)**

```
Raspi side (TTL):              Encoder side (screw terminal):
  VCC ← Raspi Pin 17 (3.3V)     A ←── White wire  (DATA+)
  RO  ──→ Raspi Pin 13 (GPIO 27) B ←── Gray wire   (DATA-)
  DE  ← GND (Pin 30)
  RE  ← GND (Pin 30)
  GND ← Raspi Pin 30 (GND)
```

**Briter Encoder Power**

```
Red wire   (VCC) ←── Raspi Pin 4 (5V)
Black wire (GND) ─── Raspi Pin 30 (GND)
```

> Both RS-485 modules powered at 3.3V from Raspi. This ensures RO output is 3.3V safe for Pi GPIO.

### 4. GPS NEO-M10 — UART3

```
Raspi GPIO 8  (Pin 24) TX ──→ GPS RX
Raspi GPIO 9  (Pin 21) RX ←── GPS TX
Raspi 3.3V    (Pin 1)     ──→ GPS VCC
Raspi GND     (Pin 20)    ─── GPS GND
```

### 5. MPU6050 IMU — I2C1 (shared bus with Camarray HAT)

```
Raspi GPIO 2  (Pin 3)  SDA ↔── MPU6050 SDA
Raspi GPIO 3  (Pin 5)  SCL ──→ MPU6050 SCL
Raspi 3.3V    (Pin 1)      ──→ MPU6050 VCC
Raspi GND     (Pin 25)     ─── MPU6050 GND
                                MPU6050 AD0 ─── GND (address 0x68)
```

> I2C1 is shared between Camarray HAT and MPU6050 — different addresses, no conflict.

### 6. Brake Servo PDI-6221MG — PWM + External 6V Power

```
Raspi GPIO 12 (Pin 32) PWM ──→ Servo signal wire (white/orange)
Raspi GND     (Pin 34)     ─── Servo GND + Pololu F6 GND

Pololu D24V55F6:
  VIN  ← Battery 48V+
  GND  ← Battery 48V−
  VOUT (6V) ──→ Servo +V (red wire)
  GND       ──→ Servo GND

  EN, PG, VRP → leave unconnected
```

> **IMPORTANT:** GND must be common between Raspi, servo, and Pololu F6.

## Power Distribution

```
48V BATTERY (13S Li-ion)
    │
    ├──→ Pololu D24V55F5 ──→ 5V ──→ Raspi Pin 2 (powers Raspi + HAT)
    │                                  ├── Pin 4 (5V) → Encoder Briter VCC
    │                                  ├── Pin 1 (3.3V) → GPS + MPU6050 + RS-485 x2
    │                                  └── Pin 17 (3.3V) → RS-485 VCC + encoder enables
    │
    ├──→ Pololu D24V55F6 ──→ 6V ──→ Servo PDI-6221MG
    │
    └──→ VESC (direct 48V) ──→ Flipsky 6354 BLDC steering motor
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
| Vision | `pi/vision/rtsp_stream.py` | Stereo cam RTSP streaming |
