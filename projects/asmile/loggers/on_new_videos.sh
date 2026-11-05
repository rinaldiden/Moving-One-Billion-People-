#!/bin/bash
# on_new_videos.sh — hook lanciato da pull_from_loggers.py quando arrivano video NUOVI.
# Ordine OBBLIGATORIO (GDPR): download -> ANONIMIZZA -> [gate verdetto] -> depth/segmentazione.
# I video grezzi con PII non arrivano MAI al training: a valle vanno solo gli _anon che PASSano.
# Arg $1 = cartella base asmile-loggers/. Tutto LOCALE, niente su git.
set -u
BASE="${1:-$(cd "$(dirname "$0")/../asmile-loggers" && pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"                 # projects/asmile/loggers
ANON="$(cd "$HERE/../logger/anonymize" && pwd)"
DEPTH="$(cd "$HERE/../logger/depth" && pwd)"
PY="$HOME/.asmile_depth_venv/bin/python"; [ -x "$PY" ] || PY=python3
LOG="$BASE/ingest.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
echo "[$(ts)] on_new_videos START ($BASE)" >> "$LOG"

for d in "$BASE"/*/ ; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  [ "$name" = "_anon" ] && continue                   # non ri-processare gli output
  n=$(ls "$d"/*.h264 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] || continue
  outdir="$BASE/_anon/$name"; mkdir -p "$outdir"
  echo "[$(ts)] $name: $n clip" >> "$LOG"

  # ---- 1) GDPR: anonimizza SOLO le clip non ancora fatte (volti+targhe -> blur -> audit) ----
  for clip in "$d"/*.h264; do
    stem="$(basename "${clip%.h264}")"
    [ -f "$outdir/${stem}_anon.mp4" ] && continue     # idempotente
    echo "[$(ts)]   anon $stem ..." >> "$LOG"
    "$PY" "$ANON/anonymize.py" "$clip" -o "$outdir/${stem}_anon.mp4" \
          --backend yolo --margin 0.3 --window 5 >> "$LOG" 2>&1 || \
          echo "[$(ts)]   anon $stem FALLITO" >> "$LOG"
  done

  # ---- 2) GATE: a valle solo i video con verdetto PASS nel referto .audit.json ----
  #        (la firma di conformità resta a Daniele; i FAIL restano da rivedere)
  pass=0; fail=0
  for aud in "$outdir"/*.audit.json; do
    [ -f "$aud" ] || continue
    v=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$aud" 2>/dev/null)
    [ "$v" = "PASS" ] && pass=$((pass+1)) || fail=$((fail+1))
  done
  echo "[$(ts)] $name: anon fatto — PASS=$pass FAIL=$fail (a valle vanno solo i PASS)" >> "$LOG"

  # ---- 3) DEPTH / SEGMENTAZIONE sui _anon PASS (TODO: attivare quando c'è la calib metrica) ----
  #   calib: $DEPTH/calib_${name}.json  (da autorectify + muro-test col metro)
  #   - depth:  python3 $DEPTH/depth.py --video <anon PASS> --calib calib_${name}.json ...
  #   - segm.:  skill asmile-segmentazione-modello sugli _anon PASS
  #   (ragionamento headless opz.:  claude -p "...")
  if [ -f "$DEPTH/calib_${name}.json" ]; then
    echo "[$(ts)] $name: calib presente -> depth/seg sui PASS (da attivare)" >> "$LOG"
  else
    echo "[$(ts)] $name: MANCA calib_${name}.json -> prima autorectify + muro-test col metro" >> "$LOG"
  fi
done
echo "[$(ts)] on_new_videos END" >> "$LOG"
