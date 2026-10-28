# Ripristino asmile #001 (asmile-tirano, hw1) — config SPECIFICA di questa unità

> ⚠️ **NON MISCHIARE CON asmile2 / altre unità.** Questa cartella contiene SOLO ciò che è
> specifico di **asmile #001** (`ASMILE_ID=001`, Tirano, hw1) e che **non vive da nessun'altra
> parte nel git**. L'unità #001 ha **2 camere OV9281 Inno-Maker SEPARATE** (CSI cam0 + cam1),
> **NON** la Arducam Camarray HAT 2560. La calibrazione, gli overlay di boot e l'ID qui dentro
> valgono per #001 e basta — non copiarli su asmile2.

Snapshot creato il **2026-10-28** per avere su GitHub il ripristino completo di #001 se si corrompe la SD.

## Cosa c'è qui (roba #001 che NON è nel resto del git)
| File | Origine sul Pi | Note |
|---|---|---|
| `boot/config.txt` | `/boot/firmware/config.txt` | overlay #001: `ov9281,cam0`+`ov9281,cam1` (dual separate), `uart0` (VESC GPIO14/15), `uart3` (GPS NEO-M10), `spi1-2cs,cs1_pin=16` (encoder AMT22) |
| `boot/cmdline.txt` | `/boot/firmware/cmdline.txt` | kernel cmdline di #001 |
| `asmile_id.conf` | `/home/asmile/asmile_id.conf` | identità unità (ID=001, name=asmile-tirano, hw1) |
| `systemd/*.service` | `/etc/systemd/system/` | snapshot dei 5 service **istanziati** su #001 (`User=asmile`). I template generici con `%USER%` stanno in `config/*.service` (quelli NON vanno toccati) |

## Cosa invece è GIÀ su GitHub (origin/main) — NON va ricopiato qui
- **Tutto il codice** del progetto (`pi/`, `firmware/`, `training/`, …). Il Pi gira 71 commit indietro ma origin/main ha tutto.
- **Calibrazione camere**: `config/calibration/stereo_calibration_2560x800.yaml` + `config/stereo_calibration.yaml` (verificato su origin/main).
- Lavoro di questi giorni (già committato+pushato):
  - **Encoder via ponte Arduino-USB**: `firmware/steering/amt22_dual_uno/` + `pi/steering/usb_encoder_bridge.py` + `config/usb_encoder_bridge.service` (CS D11=sterzo, D10=ruota → `/tmp/encoder_steer,_wheel,_position`).
  - **Camera stream pulito**: `pi/camera/raw_stream.py` via `rpicam-vid` MJPEG (l'ISP funziona per il video).
  - **Logging 2 encoder**: `pi/logging/training_recorder.py` logga `encoder_steer`+`encoder_wheel`.
  - **safe_shutdown allineato**: `pi/power/safe_shutdown.py` con `DEBOUNCE_MS=0` + commit-to-shutdown al primo LOW (fix brownout cycling).

## Procedura di ripristino (SD nuova su asmile #001)
1. Flash Raspberry Pi OS (Debian Trixie, Pi5), utente **`asmile`** (password `asmile`), hostname `asmile`.
2. `git clone https://github.com/rinaldiden/Moving-One-Billion-People-.git ~/wip/Moving-One-Billion-People-`
3. Copia la config di boot di #001:
   - `sudo cp ~/wip/.../config/asmile001_hw1/boot/config.txt  /boot/firmware/config.txt`
   - `sudo cp ~/wip/.../config/asmile001_hw1/boot/cmdline.txt /boot/firmware/cmdline.txt`  *(verifica il PARTUUID della nuova SD!)*
4. `cp ~/wip/.../config/asmile001_hw1/asmile_id.conf ~/asmile_id.conf`
5. Installa i service (usa i template `config/*.service` sostituendo `%USER%`→`asmile`, oppure direttamente gli snapshot in `systemd/`):
   `sudo cp ~/wip/.../config/asmile001_hw1/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload`
   `sudo systemctl enable --now safe_shutdown usb_encoder_bridge master_switch servofreno`
6. `sudo reboot` per attivare gli overlay (i2c/uart/spi/camere).
7. Verifica: `rpicam-hello --list-cameras` (2× ov9281), `/var/log/safe_shutdown.log` → `ARMED`, `/tmp/encoder_steer`/`_wheel` popolati.

> ⚠️ `cmdline.txt` contiene il `PARTUUID` della SD attuale: su una SD nuova va aggiornato al nuovo PARTUUID, altrimenti non boota.
