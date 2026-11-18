#!/bin/bash
# Aggiorna logger02 via wifi (prima la A, poi la B passando dalla A) e lascia traccia per il rollback:
#  - il .bin va in logger02/rilasci/<versione>.bin (SOLO in locale: rilasci/ è in .gitignore dal 17/11, un .bin
#    su git aveva dentro la chiave Tailscale). Il rollback vero è sulla scheda: l'altra partizione OTA.
#  - prima di caricare, il .bin viene controllato: se contiene una chiave Tailscale o un valore di
#    firmware/sdkconfig.defaults.local (password, chiavi), mi fermo
#  - una riga per scheda in logger02/DEPLOY_LOG.md (su git)
#  - la scheda tiene il suo storico in NVS: GET /api/storia ; torna indietro con POST /rollback
# Uso:  bash logger02/ota.sh            (logger02; un altro: LOGGER=logger03 bash logger02/ota.sh)
#       bash logger02/ota.sh rollback   (A e B tornano alla versione precedente)
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
LOGGER="${LOGGER:-logger02}"                  # quale logger HW3 (flotta.csv); tutti insieme: ota_flotta.sh
riga=$(grep "^$LOGGER," "$(cd "$(dirname "$0")" && pwd)/flotta.csv") || { echo "$LOGGER non è in flotta.csv"; exit 1; }
TS=$(echo "$riga" | cut -d, -f8); LAN=$(echo "$riga" | cut -d, -f2)
A="${LOGGER02_HOST:-${TS:-$LAN}}"            # Tailscale se c'è, se no l'IP di casa della A
BIN="$QUI/firmware/build/logger02.bin"
LOG="$QUI/DEPLOY_LOG.md"

versione() { curl -s -m 8 "http://$A$1/api/stato" | python3 -c "import json,sys;print(json.load(sys.stdin)['versione'])" 2>/dev/null; }

aspetta() {   # aspetta che la scheda risponda con una versione diversa da $2 (max 150 s)
    local pref=$1 prima=$2 t0=$(date +%s) v
    while [ $(( $(date +%s) - t0 )) -lt 150 ]; do
        v=$(versione "$pref"); [ -n "$v" ] && [ "$v" != "$prima" ] && { echo "$v"; return 0; }
        sleep 5
    done
    return 1
}

scrivi_log() { echo "| $(date '+%Y-%m-%d %H:%M') | $LOGGER $1 | $2 | $3 | $4 |" >> "$LOG"; }
[ -f "$LOG" ] || printf "# logger02 — registro aggiornamenti (rollback: \`bash logger02/ota.sh rollback\`)\n\n| quando | scheda | da | a | esito |\n|---|---|---|---|---|\n" > "$LOG"

if [ "${1:-}" = "rollback" ]; then
    for pref in "" "/b"; do
        nome=$([ -z "$pref" ] && echo A || echo B); prima=$(versione "$pref")
        curl -s -m 20 -X POST "http://$A$pref/rollback"; echo
        dopo=$(aspetta "$pref" "$prima") && scrivi_log "$nome" "$prima" "$dopo" "ROLLBACK ok" || scrivi_log "$nome" "$prima" "?" "ROLLBACK non verificato"
    done
    exit 0
fi

[ -f "$BIN" ] || { echo "manca $BIN: compila prima"; exit 1; }
bash "$QUI/controlla_segreti.sh" "$BIN" || exit 1
mkdir -p "$QUI/rilasci"
GIT=$(git -C "$QUI" describe --always --dirty 2>/dev/null)
cp "$BIN" "$QUI/rilasci/logger02_$GIT.bin"

for pref in "" "/b"; do                         # A prima: se qualcosa va storto la B resta com'era
    nome=$([ -z "$pref" ] && echo A || echo B)
    prima=$(versione "$pref")
    ok=""
    for tentativo in 1 2 3; do
        r=$(curl -s -m 150 -X POST --data-binary @"$BIN" "http://$A$pref/ota")
        echo "$nome tentativo $tentativo: $r"
        if dopo=$(aspetta "$pref" "$prima"); then ok=1; break; fi
    done
    if [ -n "$ok" ]; then scrivi_log "$nome" "$prima" "$dopo" "ok ($GIT)"; echo "$nome: $prima -> $dopo"
    else scrivi_log "$nome" "$prima" "-" "FALLITO ($GIT)"; echo "$nome: aggiornamento NON riuscito, mi fermo"; exit 1; fi
done
