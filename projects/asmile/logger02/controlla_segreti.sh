#!/bin/bash
# Controlla che un firmware (.bin) non abbia dentro segreti. Lo chiama ota.sh prima di ogni aggiornamento.
#  - qualsiasi chiave Tailscale (tskey-...)
#  - qualsiasi valore di firmware/sdkconfig.defaults.local tranne SSID e password wifi (quelle servono alla
#    scheda e il .bin non va più su git)
# Uso: bash logger02/controlla_segreti.sh firmware/build/logger02.bin   → esce 1 se trova qualcosa (senza stamparlo)
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
BIN="${1:?uso: controlla_segreti.sh <file.bin>}"
LOCALE="$QUI/firmware/sdkconfig.defaults.local"
male=0
if LC_ALL=C grep -q -a -E 'tskey-[a-z]+-[A-Za-z0-9]{6,}-[A-Za-z0-9]{12,}' "$BIN"; then
    echo "STOP: $BIN contiene una chiave Tailscale (tskey-...). La chiave va nella NVS: bash logger02/chiave_tailscale.sh"
    male=1
fi
if [ -f "$LOCALE" ]; then
    while IFS= read -r riga; do
        nome="${riga%%=*}"; val="${riga#*=\"}"; val="${val%\"}"
        case "$nome" in CONFIG_EXAMPLE_WIFI_SSID|CONFIG_EXAMPLE_WIFI_PASSWORD) continue ;; esac
        [ ${#val} -ge 8 ] || continue
        if LC_ALL=C grep -q -a -F -- "$val" "$BIN"; then echo "STOP: $BIN contiene il valore di $nome (da sdkconfig.defaults.local)"; male=1; fi
    done < <(grep -E '^CONFIG_[A-Z0-9_]+="' "$LOCALE")
fi
[ $male -eq 0 ] && echo "segreti: nessuno nel firmware"
exit $male
