#!/bin/bash
# Scrive la chiave auth Tailscale nella NVS della A (mai nel firmware, mai su git).
# Serve SOLO se la A deve registrarsi da capo (NVS cancellata, scheda nuova, nodo tolto dal pannello):
# finché è registrata si ricollega da sola con le sue chiavi macchina.
#  1. pannello https://console.tailscale.com/admin/settings/keys → Generate auth key: monouso (non reusable),
#     non ephemeral, scadenza breve (1 giorno)
#  2. security add-generic-password -U -s claude-tailscale-logger02 -a logger02 -w   (incolla la chiave)
#  3. bash logger02/chiave_tailscale.sh   (in casa: LOGGER02_HOST=192.168.1.122) → riavvia la A
#  4. dal pannello: logger02 → Disable key expiry
# Uso: bash logger02/chiave_tailscale.sh
set -u
A="${LOGGER02_HOST:-100.117.207.99}"
K=$(security find-generic-password -s claude-tailscale-logger02 -a logger02 -w 2>/dev/null) || { echo "manca la chiave nel Portachiavi (claude-tailscale-logger02)"; exit 1; }
printf '%s' "$K" | curl -s -m 15 -X POST --data-binary @- "http://$A/tskey"
