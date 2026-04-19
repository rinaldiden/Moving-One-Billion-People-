#!/bin/bash
# install_cosign.sh
# Downloads the latest cosign binary for linux/arm64 from GitHub Releases
# and installs it to /usr/local/bin/cosign.
#
# cosign is used to verify the cryptographic signature of OTA release packages
# before they are installed via RAUC.
#
# Target: Raspberry Pi 5 (arm64, Debian Trixie)
# Run as: sudo bash install_cosign.sh

set -euo pipefail

INSTALL_DIR="/usr/local/bin"
COSIGN_BIN="${INSTALL_DIR}/cosign"
RELEASES_API="https://api.github.com/repos/sigstore/cosign/releases/latest"

echo "=== Cosign Installer (linux/arm64) ==="
echo ""

# Resolve the latest release tag via GitHub API
echo "[INFO] Fetching latest cosign release tag from GitHub ..."
LATEST_TAG=$(curl -fsSL "${RELEASES_API}" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')

if [[ -z "${LATEST_TAG}" ]]; then
    echo "[ERROR] Could not determine latest cosign release. Check network connectivity."
    exit 1
fi

echo "[INFO] Latest release: ${LATEST_TAG}"

# Build download URL — cosign releases follow the pattern cosign-linux-arm64
ASSET_NAME="cosign-linux-arm64"
DOWNLOAD_URL="https://github.com/sigstore/cosign/releases/download/${LATEST_TAG}/${ASSET_NAME}"

TMP_FILE=$(mktemp /tmp/cosign.XXXXXX)

echo "[INFO] Downloading ${DOWNLOAD_URL} ..."
curl -fsSL -o "${TMP_FILE}" "${DOWNLOAD_URL}"

# Install
echo "[INFO] Installing to ${COSIGN_BIN} ..."
install -m 0755 "${TMP_FILE}" "${COSIGN_BIN}"
rm -f "${TMP_FILE}"

# Verify installation
echo "[INFO] Verifying installation ..."
cosign version

echo ""
echo "[OK] cosign installed successfully at ${COSIGN_BIN}."
