#!/bin/bash
# verify_release.sh
# Verifies the cosign signature of an OTA release package.
# Used by ota_update.sh before handing any package to RAUC.
#
# Usage:  verify_release.sh <package.tar.gz> <package.sig>
# Exit:   0 = signature valid
#         1 = signature invalid or verification error
#
# Log:    /var/log/asmile_verify.log
# Key:    /home/$(whoami)/asmile/keys/cosign.pub
#
# Target: Raspberry Pi 5 (arm64, Debian Trixie)

set -uo pipefail   # note: no -e so we control exit codes explicitly

COSIGN_PUB="/home/$(whoami)/asmile/keys/cosign.pub"
LOG_FILE="/var/log/asmile_verify.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# ---- helpers ----------------------------------------------------------------

log() {
    echo "[${TIMESTAMP}] $*" | tee -a "${LOG_FILE}"
}

die() {
    log "FAIL: $*"
    exit 1
}

# ---- argument validation ----------------------------------------------------

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <package.tar.gz> <package.sig>" >&2
    exit 1
fi

PACKAGE="$1"
SIGFILE="$2"

log "=== verify_release.sh start ==="
log "Package : ${PACKAGE}"
log "Sig file: ${SIGFILE}"

# ---- pre-flight checks ------------------------------------------------------

if [[ ! -f "${COSIGN_PUB}" ]]; then
    die "Cosign public key not found at ${COSIGN_PUB}. Run import_cosign_key.sh first."
fi

if [[ ! -f "${PACKAGE}" ]]; then
    die "Package file not found: ${PACKAGE}"
fi

if [[ ! -f "${SIGFILE}" ]]; then
    die "Signature file not found: ${SIGFILE}"
fi

if ! command -v cosign &>/dev/null; then
    die "cosign not installed. Run install_cosign.sh first."
fi

# ---- verify -----------------------------------------------------------------

log "Running cosign verify-blob ..."

if cosign verify-blob \
        --key "${COSIGN_PUB}" \
        --signature "${SIGFILE}" \
        "${PACKAGE}" >> "${LOG_FILE}" 2>&1; then
    log "OK: Signature is VALID for ${PACKAGE}"
    exit 0
else
    die "Signature verification FAILED for ${PACKAGE}"
fi
