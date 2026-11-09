# 001 — stato fotografato 2026-11-09 17:37 dopo: STERZO APPROVATO da Daniele (così è perfetto): sterzo_fluido_001 400 Hz, 15 deg/s, KD 0.6, kp 3; parametri in /data/sterzo_001_parametri.json; VESC ±30 A + hall_interp 20 in flash
kernel: 6.12.75+rpt-rpi-2712
git sul Pi: 1967cbf 2026-05-13 fix: separate boot config for asmile (ov9281 dual cam, no arducam HAT)
overlay: si

## servizi attivi
asmile_health.service
camera_sync_lo.service
master_switch.service
safe_shutdown.service
sensor_hub.service
servofreno.service
tailscaled.service
usb_encoder_bridge.service

## servizi abilitati al boot
asmile_health.service
camera_sync_lo.service
master_switch.service
safe_shutdown.service
sensor_hub.service
servofreno.service
tailscaled.service
usb_encoder_bridge.service
