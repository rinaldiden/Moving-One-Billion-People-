# Provisioning — unità `asmile-logger` (video logger standalone)

Procedura per preparare la SD del **logger video standalone** (Pi 5 2GB + Camarray)
e come collegarsi via SSH. Vedi anche [bom_logger_video_standalone.md](bom_logger_video_standalone.md)
e [logger_video_logging.md](logger_video_logging.md).

## Identità unità

- **Hostname:** `asmile-logger`
- **Utente:** `asmile` (password = default flotta `asmile`, come le altre unità)
- **WiFi:** `EOLO_378899` — ⚠️ **password NON in repo** (repo pubblico): sta nel
  Keychain del Mac (`security find-generic-password -ga "EOLO_378899" -w`).
- **SSH:** abilitato, con **chiave pubblica del Mac** (`~/.ssh/id_ed25519.pub`,
  `danielerinaldi@mac`) iniettata → login passwordless, + password come fallback.

## Come collegarsi (da qualsiasi istanza/sessione)

```bash
ssh asmile@asmile-logger.local        # mDNS sulla rete EOLO
# oppure, trovato l'IP sul router:   ssh asmile@192.168.1.X
```

La chiave `id_ed25519` del Mac è già autorizzata sul Pi. Se cambia rete e non
risolve `.local`, cerca l'IP (DHCP) o aggiungi un alias in `~/.ssh/config`.

## Flashare la SD (Raspberry Pi Imager CLI, headless, no GUI)

Tutto preparato sul Mac (2026-10-29):

- **Imager:** installato via `brew install --cask raspberry-pi-imager`
  → CLI in `/Applications/Raspberry Pi Imager.app/Contents/MacOS/rpi-imager`.
- **Immagine:** `2026-10-06-raspios-trixie-arm64-lite` (64-bit, headless)
  `https://downloads.raspberrypi.com/raspios_lite_arm64_latest`
- **`/tmp/firstrun.sh`** (iniettato con `--first-run-script`): imposta hostname,
  utente `asmile`, `enable_ssh -k <pubkey Mac>`, WiFi `EOLO_378899`, keymap/timezone IT.
- **`/tmp/flash_pi.sh`**: auto-rileva la SD esterna, rifiuta il disco interno e
  drive >300GB, smonta e scrive con `rpi-imager --cli`.

Lancio (serve `sudo`: macOS richiede privilegi per scrivere su disco raw):

```bash
sudo bash /tmp/flash_pi.sh
# → scarica immagine, scrive la SD, inietta WiFi+SSH+hostname, espelle
```

Equivalente esplicito:

```bash
RPI="/Applications/Raspberry Pi Imager.app/Contents/MacOS/rpi-imager"
sudo "$RPI" --cli --first-run-script /tmp/firstrun.sh \
  "https://downloads.raspberrypi.com/raspios_lite_arm64_latest" /dev/diskN
```

Poi: SD nel Pi 5 → accendi → si connette a EOLO da solo → `ssh asmile@asmile-logger.local`.

## Stato (2026-10-29)

Flash **in attesa**: la SD non è ancora rilevata dal Mac (reader `Link: Off`,
0 dischi esterni) — problema fisico di contatto/lettore/card, non software.
Appena la card compare, il flash parte col comando sopra.
