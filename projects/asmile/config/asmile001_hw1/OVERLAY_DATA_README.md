# asmile #001 — overlay-root + partizione /data (anti-corruzione) — 2026-10-30

Fatto su #001 per **non corrompere la SD allo spegnimento** (anche a corrente staccata
mentre gira) e per separare, in prospettiva, la **guida autonoma** (su `/data`) dall'**OTA**
(aggiornamenti su root). Procedura replicata da `logger/data_partition/` (testata sul logger).

## Layout risultante
```
mmcblk0p1  /boot/firmware  vfat   (RW reale — qui sta cmdline.txt)
mmcblk0p2  /  → OVERLAY: lower /media/root-ro (ext4 18G, READ-ONLY) + upper tmpfs (RAM)
mmcblk0p3  /data  ext4 98G  (RW, PERSISTENTE — qui vanno recording/log/guida)
```
cmdline.txt: `overlayroot=tmpfs:recurse=0 ...`  (il `:recurse=0` è ESSENZIALE: senza,
overlaya anche /data → scritture in RAM / permission denied).

## Scritture persistenti → /data (bind-mount, nessuno script modificato)
In `/etc/fstab` (reale = `/media/root-ro/etc/fstab`):
```
LABEL=data /data ext4 defaults,noatime,nofail 0 2
/data/training_sessions /home/asmile/training_sessions none bind,nofail 0 0   # recording video+sensori
/data/logging           /home/asmile/wip/logging       none bind,nofail 0 0   # limiter, CAN, servofreno, training
/data/var_lib_asmile    /var/lib/asmile                none bind,nofail 0 0   # tombstone safe_shutdown (post-mortem)
```
+ `asmile_health.service`: `Environment=ASMILE_HEALTH_LOG=/data/asmile_health.csv`.
NB: `/var/log/safe_shutdown.log` resta in RAM (effimero); il **tombstone** (eventi chiave)
persiste su /data via il bind.

## Spegnimento / stacco corrente
- **Root READ-ONLY** → staccare la corrente **non può corrompere** il sistema. ✓
- `/data` è ext4 **journaled**: niente corruzione; si perde al più l'ultima scrittura non
  sincronizzata. I writer scrivono a segmenti/con flush.
- Il supercap/safe_shutdown non sono più critici per la corruzione (restano come buzzer/flush).

## AGGIORNARE il codice (root è READ-ONLY → scp/git-pull vanno in RAM e si perdono!)
Due modi per scrivere persistente sul root:
- **A (veloce):** `sudo mount -o remount,rw /media/root-ro` → modifica/pull sotto `/media/root-ro/...`
  (è la p2 vera) → `sync` → `sudo mount -o remount,ro /media/root-ro` (o reboot).
- **B (pulito):** `sudo raspi-config nonint disable_overlayfs && sudo reboot` → modifica normale →
  `sudo raspi-config nonint enable_overlayfs` → **rimetti `:recurse=0` nel cmdline** → `sudo reboot`.
→ Questo è il punto "OTA" (dove ci si connette e si aggiorna); la **guida gira sull'overlay** (root congelato).
`asmile-autoupdate` (git pull al boot) sotto overlay è inefficace (va in RAM): l'OTA vera è il metodo A/B.

## RECUPERO se un boot si rompe (es. cmdline overlay errato)
SD → PC → monta la partizione **boot (FAT, leggibile ovunque)** → in `cmdline.txt` togli
`overlayroot=tmpfs:recurse=0 ` (oppure ripristina `cmdline.txt.pre-overlay`, salvato lì) → riavvia:
il Pi torna normale (root RW). Il rootfs p2 (18G) è intatto.

## Replica da zero
`logger/data_partition/README.md` + hook/premount (resize2fs offline a 18G, poi parted live +
mkfs p3), poi `raspi-config nonint enable_overlayfs` e `:recurse=0` nel cmdline.
