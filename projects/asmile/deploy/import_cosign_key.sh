#!/bin/bash
# import_cosign_key.sh
# Copies the cosign public key from a USB drive to ~/asmile/keys/.
# This public key is used by verify_release.sh to authenticate OTA packages.
#
# Expected USB mount point: /media/usb/
# Expected source file:     /media/usb/cosign.pub
# Destination:              /home/asmile/asmile/keys/cosign.pub
#
# Run as: bash import_cosign_key.sh  (does NOT require root)
# Target: Raspberry Pi 5 (arm64, Debian Trixie), user asmile

set -euo pipefail

USB_MOUNT="/media/usb"
SOURCE_KEY="${USB_MOUNT}/cosign.pub"
DEST_DIR="/home/asmile/asmile/keys"
DEST_KEY="${DEST_DIR}/cosign.pub"

echo "=== Asmile Cosign Public Key Import ==="
echo ""

# Check USB is mounted
if [[ ! -d "${USB_MOUNT}" ]]; then
    echo "[ERROR] USB mount point ${USB_MOUNT} does not exist."
    echo "        Mount the USB drive first:  sudo mount /dev/sdX1 ${USB_MOUNT}"
    exit 1
fi

if [[ ! -f "${SOURCE_KEY}" ]]; then
    echo "[ERROR] cosign.pub not found at ${SOURCE_KEY}."
    echo "        Make sure the USB drive contains cosign.pub in its root."
    exit 1
fi

# Validate it looks like a PEM/cosign public key (basic sanity check)
if ! grep -qE "^-----BEGIN PUBLIC KEY-----|^-----BEGIN EC PUBLIC KEY-----" "${SOURCE_KEY}"; then
    echo "[WARN] ${SOURCE_KEY} does not look like a PEM public key. Proceeding anyway."
fi

# Create destination directory with restricted permissions
mkdir -p "${DEST_DIR}"
chmod 700 "${DEST_DIR}"

# Copy and lock down the key
cp "${SOURCE_KEY}" "${DEST_KEY}"
chmod 444 "${DEST_KEY}"   # read-only for everyone; only root can modify

echo "[OK]  cosign.pub copied to ${DEST_KEY}"
echo "[OK]  Permissions set to 444 (read-only)."
echo ""
echo "Key fingerprint (SHA-256):"
openssl pkey -pubin -in "${DEST_KEY}" -outform DER 2>/dev/null | \
    openssl dgst -sha256 -hex | awk '{print $2}' || \
    sha256sum "${DEST_KEY}"
echo ""
echo "Import complete. You can now unmount the USB drive:"
echo "  sudo umount ${USB_MOUNT}"
