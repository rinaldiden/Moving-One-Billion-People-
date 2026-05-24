# Asmile — Claude development guide

## Critical safety rules

- **NEVER reboot or shutdown the Raspberry Pi** unless the user explicitly says to
- **NEVER start safe_shutdown.service** manually — it arms only after GPIO HIGH
- The user controls all power operations manually

## Raspi "asmile"

- **SSH**: `asmile@192.168.1.119` (DHCP, IP may change on hotspot)
- **Password**: `asmile`
- **Repo**: `/home/asmile/wip/Moving-One-Billion-People-/`
- **OS**: Debian Trixie, Raspberry Pi 5, kernel 6.12

## Hardware parameters (do not change without testing)

### Servo freno (DFRobot SER0062 brushless waterproof)
- GPIO 12, PWM **50Hz** (NOT 330Hz — il SER0062 brusha se >50Hz)
- Pulse 500-2500us, RELEASE_ANGLE=0° (raw 180°), BRAKE_ANGLE=60° (raw 120°)
- Pattern: pulse durante movimento (1.5s), poi PWM off + gpio_free → pin hi-Z
- Sistema **idraulico MTB**: servo → camma eccentrica → master piston → caliper
- NON superare 60° (a 65° l'idraulico inchioda meccanicamente, vedi feedback_brake_angle_hydraulic)
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
- Shifter HV powered from Pololu F5 VOUT (before LM74700)
- **Bleed resistor 10kΩ tra Pololu VOUT e GND** (essenziale: scarica il cap di uscita del Pololu in <2ms quando stacchi batteria, altrimenti shifter resta alive per secondi e Pi va in brownout prima di vedere il LOW)
- HV jumpered to HV3 on the board, GND pins jumpered with one wire to common terminal
- Battery ON → shifter alive → LV3=2.7V (partitore pull-up shifter + pull-down interno Pi) → GPIO HIGH
- Battery OFF → bleed scarica cap → shifter muore in ms → LV3=0V → GPIO LOW → shutdown
- safe_shutdown.py usa edge detection (lgpio.callback BOTH_EDGES) + backup poll 50ms + debounce 200ms
- Log persistente: /var/log/safe_shutdown.log + tombstone /var/lib/asmile/last_shutdown.txt

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
LD_PRELOAD=~/streaming/arducam_fix.so rpicam-vid --width 2560 --height 800 \
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
- Stereo side-by-side: 2560x800 total, left 1280x800 | right 1280x800

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
