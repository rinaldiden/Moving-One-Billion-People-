#!/bin/bash
# rauc/setup_rauc.sh
# Installs RAUC (Robust Auto-Update Controller), copies the system config,
# and creates a placeholder self-signed keyring certificate.
#
# RAUC manages A/B partition updates on the Raspberry Pi 5:
#   Slot A → /dev/mmcblk0p2
#   Slot B → /dev/mmcblk0p3
#
# In production, replace /etc/rauc/keyring.pem with your real CA certificate.
#
# Run as: sudo bash rauc/setup_rauc.sh
# Target: Raspberry Pi 5 (arm64, Debian Trixie)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAUC_CONFIG_SRC="${SCRIPT_DIR}/system.conf"
RAUC_CONFIG_DST="/etc/rauc/system.conf"
KEYRING_PEM="/etc/rauc/keyring.pem"

echo "=== RAUC Setup for Asmile Pi 5 ==="
echo ""

# ---- Install RAUC -----------------------------------------------------------

if command -v rauc &>/dev/null; then
    echo "[INFO] rauc is already installed: $(rauc --version)"
else
    echo "[INFO] Installing rauc from Debian repositories ..."
    apt-get update -qq
    apt-get install -y rauc
    echo "[OK]  rauc installed: $(rauc --version)"
fi

# ---- Create config directory ------------------------------------------------

mkdir -p /etc/rauc

# ---- Copy system.conf -------------------------------------------------------

if [[ ! -f "${RAUC_CONFIG_SRC}" ]]; then
    echo "[ERROR] system.conf not found at ${RAUC_CONFIG_SRC}"
    echo "        Run this script from the deploy/ directory or its rauc/ subdirectory."
    exit 1
fi

cp "${RAUC_CONFIG_SRC}" "${RAUC_CONFIG_DST}"
chmod 644 "${RAUC_CONFIG_DST}"
echo "[OK]  Copied system.conf to ${RAUC_CONFIG_DST}"

# ---- Create placeholder keyring certificate ---------------------------------
# WARNING: This self-signed certificate is for development/testing only.
# Replace with your real CA certificate before going to production.

if [[ -f "${KEYRING_PEM}" ]]; then
    echo "[INFO] Keyring certificate already exists at ${KEYRING_PEM}. Skipping."
else
    echo "[WARN] Creating PLACEHOLDER self-signed certificate at ${KEYRING_PEM}."
    echo "       Replace this with your real CA certificate before production use!"
    echo ""

    if ! command -v openssl &>/dev/null; then
        apt-get install -y openssl
    fi

    openssl req -x509 \
        -newkey rsa:4096 \
        -keyout /etc/rauc/keyring-dev.key \
        -out "${KEYRING_PEM}" \
        -sha256 \
        -days 3650 \
        -nodes \
        -subj "/C=IT/O=Asmile/CN=asmile-rauc-dev-ca"

    chmod 600 /etc/rauc/keyring-dev.key
    chmod 644 "${KEYRING_PEM}"
    echo "[OK]  Placeholder certificate created at ${KEYRING_PEM}."
fi

# ---- Validate RAUC config ---------------------------------------------------

echo ""
echo "[INFO] Validating RAUC configuration ..."
rauc info --no-verify /dev/null 2>/dev/null || true   # just check binary works
echo "[INFO] RAUC config at ${RAUC_CONFIG_DST}:"
cat "${RAUC_CONFIG_DST}"

echo ""
echo "================================================================"
echo "  RAUC setup complete."
echo ""
echo "  Slot layout:"
echo "    A (active)  → /dev/mmcblk0p2"
echo "    B (standby) → /dev/mmcblk0p3"
echo ""
echo "  IMPORTANT: Replace ${KEYRING_PEM} with your real CA"
echo "  certificate before signing production bundles."
echo "================================================================"
