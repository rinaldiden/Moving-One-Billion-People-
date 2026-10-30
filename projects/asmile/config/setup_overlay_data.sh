#!/bin/bash
# ============================================================================
# setup_overlay_data.sh — STANDARD architettura anti-corruzione di OGNI asmile.
#
#   root in OVERLAY read-only (lo stacco corrente NON corrompe la SD)
#   + partizione /data ext4 persistente (recording, log, guida autonoma)
#
# Provato sul campo su asmile #001 (2026-10-30): stacco a caldo mentre registrava,
# ANCHE senza supercap → SD integra, tutto riparte, recording salvate. Il supercap
# diventa superfluo per la corruzione.
#
# RESUMABLE: rilancialo più volte; avanza di fase e dice quando RIAVVIARE.
#   sudo bash setup_overlay_data.sh   → reboot quando lo chiede → rilancia → ...
#
# Fasi: A) resize FS offline (reboot)  B) crea /data (p3)  C) bind + health env
#       D) overlay read-only + recurse=0 (reboot)  → FATTO.
# Recupero se un boot si rompe: SD→PC, togli overlayroot=... da cmdline.txt (boot FAT).
# ============================================================================
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "Esegui con sudo."; exit 1; }
USER_NAME="${SUDO_USER:-asmile}"; HOME_DIR="/home/$USER_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV=/dev/mmcblk0

echo "== setup_overlay_data (user=$USER_NAME) =="

# ---- FASE A: resize FS offline (solo se root ancora grande e /data assente) ----
if [ ! -b ${DEV}p3 ]; then
  ROOTFS_G=$(df -BG --output=size / | tail -1 | tr -dc 0-9)
  if [ "${ROOTFS_G:-0}" -gt 30 ]; then
    echo "[A] installo hook resize OFFLINE + fstab /data + initramfs"
    install -m0755 "$SCRIPT_DIR/../logger/data_partition/asmile_resize.hook"     /etc/initramfs-tools/hooks/asmile_resize
    install -m0755 "$SCRIPT_DIR/../logger/data_partition/asmile_resize.premount" /etc/initramfs-tools/scripts/init-premount/asmile_resize
    grep -q "LABEL=data" /etc/fstab || echo "LABEL=data /data ext4 defaults,noatime,nofail 0 2" >> /etc/fstab
    mkdir -p /data; update-initramfs -u
    echo ">>> RIAVVIA ORA (sudo reboot), poi rilancia questo script. <<<"; exit 0
  fi
  # ---- FASE B: FS già 18G, partizione da shrinkare + crea p3 (dal sistema vivo) ----
  echo "[B] shrink partizione p2 -> 20000MiB + crea /data (p3)"
  printf "Yes\nYes\n" | parted ---pretend-input-tty $DEV unit MiB resizepart 2 20000 || true
  parted -s $DEV unit MiB mkpart primary ext4 20001 100%
  partx -a -n 3 $DEV 2>/dev/null; partprobe $DEV; sleep 2
  mkfs.ext4 -F -L data ${DEV}p3
fi

# ---- FASE C: /data dirs + bind-mount + health env (idempotente) ----
echo "[C] /data dirs + bind-mount scritture persistenti + health env"
mkdir -p /data /data/training_sessions /data/logging /data/var_lib_asmile
mountpoint -q /data || mount /data || mount -a || true
[ -d "$HOME_DIR/training_sessions" ] && cp -an "$HOME_DIR/training_sessions/." /data/training_sessions/ 2>/dev/null || true
[ -d "$HOME_DIR/wip/logging" ]       && cp -an "$HOME_DIR/wip/logging/." /data/logging/ 2>/dev/null || true
[ -d /var/lib/asmile ]               && cp -an /var/lib/asmile/. /data/var_lib_asmile/ 2>/dev/null || true
chown -R "$USER_NAME:$USER_NAME" /data/training_sessions /data/logging 2>/dev/null || true
add() { grep -qF "$1" /etc/fstab || echo "$1" >> /etc/fstab; }
add "/data/training_sessions $HOME_DIR/training_sessions none bind,nofail 0 0"
add "/data/logging $HOME_DIR/wip/logging none bind,nofail 0 0"
add "/data/var_lib_asmile /var/lib/asmile none bind,nofail 0 0"
if [ -f /etc/systemd/system/asmile_health.service ] && ! grep -q ASMILE_HEALTH_LOG /etc/systemd/system/asmile_health.service; then
  sed -i "/^\[Service\]/a Environment=ASMILE_HEALTH_LOG=/data/asmile_health.csv" /etc/systemd/system/asmile_health.service
  systemctl daemon-reload
fi
mount -a || true

# ---- FASE D: overlay read-only + recurse=0 (ESSENZIALE: senza, overlaya /data) ----
if ! grep -q "overlayroot=tmpfs" /boot/firmware/cmdline.txt; then
  echo "[D] abilito OVERLAY read-only (anti-corruzione)"
  cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.pre-overlay
  raspi-config nonint enable_overlayfs
  sed -i "s/overlayroot=tmpfs /overlayroot=tmpfs:recurse=0 /" /boot/firmware/cmdline.txt
  echo ">>> RIAVVIA ORA. Dopo: root read-only, /data scrivibile. ARCHITETTURA COMPLETA. <<<"
elif ! grep -q "recurse=0" /boot/firmware/cmdline.txt; then
  sed -i "s/overlayroot=tmpfs /overlayroot=tmpfs:recurse=0 /" /boot/firmware/cmdline.txt
  echo ">>> recurse=0 aggiunto (ALTRIMENTI /data va in RAM). RIAVVIA ORA. <<<"
else
  echo "[D] overlay attivo con recurse=0 — ✅ ARCHITETTURA STANDARD COMPLETA"
  echo "    root:$(findmnt -no FSTYPE /)  /data:$(findmnt -no SOURCE,FSTYPE /data 2>/dev/null)"
fi
