# STANDARD flotta asmile — overlay-root + /data (anti-corruzione SD)

> **Questa è l'architettura STANDARD di OGNI asmile** (deciso 2026-10-30, Daniele).
> Provata sul campo su #001: stacco a caldo mentre registrava, **anche senza supercap**
> → SD **integra**, tutto riparte, recording salvate. **Il supercap è superfluo** per la corruzione.

## Cosa fa
- **Root in OVERLAY read-only**: le scritture al root vanno in RAM, la SD-root non viene mai scritta
  → **staccare la corrente NON può corromperla** (mai, nemmeno a morte istantanea).
- **Partizione `/data` ext4 persistente** (unica scrivibile su SD): ci vanno **recording stereo
  timestampati, log, e lo stack di guida autonoma**. ext4 journaled → niente corruzione, si perde
  al più l'ultima scrittura non sincronizzata.

## Layout
```
mmcblk0p1  /boot/firmware  vfat   (RW reale — cmdline.txt qui; recupero brick qui)
mmcblk0p2  /  → overlay: lower /media/root-ro (ext4 18G READ-ONLY) + upper tmpfs(RAM)
mmcblk0p3  /data  ext4 ~98G  (RW persistente)
```
cmdline: `overlayroot=tmpfs:recurse=0` (il `:recurse=0` è ESSENZIALE: senza, overlaya anche /data).
Scritture persistenti → /data via **bind-mount** (nessuno script modificato):
`~/training_sessions`, `~/wip/logging`, `/var/lib/asmile` → /data ; `asmile_health` via env `ASMILE_HEALTH_LOG=/data/...`.

## Applicare su una nuova asmile
```bash
sudo bash projects/asmile/config/setup_overlay_data.sh   # resumable: riavvia quando lo chiede, rilancia
```
Fasi: A) resize FS offline (reboot) · B) crea /data · C) bind + health env · D) overlay+recurse=0 (reboot).
Da fare DOPO `setup_new_raspi.sh` (servizi installati). Hook resize: `logger/data_partition/`.

## Aggiornare il codice (root è READ-ONLY → scp/git-pull vanno in RAM!)
- `sudo mount -o remount,rw /media/root-ro` → modifica sotto `/media/root-ro/...` → `sync` → remount,ro (o reboot)
- oppure `raspi-config nonint disable_overlayfs` → reboot → modifica → enable + rimetti `:recurse=0` → reboot

→ Questo è il punto **OTA** (ci si connette e si aggiorna); la **guida gira sull'overlay** (root congelato).

## Recupero se un boot si rompe
SD → PC → partizione **boot (FAT)** → in `cmdline.txt` togli `overlayroot=...` (o ripristina
`cmdline.txt.pre-overlay`) → riavvia. Il rootfs p2 è intatto.

## Conseguenze per la flotta
- **Supercap/safe_shutdown: non più necessari** per la corruzione (restano come spegnimento gentile/buzzer opzionale).
- Base per la separazione **OTA ↔ guida autonoma** (guida su overlay+/data offline, OTA in modalità overlay-off) — vedi TODO A/B + watchdog.
