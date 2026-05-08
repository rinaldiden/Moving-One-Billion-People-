# 🚲 Asmile — Autonomous Bicycle Guidance

An autonomous guidance system for bicycles designed to enable people with disabilities to move independently.

## Hardware

| Component | Model |
|-----------|-------|
| Computer | Raspberry Pi 5 Model B |
| Stereo Camera | Arducam Camarray HAT (2x OV9281 Global Shutter mono, baseline 200mm) |
| Steering motor | Flipsky 6354 BLDC via VESC (FOC) |
| Steering encoder | Briter SSI 12-bit absolute (SPI1, via RS-485) |
| Bevel gear | Ratio 1:5 |
| Brake | PDI-6221MG servo on hydraulic disc brake pump |
| IMU | MPU6050 — I2C1 |
| GPS | NEO-M10 — UART3 (38400 baud) |
| Safe shutdown | Supercapacitor 10F + Schottky diode + GPIO power sense |
| Master switch | GPIO toggle ON/OFF (controls brake + logging + follow-me) |

## Power

Single 48V battery (13S Li-ion) powers everything:
- **Pololu D24V55F5** → 5V for Raspberry Pi + peripherals
- **Pololu D24V55F6** → 6V for brake servo
- **VESC direct** → 48V for steering motor

## Roadmap

1. ✅ Stereo cam streaming (RTSP 2560x800@15fps)
2. ✅ Brake servo remote control (Flask :5000 + master switch ON/OFF)
3. ✅ IMU + GPS + Encoder + VESC — all connected and working
4. ✅ Training data logging (10Hz CSV + stereo H264 video, synchronized)
5. ✅ Stereo camera calibration (RMS 1.27, baseline 199.5mm)
6. ✅ Depth map from stereo (StereoSGBM, 7.8% error — improving)
7. ✅ Shadow Mode — first rides recorded, driving patterns extracted
8. ✅ Training pipeline (frame extractor, behavioral cloning, shadow analyzer)
9. ✅ Follow-me module (cone detection, safety envelope, state machine — testing)
10. ✅ Flash script for new bikes (`flash_asmile.sh`)
11. 🔄 Stereo calibration improvement (target < 2% depth error at 2560x800)
12. 🔄 Follow-me hardware test (buzzer, --dry-run, cone tuning)
13. ⬜ 50h shadow mode data collection (autoresearch + sim-to-real trigger)
14. ⬜ Behavioral cloning model training (Karpathy autoresearch overnight)
15. ⬜ Autonomous driving (single Pi)
16. ⬜ Second Asmile bike for parallel data collection
17. ⬜ Sim-to-real (CARLA/Unity simulator from real ride data)

## Structure

```
asmile/
├── firmware/              # Original Arduino sketches (archive/reference)
│   ├── steering/          # Steering control via VESC + SSI encoder
│   └── braking/           # Brake control via servo
├── pi/                    # Python code for Raspberry Pi 5
│   ├── steering/          # Steering: VESC UART + encoder SPI daemon
│   ├── braking/           # brake_servo.py + servofreno_server.py (Flask :5000)
│   ├── vision/            # Stereo camera + depth map
│   ├── sensors/           # imu_mpu6050.py + gps_neo_m10.py
│   ├── logging/           # servofreno/ + training_data/ (CSV)
│   └── power/             # safe_shutdown.py (supercap graceful shutdown)
├── training/              # Autonomous driving model training
├── docs/                  # Documentation, diagrams, photos
└── config/                # setup_new_raspi.sh, systemd services, boot_config.txt
```

## Camera Streaming

The stereo camera is operational with pipeline:

```
libcamera → GStreamer → H.264 (500kbps) → MediaMTX RTSP
Stream: rtsp://<PI_IP>:8554/stream
Resolution: 2560x800 @ 15fps (stereo side-by-side)
CPU: ~28%
```

## Development

Development on the Pi is done via SSH through Claude Code. The 27W power supply is required to avoid freezes under load.

---

## Support Asmile

Asmile is an open-source project. Your support helps purchase components, sensors, and keep development going.

[![Support me on Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20me-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/danielerinaldi)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-003087?logo=paypal&logoColor=white)](https://paypal.me/Rinaldiden1991)

💛 [**Donate on GoFundMe — Help me make Arianna smile**](https://www.gofundme.com/f/aiutami-a-far-sorridere-arianna-costruiamo-insieme-asmile)

---

*Asmile was born for Arianna. One step at a time, we'll get there.* 🚲
