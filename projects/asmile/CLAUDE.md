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
- UART3 /dev/ttyAMA3, 9600 baud
- NMEA parsing: GGA for position, RMC for speed
- Speed conversion: knots × 1.852 / 3.6 = m/s

### Encoder (Briter SSI 12-bit)
- SPI1, daemon writes to /tmp/encoder_position
- systemd service: encoder-ssi.service

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
