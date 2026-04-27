# Complete Wiring Diagram — Raspberry Pi 5

Full setup for the Asmile project: steering, braking, GPS, IMU.

> **Note:** Arducam Camarray HAT is mounted on the GPIO header with stacking (pass-through) headers. All connections are made from the top of the HAT.

## Devices

| Device | Protocol | Port |
|---|---|---|
| VESC (steering) | UART0 | /dev/ttyAMA0 |
| Briter 5V 12-bit SSI Encoder | SPI1 (via 2x RS-485) | /dev/spidev1.0 |
| GPS NEO-M10 | UART3 | /dev/ttyAMA3 |
| MPU6050 IMU | I2C1 | 0x68 |
| Brake servo | Hardware PWM0 | GPIO 12 |
| Buzzer KY-006 (passive) | PWM via Level Shifter #2 ch4 | GPIO 5 |
| Supercap discharge MOSFET | GPIO direct (IRL540N gate) | GPIO 6 |
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
| GPIO 18 | Pin 12 | SSI Encoder | SPI1 CE0 (unused but claimed) | OUT |
| GPIO 19 | Pin 35 | SSI Encoder | SPI1 MISO ← DATA (via RS-485 #2) | IN |
| GPIO 21 | Pin 40 | SSI Encoder | SPI1 SCLK → CLOCK (via RS-485 #1) | OUT |
| GPIO 26 | Pin 37 | Power sense | Battery detect (via Level Shifter #2 ch3) | IN |
| GPIO 5 | Pin 29 | Buzzer KY-006 | PWM signal (via Level Shifter #2 ch4) | OUT |
| GPIO 6 | Pin 31 | Supercap discharge | MOSFET gate control (LOW=off, float=discharge) | OUT |

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
    ║  (free)              [11] [12]  GPIO 18 SPI1_CE0 (enc)    ║
    ║  (free)              [13] [14]  GND                      ║
    ║  (free)              [15] [16]  (free)                    ║
    ║  3V3                 [17] [18]  (free)                    ║
    ║  (free)              [19] [20]  GND  GPS                  ║
    ║  GPIO 9  GPS RX      [21] [22]  (free)                   ║
    ║  (free)              [23] [24]  GPIO 8  GPS TX            ║
    ║  GND  MPU6050        [25] [26]  (free)                   ║
    ║  (free)              [27] [28]  (free)                    ║
    ║  GPIO 5  BUZZER PWM   [29] [30]  GND  RS485+Encoder        ║
    ║  GPIO 6  MOSFET GATE [31] [32]  GPIO 12 SERVO PWM         ║
    ║  (free)              [33] [34]  GND  Servo                ║
    ║  GPIO 19 SPI1_MISO   [35] [36]  (free)                    ║
    ║  (free)              [37] [38]  GPIO 20 (SPI1_MOSI free)  ║
    ║  GND                 [39] [40]  GPIO 21 SPI1_SCLK (enc)   ║
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

**Briter BRT38 Encoder Wire Colors (VERIFIED on working Arduino setup + Raspi):**

| Wire Color | Signal | Connect to |
|---|---|---|
| **Red** | VCC (5V) | 5V rail |
| **Black** | GND | common GND |
| **Green** | CLK A+ | RS-485 #1 terminal **A** |
| **Brown** | CLK B- | RS-485 #1 terminal **B** |
| **White** | DATA A+ | RS-485 #2 terminal **A** |
| **Gray** | DATA B- | RS-485 #2 terminal **B** |
| **Yellow** | ZR (zero reference) | LEAVE UNCONNECTED |
| **Orange** | Config | LEAVE UNCONNECTED (used only for reset) |

> **Yellow and Orange wires MUST be insulated/unconnected during normal operation.**
> Full differential wiring (A+B on both modules) for noise immunity.

**Level Shifter #2 — 3.3V ↔ 5V (between Pi GPIO and RS-485 modules)**

```
Level Shifter (bidirectional):
  LV  ← Raspi 3.3V (Pin 17)
  HV  ← Raspi 5V (Pin 4)
  GND ← Raspi GND (Pin 30)

  LV1 ← GPIO 21 (Pin 40) SPI1_SCLK →  HV1 → DI of RS-485 #1
  LV2 ← GPIO 19 (Pin 35) SPI1_MISO ←  HV2 ← RO of RS-485 #2
  LV3 ← GPIO 26 (Pin 37) power sense ← HV3 ← jumper to HV (same 5V)
  LV4 ← GPIO 5  (Pin 29) buzzer PWM  →  HV4 → Buzzer KY-006 signal (S)
```

> **Wiring note:** HV and HV3 are jumpered together on the board (same 5V from
> Pololu F5 VOUT, before the Schottky diode). GND pins jumpered together, one
> wire from either GND pad to the common GND terminal block.
>
> When battery is cut: Pololu VOUT drops → shifter loses power → LV3 goes LOW
> → GPIO 26 reads LOW → safe_shutdown triggers. Raspi stays alive via supercap.
>
> Channel 3 replaces the 2x 10kΩ resistor divider for power-loss detection.

**RS-485 Module #1 — CLOCK (transmit to encoder)**

```
TTL side:                      Encoder side (screw terminal):
  VCC ← 5V (Pin 4)              A ──→ Green wire  (CLK A+)
  DI  ← HV1 of level shifter    B ──→ Brown wire  (CLK B-)
  DE  ← 5V (always TX enabled)
  RE  ← 5V (RX disabled)
  GND ← GND (Pin 30)
```

**RS-485 Module #2 — DATA (receive from encoder)**

```
TTL side:                      Encoder side (screw terminal):
  VCC ← 5V (Pin 4)              A ←── White wire  (DATA A+)
  RO  ──→ HV2 of level shifter  B ←── Gray wire   (DATA B-)
  DE  ← GND (TX disabled)
  RE  ← GND (always RX enabled)
  GND ← GND (Pin 30)
```

**Briter Encoder Power**

```
Red wire    (VCC) ←── Raspi Pin 4 (5V)
Black wire  (GND) ─── Raspi Pin 30 (GND)
```

> RS-485 modules powered at 5V. Level shifter #2 converts between Pi 3.3V SPI1 and 5V RS-485 TTL signals.
> GPIO 22 and GPIO 23 are no longer used (DE/RE pins now hardwired to 5V/GND).

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

### 6. Brake Servo Miuzei M S69 (45 kg.cm) — PWM + Level Shifter + External 6V Power

**Level Shifter #1 — 3.3V ↔ 6V (between Pi GPIO and servo signal)**

```
Level Shifter (bidirectional):
  LV  ← Raspi 3.3V (Pin 17)
  HV  ← Pololu F6 6V
  GND ← common (Raspi + Pololu F6)

  LV1 ← GPIO 12 (Pin 32) PWM0  →  HV1 → Servo signal wire (white/orange)
```

```
Raspi GND     (Pin 34)     ─── Servo GND + Pololu F6 GND

Pololu D24V55F6:
  VIN  ← Battery 48V+
  GND  ← Battery 48V−
  VOUT (6V) ──→ Servo +V (red wire) + Level Shifter HV
  GND       ──→ Servo GND

  EN, PG, VRP → leave unconnected
```

> **IMPORTANT:** GND must be common between Raspi, servo, level shifter, and Pololu F6.

### 7. Buzzer KY-006 (passive) — via Level Shifter #2 ch4

```
Raspi GPIO 5  (Pin 29) → LV4 of Level Shifter #2
                          HV4 → Buzzer S (signal)
Raspi GND     (Pin 30)   ─── Buzzer - (GND)
```

> Buzzer needs 5V signal to produce audible sound. 3.3V GPIO is too weak.
> Level Shifter #2 converts 3.3V PWM → 5V PWM on channel 4.
> Middle pin (+/VCC) of KY-006 is NOT connected on the PCB — ignore it.

### 8. Supercap 2.2F Auto-Discharge — IRL540N MOSFET

```
Supercap + ──→ Resistenza 22Ω ──→ Drain IRL540N
                                   Source ──→ GND
                                   Gate ──┬── pull-up 10kΩ ──→ Supercap +
                                          └── GPIO 6 (Pin 31)
```

> Pi ON: GPIO 6 held LOW → MOSFET off → zero drain on supercap.
> Pi OFF: GPIO floats → pull-up pulls gate HIGH from supercap → MOSFET on → discharge via 22Ω.
> Discharge time: ~48 seconds (τ = 22 × 2.2). After discharge, supercap ready for next power cycle.
> IRL540N is logic-level: 5V gate is enough to fully saturate.

### 9. INA219 Current Sensor (when available) — I2C1

```
Pololu F6 VOUT (6V) ──→ INA219 VIN+ ──→ INA219 VIN- ──→ Servo +V (red)
INA219 SDA ──→ Raspi GPIO 2 (Pin 3)   ← same I2C bus as MPU6050
INA219 SCL ──→ Raspi GPIO 3 (Pin 5)
INA219 VCC ──→ Raspi 3.3V (Pin 1)
INA219 GND ──→ GND
```

> Address 0x40 (MPU6050 is 0x68, no conflict). Measures servo current to detect:
> arrived (current drops), moving (current high), stalled (current stays high → cut PWM).

## Power Distribution

```
48V BATTERY (13S Li-ion)
    │
    ├──→ Pololu D24V55F5 ──→ 5V ──→ Raspi Pin 2 (powers Raspi + HAT)
    │                                  ├── Pin 4 (5V) → Encoder Briter VCC + RS-485 x2 VCC + Level Shifter HV
    │                                  ├── Pin 1 (3.3V) → GPS + MPU6050
    │                                  └── Pin 17 (3.3V) → Level Shifter LV
    │
    ├──→ Pololu D24V55F6 ──→ 6V ──→ Servo Miuzei M S69 (45 kg.cm)
    │
    └──→ VESC (direct 48V) ──→ Flipsky 6354 BLDC steering motor
```

## Raspi Configuration

Add to `/boot/firmware/config.txt`:

```
dtoverlay=uart3
dtparam=i2c_arm=on
dtoverlay=spi1-1cs
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
| Encoder SPI | `pi/steering/test_encoder_spi.py` | SPI1 SSI encoder test |
| Encoder C | `pi/steering/test_encoder_bitbang.c` | C bit-bang fallback (libgpiod v2) |
| Braking | `pi/braking/brake_servo.py` | Servo PWM realistic braking profile |
| GPS | `pi/sensors/gps_neo_m10.py` | NMEA parser lat/lon/speed |
| IMU | `pi/sensors/imu_mpu6050.py` | Accelerometer + gyroscope braking feedback |
| Vision | `pi/vision/rtsp_stream.py` | Stereo cam RTSP streaming |
