# 001 — stato fotografato 2026-11-09 10:01 dopo: encoder ruota tarato coi 10 giri (15.760 m): wheel_circum_m 0.3374→0.3477 (m/giro encoder), m_per_count 2.1219e-5; backup .bak-20261109; ALLOW asmile-sicurezza, vai di Daniele
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
