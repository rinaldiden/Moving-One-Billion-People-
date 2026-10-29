#!/bin/bash
# recorder.sh — logger video a SEGMENTI per asmile-logger (Pi 5 + Camarray).
#
# Scrive clip da N secondi in /data/recordings (partizione dati scrivibile,
# FUORI dalla root in overlay). Con overlay FS attivo si puo' staccare la
# corrente in qualsiasi momento: si perde al massimo l'ultima clip in corso.
#
# Parametri via env (default per Camarray 2560x800):
#   W,H,FPS,BR  risoluzione/framerate/bitrate   (default 2560 800 15 500000)
#   SEG         durata segmento in ms           (default 30000 = 30s)
#   OUT         cartella output                 (default /data/recordings)
#   ARDUCAM_FIX path di arducam_fix.so (Camarray) — vuoto = camera standard
set -u

OUT="${OUT:-/data/recordings}"
W="${W:-2560}"; H="${H:-800}"; FPS="${FPS:-15}"; BR="${BR:-500000}"
SEG="${SEG:-30000}"
ARDUCAM_FIX="${ARDUCAM_FIX:-$HOME/streaming/arducam_fix.so}"

mkdir -p "$OUT"

# attende che /data sia montata (la partizione dati) prima di scrivere
for i in $(seq 1 30); do mountpoint -q /data && break; sleep 1; done

STAMP="$(date +%Y%m%d_%H%M%S)"
PRE=""
[ -f "$ARDUCAM_FIX" ] && PRE="env LD_PRELOAD=$ARDUCAM_FIX"

# Pi 5 = encode H264 software (nessun encoder HW). Camera montata capovolta.
exec $PRE rpicam-vid \
  --width "$W" --height "$H" --framerate "$FPS" \
  --codec h264 --profile baseline --bitrate "$BR" \
  --vflip --hflip --nopreview --timeout 0 \
  --segment "$SEG" \
  -o "$OUT/clip_${STAMP}_%05d.h264"
