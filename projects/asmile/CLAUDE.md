# Asmile — Claude development guide

## Critical safety rules

- **NEVER reboot or shutdown the Raspberry Pi** unless the user explicitly says to
- **NEVER start safe_shutdown.service** manually — it arms only after GPIO HIGH
- The user controls all power operations manually

## Raspi "asmile2"

- **SSH**: `asmile2@192.168.1.119` (DHCP, IP may change on hotspot)
- **Password**: `asmile`
- **Repo**: `/home/asmile2/wip/Moving-One-Billion-People-/`
- **OS**: Debian Trixie, Raspberry Pi 5, kernel 6.12

## Hardware parameters (do not change without testing)

### Servo freno (PDI-6221MG)
- GPIO 12, PWM at 330Hz (NOT 50Hz)
- Pulse 500-2500us, CENTER=0°, MAX_BRAKE=85°
- Via level shifter 3.3V→6V (Pololu D24V55F6)

### IMU (MPU6050)
- I2C bus 1, address 0x68
- smbus2 library, ±2g / ±250°/s
- Longitudinal deceleration = -ax

### GPS (NEO-M10)
- UART3 /dev/ttyAMA3, 38400 baud
- NMEA parsing: GGA for position, RMC for speed
- Speed conversion: knots × 1.852 / 3.6 = m/s

### INA219 (servo current sensor)
- I2C bus 1, address 0x40 (shared bus with MPU6050)
- Shunt 0.1Ω, monitors brake servo PDI-6221MG current
- smbus2 library, current_LSB = 0.1mA
- Inline between 6V supply and servo power pin

### Encoder (Briter SSI 12-bit)
- SPI1, daemon writes to /tmp/encoder_position
- systemd service: encoder-ssi.service

### Power sense (safe shutdown)
- GPIO 26 (Pin 37) via Level Shifter #2 channel 3 (same shifter as encoder)
- Shifter powered from Pololu F5 VOUT (before Schottky diode)
- HV jumpered to HV3 on the board, GND pins jumpered with one wire to common terminal
- Battery ON → shifter alive → LV3=3.3V → GPIO HIGH
- Battery OFF → shifter dies → LV3=0V → GPIO LOW → shutdown

### VESC (steering motor)
- UART0 /dev/ttyAMA0, 115200 baud
- Serial console disabled in cmdline.txt

## Services

```
encoder-ssi.service     — SPI encoder daemon (enabled, starts on boot)
safe_shutdown.service   — GPIO 26 power monitor (enabled, arms after HIGH)
```

Both have crash-loop protection: max 5 restarts in 60s.

## Logging structure

```
pi/logging/servofreno/      → servofreno_YYYYMMDD.csv (brake events)
pi/logging/training_data/   → training_YYYYMMDD.csv (10Hz continuous)
```

Training CSV: `timestamp,gps_lat,gps_lon,gps_speed_ms,gps_heading,imu_accel_x,imu_accel_y,imu_accel_z,imu_gyro_x,imu_gyro_y,imu_gyro_z,encoder_pos,evento`

## Camera — critical notes

**IMPORTANT:** Use `rpicam-vid` for video recording, NOT `gst-launch + libcamerasrc`.
gst-launch produces very dark frames (brightness ~36) while rpicam-vid exposes correctly (~110).

```bash
# CORRECT — good exposure
LD_PRELOAD=~/streaming/arducam_fix.so rpicam-vid --width 1280 --height 400 \
  --framerate 15 --bitrate 500000 --codec h264 --profile baseline \
  --timeout 0 --nopreview --vflip --hflip -o output.h264

# WRONG — dark frames, broken auto-exposure
gst-launch-1.0 libcamerasrc ! ... ! openh264enc ! filesink  # DO NOT USE
```

Camera notes:
- Cameras mounted upside down → use `--vflip --hflip` (rpicam) or `videoflip method=rotate-180` (gst)
- LD_PRELOAD of arducam_fix.so is required for Camarray HAT
- First ~2 seconds of recording are warm-up (exposure stabilizing), skip frame 0-30
- OV9281 global shutter mono — poor low-light performance, record in daylight
- Stereo side-by-side: 1280x400 total, left 640x400 | right 640x400

## Running the brake server

```bash
sudo python3 pi/braking/servofreno_server.py
# → http://<PI_IP>:5000
```

Server is resilient: works with or without IMU/GPS connected.

## Setup a new Raspi

```bash
cd projects/asmile/config
sudo bash setup_new_raspi.sh
# Then reboot to activate I2C, UART3, SPI1 overlays
```
