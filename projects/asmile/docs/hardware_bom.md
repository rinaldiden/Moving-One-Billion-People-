# Bill of Materials — Asmile

Complete hardware list for the autonomous bicycle guidance system.

## Computation

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 1 | Single Board Computer | Raspberry Pi 5 Model B | 1 | 8GB RAM recommended |
| 2 | Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | 1 | Global shutter, 2560x800 stereo (native) |

## Steering

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 3 | Motor controller | VESC (FOC) | 1 | FOC firmware configured |
| 4 | Steering motor | Flipsky 6354 BLDC | 1 | Connected to VESC (3 phases U/V/W) |
| 5 | Absolute encoder | Briter 5V 12-bit SSI | 1 | Steering position, RS-485 differential output |
| 6 | RS-485 module | TTL to RS-485 (MAX485) | 2 | #1 for CLOCK, #2 for DATA |
| 6b | Bevel gear | Ratio 1:5 (⚠️ TO BE VERIFIED) | 1 | Coupling Flipsky 6354 motor ↔ steering axis |

## Braking

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 7 | Brake servo | PDI-6221MG (20kg, 180°) | 1 | 6V, PWM 500-2500µs |
| 8 | Mechanical brake | Hydraulic disc brake | 1 | Servo connected to pump lever |

## Sensors

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 9 | GPS | NEO-M10 | 1 | UART, 9600 baud default |
| 10 | IMU | MPU6050 | 1 | I2C, accelerometer + gyroscope, braking feedback |

## Power

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 11 | Battery | 13S Li-ion 48V | 1 | ~54.6V full charge, powers everything |
| 12 | 5V step-down | Pololu D24V55F5 | 1 | 48V→5V, for Raspberry Pi + peripherals |
| 13 | 6V step-down | Pololu D24V55F6 | 1 | 48V→6V, for brake servo PDI-6221MG |

## Safe shutdown + hold-up

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 14 | Ideal diode controller module | LM74700 module (3-pin VIN/VOUT/GND) | 2 | #1 charge path Pololu→Pi, #2 discharge path Supercap→Pi (parallel to pre-charge R) |
| 15 | Supercapacitor | 10F 5.5V (radial) | 1 | Hold-up storage, ~13s of Pi shutdown time |
| 16 | Pre-charge resistor | 6.8Ω 5W (or 10Ω 5W) | 1 | In series between Pi 5V and Supercap+, limits inrush to 735mA peak |
| 17 | Drain resistor | 22Ω 5W (TBD: smaller for faster discharge) | 1 | Supercap discharge path, ~6 min to discharge after shutdown |
| 18 | Drain MOSFET | IRFZ44N (TBD: upgrade to IRL540N logic-level) | 1 | N-channel, TO-220, controlled by 2N2222 inverter |
| 19 | Bias transistor | 2N2222 (TO-92) | 1 | Sense Pololu+, inverts for drain MOSFET gate |
| 20 | Pull-up + bleed resistors | 10kΩ 1/4W | 3 | Drain gate pull-up, 2N2222 base, Pololu bleed |
| 21 | Buzzer | Active or passive piezo | 1 | Safe shutdown audio (replace KY-006: too quiet for direct-drive) |
| 22 | Buzzer driver | 2N2222 (TO-92) + 1kΩ 1/4W | 1 | Amplifica corrente da GPIO 4 al buzzer |
| 23 | Level shifter (shared w/ encoder) | Bidirectional 4-channel (BSS138) | 1 | Channel 3 used for power sense (GPIO 26 ← HV3 ← Pololu VOUT) |

## Planned / Future

| # | Component | Notes |
|---|---|---|
| 14 | Ultrasonic sensors | Side/rear obstacle detection |
| 15 | Wheel encoder | Speed/odometry |
| 16 | Kill switch / E-stop | Emergency switch on 48V line |
| 17 | Second Raspberry Pi 5 | Redundancy with failover |
| 18 | Inductive proximity sensor | LJ8A3-2-Z/BX M8, NPN NO, 2mm range, 12-24VDC — **da valutare** ([Link Amazon](https://amzn.eu/d/0dW2BKb2)). Candidato wheel speed/odometry (rileva metallo: bulloni disco/raggi) <!-- nota 2026-08-29: link Amazon da valutare --> |

## Raspi 5 Interfaces Used

```
UART0 (/dev/ttyAMA0)  → VESC (steering)
UART3 (/dev/ttyAMA3)  → GPS NEO-M10
I2C1  (bus 1, 0x68)   → MPU6050 IMU
PWM0  (GPIO 12)       → Brake servo PDI-6221MG
GPIO 4  (Pin 7)        → Buzzer safe_shutdown (via 2N2222 driver)
GPIO 26 (Pin 37)       → Power sense (via level shifter ch3, see safe_shutdown.py)
SPI1  (GPIO 19/21)     → Briter SSI encoder (via 2x RS-485)
CSI   (camera port)    → Arducam Camarray HAT
```

## Related Documents

| Document | Path |
|---|---|
| Raspi pin wiring diagram | [wiring_raspi5.md](wiring_raspi5.md) |
| 48V power wiring diagram | [power_48v.md](power_48v.md) |
| VESC FOC config | [../config/vesc_foc_ok.xml](../config/vesc_foc_ok.xml) |
| OV9281 camera config | [../config/ov9281_mono_pisp.json](../config/ov9281_mono_pisp.json) |
