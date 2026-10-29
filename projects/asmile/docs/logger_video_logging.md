# Modello di logging video — `asmile-logger`

Come l'unità standalone registra video per **alimentare il training** (segmentazione,
cattura di situazioni nuove). È **solo logging passivo**: nessun attuatore, nessun
UART/IMU/encoder, nessun safe-shutdown. Vedi
[bom_logger_video_standalone.md](bom_logger_video_standalone.md) e
[logger_provisioning.md](logger_provisioning.md).

## Principio

- **Scopo:** raccogliere ore di video (+ situazioni nuove/rare) da dare al modello
  da trainare. Niente guida autonoma, niente attuatori a bordo.
- **HW:** Pi 5 2GB + Arducam Camarray (2× OV9281, 2560×800), Li-ion → buck 5V.
- **Niente supercap / niente safe-shutdown -h.** Il logger è non presidiato e si
  stacca a corrente: la protezione è software, non hardware.

## Perché NESSUN supercap / safe-shutdown

- **Overlay File System** (`raspi-config → Performance → Overlay File System`):
  root in sola lettura, scritture in RAM → **puoi staccare la corrente quando vuoi,
  zero corruzione della SD.** Costo zero, nessun hardware.
- I video vanno su una **partizione dati separata** (scrivibile). Lì l'overlay non
  protegge → si registra **a segmenti**, così un taglio di corrente perde **solo
  l'ultimo spezzone**, mai l'intera registrazione né il sistema.
- Rispetto alla flotta asmile/asmile2: qui **non** servono LM74700, supercap 10F,
  pre-charge, drain MOSFET, ADS1115-per-shutdown. (La matematica supercap era
  corretta — ~126 J ≈ ~30 s a 4W — ma inutile con l'overlay.)

## Registrazione (a segmenti)

Camera: `rpicam-vid` (NON gst-launch, che sottoespone), Camarray con
`LD_PRELOAD=~/streaming/arducam_fix.so`, cam montata capovolta → `--vflip --hflip`.
Segmentazione per non perdere più dell'ultimo file su power-cut:

```bash
LD_PRELOAD=~/streaming/arducam_fix.so rpicam-vid \
  --width 2560 --height 800 --framerate 15 \
  --codec h264 --profile baseline --bitrate 500000 \
  --vflip --hflip --nopreview --timeout 0 \
  --segment 30000 \
  -o /data/recordings/clip_%05d.h264
```

- `--segment 30000` = un file ogni 30 s (su power-cut perdi al massimo 30 s).
- `/data/...` = partizione dati scrivibile (NON la root in overlay).
- H264 500 kbit ≈ 225 MB/h → su SD 128GB stai larghissimo (~540 h). Su uplink 4G
  usare H264 (NON MJPEG, ~30 GB/6h). Saltare i primi ~30 frame (warm-up esposizione).
- Luce: OV9281 global shutter mono, scarso al buio → registrare di giorno.

## Offload per il training

Push automatico delle clip verso il Mac quando c'è rete (Tailscale baseline,
alternative Cloudflare R2 / Tunnel se serve), `rsync --partial` ripartibile.
Dettagli in [bom_logger_video_standalone.md](bom_logger_video_standalone.md)
sezione "Trasmissione dati".

## Stato

Da fare al primo boot del Pi: abilitare overlay FS, creare la partizione dati,
installare il recorder a segmenti come servizio. Provisioning SD in attesa
(vedi logger_provisioning.md).
