#!/bin/bash
# autoupdate.sh — al boot aggiorna il repo asmile (git pull --ff-only) e, se il
# codice e' cambiato, lancia l'eventuale hook post_update.sh della flotta.
# NON blocca mai il boot: su qualunque errore esce 0. Attende la rete, poi pulla.
# Sicuro: --ff-only non forza, non perde modifiche locali (in quel caso salta).
#
# REPO: da env ASMILE_REPO, altrimenti auto-individuato dalla posizione dello script.
set -uo pipefail

REPO="${ASMILE_REPO:-$(cd "$(dirname "$0")/../../.." 2>/dev/null && pwd)}"
LOG="/var/log/asmile_autoupdate.log"
exec >>"$LOG" 2>&1

echo "=== $(date -Iseconds) autoupdate ($REPO) ==="
[ -d "$REPO/.git" ] || { echo "repo non trovato: $REPO"; exit 0; }
cd "$REPO" || exit 0

# attende rete (max ~60s)
for i in $(seq 1 30); do
  timeout 8 git ls-remote origin -h >/dev/null 2>&1 && break
  sleep 2
done

BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
if timeout 60 git pull --ff-only --quiet 2>&1; then
  AFTER="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  if [ "$BEFORE" != "$AFTER" ]; then
    echo "aggiornato $BEFORE -> $AFTER"
    HOOK="$REPO/projects/asmile/config/post_update.sh"
    [ -x "$HOOK" ] && { echo "eseguo post_update.sh"; "$HOOK" || true; }
  else
    echo "gia' aggiornato ($AFTER)"
  fi
else
  echo "pull non fast-forward (modifiche locali o offline) - skip, repo invariato"
fi
echo "=== fine autoupdate ==="
exit 0
