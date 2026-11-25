#!/bin/bash
# Deploy su #001 della SOLA configurazione del limiter v3 per la prova loop decel-velocita senza tetti (Daniele 25/11 giro 4).
# Live + /media/root-ro, backup .bak_20261125d. Nessun riavvio di servizi: il limiter legge il file al prossimo
# interruttore OFF->ON (lo avvia il master). Uso: bash deploy/deploy_soglie_8_10_20261125.sh [rollback]
set -euo pipefail
H=asmile@100.75.198.118; R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; PW=asmile
cd "$(dirname "$0")/.."
F=config/soglie_speed_limiter_v3.json; V=pi/autonomous/speed_limiter_v3/validazione.py; P=pi/autonomous/speed_limiter_v3/freno.py
[ "${1:-}" != rollback ] && scp -q "$F" "$H:/tmp/soglie_8_10.json" && scp -q "$V" "$H:/tmp/validazione_25b.py" && scp -q "$P" "$H:/tmp/freno_25c.py"
TMP=$(mktemp)
cat > "$TMP" <<EOS
set -e
mount -o remount,rw /media/root-ro
for base in $R /media/root-ro$R; do
  if [ "${1:-}" = rollback ]; then
    cp -p \$base/$F.bak_20261125d \$base/$F; cp -p \$base/$V.bak_20261125d \$base/$V; cp -p \$base/$P.bak_20261125d \$base/$P
  else
    [ -f \$base/$V.bak_20261125d ] || cp -p \$base/$V \$base/$V.bak_20261125d
    cp /tmp/validazione_25b.py \$base/$V; [ -f \$base/$P.bak_20261125d ] || cp -p \$base/$P \$base/$P.bak_20261125d; cp /tmp/freno_25c.py \$base/$P
    [ -f \$base/$F.bak_20261125d ] || cp -p \$base/$F \$base/$F.bak_20261125d
    cp /tmp/soglie_8_10.json \$base/$F
  fi
done
sync; mount -o remount,ro /media/root-ro
echo "\$(md5sum $R/$F | cut -c1-8) \$(md5sum /media/root-ro$R/$F | cut -c1-8) $F"
echo "\$(md5sum $R/$V | cut -c1-8) \$(md5sum /media/root-ro$R/$V | cut -c1-8) $V"
cd $R/pi/autonomous && python3 -c "import sys; sys.path.insert(0,'.'); from speed_limiter_v3.controllo import carica_soglie; c=carica_soglie(); print('VALIDA sul Pi: base', c['freno']['contatto_min_deg']-c['freno']['margine_contatto_deg'], 'ingaggio', c['velocita']['zona_inizio_kmh']-c['regolatore']['ingaggio_sotto_zona_kmh'])"
python3 -c "import json; c=json.load(open('$R/$F')); print('v_max', c['velocita']['v_max_kmh'], 'zona', c['velocita']['zona_inizio_kmh'], 'obiettivo', c['regolatore']['v_obiettivo_kmh'], 'tetto', c['freno']['tetto_deg'])"
pgrep -af speed_limiter_v3 || echo "limiter non in corsa: parte all'interruttore OFF->ON"
EOS
scp -q "$TMP" $H:/tmp/dep_soglie_run.sh; rm -f "$TMP"
ssh $H "echo $PW | sudo -S -p '' bash /tmp/dep_soglie_run.sh"
