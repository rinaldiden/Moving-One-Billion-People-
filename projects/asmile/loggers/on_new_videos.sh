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

# 0) PRIMA della percezione: taglia i tratti con frame fermi (bici ferma E scena immobile, >=5 s).
#    I grezzi restano intatti; la percezione usa i video "solo movimento" in _solo_movimento/<unita>/<sess>/.
#    Calibrazioni/metro NON tagliate (vedi taglia_fermi.py). Se fallisce -> si usa il grezzo.
python3 "$HERE/taglia_fermi.py" "$BASE" >> "$LOG" 2>&1 || echo "[$(ts)] taglia_fermi FALLITO -> percezione sui grezzi" >> "$LOG"
SM="$BASE/_solo_movimento"

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
        if [ -f "$SM/$name/$sess/${sess}_left.h264" ] && [ -f "$SM/$name/$sess/${sess}_right.h264" ]; then
          clip="$SM/$name/$sess/${sess}_left.h264"; right="$SM/$name/$sess/${sess}_right.h264"
          echo "[$(ts)]   $name/$sess: uso video SOLO MOVIMENTO (fermi tagliati)" >> "$LOG"
        elif [ -f "$SM/$name/$sess/index.json" ] && grep -q '"tagliato_s": [1-9]' "$SM/$name/$sess/index.json" \
             && ! grep -q '"stato": "tenuto"' "$SM/$name/$sess/index.json"; then
          echo "[$(ts)]   $name/$sess: tutta ferma -> salto" >> "$LOG"; continue
        fi
        echo "[$(ts)]   $name/$sess: depth+seg ..." >> "$LOG"
        run_perception "$BASE/_work/$name/$sess" --left "$clip" --right "$right" ${CAL[@]+"${CAL[@]}"} ;;
      *)                                              # logger Camarray side-by-side
        sess="$(basename "${clip%.h264}")"
        csess="$(echo "$sess" | sed -E 's/_[0-9]{5}$//')"      # clip_<data>_<ora>
        if [ -f "$SM/$name/$csess/$csess.h264" ]; then         # sessione tagliata: una sola volta, sul concatenato
          mov="$SM/$name/$csess/$csess.h264"
          echo "[$(ts)]   $name/$csess: uso video SOLO MOVIMENTO (fermi tagliati)" >> "$LOG"
          run_perception "$BASE/_work/$name/${csess}_solomov" --video "$mov" ${CAL[@]+"${CAL[@]}"}
          continue
        elif [ -f "$SM/$name/$csess/index.json" ] && ! grep -q '"stato": "tenuto"' "$SM/$name/$csess/index.json"; then
          continue                                             # tutta ferma
        fi
        echo "[$(ts)]   $name/$sess: depth+seg ..." >> "$LOG"
        run_perception "$BASE/_work/$name/$sess" --video "$clip" ${CAL[@]+"${CAL[@]}"} ;;
    esac
  done
done
echo "[$(ts)] on_new_videos END" >> "$LOG"
