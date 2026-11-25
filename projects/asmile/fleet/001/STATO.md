# 001 — stato fotografato 2026-11-25 09:12 dopo: freno: soglie 8-10 km/h dolce (v_max 10, zona 8, obiettivo 9, rampe lente, tetto 50), sicurezza ALLOW condizionato
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
