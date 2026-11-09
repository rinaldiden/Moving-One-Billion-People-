# 001 — stato fotografato 2026-11-09 17:35 dopo: sterzo fluido tarato: KD 0.6, filtro 0.35/0.05, niente dither/ripple, vel default 15 deg/s (variazione 8-12%, nessuna vibrazione); VESC invariato (±30 A, hall_interp 20, salvato in flash)
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
