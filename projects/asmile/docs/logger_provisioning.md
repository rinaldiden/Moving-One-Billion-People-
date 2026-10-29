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

### ⚠️ Muro TCC su macOS — metodo che FUNZIONA

Scrivere direttamente su `/dev/rdiskN` con `rpi-imager --cli` **o** con `dd`
**fallisce** da una shell non-GUI (es. agente), anche da root:
- rpi-imager → `Authorization failed / cancelled`
- dd → `Operation not permitted`

È il **TCC "volumi rimovibili"**: serve un'app con *Accesso completo al disco*.
Soluzione in 2 tempi che aggira il problema:

**1) Personalizza l'immagine su FILE (nessun device → nessun TCC):**
```bash
RPI="/Applications/Raspberry Pi Imager.app/Contents/MacOS/rpi-imager"
curl -fL -o /tmp/rpios.img.xz "https://downloads.raspberrypi.com/raspios_lite_arm64_latest"
xz -dkf -T0 /tmp/rpios.img.xz                    # → /tmp/rpios.img
mkfile -n 4g /tmp/custom.img                      # il file dst DEVE preesistere
"$RPI" --cli --enable-writing-system-drives --disable-verify \
  --first-run-script /tmp/firstrun.sh /tmp/rpios.img /tmp/custom.img
# → /tmp/custom.img = RPi OS + firstrun (hostname/user/SSH/WiFi) iniettato
```

**2) Scrivi il file sulla SD con `dd` da un Terminal con *Accesso completo al disco*:**
```bash
sudo dd if=/tmp/custom.img of=/dev/rdiskN bs=4m; sync; diskutil eject /dev/diskN
```
Se `Operation not permitted`: System Settings → Privacy & Security → Full Disk
Access → aggiungi **Terminal**, riapri, rilancia. (La SD nel lettore interno è un
disco *internal* rimovibile, es. `/dev/disk4` — NON esterno.)

Poi: SD nel Pi 5 → accendi → si connette a EOLO da solo → `ssh asmile@asmile-logger.local`.

## Stato (2026-10-29)

Immagine personalizzata **già pronta** in `/tmp/custom.img` (RPi OS Lite arm64 +
firstrun: hostname asmile-logger, user asmile, SSH key del Mac + password, WiFi
EOLO_378899). Manca solo lo `sudo dd` del passo 2, da un Terminal con Full Disk
Access — bloccato dal TCC se lanciato dall'agente.
