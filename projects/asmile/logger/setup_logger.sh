#!/bin/bash
# setup_logger.sh — setup ON-PI (una volta sola) per asmile-logger (Pi 5).
# Esegui dopo il primo boot:  sudo bash setup_logger.sh
#
# 1) crea la partizione dati /data dallo spazio libero della SD (NON sotto overlay)
# 2) installa il servizio recorder
# 3) abilita l'overlay FS sulla root (ULTIMO: dopo, la root e' read-only)
#
# ATTENZIONE: va lanciato PRIMA di abilitare l'overlay (serve scrivere su root).
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "Esegui con sudo."; exit 1; }

USER_NAME="asmile"
HOME_DIR="/home/${USER_NAME}"
DATA_PART_LABEL="data"

echo "== 1) partizione dati /data =="
# individua il device della root (es. /dev/mmcblk0p2 -> disco /dev/mmcblk0)
ROOT_SRC="$(findmnt -no SOURCE /)"
DISK="/dev/$(lsblk -no PKNAME "$ROOT_SRC")"
echo "root=$ROOT_SRC disco=$DISK"

if ! blkid -L "$DATA_PART_LABEL" >/dev/null 2>&1; then
  # NB: l'immagine RPi auto-espande la root al primo boot. Per avere spazio per
  # /data, qui NON ri-espandiamo: creiamo una 3a partizione nello spazio libero.
  # Se la root ha gia' riempito la SD, riduci prima la root (vedi README).
  echo "Creo partizione dati nello spazio libero di $DISK ..."
  parted -s "$DISK" --align optimal mkpart primary ext4 70% 100%
  partprobe "$DISK"; sleep 2
  NEWPART="$(lsblk -nrpo NAME "$DISK" | tail -1)"
  mkfs.ext4 -F -L "$DATA_PART_LABEL" "$NEWPART"
else
  echo "Partizione '$DATA_PART_LABEL' gia' presente."
fi

mkdir -p /data
if ! grep -q 'LABEL=data' /etc/fstab; then
  echo "LABEL=${DATA_PART_LABEL} /data ext4 defaults,noatime,nofail 0 2" >> /etc/fstab
fi
mount -a || true
mkdir -p /data/recordings
chown -R "${USER_NAME}:${USER_NAME}" /data
echo "/data montata: $(findmnt -no TARGET,SOURCE /data 2>/dev/null || echo NO)"

echo "== 2) servizio recorder =="
install -D -m 0755 "${HOME_DIR}/logger/recorder.sh" "${HOME_DIR}/logger/recorder.sh"
install -m 0644 "${HOME_DIR}/logger/logger-recorder.service" /etc/systemd/system/logger-recorder.service
systemctl daemon-reload
systemctl enable logger-recorder.service
echo "servizio abilitato (parte al prossimo boot, quando /data e' montata)."

echo "== 3) overlay FS (root read-only) =="
echo "Abilito overlay: dopo questo, la root e' read-only e si puo' staccare la corrente."
raspi-config nonint enable_overlayfs
echo
echo "FATTO. Riavvia:  sudo reboot"
echo "Dopo il reboot: root in overlay (RAM), /data scrivibile, recorder attivo."
echo "Per modifiche future: raspi-config nonint disable_overlayfs -> reboot -> modifica -> ri-abilita."
