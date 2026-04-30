# Dual OV9281 Setup — Inno-Maker CAM-OV9281RAW-V2

Alternative to Arducam Camarray HAT. Two separate OV9281 cameras
connected to Raspberry Pi 5 via CAM0 and CAM1 CSI ports.

## Hardware
- 2x Inno-Maker CAM-MIPI9281RAW-V2 (OV9281 global shutter mono)
- Connected via 22-pin flat cables to Pi 5 CAM0 and CAM1
- No HAT needed — direct connection

## config.txt
```
dtoverlay=ov9281,cam0
dtoverlay=ov9281,cam1
```

## Verify cameras
```bash
rpicam-hello --list-cameras
# Should show camera 0 and camera 1
```

## Key differences from Arducam Camarray
| | Arducam Camarray | Dual Inno-Maker |
|--|---|---|
| Sync | Hardware (HAT) | Software (timestamp matching) |
| Connection | 1 CSI port via HAT | 2 CSI ports direct |
| Output | Side-by-side 1280x400 | 2 separate streams |
| LD_PRELOAD | arducam_fix.so needed | Not needed |
| Max frame drift | 0ms (hardware sync) | ~1-5ms (software) |

## Synchronization approach
Global shutter OV9281 captures entire frame at once (no rolling shutter).
Software sync via timestamps — at 15fps (66ms per frame), a ~1-5ms drift
is acceptable for stereo depth at cycling speeds.
