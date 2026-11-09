#!/bin/bash
# prova_bike_speed.sh — prove del gate per bike_speed sul logger (guardian VETO parziale 2026-11-09). Solo letture + il
# rollback/redeploy dello script + kill -9 del solo bike_speed. Niente reboot, recorder non toccato.
# Uso:  bash deploy/prova_bike_speed.sh rollback | crash | riavvio
#   rollback : --rollback, verifica (sensor_hub==.bak-bike in live e root-ro, wants assente, 48 colonne, recorder intatto), poi ri-deploy (52 col.)
#   crash    : kill -9 bike_speed → sensor_hub+recorder active, ble_* vuote entro 3 s, systemd riavvia entro ~10 s (NRestarts)
#   riavvio  : DOPO un riavvio vero (lo fa Daniele): bike_speed enabled+attivo, sensor_hub/IMU ok, 52 colonne, MAC in /data, ble_* (serve la ruota)
set -u
A="$(cd "$(dirname "$0")/.." && pwd)"
U=asmile-logger; HOST="${HOST:-100.83.200.55}"; R=/home/$U/logger; PW="${PI_PW:-asmile}"
ssh_() { ssh -o BatchMode=yes -o ConnectTimeout=8 $U@$HOST "$@"; }
sudo_() { ssh_ "echo '$PW' | sudo -S -p '' bash -c $(printf %q "$*")"; }
cols() { ssh_ 'f=$(ls -t /data/logging/sensors/sensors_*.csv|head -1); echo "$f: $(head -1 $f | awk -F, "{print NF}") colonne"; tail -1 $f | awk -F, "{print \"ble:\", \$(NF-3), \$(NF-2), \$(NF-1), \$NF}"'; }
rec() { ssh_ 'echo "recorder pid: $(pgrep -f recorder.sh | head -1) · rpicam-vid: $(pgrep -c rpicam-vid)"; systemctl is-active logger-recorder'; }
ssh_ true || { echo "logger non raggiungibile"; exit 1; }
case "${1:?rollback|crash|riavvio}" in
 rollback)
  rec
  bash "$A/deploy/deploy_bike_speed.sh" --rollback || exit 1
  sleep 8
  for r in "" /media/root-ro; do
    echo "== root '${r:-viva}'"; ssh_ "cmp $r$R/sensor_hub.py $r$R/sensor_hub.py.bak-bike && echo 'sensor_hub == bak-bike'; ls -l $r/etc/systemd/system/multi-user.target.wants/bike_speed.service 2>&1 | cut -c1-90"
  done
  ssh_ 'systemctl is-active sensor_hub bike_speed; systemctl is-enabled bike_speed'; cols; rec
  echo "== ri-deploy"; bash "$A/deploy/deploy_bike_speed.sh" || exit 1
  sleep 8; cols; rec ;;
 crash)
  ssh_ 'systemctl show bike_speed -p MainPID -p NRestarts'
  PID=$(ssh_ 'systemctl show bike_speed -p MainPID --value'); echo "kill -9 $PID"; sudo_ "kill -9 $PID"
  for i in 1 2 3 4; do sleep 1; echo "t+${i}s"; cols; done
  ssh_ 'systemctl is-active sensor_hub logger-recorder'
  sleep 8; ssh_ 'systemctl is-active bike_speed; systemctl show bike_speed -p MainPID -p NRestarts'; rec ;;
 riavvio)
  ssh_ 'uptime -s; systemctl is-active bluetooth sensor_hub bike_speed; systemctl is-enabled bike_speed; cat /data/bike_speed_mac; i2cdetect -y 1 | head -3; journalctl -u bike_speed -b --no-pager | cut -c40-160 | tail -6'; cols; rec
  echo "SERVE: ruota (poi rilancia 'riavvio' per vedere ble_* pieni)" ;;
esac
