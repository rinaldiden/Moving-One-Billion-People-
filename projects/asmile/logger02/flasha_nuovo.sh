#!/bin/bash
# Logger HW3 nuovo (2 × ESP32-P4: A e B) pronto in un minuto, collegato al Mac col cavo, PRIMA di montarlo.
# Deciso da Daniele 18/11/2026: il prossimo è automaticamente logger03, poi 04...; si flashano sempre A e B;
# un solo IP fisso crescente (quello della A: da fuori il logger è un apparecchio solo, la B sta dietro la A).
#
#  1. nome = primo loggerNN libero in flotta.csv; IP = il più alto già usato + 1 (192.168.1.x)
#  2. compila il firmware (lo stesso per tutti i logger: l'identità sta nella NVS "ident", non nel .bin)
#  3. "attacca la A": aspetta la prima scheda che compare in USB → cancella, flasha, scrive NVS ident (A, nome, IP)
#     e la chiave Tailscale se c'è nel Portachiavi (claude-tailscale-<nome>; mai su git, mai nel .bin)
#  4. "attacca la B": la seconda scheda che compare → stessa cosa con ruolo B (DHCP)
#  5. scrive i MAC in flotta.csv e una riga in DEPLOY_LOG.md
# La A è quella cablata con IMU e partitore: attaccala per prima. Dopo: test (stato, voce, camere), poi si monta.
#
# Uso:  bash logger02/flasha_nuovo.sh              (nome e IP automatici)
#       bash logger02/flasha_nuovo.sh logger05     (nome scelto; IP sempre automatico)
#       SOLO=A bash logger02/flasha_nuovo.sh logger03   (rifà solo una scheda, es. dopo un cambio)
set -eu
QUI="$(cd "$(dirname "$0")" && pwd)"
FW="$QUI/firmware"
FLOTTA="$QUI/flotta.csv"
IDF="${IDF_PATH:-$HOME/esp/esp-idf-556}"
NVS_OFF=0x9000; NVS_DIM=0x6000           # come firmware/partitions.csv

