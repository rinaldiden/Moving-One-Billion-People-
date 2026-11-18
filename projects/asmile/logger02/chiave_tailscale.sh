#!/bin/bash
# Scrive la chiave auth Tailscale nella NVS della A (mai nel firmware, mai su git).
# Serve SOLO se la A deve registrarsi da capo (NVS cancellata, scheda nuova, nodo tolto dal pannello):
# finché è registrata si ricollega da sola con le sue chiavi macchina.
#  1. pannello https://console.tailscale.com/admin/settings/keys → Generate auth key: monouso (non reusable),
#     non ephemeral, scadenza breve (1 giorno)
#  2. security add-generic-password -U -s claude-tailscale-logger02 -a logger02 -w   (incolla la chiave)
#  3. bash logger02/chiave_tailscale.sh   (in casa: LOGGER02_HOST=192.168.1.122) → riavvia la A
#  4. dal pannello: logger02 → Disable key expiry
# Uso: bash logger02/chiave_tailscale.sh [loggerNN]   (default logger02; nome = quello di flotta.csv)
set -u
N="${1:-logger02}"
riga=$(grep "^$N," "$(cd "$(dirname "$0")" && pwd)/flotta.csv") || { echo "$N non è in flotta.csv"; exit 1; }
TS=$(echo "$riga" | cut -d, -f8)
A="${LOGGER02_HOST:-${TS:-$(echo "$riga" | cut -d, -f2)}}"
K=$(security find-generic-password -s "claude-tailscale-$N" -a "$N" -w 2>/dev/null) || { echo "manca la chiave nel Portachiavi (claude-tailscale-$N)"; exit 1; }
printf '%s' "$K" | curl -s -m 15 -X POST --data-binary @- "http://$A/tskey"
