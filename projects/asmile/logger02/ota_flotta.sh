#!/bin/bash
# REGOLA FERREA di Daniele (18/11/2026, fino a nuovo ordine): MAI aggiornamenti a tutta la flotta "a vacca".
# Ogni modifica va SOLO sul logger di prova di Daniele (LOGGER_PROVA, oggi logger02) con ota.sh; il resto della
# flotta si aggiorna SOLO quando Daniele lo decide, dopo averlo provato e visto funzionare lui sul suo logger.
# Questo script quindi parte solo con OK_DANIELE="<sue parole, canale, ora>" e solo se il logger di prova gira già
# esattamente il firmware compilato da distribuire. Il logger di prova lo salta (è già aggiornato).
# Un logger alla volta, in ognuno prima la A poi la B (ota.sh); al primo logger che fallisce mi fermo: gli altri
# restano com'erano. Un logger spento/fuori rete viene saltato e scritto: va aggiornato quando torna (rilancia).
# Uso: bash logger02/ota_flotta.sh            (usa firmware/build/logger02.bin già compilato)
#      bash logger02/ota_flotta.sh rollback
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
PROVA="${LOGGER_PROVA:-logger02}"
[ -n "${OK_DANIELE:-}" ] || { echo "STOP: la flotta si aggiorna solo con l'ok di Daniele dopo la sua prova su $PROVA (OK_DANIELE=\"...\"). Per $PROVA: bash logger02/ota.sh"; exit 1; }
BIN="$QUI/firmware/build/logger02.bin"
VB=$(python3 - "$BIN" <<'PY'
import sys
b=open(sys.argv[1],'rb').read(); d=b[0x20:0x120]   # esp_app_desc_t: dopo header immagine (24 B) + header segmento (8 B)
v=d[0x10:0x30].split(b'\0')[0].decode(); t=d[0x50:0x60].split(b'\0')[0].decode(); dt=d[0x60:0x70].split(b'\0')[0].decode()
print(f"{v} {dt} {t}")
PY
)
rp=$(grep "^$PROVA," "$QUI/flotta.csv"); HP=$(echo "$rp" | cut -d, -f8); HP=${HP:-$(echo "$rp" | cut -d, -f2)}
VP=$(curl -s -m 8 "http://$HP/api/stato" | python3 -c "import json,sys;print(json.load(sys.stdin)['versione'])" 2>/dev/null)
[ "$VP" = "$VB" ] || { echo "STOP: $PROVA gira «$VP», il .bin è «$VB»: prima va provato su $PROVA"; exit 1; }
echo "ok di Daniele: $OK_DANIELE · firmware già provato su $PROVA: $VB" | tee -a "$QUI/DEPLOY_LOG.md"
saltati=""
for L in $(tail -n +2 "$QUI/flotta.csv" | cut -d, -f1 | grep -v "^$PROVA$"); do
    riga=$(grep "^$L," "$QUI/flotta.csv"); TS=$(echo "$riga" | cut -d, -f8); H=${TS:-$(echo "$riga" | cut -d, -f2)}
    if ! curl -s -m 6 "http://$H/api/stato" >/dev/null; then echo "== $L ($H) non risponde: saltato"; saltati="$saltati $L"; continue; fi
    echo "== $L ($H)"
    LOGGER=$L bash "$QUI/ota.sh" "$@" || { echo "STOP: $L non aggiornato, mi fermo qui"; exit 1; }
done
[ -z "$saltati" ] && echo "flotta HW3 tutta aggiornata" || { echo "DA AGGIORNARE quando tornano in rete:$saltati"; exit 2; }
