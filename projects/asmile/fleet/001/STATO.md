# 001 — stato fotografato 2026-11-09 17:05 dopo: sterzo_fluido_001: loop 200 Hz su encoder piantone, attrito appreso, compensazione ripple per fase elettrica (/data/sterzo_ripple_001.json), rilascio corrente all'arrivo; 24 prove 5-15 deg/s
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
