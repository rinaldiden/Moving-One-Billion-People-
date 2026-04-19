#!/bin/bash
# ota_update.sh
# Full OTA update logic for the Asmile Pi 5.
# Fetches the latest release from GitHub, verifies the cosign signature,
# installs via RAUC, and sends Telegram notifications on success or failure.
#
# Design principle: ALL errors are non-blocking (exit 0).
# This script is run by asmile-ota.service at boot; it must never prevent
# the main application from starting.
#
# Log:    /var/log/asmile_ota.log
# Target: Raspberry Pi 5 (arm64, Debian Trixie), user asmile2

set -uo pipefail  # no -e: we handle errors explicitly

# ---- Configuration ----------------------------------------------------------

GITHUB_REPO="Moving-One-Billion-People-"
GITHUB_OWNER="rinaldiden"
GITHUB_API="https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest"

VERSION_FILE="/home/asmile2/asmile/current_version.txt"
OTA_TMP_DIR="/tmp/asmile_ota"
LOG_FILE="/var/log/asmile_ota.log"
LAST_CHECK_FILE="/home/asmile2/asmile/.last_ota_check"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="${SCRIPT_DIR}/verify_release.sh"
NOTIFY_SCRIPT="${SCRIPT_DIR}/notify.sh"
HEALTH_SCRIPT="${SCRIPT_DIR}/health_check.sh"

CURL_TIMEOUT=30            # seconds for release downloads
OTA_INTERVAL_HOURS=24      # rate limit: max 1 OTA check per day

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# ---- Helpers ----------------------------------------------------------------

log() {
    echo "[${TIMESTAMP}] $*" | tee -a "${LOG_FILE}"
}

notify() {
    if [[ -x "${NOTIFY_SCRIPT}" ]]; then
        bash "${NOTIFY_SCRIPT}" "$1" || true
    fi
}

# Non-blocking failure: log, notify, exit 0 to not block boot
fail() {
    log "FAIL: $*"
    notify "OTA FAIL: $*"
    exit 0
}

# ---- Step 0: Rate limiting ---------------------------------------------------

log "=== asmile OTA update start ==="

if [[ -f "${LAST_CHECK_FILE}" ]]; then
    last_check=$(cat "${LAST_CHECK_FILE}")
    now=$(date +%s)
    diff_hours=$(( (now - last_check) / 3600 ))
    if [[ $diff_hours -lt $OTA_INTERVAL_HOURS ]]; then
        log "INFO: Last check ${diff_hours}h ago (limit: ${OTA_INTERVAL_HOURS}h). Skipping."
        exit 0
    fi
fi

# ---- Step 1: Check connectivity ---------------------------------------------

if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
    log "INFO: No network connectivity. Skipping OTA check."
    exit 0
fi

log "INFO: Network OK."
date +%s > "${LAST_CHECK_FILE}"

# ---- Step 2: Fetch latest release from GitHub API ---------------------------

log "INFO: Querying GitHub API for latest release ..."

RELEASE_JSON=$(curl -fsSL --max-time "${CURL_TIMEOUT}" "${GITHUB_API}" 2>/dev/null) || \
    fail "Could not reach GitHub API at ${GITHUB_API}."

