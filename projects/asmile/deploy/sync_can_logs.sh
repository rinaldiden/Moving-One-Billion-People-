#!/bin/bash
# sync_can_logs.sh
# Salva sul Mac tutti i logging CAN di OGGI dal raspi, anche quelli in corso,
# e continua a salvarli fin quando il raspi resta acceso.
#
# Gira SUL MAC (non sul Pi). Fa il pull, non il push: legge dal Pi in sola
# lettura (rsync) e scrive solo sul Mac. Non tocca nulla sul raspi, mai.
#
# "Logging CAN" su Asmile = i CSV che gli script sterzo VESC scrivono in
#   ~/wip/logging/vesc/   (return_duty_*.csv, return_rpm_*.csv, return_*.csv)
# più eventuali dump grezzi del bus (candump*.log). Filtro: percorso che
# contiene "vesc" o "can", modificato oggi.
#
# Cosa fa, in loop finché il Pi è acceso:
#   1. trova il raspi (alias ssh o IP; l'IP cambia su hotspot → riprova la lista)
#   2. elenca sul Pi i file CAN di oggi (find -newermt "oggi 00:00")
#   3. li rsync-a sul Mac preservando la struttura, anche mentre crescono
#      (--partial --inplace: i file "in corso" si aggiornano a delta)
#   4. dorme INTERVAL secondi e ripete
#   5. quando il Pi non risponde per OFF_THRESHOLD cicli di fila → "raspi
#      spento" → esce pulito (0). I blip di rete brevi non fermano il loop.
#
# Uso:
#   bash sync_can_logs.sh                 # loop continuo, autodiscovery del Pi
#   bash sync_can_logs.sh --once          # un solo giro (utile per test)
#   bash sync_can_logs.sh --host asmile2  # forza un host/alias/ip
#   bash sync_can_logs.sh --dest ~/mydir  # cambia la cartella di destinazione
#   bash sync_can_logs.sh --interval 3    # cadenza in secondi (default 5)
#
# In background (così Daniele lo lascia girare e chiude il terminale):
#   nohup bash sync_can_logs.sh >/dev/null 2>&1 &
#
# Destinazione Mac (default): ~/asmile-data/can-logs/<host>/wip/logging/...
#   fuori dal repo di proposito: sono dati del Pi, non codice (niente commit).
#
# Log locale: <dest>/_sync.log
# Target Pi: Raspberry Pi 5, user asmile, repo/dati in /home/asmile/wip/

set -uo pipefail

# ---- Configurazione (override via env o flag) -------------------------------

# Candidati Pi provati in ordine finché uno risponde. L'IP su hotspot cambia,
# quindi teniamo sia gli alias ~/.ssh/config sia gli IP statici noti.
DEFAULT_CANDIDATES=(asmile asmile2 asmile@192.168.1.108 asmile2@192.168.1.119)

DEST="${ASMILE_CAN_DEST:-$HOME/asmile-data/can-logs}"
INTERVAL="${ASMILE_SYNC_INTERVAL:-5}"     # secondi tra un giro e l'altro
OFF_THRESHOLD="${ASMILE_OFF_THRESHOLD:-6}" # cicli di silenzio → "Pi spento"
STARTUP_WAIT="${ASMILE_STARTUP_WAIT:-60}"  # sec di attesa al primo aggancio
CONNECT_TIMEOUT=5                          # ssh ConnectTimeout
REMOTE_ROOTS="${ASMILE_LOG_ROOTS:-wip/logging}"  # radici (relative a ~) da scandire
FORCED_HOST=""
RUN_ONCE=0

# ---- Parse argomenti --------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --once)     RUN_ONCE=1; shift ;;
        --host)     FORCED_HOST="${2:-}"; shift 2 ;;
        --dest)     DEST="${2:-}"; shift 2 ;;
        --interval) INTERVAL="${2:-}"; shift 2 ;;
        -h|--help)
            sed -n '2,40p' "$0"; exit 0 ;;
        *)
            echo "Argomento sconosciuto: $1" >&2; exit 1 ;;
    esac
done

mkdir -p "$DEST"
LOG_FILE="$DEST/_sync.log"

log() {
    local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new)

