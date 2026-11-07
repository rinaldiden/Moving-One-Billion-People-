#!/bin/bash
# deploy_sensor_hub.sh — porta un Pi della flotta al METODO UNICO di registrazione (2026-11-07):
# sensor_hub (CSV unico 50 Hz, t_ms = orologio dei frame), frame camera con SensorTimestamp,
# encoder con istante dell'Arduino, GPS 10 Hz. Chirurgico: backup .bak-<data>, scrive sia nella
# root viva sia nella root vera sotto overlay (/media/root-ro), niente git pull, niente reboot.
#
# Uso (dal Mac):  bash deploy/deploy_sensor_hub.sh 001     [--dry-run]
#                 bash deploy/deploy_sensor_hub.sh asmile2 [--dry-run]
#                 bash deploy/deploy_sensor_hub.sh logger  [--dry-run]
# Host sovrascrivibile:  HOST=192.168.1.108 bash deploy/deploy_sensor_hub.sh 001
#
# NON riavvia speed_limiter né recorder (li lancia master_switch con l'interruttore ON):
# il codice nuovo entra al prossimo ON. Se l'interruttore è ON lo dice e si ferma lì.
# NON riavvia master_switch (deve restare sempre su; al riavvio potrebbe pulsare il servo):
# il suo log delle uscite entra al prossimo boot. steering.service: riavvio solo se già attivo.
set -u
ROLE="${1:?ruolo: 001 | asmile2 | logger}"; DRY="${2:-}"
A="$(cd "$(dirname "$0")/.." && pwd)"                    # projects/asmile
STAMP=$(date +%Y%m%d)
case "$ROLE" in
  001)     HOST="${HOST:-100.75.198.118}"; U=asmile
           R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; HUB_DIR=$R/pi/sensors
           FILES="pi/sensors/sensor_hub.py pi/sensors/hub_client.py pi/sensors/actuator_log.py
                  pi/autonomous/speed_limiter.py pi/power/master_switch.py
                  pi/steering/steering_controller.py pi/steering/power_steering.py pi/autonomous/route_replay.py
                  pi/steering/usb_encoder_bridge.py pi/steering/flash_encoder_arduino.sh
                  pi/braking/servofreno_server.py pi/camera/dual_cam_recorder.py pi/camera/frame_times.py
                  firmware/steering/hex/amt22_dual_uno_v2_20261107.hex firmware/steering/FLASH_LOG.md"
           CONF_EXTRA="" ;;
  asmile2) HOST="${HOST:-192.168.1.119}"; U=asmile
           R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile; HUB_DIR=$R/pi/sensors
           FILES="pi/sensors/sensor_hub.py pi/sensors/hub_client.py pi/sensors/actuator_log.py
                  pi/autonomous/speed_limiter.py pi/power/master_switch.py
                  pi/steering/steering_controller.py pi/steering/power_steering.py pi/autonomous/route_replay.py
                  pi/steering/usb_encoder_bridge.py pi/braking/servofreno_server.py
                  pi/logging/training_recorder.py pi/camera/frame_times.py"
           CONF_EXTRA="HUB_VESC=1" ;;                    # il training_recorder leggeva il VESC: ora lo fa il hub
  logger)  HOST="${HOST:-100.83.200.55}"; U=asmile-logger
           R=/home/asmile-logger/logger; HUB_DIR=$R
           FILES="pi/sensors/sensor_hub.py=sensor_hub.py pi/sensors/hub_client.py=hub_client.py pi/sensors/actuator_log.py=actuator_log.py logger/recorder.sh=recorder.sh"
           CONF_EXTRA="" ;;
  *) echo "ruolo sconosciuto: $ROLE"; exit 1 ;;
esac
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $U@$HOST"
run() { echo "+ $*"; [ "$DRY" = "--dry-run" ] || $SSH "$@"; }

$SSH true || { echo "$HOST non raggiungibile"; exit 1; }
OVL=$($SSH 'mountpoint -q /media/root-ro && echo 1 || echo 0')
echo "== $ROLE @ $HOST (overlay=$OVL)"
if $SSH 'pgrep -f "[s]peed_limiter.py|[d]ual_cam_recorder.py|[t]raining_recorder.py" >/dev/null'; then
  echo "!! interruttore ON (limiter/recorder in corsa): spegnilo e rilancia. Nessuna modifica fatta."; exit 2
fi

$SSH "mkdir -p /tmp/hubdeploy"
[ "$OVL" = 1 ] && run "sudo mount -o remount,rw /media/root-ro"   # root vera scrivibile per le copie
for item in $FILES; do
  src="${item%%=*}"; dst="${item#*=}"; [ "$dst" = "$item" ] && dst="$src"
  scp -q -o BatchMode=yes "$A/$src" "$U@$HOST:/tmp/hubdeploy/$(basename "$dst")" || { echo "scp fallito: $src"; exit 1; }
  for root in "" $([ "$OVL" = 1 ] && echo /media/root-ro); do
    tgt="$root$R/$dst"
    run "sudo mkdir -p \$(dirname $tgt); [ -f $tgt ] && sudo cp -n $tgt $tgt.bak-$STAMP; sudo cp /tmp/hubdeploy/$(basename "$dst") $tgt"
  done
done

# unità systemd + attivazione per unità
sed "s#__HUB_DIR__#$HUB_DIR#" "$A/config/sensor_hub.service" > /tmp/sensor_hub.service.$ROLE
scp -q -o BatchMode=yes /tmp/sensor_hub.service.$ROLE "$U@$HOST:/tmp/hubdeploy/sensor_hub.service"
CONF=/home/$U/asmile_id.conf
for root in "" $([ "$OVL" = 1 ] && echo /media/root-ro); do
  run "sudo cp /tmp/hubdeploy/sensor_hub.service $root/etc/systemd/system/sensor_hub.service"
  run "sudo mkdir -p $root/etc/systemd/system/multi-user.target.wants && sudo ln -sf /etc/systemd/system/sensor_hub.service $root/etc/systemd/system/multi-user.target.wants/sensor_hub.service"
  run "sudo touch $root$CONF; grep -q '^SENSOR_HUB=' $root$CONF && sudo sed -i 's/^SENSOR_HUB=.*/SENSOR_HUB=1/' $root$CONF || echo SENSOR_HUB=1 | sudo tee -a $root$CONF >/dev/null"
  for kv in $CONF_EXTRA; do
    run "grep -q '^${kv%%=*}=' $root$CONF || echo $kv | sudo tee -a $root$CONF >/dev/null"
  done
done
[ "$OVL" = 1 ] && run "sync; sudo mount -o remount,ro /media/root-ro"

run "sudo mkdir -p /data/logging/sensors /data/firmware; sudo systemctl daemon-reload; sudo systemctl restart sensor_hub.service"
[ "$ROLE" != logger ] && run "sudo systemctl restart usb_encoder_bridge.service 2>/dev/null; sudo systemctl try-restart servofreno.service steering.service 2>/dev/null; true"
[ "$ROLE" = logger ] && run "sudo systemctl restart logger-recorder.service"
sleep 4
echo "== verifica"
run "systemctl is-active sensor_hub; ls -t /data/logging/sensors | head -2; f=\$(ls -t /data/logging/sensors/*.csv | head -1); wc -l \$f; tail -2 \$f; cat /tmp/encoder_fw_version 2>/dev/null"
echo "fatto. Backup: <file>.bak-$STAMP accanto a ogni file sostituito."
