# Bill of Materials — Asmile

Complete hardware list for the autonomous bicycle guidance system.

## Computation

| # | Component | Model | Qty | Notes |
|---|---|---|---|---|
| 1 | Single Board Computer | Raspberry Pi 5 Model B | 1 | 8GB RAM recommended |
| 2 | Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | 1 | Global shutter, 1280x400 stereo |

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

## Planned / Future

| # | Component | Notes |
|---|---|---|
| 14 | Ultrasonic sensors | Side/rear obstacle detection |
| 15 | Wheel encoder | Speed/odometry |
| 16 | Kill switch / E-stop | Emergency switch on 48V line |
| 17 | Second Raspberry Pi 5 | Redundancy with failover |

## Raspi 5 Interfaces Used

```
UART0 (/dev/ttyAMA0)  → VESC (steering)
UART3 (/dev/ttyAMA3)  → GPS NEO-M10
I2C1  (bus 1, 0x68)   → MPU6050 IMU
PWM0  (GPIO 12)       → Brake servo PDI-6221MG
GPIO  (bit-bang SSI)   → Briter encoder (via RS-485)
CSI   (camera port)    → Arducam Camarray HAT
```

## Related Documents

| Document | Path |
|---|---|
| Raspi pin wiring diagram | [wiring_raspi5.md](wiring_raspi5.md) |
| 48V power wiring diagram | [power_48v.md](power_48v.md) |
| VESC FOC config | [../config/vesc_foc_ok.xml](../config/vesc_foc_ok.xml) |
| OV9281 camera config | [../config/ov9281_mono_pisp.json](../config/ov9281_mono_pisp.json) |
