#!/bin/bash
# ============================================================================
# restore_asmile_logger.sh — ripristino COMPLETO di asmile-logger in UN comando
# Pi5 + Arducam Camarray (Pivariety). Riporta tutto allo stato funzionante
# (camera + streaming + recorder + overlay FS) dopo un reflash.
#
# Prerequisiti su un OS appena flashato:
#   - hostname asmile-logger, utente asmile-logger, WiFi+SSH gia' configurati
#     (firstrun, vedi firstrun.sh.example / logger_provisioning.md)
#   - repo clonato, es: /home/asmile-logger/Moving-One-Billion-People-
#   - OVERLAY FS DISABILITATO (altrimenti le modifiche vanno in RAM e si perdono)
#       sudo raspi-config nonint disable_overlayfs && sudo reboot   # se serve
#
# Uso:  sudo bash projects/asmile/logger/restore_asmile_logger.sh
#       (al termine: sudo reboot)
# ============================================================================
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "Esegui con sudo."; exit 1; }

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
VISION="$REPO/projects/asmile/pi/vision"
LOGGER="$REPO/projects/asmile/logger"
USER_NAME="${SUDO_USER:-asmile-logger}"
HOME_DIR="/home/$USER_NAME"
STREAM_DIR="$HOME_DIR/streaming"
CFG="/boot/firmware/config.txt"

echo "== asmile-logger restore — utente $USER_NAME =="

echo "[1/6] Config camera (Arducam Camarray = dtoverlay=arducam-pivariety)"
cp "$CFG" "$CFG.bak.$(date +%s)"
sed -i 's/^camera_auto_detect=0/camera_auto_detect=1/' "$CFG"
sed -i '/dtoverlay=ov9281/d; /dtoverlay=camera-mux/d; /dtoverlay=arducam-pivariety/d' "$CFG"
echo 'dtoverlay=arducam-pivariety' >> "$CFG"

echo "[2/6] arducam_fix.so (shim arducam-pivariety -> ov9281)"
mkdir -p "$STREAM_DIR"
cp "$VISION/arducam_fix.c" "$STREAM_DIR/"
command -v gcc >/dev/null 2>&1 || { apt-get update -qq; apt-get install -y -qq gcc; }
gcc -shared -fPIC -O2 -o "$STREAM_DIR/arducam_fix.so" "$STREAM_DIR/arducam_fix.c" -ldl

echo "[3/7] script: stream + recorder + offload + cleanup"
cp "$LOGGER/stream_logger.py" "$STREAM_DIR/"
install -D -m 0755 "$LOGGER/recorder.sh"         "$HOME_DIR/logger/recorder.sh"
install -D -m 0755 "$LOGGER/offload_confirm.py"  "$HOME_DIR/logger/offload_confirm.py"
install -D -m 0755 "$LOGGER/cleanup.py"          "$HOME_DIR/logger/cleanup.py"
chown -R "$USER_NAME:$USER_NAME" "$STREAM_DIR" "$HOME_DIR/logger"

echo "[4/7] Servizio streaming — installato ma NON al boot (avvio manuale)"
# Al boot deve partire il RECORDING, non lo streaming (stessa camera = conflitto).
# Per guardare la camera: sudo systemctl start logger-stream  (poi stop; ferma il recorder nel frattempo).
sed "s/__USER__/$USER_NAME/g" "$LOGGER/logger-stream.service" \
    > /etc/systemd/system/logger-stream.service
systemctl daemon-reload
systemctl disable logger-stream.service 2>/dev/null || true

echo "[5/7] Servizio RECORDER (auto-start al boot, quando /data e' montata)"
sed "s/__USER__/$USER_NAME/g" "$LOGGER/logger-recorder.service" \
    > /etc/systemd/system/logger-recorder.service
systemctl enable logger-recorder.service || true
usermod -aG video,i2c "$USER_NAME" 2>/dev/null || true

echo "[6/7] Offload (Tailscale + prova + delete) + cleanup (>10gg, timer giornaliero)"
sed "s/__USER__/$USER_NAME/g" "$LOGGER/logger-offload.service"  > /etc/systemd/system/logger-offload.service
sed "s/__USER__/$USER_NAME/g" "$LOGGER/logger-cleanup.service"  > /etc/systemd/system/logger-cleanup.service
cp "$LOGGER/logger-cleanup.timer" /etc/systemd/system/logger-cleanup.timer
systemctl daemon-reload
systemctl enable logger-offload.service || true
systemctl enable logger-cleanup.timer || true
# NB offload invia solo se Tailscale e' attivo sul Pi + Mac Remote Login ON + chiave Pi nel Mac.

echo "[7/7] Overlay FS (root read-only, power-cut safe)"
raspi-config nonint enable_overlayfs

echo
echo "FATTO. Ora:  sudo reboot"
echo "Dopo il reboot: camera via arducam_fix.so, streaming http://<IP>:8080/,"
echo "recorder attivo se /data e' montata (crea la partizione dati a parte)."
