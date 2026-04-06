# 🚲 Asmile — Autonomous Bicycle Guidance

An autonomous guidance system for bicycles designed to enable people with disabilities to move independently.

## Hardware

| Component | Model | Status |
|-----------|-------|--------|
| Computer | Raspberry Pi 5 Model B | ✅ Operational |
| Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | ✅ Streaming OK |
| Steering motor | Flipsky 6354 BLDC via VESC (FOC) + Briter SSI 12-bit encoder | ✅ Mounted |
| Bevel gear | Ratio 1:5 (⚠️ TO BE VERIFIED) | ✅ Mounted |
| Brake | PDI-6221MG servo on hydraulic disc brake pump | ✅ Mounted + remote control |
| IMU | MPU6050 — I2C1 (0x68) | ⏳ Needs reboot for I2C overlay |
| GPS | NEO-M10 — UART3 (/dev/ttyAMA3, 9600 baud) | ⏳ Needs reboot for UART3 overlay |
| Steering encoder | Briter SSI 12-bit — SPI1 | ⏳ Needs reboot for SPI1 overlay |

## Power

Single 48V battery (13S Li-ion) powers everything:
- **Pololu D24V55F5** → 5V for Raspberry Pi + peripherals
- **Pololu D24V55F6** → 6V for brake servo
- **VESC direct** → 48V for steering motor

## Raspi "asmile2" — current state (2026-04-06)

| What | Status | Notes |
|------|--------|-------|
| SSH | ✅ | user `asmile2`, DHCP on WiFi EOLO_378899 |
| Servo freno | ✅ running | GPIO 12, 330Hz, CENTER=0°, MAX=85° |
| servofreno_server.py | ✅ running | Flask on :5000, hold-to-brake button |
| Training data logger | ✅ running | 10Hz CSV in `pi/logging/training_data/` |
| Brake event logger | ✅ running | CSV in `pi/logging/servofreno/` |
| IMU / GPS / Encoder / VESC | ⏳ need reboot | config.txt overlays ready, boot activates them |
| safe_shutdown service | ✅ safe | arms only after seeing GPIO HIGH (no spurious shutdown) |

## Logging

Continuous data collection for autonomous driving training:

```
pi/logging/
  servofreno/           servofreno_YYYYMMDD.csv  — brake events
  training_data/        training_YYYYMMDD.csv    — 10Hz IMU+GPS+encoder+events
```

**Training CSV columns** (10Hz, continuous):
`timestamp, gps_lat, gps_lon, gps_speed_ms, gps_heading, imu_accel_x/y/z, imu_gyro_x/y/z, encoder_pos, evento`

The `evento` field = `FRENATA` during active braking, empty otherwise. Used to correlate stereo camera frames with driver actions.

## Roadmap

1. ✅ Stereo cam streaming (RTSP 1280x400@15fps)
2. ✅ Brake servo remote control (Flask + progressive braking loop)
3. ✅ Training data logging pipeline (10Hz CSV)
4. 🔄 Stereo camera calibration
5. ⬜ Reboot to activate IMU + GPS + Encoder + VESC overlays
6. ⬜ Real-time depth map
7. ⬜ Manual driving with data recording (cam + sensors + commands)
8. ⬜ Training driving model
9. ⬜ Autonomous driving (single Pi)
10. ⬜ Second redundant Pi with failover

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
Resolution: 1280x400 @ 15fps (stereo side-by-side)
CPU: ~28%
```

## Development

Development on the Pi is done via SSH through Claude Code. The 27W power supply is required to avoid freezes under load.

---

## Support Asmile

💛 [**Donate on GoFundMe — Help me make Arianna smile**](https://www.gofundme.com/f/aiutami-a-far-sorridere-arianna-costruiamo-insieme-asmile)

---

*Asmile was born for Arianna. One step at a time, we'll get there.* 🚲
