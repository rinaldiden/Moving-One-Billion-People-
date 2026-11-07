#!/bin/bash
# on_new_videos.sh — hook lanciato da pull_from_loggers.py quando arrivano video NUOVI.
# Ordine: download -> asmile_perception.py (schema UNICO flotta+logger: YOLO26-depth densa,
# scala ancorata allo stereo con la calib della bici, YOLO26-seg + distanza per oggetto).
# Anonimizzazione GDPR ESCLUSA su decisione di Daniele (2026-11-07): si lavora sui grezzi.
# Lo script di anonimizzazione resta in logger/anonymize/ se servirà riattivarla.
# Arg $1 = cartella base asmile-loggers/. Tutto LOCALE, niente su git.
set -u
BASE="${1:-$(cd "$(dirname "$0")/../asmile-loggers" && pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"                 # projects/asmile/loggers
DEPTH="$(cd "$HERE/../logger/depth" && pwd)"
PY="$HOME/.asmile_depth_venv/bin/python"; [ -x "$PY" ] || PY=python3
LOG="$BASE/ingest.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
echo "[$(ts)] on_new_videos START ($BASE)" >> "$LOG"

run_perception() {   # $1=out  resto=argomenti input per asmile_perception.py
  local out="$1"; shift
  [ -f "$out/mosaic.jpg" ] && return 0                # idempotente
  mkdir -p "$out"
  (cd "$DEPTH" && "$PY" asmile_perception.py "$@" --out "$out" --samples 12 --video-out 40 >> "$LOG" 2>&1) \
    && echo "[$(ts)]   OK -> $out" >> "$LOG" || echo "[$(ts)]   FALLITO -> $out" >> "$LOG"
}

for d in "$BASE"/*/ ; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  case "$name" in _*) continue ;; esac                # _anon, _work = output
  calib="$DEPTH/calib_${name}.json"
  CAL=(); [ -f "$calib" ] && CAL=(--calib "$calib") \
    || echo "[$(ts)] $name: niente calib_${name}.json -> depth densa con scala del modello (non ancorata)" >> "$LOG"
  for clip in "$d"/*.h264; do
    [ -f "$clip" ] || continue
    sz=$(stat -f%z "$clip" 2>/dev/null || echo 0)
    [ "$sz" -lt 2000000 ] && continue                 # test switch / clip vuote
    case "$clip" in
      *_right.h264) continue ;;                       # gestita insieme alla _left
      *_left.h264)                                    # bici con camere separate (#001)
        sess="$(basename "${clip%_left.h264}")"
        right="$d/${sess}_right.h264"; [ -f "$right" ] || continue
        echo "[$(ts)]   $name/$sess: depth+seg ..." >> "$LOG"
        run_perception "$BASE/_work/$name/$sess" --left "$clip" --right "$right" ${CAL[@]+"${CAL[@]}"} ;;
      *)                                              # logger Camarray side-by-side
        sess="$(basename "${clip%.h264}")"
        echo "[$(ts)]   $name/$sess: depth+seg ..." >> "$LOG"
        run_perception "$BASE/_work/$name/$sess" --video "$clip" ${CAL[@]+"${CAL[@]}"} ;;
    esac
  done
done
echo "[$(ts)] on_new_videos END" >> "$LOG"