# ---- Discovery del Pi -------------------------------------------------------
# Ritorna (su stdout) il primo target raggiungibile, o vuoto.
discover_pi() {
    local cands=()
    if [[ -n "$FORCED_HOST" ]]; then
        cands=("$FORCED_HOST")
    else
        cands=("${DEFAULT_CANDIDATES[@]}")
    fi
    local c
    for c in "${cands[@]}"; do
        if ssh "${SSH_OPTS[@]}" "$c" true 2>/dev/null; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

# ---- Un giro di sync --------------------------------------------------------
# $1 = target ssh. Ritorna 0 se il giro è andato (Pi vivo), 1 se il Pi non
# risponde durante il giro.
sync_once() {
    local target="$1"
    local today; today="$(date +%F)"

    # Comando remoto: elenca i file CAN di oggi, NUL-delimited, relativi a ~.
    local find_expr
    printf -v find_expr 'cd "$HOME" 2>/dev/null || exit 0; for r in %s; do [ -d "$r" ] && find "$r" -type f \\( -ipath "*vesc*" -o -ipath "*can*" \\) -newermt "%s 00:00:00" -print0 2>/dev/null; done' \
        "$REMOTE_ROOTS" "$today"

    # Lista dei file su una var (per contarli e riusarla in rsync).
    local list
    if ! list="$(ssh "${SSH_OPTS[@]}" "$target" "$find_expr" 2>/dev/null)"; then
        return 1   # Pi non ha risposto
    fi

    local n
    n="$(printf '%s' "$list" | tr -dc '\0' | wc -c | tr -d ' ')"
    if [[ "$n" -eq 0 ]]; then
        log "nessun logging CAN di oggi ($today) su $target — in attesa"
        return 0
    fi

    local outdir="$DEST/${target//[:@\/]/_}"
    mkdir -p "$outdir"

    # rsync a delta, tiene i file parziali/in-crescita, preserva la struttura.
    # --files-from da stdin (NUL-delimited) → solo i file CAN di oggi.
    if printf '%s' "$list" | rsync -az --partial --inplace --from0 \
            --files-from=- \
            --out-format='  ↳ %n (%b B)' \
            -e "ssh ${SSH_OPTS[*]}" \
            "$target:" "$outdir/" >>"$LOG_FILE" 2>&1; then
        log "sync OK: $n file CAN di oggi da $target → $outdir"
        return 0
    else
        local rc=$?
        # rsync 255 = errore ssh (Pi sparito a metà); altri = da segnalare
        if [[ $rc -eq 255 ]]; then
            return 1
        fi
        log "rsync warning (rc=$rc) da $target — riprovo al prossimo giro"
        return 0
    fi
}

# ---- Main loop --------------------------------------------------------------

trap 'log "interrotto (segnale) — esco"; exit 0' INT TERM

log "=== sync_can_logs start — dest: $DEST — intervallo ${INTERVAL}s ==="

# Aggancio iniziale: aspetta che il Pi compaia (fino a STARTUP_WAIT).
TARGET=""
waited=0
while :; do
    if TARGET="$(discover_pi)"; then
        log "raspi trovato: $TARGET"
        break
    fi
    if [[ $waited -ge $STARTUP_WAIT ]]; then
        log "raspi non raggiungibile dopo ${STARTUP_WAIT}s — è spento o Mac su rete diversa. Esco."
        exit 2
    fi
    log "raspi non ancora raggiungibile — riprovo... (${waited}/${STARTUP_WAIT}s)"
    sleep "$INTERVAL"
    waited=$((waited + INTERVAL))
done

# Primo sync subito.
sync_once "$TARGET" || true

if [[ $RUN_ONCE -eq 1 ]]; then
    log "modalità --once: fatto un giro, esco."
    exit 0
fi

# Loop finché il Pi è acceso.
misses=0
while :; do
    sleep "$INTERVAL"

    if sync_once "$TARGET"; then
        misses=0
        continue
    fi

    # Il Pi non ha risposto in questo giro.
    misses=$((misses + 1))
    log "raspi $TARGET non risponde ($misses/$OFF_THRESHOLD)"

    if [[ $misses -ge $OFF_THRESHOLD ]]; then
        log "raspi spento (silenzio per $OFF_THRESHOLD cicli) — sync terminato. Buona notte 🙏"
        exit 0
    fi

    # Prima di arrendersi, ri-cerca il Pi (magari è cambiato IP su hotspot).
    if NEWT="$(discover_pi)"; then
        if [[ "$NEWT" != "$TARGET" ]]; then
            log "raspi ricomparso su nuovo target: $NEWT"
        fi
        TARGET="$NEWT"
        misses=0
    fi
done
