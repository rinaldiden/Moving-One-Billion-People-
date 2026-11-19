#!/bin/bash
# Catena completa del PCB del logger HW4: piazzamento → fanout ai piani → coppie MIPI (A*) → Freerouting (N giri, tengo il migliore)
# → riempimenti/cucitura → DRC. Uso: bash costruisci_pcb.sh /percorso/freerouting.jar [passate] [giri]
# Metrica del migliore: 1000 × (errori DRC + collegamenti aperti) + differenza P/N massima delle coppie MIPI (mm).
set -e
cd "$(dirname "$0")"
KA=${KICAD_APP:-/Applications/KiCad/KiCad.app}
P=$KA/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
K=$KA/Contents/MacOS/kicad-cli
JAR=${1:?serve il percorso di freerouting.jar}
PASSI=${2:-80}
GIRI=${3:-3}
T=$(mktemp -d)
filtro() { grep -v -E "wxApp|Fontconfig|PCB_VIA::GetWidth" || true; }
$P genera_pcb.py 2>&1 | filtro
$P fanout.py 2>&1 | filtro
$P premipi.py 2>&1 | filtro | grep -E "coppia|NON" || true
cp logger_hw4.kicad_pcb "$T/piazzato.kicad_pcb"
MIGLIORE=999999
for g in $(seq 1 "$GIRI"); do
  cp "$T/piazzato.kicad_pcb" logger_hw4.kicad_pcb
  $P sbroglia.py --jar "$JAR" --passi "$PASSI" 2>&1 | filtro | tail -1
  $P unisci_vie.py 2>&1 | filtro | tail -1
  $P finitura.py 2>&1 | filtro | tail -1
  # collegamenti rimasti aperti: router A* nostro (pochi, corti), poi di nuovo DRC
  $K pcb drc --severity-error --format json -o "$T/drc0.json" logger_hw4.kicad_pcb >/dev/null 2>&1 || true
  $P completa.py "$T/drc0.json" 2>&1 | filtro
  $K pcb drc --severity-error --format json -o "$T/drc.json" logger_hw4.kicad_pcb >/dev/null 2>&1 || true
  PUNTI=$($P - "$T/drc.json" <<'PY' 2>/dev/null | tail -1
import json, sys, subprocess
d = json.load(open(sys.argv[1]))
err, unc = len(d['violations']), len(d['unconnected_items'])
out = subprocess.run([sys.executable, 'misura_piste.py'], capture_output=True, text=True).stdout
mm = max([float(l.split('differenza ')[1].split(' ')[0]) for l in out.splitlines() if l.startswith('coppia')] or [0])
print("%.1f %d %d %.1f" % (1000 * (err + unc) + mm, err, unc, mm))
PY
)
  echo "giro $g: punti/errori/aperti/MIPI-max = $PUNTI"
  p=${PUNTI%% *}
  if python3 -c "import sys; sys.exit(0 if float('$p') < float('$MIGLIORE') else 1)"; then
    MIGLIORE=$p; cp logger_hw4.kicad_pcb "$T/migliore.kicad_pcb"; cp sbroglio.log "$T/migliore.log"
  fi
done
cp "$T/migliore.kicad_pcb" logger_hw4.kicad_pcb; cp "$T/migliore.log" sbroglio.log
echo "tenuto il giro con punteggio $MIGLIORE"
# piste di potenza allargate dove c'è posto (DRC dopo, i segmenti che violano tornano come prima)
$P allarga.py "$K" 2>&1 | filtro | grep -E "allargati|giro|pulito|ATTENZIONE" || true
# vie e piste pendenti: solo quelle che segnala il DRC di KiCad (2 passate: togliere una via lascia un moncone)
for k in 1 2; do
  $K pcb drc --severity-all --format json -o "$T/tutto.json" logger_hw4.kicad_pcb >/dev/null 2>&1 || true
  $P togli_vie_pendenti.py "$T/tutto.json" 2>&1 | filtro | grep -v "memory leak" | tail -1
done
$K pcb drc --severity-all --format report -o DRC.rpt logger_hw4.kicad_pcb 2>&1 | grep -E "Found" || true
