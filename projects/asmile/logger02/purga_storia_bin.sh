#!/bin/bash
# Toglie i firmware .bin di logger02/rilasci/ da TUTTA la storia di GitHub (17/11/2026: logger02_38fd492f-dirty.bin,
# commit 02e5b2a3, aveva dentro una chiave auth Tailscale → avviso secret scanning).
# FATTO il 17/11/2026 22:45 (Daniele: "sistema"): main su GitHub 02e5b2a3 → 68f929d8. La chiave era già morta (monouso, consumata dalla A, pannello: "invalidated"), quindi questo è pulizia, non emergenza.
#
# RISCRIVE LA STORIA E FA FORCE PUSH: parte solo con la firma di Daniele (D015) e con FIRMA=D015.
# Lavora su un clone --mirror in /tmp: il repo di lavoro (con le modifiche non committate degli agenti) non si tocca.
#
# Uso:  bash projects/asmile/logger02/purga_storia_bin.sh            → prova a secco: riscrive e controlla, NON spinge
#       FIRMA=D015 bash projects/asmile/logger02/purga_storia_bin.sh → riscrive, controlla e fa force push su GitHub
# Dopo il push, nel repo di lavoro:  git fetch origin && git rebase --onto origin/main 02e5b2a3 main
# (i commit locali dopo 02e5b2a3 si rimettono sopra la storia nuova; prima: niente agenti che committano).
set -eu
URL="https://github.com/rinaldiden/Moving-One-Billion-People-.git"
PERCORSO="projects/asmile/logger02/rilasci/"
DIR="/tmp/purga_logger02_$(date +%Y%m%d_%H%M%S).git"

command -v git-filter-repo >/dev/null || { echo "manca git-filter-repo (brew install git-filter-repo)"; exit 1; }
git clone -q --mirror "$URL" "$DIR"
cd "$DIR"
prima=$(git log --all --oneline -- "$PERCORSO" | wc -l | tr -d ' ')
echo "commit che toccano $PERCORSO prima: $prima"
# solo dal primo commit col .bin in poi: filter-repo toglie le firme GPG, su tutta la storia cambierebbe ogni hash
# (prova a secco del 17/11: si rompeva dal 7° commit, firmato da GitHub web). Così cambia solo 02e5b2a3 (e i successivi).
PRIMO=$(git log --all --format=%H -- "$PERCORSO" | tail -1)
RAMI=$(git branch --contains "$PRIMO" --format='%(refname:short)')
echo "primo commit col .bin: $PRIMO · rami: $RAMI"
git filter-repo --force --invert-paths --path "$PERCORSO" --refs $(for r in $RAMI; do echo "$PRIMO^..$r"; done)
dopo=$(git log --all --oneline -- "$PERCORSO" | wc -l | tr -d ' ')
echo "commit che toccano $PERCORSO dopo: $dopo"
[ "$dopo" = "0" ] || { echo "STOP: il percorso è ancora nella storia"; exit 1; }
if git rev-list --all --objects | git cat-file --batch-check='%(objectname) %(objecttype)' | awk '$2=="blob"{print $1}' \
   | git cat-file --batch 2>/dev/null | LC_ALL=C grep -q -a -E 'tskey-[a-z]+-[A-Za-z0-9]{6,}-[A-Za-z0-9]{12,}'; then
    echo "STOP: c'è ancora una chiave Tailscale da qualche parte nella storia"; exit 1
fi
echo "storia pulita: nessuna chiave Tailscale in nessun oggetto"
git log --oneline -3 main
uguale=$(git rev-parse "$PRIMO^")
git merge-base --is-ancestor "$uguale" main && echo "storia precedente intatta (hash invariati fino a ${uguale:0:8})" \
    || { echo "STOP: la riscrittura ha toccato commit prima di $PRIMO"; exit 1; }

if [ "${FIRMA:-}" != "D015" ]; then
    echo "prova a secco finita (clone in $DIR). Per spingere: FIRMA=D015 bash $0"
    exit 0
fi
git config --unset remote.origin.mirror 2>/dev/null || true   # 17/11: il clone --mirror rifiuta i refspec
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$URL"
git push --force origin 'refs/heads/*:refs/heads/*'
echo "fatto. Ora: 1) nel repo di lavoro git fetch origin && git rebase --onto origin/main 02e5b2a3 main"
echo "           2) GitHub → Security → Secret scanning → chiudi l'avviso come «Revoked»"
echo "           3) (facoltativo) GitHub Support per togliere il commit 02e5b2a3 dalla cache delle viste"