# --- 1. nome e IP --------------------------------------------------------------------------------------
if [ -n "${1:-}" ]; then NOME="$1"
else
    n=$(cut -d, -f1 "$FLOTTA" | sed -n 's/^logger\([0-9][0-9]*\)$/\1/p' | sort -n | tail -1)
    NOME=$(printf 'logger%02d' $((10#$n + 1)))
fi
[[ "$NOME" =~ ^logger[0-9]{2,3}$ ]] || { echo "nome non valido: $NOME (es. logger03)"; exit 1; }
riga=$(grep "^$NOME," "$FLOTTA" || true)
if [ -n "$riga" ]; then
    IP=$(echo "$riga" | cut -d, -f2)
    [ -n "${SOLO:-}" ] || { echo "$NOME c'è già in flotta.csv ($IP). Per rifare una scheda: SOLO=A o SOLO=B"; exit 1; }
else
    ultimo=$(cut -d, -f2,3 "$FLOTTA" | tr ',' '\n' | sed -n 's/^192\.168\.1\.\([0-9]*\)$/\1/p' | sort -n | tail -1)
    IP="192.168.1.$((ultimo + 1))"
    ping -c 2 -t 2 "$IP" >/dev/null 2>&1 && { echo "STOP: $IP risponde già in rete, scegline un altro in flotta.csv"; exit 1; }
fi
echo "== $NOME · IP fisso della A: $IP · la B prende il DHCP"

# --- 2. firmware ---------------------------------------------------------------------------------------
. "$IDF/export.sh" >/dev/null
cd "$FW"
if [ ! -f sdkconfig.defaults.local ]; then
    PW=$(security find-generic-password -D 'AirPort network password' -a EOLO_378899 -w)
    printf 'CONFIG_EXAMPLE_WIFI_SSID="EOLO_378899"\nCONFIG_EXAMPLE_WIFI_PASSWORD="%s"\n' "$PW" > sdkconfig.defaults.local
    chmod 600 sdkconfig.defaults.local
fi
[ -f sdkconfig ] || idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.esp32p4;sdkconfig.defaults.local" set-target esp32p4 >/dev/null
idf.py build >/dev/null || { echo "compilazione fallita: idf.py build per vedere l'errore"; exit 1; }
bash "$QUI/controlla_segreti.sh" build/logger02.bin
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

porte() { ls /dev/cu.usbmodem* /dev/cu.wchusbserial* 2>/dev/null | sort; }

aspetta_scheda() {   # stampa la porta della prima scheda ESP nuova che compare (max 5 minuti)
    local prima ora p t0=$(date +%s)
    prima=$(porte)
    while [ $(( $(date +%s) - t0 )) -lt 300 ]; do
        sleep 2; ora=$(porte)
        for p in $(comm -13 <(echo "$prima") <(echo "$ora")); do
            sleep 2
            esptool.py --chip esp32p4 -p "$p" read_mac >/dev/null 2>&1 && { echo "$p"; return 0; }
        done
        prima=$ora
    done
    return 1
}

flasha() {   # $1 = A|B
    local R=$1 P MAC ascii csv
    echo; echo ">> attacca al Mac la scheda $R (cavo USB). $( [ "$R" = A ] && echo 'La A è quella con IMU e partitore.' || echo 'Lascia attaccata la A, va bene.')"
    P=$(aspetta_scheda) || { echo "nessuna scheda nuova in 5 minuti"; exit 1; }
    MAC=$(esptool.py --chip esp32p4 -p "$P" read_mac 2>/dev/null | sed -n 's/^MAC: *//p' | head -1)
    echo "   $R su $P, MAC $MAC"
    csv="$TMP/nvs_$R.csv"
    { echo "key,type,encoding,value"
      echo "ident,namespace,,"
      echo "nome,data,string,$NOME"
      echo "ruolo,data,u8,$([ "$R" = A ] && echo 65 || echo 66)"
      [ "$R" = A ] && echo "ip,data,string,$IP"
      if [ "$R" = A ] && K=$(security find-generic-password -s "claude-tailscale-$NOME" -a "$NOME" -w 2>/dev/null); then
          echo "logger02,namespace,,"; echo "ts_key,data,string,$K"
      fi; } > "$csv"
    chmod 600 "$csv"
    python "$IDF/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py" generate "$csv" "$TMP/nvs_$R.bin" $NVS_DIM >/dev/null
    idf.py -p "$P" erase-flash >/dev/null
    idf.py -p "$P" flash >/dev/null
    esptool.py --chip esp32p4 -p "$P" write_flash $NVS_OFF "$TMP/nvs_$R.bin" >/dev/null
    esptool.py --chip esp32p4 -p "$P" run >/dev/null 2>&1 || true
    rm -f "$csv"
    echo "   $R flashata: deve dire \"Narmadé Har\""
    eval "MAC_$R=\$MAC"
}

MAC_A=""; MAC_B=""
for R in A B; do [ -z "${SOLO:-}" ] || [ "$SOLO" = "$R" ] && flasha "$R"; done

# --- 5. registro ---------------------------------------------------------------------------------------
GIT=$(git -C "$QUI" describe --always --dirty 2>/dev/null)
if [ -z "$riga" ]; then echo "$NOME,$IP,,$MAC_A,$MAC_B,$(date +%F),$GIT," >> "$FLOTTA"
else
    python3 - "$FLOTTA" "$NOME" "$MAC_A" "$MAC_B" <<'EOF'
import sys,csv
f,nome,ma,mb=sys.argv[1:]; r=list(csv.reader(open(f)))
for x in r:
    if x[0]==nome:
        if ma: x[3]=ma
        if mb: x[4]=mb
csv.writer(open(f,'w'),lineterminator='\n').writerows(r)
EOF
fi
echo "| $(date '+%Y-%m-%d %H:%M') | $NOME ${SOLO:-A+B} | primo flash (cavo) | $GIT | A $MAC_A B $MAC_B |" >> "$QUI/DEPLOY_LOG.md"
grep -q "claude-tailscale-$NOME" <(security find-generic-password -s "claude-tailscale-$NOME" 2>/dev/null) \
    || echo "NB: nessuna chiave Tailscale per $NOME nel Portachiavi: la A va in rete solo in casa ($IP) finché non la metti (bash logger02/chiave_tailscale.sh $NOME), poi scrivi il suo IP Tailscale nella colonna tailscale di flotta.csv."
echo; echo "== $NOME pronto. Prova: curl http://$IP/api/stato ; curl http://$IP/b/api/stato ; pagina http://$IP/"
