#!/bin/bash
# registra_deploy.sh — dopo OGNI deploy su un Pi: fotografa la config che gira davvero sul Pi, la mette
# nel repo (projects/asmile/fleet/<ruolo>/) e fa commit + push su GitHub. Così resta traccia di cosa
# gira su ogni unità e quando (deciso da Daniele 2026-11-09).
#
# Uso (dal Mac):  bash deploy/registra_deploy.sh 001 "sensor_hub v2 + encoder fw 20261107" [file deployati...]
#                 bash deploy/registra_deploy.sh logger "recorder a segmenti" logger/recorder.sh
#   --no-push     come ultimo argomento: commit locale senza push
# Host sovrascrivibile: HOST=192.168.1.108 bash deploy/registra_deploy.sh 001 "..."
#
# Cosa prende dal Pi (sola lettura, niente riavvii): /var/lib/asmile/*.json (calibrazioni, es. encoder),
# ~/asmile_id.conf, i file .service di asmile, servizi attivi/abilitati, sha256 del codice in pi/ e logger/,
# commit git del repo sul Pi, kernel. Mai video, mai log grossi, mai segreti (.env escluso).
# Il commit tocca SOLO fleet/<ruolo>/ e i file passati come argomento: il resto del working tree resta com'è.
set -u
ROLE="${1:?ruolo: 001 | asmile2 | logger}"; MSG="${2:?descrizione del deploy}"; shift 2
PUSH=1; EXTRA=()
for f in "$@"; do [ "$f" = --no-push ] && PUSH=0 || EXTRA+=("$f"); done
A="$(cd "$(dirname "$0")/.." && pwd)"                    # projects/asmile
case "$ROLE" in
  001)     HOST="${HOST:-100.75.198.118}"; U=asmile;        R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile ;;
  asmile2) HOST="${HOST:-192.168.1.119}";  U=asmile;        R=/home/asmile/wip/Moving-One-Billion-People-/projects/asmile ;;
  logger)  HOST="${HOST:-100.83.200.55}";  U=asmile-logger; R=/home/asmile-logger/logger ;;
  *) echo "ruolo sconosciuto: $ROLE"; exit 1 ;;
esac
OUT="$A/fleet/$ROLE"; mkdir -p "$OUT/var_lib_asmile" "$OUT/systemd"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $U@$HOST"

if $SSH true 2>/dev/null; then
  echo "== fotografo $ROLE ($HOST)"
  $SSH "cd /var/lib/asmile 2>/dev/null && tar cf - --exclude='*.env' *.json *.conf 2>/dev/null" | tar xf - -C "$OUT/var_lib_asmile" 2>/dev/null
  $SSH "cat ~/asmile_id.conf 2>/dev/null" > "$OUT/asmile_id.conf"
  $SSH "cat /boot/firmware/config.txt 2>/dev/null; echo '# --- modules-load.d ---'; cat /etc/modules-load.d/*.conf 2>/dev/null" > "$OUT/boot_config.txt"
  $SSH "cd /etc/systemd/system && tar cf - \$(ls *.service 2>/dev/null | grep -Ei 'asmile|sensor|encoder|speed|servo|steer|master|camera|logger|record|shutdown') 2>/dev/null" \
    | tar xf - -C "$OUT/systemd" 2>/dev/null
  {
    echo "# $ROLE — stato fotografato $(date '+%Y-%m-%d %H:%M') dopo: $MSG"
    echo "kernel: $($SSH 'uname -r')"
    echo "git sul Pi: $($SSH "cd $R && git log -1 --format='%h %ad %s' --date=short 2>/dev/null || echo 'nessun git'")"
    echo "overlay: $($SSH 'mountpoint -q /media/root-ro && echo si || echo no')"
    echo; echo "## servizi attivi"
    $SSH "systemctl list-units --type=service --state=active --no-legend | awk '{print \$1}' | grep -Ei 'asmile|sensor|encoder|speed|servo|steer|master|camera|logger|record|shutdown|tailscale'"
    echo; echo "## servizi abilitati al boot"
    $SSH "systemctl list-unit-files --state=enabled --no-legend | awk '{print \$1}' | grep -Ei 'asmile|sensor|encoder|speed|servo|steer|master|camera|logger|record|shutdown|tailscale'"
  } > "$OUT/STATO.md"
  # sha256 del codice sul Pi, confrontato col repo del Mac: "≠" = sul Pi gira una versione diversa
  $SSH "cd $R && find . -path ./node_modules -prune -o \( -name '*.py' -o -name '*.sh' -o -name '*.hex' \) -print0 2>/dev/null | xargs -0 sha256sum" \
    | sort -k2 > "$OUT/codice_sul_pi.sha256"
  REPO_BASE="$A"; [ "$ROLE" = logger ] && REPO_BASE="$A/logger"
  awk '{print $2}' "$OUT/codice_sul_pi.sha256" | while read -r p; do
    pi=$(grep -F "  $p" "$OUT/codice_sul_pi.sha256" | head -1 | cut -c1-64)
    if [ -f "$REPO_BASE/$p" ]; then mac=$(shasum -a 256 "$REPO_BASE/$p" | cut -c1-64)
      [ "$pi" = "$mac" ] || echo "≠ $p"
    else echo "solo-Pi $p"; fi
  done > "$OUT/differenze_dal_repo.txt"
  echo "   $(wc -l < "$OUT/differenze_dal_repo.txt" | tr -d ' ') file diversi dal repo (fleet/$ROLE/differenze_dal_repo.txt)"
else
  echo "⚠ $ROLE ($HOST) non raggiungibile: registro solo il messaggio e i file passati"
fi
echo "- $(date '+%Y-%m-%d %H:%M') $ROLE: $MSG ${EXTRA[*]+${EXTRA[*]}}" >> "$A/fleet/DEPLOY_LOG.md"

cd "$A"
PATHS=("fleet/$ROLE" "fleet/DEPLOY_LOG.md" ${EXTRA[@]+"${EXTRA[@]}"})   # bash 3.2 del Mac: array vuoto + set -u
git add -- "${PATHS[@]}"
if git diff --cached --quiet -- "${PATHS[@]}"; then echo "niente di nuovo da registrare"; exit 0; fi
git commit -q -m "deploy $ROLE: $MSG" -m "Fotografia config dal Pi in projects/asmile/fleet/$ROLE (registra_deploy.sh)." -- "${PATHS[@]}" \
  && echo "commit: $(git log -1 --format='%h %s')"
[ "$PUSH" = 1 ] && git push -q origin HEAD && echo "push fatto su GitHub"
