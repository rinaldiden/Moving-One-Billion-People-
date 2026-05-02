#!/bin/bash
# push_session.sh
# Validates all data files in a session directory, then pushes them to the
# data/ branch of the GitHub repository using the asmile_data_key deploy key.
#
# Usage:  bash push_session.sh <session_directory>
#
# The session directory should contain only .bin, .json, or .csv files.
# All files are validated with validate_log.py before any git operation.
# If any file fails validation, nothing is pushed.
#
# Log:    /var/log/asmile_push.log
# Key:    ~/.ssh/asmile_data_key (configured by setup_deploy_key.sh)
# Repo:   /home/$(whoami)/wip/Moving-One-Billion-People-
# Target: Raspberry Pi 5 (arm64, Debian Trixie), user asmile

set -uo pipefail

REPO_DIR="/home/$(whoami)/wip/Moving-One-Billion-People-"
DATA_BRANCH="data"
DEPLOY_KEY="/home/$(whoami)/.ssh/asmile_data_key"
LOG_FILE="/var/log/asmile_push.log"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATE_SCRIPT="${SCRIPT_DIR}/validate_log.py"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# ---- Helpers ----------------------------------------------------------------

log() {
    echo "[${TIMESTAMP}] $*" | tee -a "${LOG_FILE}"
}

die() {
    log "FAIL: $*"
    exit 1
}

# ---- Argument validation ----------------------------------------------------

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "Usage: $0 <session_directory>" >&2
    exit 1
fi

SESSION_DIR="$1"

if [[ ! -d "${SESSION_DIR}" ]]; then
    die "Session directory not found: ${SESSION_DIR}"
fi

log "=== push_session.sh start: ${SESSION_DIR} ==="

# ---- Check dependencies -----------------------------------------------------

if [[ ! -f "${VALIDATE_SCRIPT}" ]]; then
    die "validate_log.py not found at ${VALIDATE_SCRIPT}"
fi

if ! command -v python3 &>/dev/null; then
    die "python3 is not installed."
fi

if [[ ! -f "${DEPLOY_KEY}" ]]; then
    die "Deploy key not found at ${DEPLOY_KEY}. Run setup_deploy_key.sh first."
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    die "Repository not found at ${REPO_DIR}"
fi

# ---- Step 1: Validate all files in session directory ------------------------

log "INFO: Validating files in ${SESSION_DIR} ..."

VALIDATION_FAILED=0
FILE_COUNT=0

while IFS= read -r -d '' FILE; do
    FILE_COUNT=$((FILE_COUNT + 1))
    log "INFO: Validating ${FILE} ..."
    if ! python3 "${VALIDATE_SCRIPT}" "${FILE}" >> "${LOG_FILE}" 2>&1; then
        log "FAIL: Validation failed for ${FILE}"
        VALIDATION_FAILED=1
    else
        log "OK:   ${FILE} passed."
    fi
done < <(find "${SESSION_DIR}" -maxdepth 1 -type f -print0)

if [[ "${FILE_COUNT}" -eq 0 ]]; then
    die "Session directory is empty: ${SESSION_DIR}"
fi

if [[ "${VALIDATION_FAILED}" -ne 0 ]]; then
    die "One or more files failed validation. Aborting push."
fi

log "INFO: All ${FILE_COUNT} file(s) passed validation."

# ---- Step 2: Push to data/ branch ------------------------------------------

# Use the deploy key for git operations
export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

SESSION_NAME=$(basename "${SESSION_DIR}")
DEST_PATH="sessions/${SESSION_NAME}"

cd "${REPO_DIR}"

log "INFO: Fetching and checking out ${DATA_BRANCH} branch ..."
git fetch origin "${DATA_BRANCH}" >> "${LOG_FILE}" 2>&1 || \
    die "Failed to fetch ${DATA_BRANCH} from origin."

git checkout "${DATA_BRANCH}" >> "${LOG_FILE}" 2>&1 || \
    die "Failed to checkout ${DATA_BRANCH} branch."

# Copy session files into the data branch directory
log "INFO: Copying session files to ${DEST_PATH} ..."
mkdir -p "${DEST_PATH}"
cp -r "${SESSION_DIR}/." "${DEST_PATH}/"

# Stage, commit, push
log "INFO: Staging files ..."
git add "${DEST_PATH}" >> "${LOG_FILE}" 2>&1 || \
    die "git add failed."

COMMIT_MSG="data: add session ${SESSION_NAME} [$(date '+%Y-%m-%dT%H:%M:%S')]"
log "INFO: Committing: ${COMMIT_MSG}"
git commit -m "${COMMIT_MSG}" >> "${LOG_FILE}" 2>&1 || \
    die "git commit failed (nothing to commit?)."

log "INFO: Pushing to origin/${DATA_BRANCH} ..."
git push origin "${DATA_BRANCH}" >> "${LOG_FILE}" 2>&1 || \
    die "git push failed. Check deploy key permissions on GitHub."

log "OK: Session ${SESSION_NAME} pushed to ${DATA_BRANCH} branch successfully."
exit 0
