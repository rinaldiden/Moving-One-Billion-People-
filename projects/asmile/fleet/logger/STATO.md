# logger — stato fotografato 2026-11-09 08:50 dopo: IMU HW-123 (MPU6050 0x68) su I2C1: dtparam=i2c_arm=on in config.txt + i2c-dev in modules-load.d (live+root-ro); sensor_hub la logga nello stesso CSV/t_ms
kernel: 6.18.50+rpt-rpi-2712
git sul Pi: nessun git
overlay: si

## servizi attivi
asmile-health.service
logger-offload.service
logger-recorder.service
sensor_hub.service
tailscaled.service

## servizi abilitati al boot
asmile-autoupdate.service
asmile-health.service
logger-offload.service
logger-recorder.service
sensor_hub.service
tailscaled.service
logger-cleanup.timer
