#!/bin/bash
# Deploy su #001 del freno sul loop dell'encoder (main 14bebb6d: stimatore a pettine, contatto appreso, PI velocita',
# regola dura, correzione encoder 87be0cac) + sensor_hub del 7/11 con la sola scrittura /tmp/gps_state.json (fallback GPS+IMU).
# Live + /media/root-ro, backup .bak_20261124c. Riavvia sensor_hub e master_switch (NON il Pi). Ordine di Daniele 24/11 sera.
# Uso: bash deploy/deploy_freno_encoder_20261124.sh [rollback]
set -euo pipefail
H=asmile@100.75.198.118; R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; PW=asmile
cd "$(dirname "$0")/.."
L="pi/autonomous/speed_limiter_v3/controllo.py pi/autonomous/speed_limiter_v3/fonti.py pi/autonomous/speed_limiter_v3/freno.py pi/autonomous/speed_limiter_v3/scenari.py pi/autonomous/speed_limiter_v3/sim.py pi/autonomous/speed_limiter_v3/validazione.py pi/autonomous/speed_limiter_v3/test_fascia_contatto.py config/soglie_speed_limiter_v3.json"
if [ "${1:-}" != rollback ]; then
  ssh $H "rm -rf /tmp/dep_fe && mkdir -p /tmp/dep_fe/pi/autonomous/speed_limiter_v3 /tmp/dep_fe/config /tmp/dep_fe/pi/sensors"
  for f in $L; do scp -q "$f" "$H:/tmp/dep_fe/$f"; done
  scp -q fleet/001/patch/sensor_hub_001_20261124.py "$H:/tmp/dep_fe/pi/sensors/sensor_hub.py"
fi
F="$L pi/sensors/sensor_hub.py"
TMP=$(mktemp)
cat > "$TMP" <<EOS
set -e
mount -o remount,rw /media/root-ro
for base in $R /media/root-ro$R; do
  for f in $F; do
    if [ "${1:-}" = rollback ]; then
      if [ -f \$base/\$f.bak_20261124c ]; then cp -p \$base/\$f.bak_20261124c \$base/\$f; elif [ \$f = pi/autonomous/speed_limiter_v3/test_fascia_contatto.py ]; then rm -f \$base/\$f; fi
    else
      if [ -f \$base/\$f ] && [ ! -f \$base/\$f.bak_20261124c ]; then cp -p \$base/\$f \$base/\$f.bak_20261124c; fi
      cp /tmp/dep_fe/\$f \$base/\$f
    fi
  done
done
sync; mount -o remount,ro /media/root-ro
cd $R && for f in $F; do echo "\$(md5sum \$f | cut -c1-8) \$(md5sum /media/root-ro$R/\$f | cut -c1-8) \$f"; done
systemctl restart sensor_hub; sleep 3; systemctl restart master_switch
sleep 6; systemctl is-active sensor_hub master_switch; pinctrl get 12
EOS
scp -q "$TMP" $H:/tmp/dep_fe_run.sh; rm -f "$TMP"
ssh $H "echo $PW | sudo -S -p '' bash /tmp/dep_fe_run.sh"