LATEST_TAG=$(echo "${RELEASE_JSON}" | grep '"tag_name"' | head -1 | \
    sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')

if [[ -z "${LATEST_TAG}" ]]; then
    fail "Could not parse tag_name from GitHub API response."
fi

log "INFO: Latest release tag: ${LATEST_TAG}"

# ---- Step 3: Compare with installed version ---------------------------------

CURRENT_VERSION=""
if [[ -f "${VERSION_FILE}" ]]; then
    CURRENT_VERSION=$(cat "${VERSION_FILE}" | tr -d '[:space:]')
fi

if [[ "${CURRENT_VERSION}" == "${LATEST_TAG}" ]]; then
    log "INFO: Already on latest version (${CURRENT_VERSION}). Nothing to do."
    exit 0
fi

log "INFO: Update available: ${CURRENT_VERSION:-<none>} → ${LATEST_TAG}"
notify "OTA: Update available ${CURRENT_VERSION:-<none>} → ${LATEST_TAG}. Starting download."

# ---- Step 4: Download .tar.gz and .sig to /tmp/asmile_ota/ -----------------

mkdir -p "${OTA_TMP_DIR}"

# Derive asset URLs from release JSON
PACKAGE_URL=$(echo "${RELEASE_JSON}" | grep '"browser_download_url"' | \
    grep '\.tar\.gz"' | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')
SIG_URL=$(echo "${RELEASE_JSON}" | grep '"browser_download_url"' | \
    grep '\.sig"' | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')

if [[ -z "${PACKAGE_URL}" ]]; then
    fail "No .tar.gz asset found in release ${LATEST_TAG}."
fi
if [[ -z "${SIG_URL}" ]]; then
    fail "No .sig asset found in release ${LATEST_TAG}."
fi

PACKAGE_FILE="${OTA_TMP_DIR}/asmile-${LATEST_TAG}.tar.gz"
SIG_FILE="${OTA_TMP_DIR}/asmile-${LATEST_TAG}.sig"

log "INFO: Downloading package from ${PACKAGE_URL} ..."
if ! curl -fsSL --max-time "${CURL_TIMEOUT}" -o "${PACKAGE_FILE}" "${PACKAGE_URL}"; then
    fail "Failed to download package from ${PACKAGE_URL}."
fi

log "INFO: Downloading signature from ${SIG_URL} ..."
if ! curl -fsSL --max-time "${CURL_TIMEOUT}" -o "${SIG_FILE}" "${SIG_URL}"; then
    fail "Failed to download signature from ${SIG_URL}."
fi

log "INFO: Download complete."

# ---- Step 5: Verify cosign signature ----------------------------------------

log "INFO: Verifying cosign signature ..."

if [[ ! -x "${VERIFY_SCRIPT}" ]]; then
    fail "verify_release.sh not found or not executable at ${VERIFY_SCRIPT}."
fi

if ! bash "${VERIFY_SCRIPT}" "${PACKAGE_FILE}" "${SIG_FILE}"; then
    # Cleanup untrusted files
    rm -f "${PACKAGE_FILE}" "${SIG_FILE}"
    fail "Signature verification failed for ${LATEST_TAG}. Aborting install."
fi

log "INFO: Signature verified OK."

# ---- Step 5b: SHA256 checksum (double verification) -------------------------

SHA256_URL=$(echo "${RELEASE_JSON}" | grep '"browser_download_url"' | \
    grep '\.sha256"' | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')

if [[ -n "${SHA256_URL}" ]]; then
    log "INFO: Verifying SHA256 checksum..."
    SHA256_FILE="${OTA_TMP_DIR}/checksum.sha256"
    curl -fsSL --max-time 10 -o "${SHA256_FILE}" "${SHA256_URL}" 2>/dev/null
    if [[ -f "${SHA256_FILE}" ]]; then
        expected=$(cat "${SHA256_FILE}" | awk '{print $1}')
        actual=$(sha256sum "${PACKAGE_FILE}" | awk '{print $1}')
        if [[ "${expected}" != "${actual}" ]]; then
            rm -f "${PACKAGE_FILE}" "${SIG_FILE}"
            fail "SHA256 mismatch! Expected: ${expected}, Got: ${actual}"
        fi
        log "INFO: SHA256 OK (${actual})"
    fi
else
    log "WARN: No .sha256 asset in release — skipping checksum (cosign verified)"
fi

# ---- Step 6: Install via RAUC -----------------------------------------------

log "INFO: Installing ${PACKAGE_FILE} via rauc ..."

if ! command -v rauc &>/dev/null; then
    fail "rauc not installed. Run rauc/setup_rauc.sh first."
fi

if ! rauc install "${PACKAGE_FILE}" >> "${LOG_FILE}" 2>&1; then
    fail "rauc install failed for ${PACKAGE_FILE}."
fi

log "INFO: rauc install complete."

# ---- Step 7: Update version file + notify success ---------------------------

echo "${LATEST_TAG}" > "${VERSION_FILE}"
chown asmile2:asmile2 "${VERSION_FILE}" 2>/dev/null || true

log "OK: OTA update to ${LATEST_TAG} successful. Reboot to activate new slot."
notify "OTA SUCCESS: Updated to ${LATEST_TAG}. Reboot scheduled."

# Clean up temp files
rm -f "${PACKAGE_FILE}" "${SIG_FILE}"

# Schedule a reboot in 60 seconds to allow the main service to complete its
# current session before activating the new RAUC slot.
log "INFO: Scheduling reboot in 60 seconds ..."
( sleep 60 && reboot ) &

exit 0
