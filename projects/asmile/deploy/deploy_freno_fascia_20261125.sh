#!/bin/bash
# Deploy su #001: freno con FASCIA DEL MORSO (Daniele 25/11 giro 12:08: "ti muovi li' attorno di pochi gradi, dolcemente,
# comandato da velocita' e decel; vieta spostamenti bruschi"). freno.py + validazione.py + soglie, live + /media/root-ro,
# backup .bak_20261125f. Nessun riavvio: vale al prossimo interruttore OFF->ON. Uso: bash deploy/deploy_freno_fascia_20261125.sh [rollback]
set -euo pipefail
H=asmile@100.75.198.118; R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; PW=asmile
cd "$(dirname "$0")/.."
FILES="config/soglie_speed_limiter_v3.json pi/autonomous/speed_limiter_v3/freno.py pi/autonomous/speed_limiter_v3/validazione.py"
if [ "${1:-}" != rollback ]; then for f in $FILES; do scp -q "$f" "$H:/tmp/dep_$(basename $f)"; done; fi
TMP=$(mktemp)
cat > "$TMP" <<EOS
set -e
mount -o remount,rw /media/root-ro
for base in $R /media/root-ro$R; do
  for f in $FILES; do
    if [ "${1:-}" = rollback ]; then cp -p \$base/\$f.bak_20261125f \$base/\$f
    else [ -f \$base/\$f.bak_20261125f ] || cp -p \$base/\$f \$base/\$f.bak_20261125f; cp /tmp/dep_\$(basename \$f) \$base/\$f; fi
  done
done
sync; mount -o remount,ro /media/root-ro
for f in $FILES; do echo "\$(md5sum $R/\$f | cut -c1-8) \$(md5sum /media/root-ro$R/\$f | cut -c1-8) \$f"; done
cd $R/pi/autonomous && python3 -c "import sys; sys.path.insert(0,'.'); from speed_limiter_v3.controllo import carica_soglie; from speed_limiter_v3 import freno; c=carica_soglie(); i=c['regolatore']['incrementale']; print('VALIDA sul Pi: fascia -%s/+%s chiude %s apre %s gradi/s' % (i['margine_morso_deg'], i['fascia_sopra_deg'], i['su_max_deg_s'], i['giu_max_deg_s']))"
pgrep -af speed_limiter_v3 || echo "limiter non in corsa: parte all'interruttore OFF->ON"
EOS
scp -q "$TMP" $H:/tmp/dep_fascia_run.sh; rm -f "$TMP"
ssh $H "echo $PW | sudo -S -p '' bash /tmp/dep_fascia_run.sh"
