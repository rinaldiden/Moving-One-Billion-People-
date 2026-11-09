# 001 — stato fotografato 2026-11-09 16:26 dopo: sterzo_vel_001: ritorno al centro a corrente regolata sull'encoder (10 deg/s, tetto 30 A); prova riuscita -42 deg -> +0.2 deg in 7.6 s, 8.5 A medi
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
