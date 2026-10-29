# Sistema logger video — `asmile-logger` (Raspberry Pi 5 + Arducam Camarray)

Sistema completo e **ripetibile in un comando** per il logger video standalone.
Raccoglie video stereo a segmenti per il training, **senza safe-shutdown hardware**
(overlay FS). Vedi anche: [logger_provisioning.md](../docs/logger_provisioning.md),
[logger_video_logging.md](../docs/logger_video_logging.md),
[bom_logger_video_standalone.md](../docs/bom_logger_video_standalone.md).

## Stato reale (2026-10-29) — FUNZIONANTE

- **Unità:** hostname `asmile-logger`, utente `asmile-logger` (pw `asmile`), WiFi `EOLO_378899`.
- **OS:** RPi OS **Desktop** Trixie (kernel 6.18), arm64.
- **Camera:** Arducam **Camarray** = sensore Pivariety a i2c 0x0c, compare come
  **ov9281 2560×800 side-by-side** grazie allo shim `arducam_fix.so`.
  Config: `camera_auto_detect=1` + `dtoverlay=arducam-pivariety` (connettore DEFAULT, bus 11).
- **Streaming live:** `stream_logger.py` → MJPEG su **http://IP:8080/** (1280×400, 15fps).
- **Overlay FS:** attivo (`overlayroot=tmpfs`) → SD read-only, **stacco-corrente sicuro** (testato).
- **Accesso:** `ssh asmile-logger` (chiave del Mac iniettata, passwordless).

## La svolta camera (perché funziona senza pacchetti Arducam)

La Camarray è una **Arducam Pivariety**: il kernel la legge (`arducam-pivariety 11-000c:
firmware version`), ma la **stock libcamera non la elenca** ("No cameras available") e i
pacchetti Arducam non sono compatibili con Trixie/kernel 6.18. Soluzione = **lo shim del
repo `pi/vision/arducam_fix.c`**: LD_PRELOAD che intercetta `MEDIA_IOC_G_TOPOLOGY` e
**rinomina l'entità `arducam-pivariety`→`ov9281`**, così la stock libcamera (che ha già
`ov9281_mono.json`) la usa. È il metodo del primo asmile.

## ⚡ RESTORE in un comando (se qualcosa si rompe)

Se un'operazione rischiosa brickа la SD → **reflash** (vedi `logger_provisioning.md`) e poi:

```bash
# sul Pi appena flashato (hostname/WiFi/SSH via firstrun), repo clonato:
sudo raspi-config nonint disable_overlayfs && sudo reboot   # se overlay già attivo
# dopo il reboot:
sudo bash projects/asmile/logger/restore_asmile_logger.sh
sudo reboot
```

`restore_asmile_logger.sh` riapplica TUTTO: config camera (arducam-pivariety), compila
`arducam_fix.so`, deploya `stream_logger.py`+`recorder.sh`, installa i servizi systemd
(stream + recorder), gruppi video/i2c, e riabilita l'overlay FS. Al reboot: camera OK,
streaming su `:8080`, recorder attivo se `/data` è montata.

## File

| File | Dove gira | Cosa fa |
|---|---|---|
| `restore_asmile_logger.sh` | Pi (una volta) | **ripristino completo in un comando** |
| `firstrun.sh.example` | Mac (flash) | template config primo boot (hostname/user/SSH/WiFi) |
| `stream_logger.py` | Pi (servizio) | streaming MJPEG Camarray → http://IP:8080/ |
| `logger-stream.service` | Pi | systemd unit dello streaming (auto-start) |
| `recorder.sh` | Pi (servizio) | `rpicam-vid` a segmenti (2560×800 + arducam_fix.so) → `/data/recordings` |
| `logger-recorder.service` | Pi | systemd unit del recorder |
| `setup_logger.sh` | Pi | crea partizione `/data` + enable overlay |
| `offload.sh` | Pi o Mac | push `rsync` delle clip (Tailscale) |

## Note
- **Persistenza:** con overlay FS attivo, le modifiche vanno in RAM → per cambiare config
  disabilita prima l'overlay (`disable_overlayfs` → reboot), modifica, riabilita.
- **Partizione dati `/data`:** scrivibile, FUORI dall'overlay (i video devono persistere).
  Serve crearla (shrink rootfs o USB) — vedi `setup_logger.sh`.
- **SSH del Pi instabile** sui comandi lunghi (WiFi EOLO debole) → lancia i processi con
  `systemd-run`/servizi, non in foreground.
