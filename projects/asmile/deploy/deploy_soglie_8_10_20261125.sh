#!/bin/bash
# Deploy su #001 della SOLA configurazione del limiter v3 per la prova 8-10 km/h dolce (Daniele 25/11, "vai").
# Live + /media/root-ro, backup .bak_20261125. Nessun riavvio di servizi: il limiter legge il file al prossimo
# interruttore OFF->ON (lo avvia il master). Uso: bash deploy/deploy_soglie_8_10_20261125.sh [rollback]
set -euo pipefail
H=asmile@100.75.198.118; R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; PW=asmile
cd "$(dirname "$0")/.."
F=config/soglie_speed_limiter_v3.json
[ "${1:-}" != rollback ] && scp -q "$F" "$H:/tmp/soglie_8_10.json"
TMP=$(mktemp)
cat > "$TMP" <<EOS
set -e
mount -o remount,rw /media/root-ro
for base in $R /media/root-ro$R; do
  if [ "${1:-}" = rollback ]; then
    cp -p \$base/$F.bak_20261125 \$base/$F
  else
    [ -f \$base/$F.bak_20261125 ] || cp -p \$base/$F \$base/$F.bak_20261125
    cp /tmp/soglie_8_10.json \$base/$F
  fi
done
sync; mount -o remount,ro /media/root-ro
echo "\$(md5sum $R/$F | cut -c1-8) \$(md5sum /media/root-ro$R/$F | cut -c1-8) $F"
python3 -c "import json; c=json.load(open('$R/$F')); print('v_max', c['velocita']['v_max_kmh'], 'zona', c['velocita']['zona_inizio_kmh'], 'obiettivo', c['regolatore']['v_obiettivo_kmh'], 'tetto', c['freno']['tetto_deg'])"
pgrep -af speed_limiter_v3 || echo "limiter non in corsa: parte all'interruttore OFF->ON"
EOS
scp -q "$TMP" $H:/tmp/dep_soglie_run.sh; rm -f "$TMP"
ssh $H "echo $PW | sudo -S -p '' bash /tmp/dep_soglie_run.sh"
