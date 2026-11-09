#!/bin/bash
# deploy_bike_speed.sh — sensore velocità ruota BLE CooSpo BK467 su asmile-logger001 (2026-11-09).
# Installa: bike_speed_ble.py + sensor_hub.py (con colonne ble_* in coda) + servizio bike_speed (enabled,
# Restart=always) + bleak/dbus-fast in logger/vendor (persistente sotto overlay) + BIKE_SPEED_CIRC_M in
# asmile_id.conf. Scrive nella root viva E in /media/root-ro. Niente reboot; restart solo di sensor_hub
# e bike_speed. Backup .bak-<data>. Chiude con registra_deploy.sh.
# Uso (dal Mac):  bash deploy/deploy_bike_speed.sh [--dry-run]     (HOST=... sovrascrive)
# Rollback:       bash deploy/deploy_bike_speed.sh --rollback      (ripristina sensor_hub .bak, ferma+disabilita bike_speed)
set -u
MODE="${1:-}"   # --dry-run | --rollback | --force-moving (solo se Daniele lo dice)
A="$(cd "$(dirname "$0")/.." && pwd)"
STAMP=$(date +%Y%m%d)
HOST="${HOST:-100.83.200.55}"; U=asmile-logger; R=/home/asmile-logger/logger
CIRC=1.576
CIRC_SRC="Daniele 2026-11-09: stessa ruota di #001, metro 10 giri = 15.760 m (agents/rapporti/L0.encoder_ruota_metro_20261109.md)"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $U@$HOST"
PI_PW="${PI_PW:-asmile}"
run() {
  echo "+ $*"
  [ "$MODE" = "--dry-run" ] && return 0
  local cmd="${*//sudo /}"
  $SSH "echo '$PI_PW' | sudo -S -p '' bash -c $(printf %q "$cmd")" </dev/null || { echo "!! fallito: $*"; exit 3; }
}
$SSH true || { echo "$HOST non raggiungibile"; exit 1; }
[ "$($SSH hostname)" = asmile-logger ] || { echo "!! hostname diverso da asmile-logger: mi fermo"; exit 1; }
$SSH "echo '$PI_PW' | sudo -S -p '' true" </dev/null || { echo "!! sudo: password sbagliata"; exit 3; }
OVL=$($SSH 'mountpoint -q /media/root-ro && echo 1 || echo 0')
ROOTS=("" $([ "$OVL" = 1 ] && echo /media/root-ro))
# su QUALSIASI uscita (anche errore) la root vera torna read-only
restore_ro() { [ "$MODE" = "--dry-run" ] || [ "$OVL" != 1 ] || $SSH "echo '$PI_PW' | sudo -S -p '' bash -c 'sync; mount -o remount,ro /media/root-ro'" </dev/null >/dev/null 2>&1; }
trap restore_ro EXIT
echo "== logger @ $HOST (overlay=$OVL)"
# bici FERMA? (restart del hub solo a bici ferma): ~10 s di IMU dal CSV vivo, gyro/accel quasi costanti
if [ "$MODE" != "--force-moving" ]; then
  STILL=$($SSH 'f=$(ls -t /data/logging/sensors/sensors_*.csv | head -1); tail -n 520 "$f" | python3 -c "
import sys,csv,statistics as st
r=[l.split(\",\") for l in sys.stdin.read().splitlines()[1:]]
r=[x for x in r if len(x)>7 and x[2] and x[5]]
if len(r)<400: print(\"POCHI\",len(r)); sys.exit()
span=(int(r[-1][0])-int(r[0][0]))/1000
g=[(float(x[5])**2+float(x[6])**2+float(x[7])**2)**.5 for x in r]
a=[(float(x[2])**2+float(x[3])**2+float(x[4])**2)**.5 for x in r]
sg=max(st.pstdev([float(x[i]) for x in r]) for i in (5,6,7)); sa=st.pstdev(a)
print(\"FERMA\" if (sg<3 and sa<0.03 and span>=8) else \"MOVIMENTO\", \"span_s=%.1f gyro_std=%.2f acc_std=%.3f\"%(span,sg,sa))
"')
  echo "== IMU: $STILL"
  case "$STILL" in FERMA*) ;; *) echo "!! bici non ferma/dati insufficienti: NON deployo, riprova al rientro"; exit 4;; esac
fi
[ "$OVL" = 1 ] && run "mount -o remount,rw /media/root-ro"

if [ "$MODE" = "--rollback" ]; then
  for root in "${ROOTS[@]}"; do
    run "[ -f $root$R/sensor_hub.py.bak-bike ] && cp -p $root$R/sensor_hub.py.bak-bike $root$R/sensor_hub.py; rm -f $root/etc/systemd/system/multi-user.target.wants/bike_speed.service"
  done
  [ "$OVL" = 1 ] && run "sync; mount -o remount,ro /media/root-ro"
  run "systemctl stop bike_speed.service; systemctl daemon-reload; systemctl restart sensor_hub.service"
  echo "rollback fatto"; exit 0
fi

if [ "$MODE" != "--dry-run" ]; then
  $SSH "mkdir -p /tmp/hubdeploy"
  scp -q -o BatchMode=yes "$A/pi/sensors/sensor_hub.py" "$A/pi/sensors/bike_speed_ble.py" "$U@$HOST:/tmp/hubdeploy/" || exit 1
  sed "s#__HUB_DIR__#$R#" "$A/config/bike_speed_logger.service" > /tmp/bike_speed.service.logger
  scp -q -o BatchMode=yes /tmp/bike_speed.service.logger "$U@$HOST:/tmp/hubdeploy/bike_speed.service" || exit 1
fi
# bleak + dbus-fast (pure+wheel aarch64) in vendor/: installazione in live, poi copia nella root vera
run "[ -d $R/vendor/bleak ] || { rm -rf $R/vendor.new && python3 -m pip install -q --break-system-packages --target $R/vendor.new bleak && python3 -c \"import sys;sys.path.insert(0,'$R/vendor.new');import bleak,dbus_fast\" && mv $R/vendor.new $R/vendor; }"
for root in "${ROOTS[@]}"; do
  [ -n "$root" ] && run "mkdir -p $root$R && rm -rf $root$R/vendor.new && cp -a $R/vendor $root$R/vendor.new && rm -rf $root$R/vendor && mv $root$R/vendor.new $root$R/vendor"
  for f in sensor_hub.py bike_speed_ble.py; do
    run "tgt=$root$R/$f; if [ -f \$tgt ] && [ ! -f \$tgt.bak-$STAMP ]; then cp -p \$tgt \$tgt.bak-$STAMP; fi; [ $f = sensor_hub.py ] && [ ! -f \$tgt.bak-bike ] && cp -p \$tgt \$tgt.bak-bike; cp /tmp/hubdeploy/$f \$tgt; true"
  done
  run "cp /tmp/hubdeploy/bike_speed.service $root/etc/systemd/system/bike_speed.service && mkdir -p $root/etc/systemd/system/multi-user.target.wants && ln -sf /etc/systemd/system/bike_speed.service $root/etc/systemd/system/multi-user.target.wants/bike_speed.service"
  C=$root/home/$U/asmile_id.conf
  run "touch $C; grep -q '^BIKE_SPEED_CIRC_M=' $C && sed -i 's/^BIKE_SPEED_CIRC_M=.*/BIKE_SPEED_CIRC_M=$CIRC/' $C || { echo '# BIKE_SPEED_CIRC_M: $CIRC_SRC' >> $C; echo BIKE_SPEED_CIRC_M=$CIRC >> $C; }"
done
[ "$OVL" = 1 ] && run "sync; mount -o remount,ro /media/root-ro"
run "systemctl enable bluetooth.service 2>/dev/null; systemctl daemon-reload; systemctl restart sensor_hub.service; systemctl restart bike_speed.service"
sleep 6
echo "== verifica"
run "systemctl is-active bluetooth sensor_hub bike_speed; systemctl is-enabled bike_speed; journalctl -u bike_speed -n 8 --no-pager; cat /data/bike_speed_mac 2>/dev/null; cat /tmp/bike_speed.json 2>/dev/null; f=\$(ls -t /data/logging/sensors/sensors_*.csv | head -1); echo \$f; head -1 \$f | tr ',' '\\n' | tail -4; tail -1 \$f | awk -F, '{print NF, \$(NF-3), \$(NF-2), \$(NF-1), \$NF}'; true"
[ "$MODE" != "--dry-run" ] && bash "$A/deploy/registra_deploy.sh" logger "bike_speed BLE CooSpo BK467 $STAMP" deploy/deploy_bike_speed.sh pi/sensors/bike_speed_ble.py pi/sensors/sensor_hub.py config/bike_speed_logger.service
