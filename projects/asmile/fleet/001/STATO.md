# 001 — stato fotografato 2026-11-25 14:35 dopo: freno come in officina: 25 gradi in 0,5 s, poi 16,7 gradi/s su velocita'/decel, PWM hardware
kernel: 6.12.75+rpt-rpi-2712
git sul Pi: 1967cbf 2026-05-13 fix: separate boot config for asmile (ov9281 dual cam, no arducam HAT)
overlay: si

## servizi attivi
asmile_health.service
camera_sync_lo.service
master_switch.service
safe_shutdown.service
sensor_hub.service
tailscaled.service
usb_encoder_bridge.service

## servizi abilitati al boot
asmile_health.service
camera_sync_lo.service
master_switch.service
safe_shutdown.service
sensor_hub.service
tailscaled.service
usb_encoder_bridge.service
