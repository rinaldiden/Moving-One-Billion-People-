# 001 — stato fotografato 2026-11-09 16:38 dopo: VESC sterzo: l_current ±30 A + foc_hall_interp_erpm 20 (scritti via UART, verificati); sterzo_vel_001 a inseguimento riferimento (molla+smorzatore), prove 16:35-16:37
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
