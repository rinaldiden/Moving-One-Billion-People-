# Logger su Pi 5 1GB? — valutazione 2026-11-14

Domanda di Daniele (TG): i servizi del logger, così come sono, girano su un Pi 5 1GB? si possono alleggerire? schede più economiche con gli stessi ingressi?

Stato: STIMA da codice (logger offline dal 13/11, nessuna misura dal vivo). Da confermare con la prova sotto.

## Servizi attivi (fleet/logger/STATO.md, 2026-11-09)
| Servizio | Cosa | Peso RAM stimato |
|---|---|---|
| logger-recorder (recorder.sh → rpicam-vid H264 software 2560x800@15 + awk) | unico pezzo pesante | ~150-250 MB |
| sensor_hub.py | python puro, smbus2/serial | ~15-25 MB |
| bike_speed_ble.py | python + bleak/dbus (asyncio) | ~30-45 MB |
| offload_confirm.py, health_logger.py, cleanup (timer) | python standard lib | ~15-20 MB l'uno |
| tailscaled | | ~40-60 MB |
| OS Lite + systemd + journald + bluetoothd | | ~150-200 MB |
Totale ≈ 450-650 MB con 1 camera (Camarray SBS). Logger nuovi con 2 OV9281 separate = 2 rpicam-vid → +150-250 MB → 650-850 MB: stretto.
Niente numpy/opencv/torch sul Pi: il codice è già leggero; il peso è rpicam-vid.

## Rischi specifici a 1GB
1. Overlay FS: tutto ciò che si scrive sulla root finisce in RAM (journald, /var/log/*.log, stato tailscale) e cresce nelle giornate lunghe.
2. asmile-autoupdate: oggi inerte (sul Pi non c'è git), ma un git pull del repo (.git 6.8 GB) dentro l'overlay in RAM lo ucciderebbe.
3. Nessuno swap: se la RAM finisce, l'OOM killer può chiudere proprio il recorder.

## Alleggerimenti (nessuno cambia cosa registra)
- journald Storage=volatile + RuntimeMaxUse=16M; log degli script su /data, non sulla root.
- Togliere asmile-autoupdate e logger-stream (già spento) dall'immagine del logger.
- rpicam-vid --buffer-count 2-3 (meno frame in coda).
- zram 256 MB come paracadute.
- MemoryMax= nelle unit python, OOMScoreAdjust=-500 sul recorder (se muore qualcosa, non è il video).
- Opzionale: sensor_hub + bike_speed + health in un solo processo (−30/40 MB).

## Prova che decide (serve ok di Daniele: tocca config.txt del Pi)
Sul logger esistente: `total_mem=1024` in /boot/firmware/config.txt → il Pi si comporta da 1GB. Un giro vero, poi `free -m`, `ps -eo rss,comm --sort=-rss | head`, `journalctl -k | grep -i oom`. Se resta >250 MB liberi → 1GB ok. Si toglie la riga e torna com'era.

## Schede alternative
- Pi 5 1GB: stessa CPU, stessi 2 CSI, ~45 $ listino / ~67 € (rivenditore EU, da verificare) contro ~95 € del 2GB nell'ordine 2 logger.
- Pi 4 / Pi Zero 2 W: 1 solo CSI → niente 2 OV9281 separate. Encoder HW max 1920 di larghezza → Camarray solo ridotta (1920x600). Zero 2 W ha 512 MB.
- Rockchip (Orange Pi 5, Radxa): 2 MIPI + encoder HW, ma nessun driver per OV9281 Inno-Maker/Camarray → mesi di porting.
- CM5 + IO board: 2 CSI ma costa di più.
Conclusione: per 2 camere separate la scheda più economica resta il Pi 5; la scelta è solo 1GB vs 2GB.
