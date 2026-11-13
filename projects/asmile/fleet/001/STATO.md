# 001 — stato fotografato 2026-11-11 07:55 dopo: recorder modo calib 6 Mbps via /tmp/asmile_calib_mode (attivo oggi 2026-11-11, overlay: sparisce al riavvio)
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

## 2026-11-13 — encoder sterzo RIMONTATO: nuovi zeri
- Centro (manubrio dritto, Daniele, rifatto) = **4112** (prima lettura 3244 scartata da Daniele; 6606 del 09/11 non vale più). Finecorsa spinti a mano: sx 2028 (−45.8°), dx 6168 (+45.2°), campo 4140 (09/11: 4580); ritorno al centro 4132 (+0.44°). File: /data/steering_limits_asmile-001.json (copia in fleet/001/data/), backup del vecchio .pre_rimontaggio_20261113.
- **REGOLA: se l'encoder sterzo viene tolto o smontato, PRIMA di azionare lo sterzo si rifanno gli zeri (centro + finecorsa), altrimenti il motore va oltre i finecorsa.**
