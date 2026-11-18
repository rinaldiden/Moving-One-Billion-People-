#!/bin/bash
# REGOLA di Daniele (18/11/2026): ogni modifica al firmware HW3 (cartella logger02) va su git E su TUTTI i logger
# HW3 di flotta.csv. Stesso firmware per tutti: l'identità (nome/ruolo/IP) sta nella NVS di ogni scheda.
# Un logger alla volta, in ognuno prima la A poi la B (ota.sh); al primo logger che fallisce mi fermo: gli altri
# restano com'erano. Un logger spento/fuori rete viene saltato e scritto: va aggiornato quando torna (rilancia).
# Uso: bash logger02/ota_flotta.sh            (usa firmware/build/logger02.bin già compilato)
#      bash logger02/ota_flotta.sh rollback
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
saltati=""
for L in $(tail -n +2 "$QUI/flotta.csv" | cut -d, -f1); do
    riga=$(grep "^$L," "$QUI/flotta.csv"); TS=$(echo "$riga" | cut -d, -f8); H=${TS:-$(echo "$riga" | cut -d, -f2)}
    if ! curl -s -m 6 "http://$H/api/stato" >/dev/null; then echo "== $L ($H) non risponde: saltato"; saltati="$saltati $L"; continue; fi
    echo "== $L ($H)"
    LOGGER=$L bash "$QUI/ota.sh" "$@" || { echo "STOP: $L non aggiornato, mi fermo qui"; exit 1; }
done
[ -z "$saltati" ] && echo "flotta HW3 tutta aggiornata" || { echo "DA AGGIORNARE quando tornano in rete:$saltati"; exit 2; }
