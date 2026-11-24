#!/bin/bash
# Deploy fix freno #001 (commit a8536c2c): ritorno a 0 con PWM lungo, pin in ingresso, guardia di rilascio.
# Live (overlay) + /media/root-ro, con backup .bak_20261124 per il rollback. Riavvia SOLO master_switch (non il Pi).
# Uso: bash deploy/deploy_freno_fix_20261124.sh [rollback]
set -euo pipefail
H=asmile@100.75.198.118
R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile
F="pi/autonomous/speed_limiter_v3/freno.py pi/autonomous/speed_limiter_v3/controllo.py pi/autonomous/speed_limiter_v3/hw.py
pi/autonomous/speed_limiter_v3/validazione.py pi/autonomous/speed_limiter_v3/test_rilascio_v3.py config/soglie_speed_limiter_v3.json
pi/power/master_switch.py"
cd "$(dirname "$0")/.."
PW=asmile
if [ "${1:-}" != rollback ]; then
  ssh $H "rm -rf /tmp/deploy_freno && mkdir -p /tmp/deploy_freno"
  for f in $F; do ssh $H "mkdir -p /tmp/deploy_freno/$(dirname $f)"; scp -q "$f" "$H:/tmp/deploy_freno/$f"; done
fi
ssh $H "echo $PW | sudo -S -p '' bash -s" <<EOF
set -e
mount -o remount,rw /media/root-ro
for base in $R /media/root-ro$R; do
  for f in $F; do
    if [ "${1:-}" = rollback ]; then
      if [ -f \$base/\$f.bak_20261124 ]; then cp -p \$base/\$f.bak_20261124 \$base/\$f; else [ \$f = pi/autonomous/speed_limiter_v3/test_rilascio_v3.py ] && rm -f \$base/\$f; fi
    else
      [ -f \$base/\$f ] && [ ! -f \$base/\$f.bak_20261124 ] && cp -p \$base/\$f \$base/\$f.bak_20261124
      cp /tmp/deploy_freno/\$f \$base/\$f
    fi
  done
done
sync; mount -o remount,ro /media/root-ro
cd $R && for f in $F; do md5sum \$f /media/root-ro$R/\$f; done
systemctl restart master_switch
sleep 4; systemctl is-active master_switch; pinctrl get 12
EOF
