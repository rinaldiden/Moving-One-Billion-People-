# 🚲 Asmile — Autonomous Bicycle Guidance

An autonomous guidance system for bicycles designed to enable people with disabilities to move independently.

## Hardware

| Component | Model | Status |
|-----------|-------|--------|
| Computer | Raspberry Pi 5 Model B | ✅ Operational |
| Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | ✅ Streaming OK |
| Steering motor | Flipsky 6354 BLDC via VESC (FOC) + Briter SSI 12-bit encoder | ✅ Mounted |
| Bevel gear | Ratio 1:5 (⚠️ TO BE VERIFIED) | ✅ Mounted |
| Brake | PDI-6221MG servo on hydraulic disc brake pump | ✅ Mounted |
| IMU | MPU6050 — I2C | ⏳ To be connected |
| GPS | NEO-M10 — UART | ⏳ To be connected |
| Wheel encoder | To be connected | ⏳ |

## Power

Single 48V battery (13S Li-ion) powers everything:
- **Pololu D24V55F5** → 5V for Raspberry Pi + peripherals
- **Pololu D24V55F6** → 6V for brake servo
- **VESC direct** → 48V for steering motor

## Roadmap

1. ✅ Stereo cam streaming (RTSP 1280x400@15fps)
2. 🔄 Stereo camera calibration
3. 🔄 Brake test from Raspberry Pi
4. ⬜ Real-time depth map
5. ⬜ Connect IMU + GPS + Encoder to Pi
6. ⬜ Convert Arduino sketches → Python Pi
7. ⬜ Synchronized logging (video + sensors + commands)
8. ⬜ Manual driving with data recording
9. ⬜ Training driving model
10. ⬜ Autonomous driving (single Pi)
11. ⬜ Second redundant Pi with failover

## Structure

```
asmile/
├── firmware/              # Original Arduino sketches (archive/reference)
│   ├── steering/          # Steering control via VESC + SSI encoder
│   └── braking/           # Brake control via servo
├── pi/                    # Python code for Raspberry Pi 5
│   ├── steering/          # Steering module
│   ├── braking/           # Braking module
│   ├── vision/            # Stereo camera + depth map
│   ├── sensors/           # IMU + GPS + Encoder
│   └── logging/           # Synchronized logging
├── training/              # Autonomous driving model training
├── docs/                  # Documentation, diagrams, photos
└── config/                # Configurations (VESC, camera, calibration)
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
