#!/usr/bin/env bash
# Flash dell'ESP32 via WiFi (OTA) — nessun cavo USB.
# Requisiti sul PC: arduino-cli + core esp32 + python3, stessa rete WiFi (SpadaBike).
# Uso:  ./flash_ota.sh [IP]      (default: esp32.local)
set -e

IP="${1:-esp32.local}"
OTA_PASS="otabike"
FQBN="esp32:esp32:esp32"
SKETCH="$(cd "$(dirname "$0")" && pwd)/esp32_wifi"

echo ">> compilo $SKETCH"
arduino-cli compile --fqbn "$FQBN" "$SKETCH"

echo ">> flash OTA su $IP"
arduino-cli upload -p "$IP" --fqbn "$FQBN" \
  --upload-field password="$OTA_PASS" "$SKETCH"

echo ">> fatto. Verifico:"
sleep 6
curl -s -m 5 "http://$IP/" | grep -oE "ESP32 online|Uptime[^<]*" || echo "(web non ancora su, riprova tra qualche secondo)"
