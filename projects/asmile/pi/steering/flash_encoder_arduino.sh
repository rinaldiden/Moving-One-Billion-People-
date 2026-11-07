#!/bin/bash
# flash_encoder_arduino.sh — flasha l'Arduino Uno del ponte encoder (sterzo+ruota) DAL Pi
# e registra il flash nello storico. Nessun motore coinvolto: si ferma solo la lettura encoder
# per ~10 s (lo speed_limiter va in fallback finché il bridge non riparte).
#
# Uso (sul Pi, dalla cartella del repo):
#   sudo bash projects/asmile/pi/steering/flash_encoder_arduino.sh \
#        projects/asmile/firmware/steering/hex/amt22_dual_uno_v2_20261107.hex
#
# Storico:
#   - sul Pi:   /data/firmware/flash_history.csv  (persistente, fuori dall'overlay)
#   - nel repo: firmware/steering/FLASH_LOG.md     (lo script stampa la riga da aggiungere)
set -u
HEX="${1:?serve il file .hex (firmware/steering/hex/...)}"
PORT="${PORT:-/dev/ttyACM0}"
HIST_DIR=/data/firmware; [ -d /data ] || HIST_DIR="$HOME/firmware"
HIST="$HIST_DIR/flash_history.csv"
UNIT=$(grep -s '^ASMILE_NAME=' /home/asmile/asmile_id.conf | cut -d= -f2); UNIT=${UNIT:-$(hostname)}
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMMIT=$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo "?")
SHA=$(sha256sum "$HEX" | cut -c1-16)

command -v avrdude >/dev/null || { echo "manca avrdude: sudo apt install avrdude"; exit 1; }
[ -e "$PORT" ] || { echo "Arduino non trovato su $PORT"; exit 1; }
mkdir -p "$HIST_DIR"
[ -f "$HIST" ] || echo "data_ora,unita,hex,sha256_16,git_commit,esito,versione_letta" > "$HIST"

echo "== stop bridge encoder"
systemctl stop usb_encoder_bridge.service 2>/dev/null; pkill -f usb_encoder_bridge.py; sleep 1

echo "== flash $HEX -> $PORT"
if avrdude -p atmega328p -c arduino -P "$PORT" -b 115200 -D -U "flash:w:$HEX:i"; then ESITO=OK; else ESITO=FALLITO; fi

echo "== riavvio bridge"
systemctl start usb_encoder_bridge.service 2>/dev/null
VER="?"
for i in $(seq 1 10); do
  sleep 1
  [ -s /tmp/encoder_fw_version ] && VER=$(head -1 /tmp/encoder_fw_version) && [ "${VER#sconosciuta}" = "$VER" ] && break
done
NOW=$(date '+%Y-%m-%d %H:%M:%S')
echo "$NOW,$UNIT,$(basename "$HEX"),$SHA,$COMMIT,$ESITO,$VER" >> "$HIST"

echo
echo "esito: $ESITO   versione letta dal bridge: $VER"
echo "storico Pi: $HIST"
echo "riga per firmware/steering/FLASH_LOG.md:"
echo "| $NOW | $UNIT | $(basename "$HEX") | $SHA | $COMMIT | $ESITO | $VER |"
[ "$ESITO" = OK ] || exit 1
