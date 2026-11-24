# 001 — stato fotografato 2026-11-24 19:00 dopo: freno sul loop dell'encoder (14bebb6d: pettine pedalate, contatto appreso, PI velocita', regola dura, encoder fix) + sensor_hub con gps_state.json; ordine di Daniele, prova domani
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
