#!/bin/bash
# offload.sh — push delle clip nuove dal logger al Mac, ripartibile.
#
# Due modi d'uso:
#   - SUL PI (push): invia /data/recordings al Mac via Tailscale, con retry.
#       bash offload.sh push
#   - SUL MAC (pull): tira le clip dal logger (riusa il pattern sync_can_logs.sh).
#       bash offload.sh pull
#
# Trasporto sicuro cross-NAT = Tailscale (vedi bom_logger_video_standalone.md).
# `rsync --partial --append-verify` riprende i trasferimenti interrotti (4G ballerino).
set -uo pipefail

MODE="${1:-push}"
MAC_HOST="${MAC_HOST:-100.87.2.77}"        # macbook-pro-di-daniele (Tailscale)
MAC_USER="${MAC_USER:-rinaldiden}"
MAC_DEST="${MAC_DEST:-~/asmile-data/video}"
PI_HOST="${PI_HOST:-asmile-logger.local}"
PI_USER="${PI_USER:-asmile}"
SRC="/data/recordings"

case "$MODE" in
  push)
    echo "push $SRC -> ${MAC_USER}@${MAC_HOST}:${MAC_DEST}"
    while :; do
      if rsync -az --partial --append-verify --remove-source-files=false \
          -e ssh "$SRC/" "${MAC_USER}@${MAC_HOST}:${MAC_DEST}/"; then
        echo "sync OK"; break
      fi
      echo "Mac non raggiungibile / rete assente — riprovo tra 60s"; sleep 60
    done
    ;;
  pull)
    echo "pull ${PI_USER}@${PI_HOST}:${SRC} -> locale"
    rsync -az --partial --append-verify --info=progress2 \
      -e ssh "${PI_USER}@${PI_HOST}:${SRC}/" "${HOME}/asmile-data/video/"
    ;;
  *) echo "uso: offload.sh [push|pull]"; exit 1 ;;
esac
