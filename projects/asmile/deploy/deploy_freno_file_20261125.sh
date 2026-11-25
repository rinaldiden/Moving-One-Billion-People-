#!/bin/bash
# Deploy su #001 di file del limiter v3 (live + /media/root-ro, backup .bak_<SUF>), controllo che il Pi accetti la config.
# Nessun riavvio: vale all'interruttore OFF->ON. Uso: SUF=20261125f bash deploy/deploy_freno_file_20261125.sh file1 file2 ...
set -euo pipefail
H=asmile@100.75.198.118; R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; PW=asmile; SUF=${SUF:?}
cd "$(dirname "$0")/.."
ssh $H "rm -rf /tmp/dep_ff && mkdir -p /tmp/dep_ff"
for f in "$@"; do ssh $H "mkdir -p /tmp/dep_ff/$(dirname $f)"; scp -q "$f" "$H:/tmp/dep_ff/$f"; done
TMP=$(mktemp)
{ echo "set -e; mount -o remount,rw /media/root-ro"
  for f in "$@"; do echo "for b in $R /media/root-ro$R; do [ -f \$b/$f.bak_$SUF ] || cp -p \$b/$f \$b/$f.bak_$SUF; cp /tmp/dep_ff/$f \$b/$f; done"; done
  echo "sync; mount -o remount,ro /media/root-ro"
  for f in "$@"; do echo "echo \$(md5sum $R/$f | cut -c1-8) \$(md5sum /media/root-ro$R/$f | cut -c1-8) $f"; done
  echo "cd $R/pi/autonomous && python3 -c \"import sys; sys.path.insert(0,'.'); from speed_limiter_v3.controllo import carica_soglie; carica_soglie(); print('VALIDA sul Pi')\""
} > "$TMP"
scp -q "$TMP" $H:/tmp/dep_ff_run.sh; rm -f "$TMP"
ssh $H "echo $PW | sudo -S -p '' bash /tmp/dep_ff_run.sh"
for f in "$@"; do echo "repo $(md5 -q $f | cut -c1-8) $f"; done
