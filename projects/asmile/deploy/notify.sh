#!/bin/bash
# notify.sh
# Sends a Telegram notification message via the Bot API.
# Used by ota_update.sh and other pipeline scripts to report status.
#
# Usage:  notify.sh "<message text>"
# Config: /home/asmile/asmile/.env  (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
# Log:    /var/log/asmile_notify.log
#
# Never blocks boot — all errors are caught and logged, script always exits 0.
#
# Target: Raspberry Pi 5 (arm64, Debian Trixie)

ENV_FILE="/home/asmile/asmile/.env"
LOG_FILE="/var/log/asmile_notify.log"
TELEGRAM_API="https://api.telegram.org"
CURL_TIMEOUT=5   # seconds

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[${TIMESTAMP}] $*" >> "${LOG_FILE}" 2>/dev/null || true
}

# ---- Validate argument -------------------------------------------------------

if [[ $# -lt 1 || -z "$1" ]]; then
    log "ERROR: No message provided. Usage: notify.sh <message>"
    exit 0   # never block
fi

MESSAGE="$1"

# ---- Load credentials -------------------------------------------------------

if [[ ! -f "${ENV_FILE}" ]]; then
    log "ERROR: .env file not found at ${ENV_FILE}. Cannot send notification."
    log "       Message was: ${MESSAGE}"
    exit 0
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    log "ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in ${ENV_FILE}."
    log "       Message was: ${MESSAGE}"
    exit 0
fi

# ---- Send notification -------------------------------------------------------

log "Sending notification: ${MESSAGE}"

HOSTNAME_VAL=$(hostname -s 2>/dev/null || echo "asmile-pi5")
FULL_MESSAGE="[${HOSTNAME_VAL}] ${MESSAGE}"

HTTP_CODE=$(curl -s -o /tmp/asmile_notify_resp.tmp -w "%{http_code}" \
    --max-time "${CURL_TIMEOUT}" \
    --connect-timeout "${CURL_TIMEOUT}" \
    -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"$(echo "${FULL_MESSAGE}" | sed 's/"/\\"/g')\"}" \
    2>/dev/null || echo "000")

if [[ "${HTTP_CODE}" == "200" ]]; then
    log "OK: Notification sent (HTTP ${HTTP_CODE})."
else
    RESP=$(cat /tmp/asmile_notify_resp.tmp 2>/dev/null || echo "(no response)")
    log "WARN: Notification failed (HTTP ${HTTP_CODE}). Response: ${RESP}"
fi

rm -f /tmp/asmile_notify_resp.tmp
exit 0   # never block boot
