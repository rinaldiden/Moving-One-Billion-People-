#!/bin/bash
# recorder.sh — logger video a SEGMENTI per asmile-logger (Pi5 + Arducam Camarray).
#
# Camera = Arducam Camarray (Pivariety) che compare come UN sensore ov9281
# side-by-side 2560x800, grazie allo shim LD_PRELOAD arducam_fix.so (rinomina
# l'entita' media arducam-pivariety -> ov9281, cosi' la stock libcamera la usa).
#
# Scrive clip da N secondi in /data/recordings (partizione dati scrivibile,
# FUORI dalla root in overlay). Con overlay FS attivo si puo' staccare la
# corrente in qualsiasi momento: si perde al massimo l'ultima clip in corso.
#
# Parametri via env:
#   W,H,FPS,BR  default 2560 800 15 500000   (frame stereo nativo)
#   SEG         durata segmento ms (default 30000 = 30s)
#   OUT         cartella output (default /data/recordings)
#   FLIP        "1" per --vflip --hflip (se camera capovolta; default no)
#   ARDUCAM_FIX path dello shim (default ~/streaming/arducam_fix.so)
#
# Istante dei frame (2026-11-07, metodo unico flotta): se rpicam-vid ha --metadata, ogni frame
# finisce in clip_<STAMP>_frames.csv  (frame,t_ms,sensor_ts_ns) con t_ms = CLOCK_MONOTONIC in ms,
# lo stesso orologio del CSV unico del sensor_hub. Numerazione continua fra i segmenti: il Mac
# assegna i frame alle clip contandoli in ordine.
set -u
set -o pipefail

OUT="${OUT:-/data/recordings}"
W="${W:-2560}"; H="${H:-800}"; FPS="${FPS:-15}"; BR="${BR:-500000}"
SEG="${SEG:-30000}"
ARDUCAM_FIX="${ARDUCAM_FIX:-$HOME/streaming/arducam_fix.so}"
FLIP="${FLIP:-0}"

mkdir -p "$OUT"
# attende che /data sia montata prima di scrivere
for i in $(seq 1 30); do mountpoint -q /data && break; sleep 1; done

STAMP="$(date +%Y%m%d_%H%M%S)"
FLIPARGS=""
[ "$FLIP" = "1" ] && FLIPARGS="--vflip --hflip"

# Pi5 = encode H264 software (no HW); Camarray via shim arducam_fix.so.
CAM=(env LD_PRELOAD="$ARDUCAM_FIX" rpicam-vid
  --width "$W" --height "$H" --framerate "$FPS"
  --codec h264 --profile baseline --bitrate "$BR"
  $FLIPARGS --nopreview --timeout 0
  --segment "$SEG"
  -o "$OUT/clip_${STAMP}_%05d.h264")

if ! rpicam-vid --help 2>&1 | grep -q -- '--metadata'; then
  exec "${CAM[@]}"                                   # rpicam vecchio: come prima
fi
# exit code = quello di rpicam (pipefail) → systemd riavvia se la camera cade
# mawk legge la pipe a blocchi (~40 s di ritardo, persi a un taglio di corrente): -W interactive = riga per riga
AWK=(awk); awk -W version 2>&1 | grep -q mawk && AWK=(awk -W interactive)
"${CAM[@]}" --metadata - --metadata-format txt | "${AWK[@]}" '
  BEGIN { print "frame,t_ms,sensor_ts_ns"; n = 0 }
  /SensorTimestamp/ { if (match($0, /[0-9][0-9][0-9][0-9][0-9][0-9]+/)) {
      ns = substr($0, RSTART, RLENGTH); printf "%d,%d,%s\n", n++, int(ns / 1000000), ns; fflush() } }
' > "$OUT/clip_${STAMP}_frames.csv"
