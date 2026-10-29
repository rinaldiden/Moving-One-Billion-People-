# Sistema logger video — `asmile-logger` (Raspberry Pi 5)

Sistema completo e ripetibile per il **logger video standalone** (Pi 5 2GB +
Camarray), configurato per raccogliere video a segmenti per il training, **senza
safe-shutdown hardware** (overlay FS). Vedi i doc di progetto:
[logger_provisioning.md](../docs/logger_provisioning.md),
[logger_video_logging.md](../docs/logger_video_logging.md),
[bom_logger_video_standalone.md](../docs/bom_logger_video_standalone.md).

## Flusso

1. **Flash SD** (sul Mac): immagine RPi OS Lite arm64 + `firstrun.sh` (hostname
   `asmile-logger`, utente `asmile`, SSH, WiFi). Vedi `logger_provisioning.md`.
   - `firstrun.sh.example` qui è il **template** (senza segreti). La versione reale
     con la password WiFi NON va nel repo (pubblico).
2. **Primo boot**: il Pi si connette al WiFi, SSH pronto.
3. **Setup on-Pi** (una volta): `sudo bash setup_logger.sh`
   - crea la partizione dati `/data` dallo spazio libero della SD,
   - installa il servizio recorder,
   - abilita l'**overlay FS** sulla root (ultimo passo: dopo, la root è read-only
     → si può staccare la corrente senza corrompere la SD).
4. **Esercizio**: al boot parte `logger-recorder.service` → registra clip a
   segmenti in `/data/recordings`. `offload.sh` spinge le clip nuove al Mac.

## File

| File | Dove gira | Cosa fa |
|---|---|---|
| `firstrun.sh.example` | Mac (flash) | template config primo boot (hostname/user/SSH/WiFi) |
| `setup_logger.sh` | Pi (una volta) | partizione `/data` + install servizio + enable overlay |
| `recorder.sh` | Pi (servizio) | `rpicam-vid` a segmenti → `/data/recordings` |
| `logger-recorder.service` | Pi | systemd unit del recorder |
| `offload.sh` | Pi o Mac | push `rsync` delle clip nuove (Tailscale) |

## Configurato per Pi 5

- **RPi OS Lite arm64** (headless, no desktop).
- Pi 5 **non ha H264 HW** → `rpicam-vid` usa encode software (regge 2560×800@15fps).
- Camera **Camarray** (2× OV9281, 2560×800): serve `LD_PRELOAD` di `arducam_fix.so`
  (driver Arducam da installare a parte sul Pi). Con camera singola/standard,
  lasciare `ARDUCAM_FIX` vuoto.
