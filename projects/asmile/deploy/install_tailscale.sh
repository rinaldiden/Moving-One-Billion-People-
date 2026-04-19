#!/bin/bash
# install_tailscale.sh
# Installs Tailscale on the Raspberry Pi 5 using the official install script.
# Does NOT automatically connect to the Tailscale network — the operator must
# run "sudo tailscale up" manually after reviewing the auth URL.
#
# Run as: sudo bash install_tailscale.sh
# Target: Raspberry Pi 5 (arm64, Debian Trixie)

set -euo pipefail

echo "=== Tailscale Installer ==="
echo ""

# Check connectivity before attempting download
if ! ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
    echo "[ERROR] No network connectivity. Check your connection before installing Tailscale."
    exit 1
fi

echo "[INFO] Downloading and running the official Tailscale install script ..."
echo "       Source: https://tailscale.com/install.sh"
echo ""

curl -fsSL https://tailscale.com/install.sh | sh

echo ""
echo "[OK]  Tailscale installed successfully."
echo ""
echo "================================================================"
echo "  NEXT STEP — connect this device to your Tailscale network:"
echo ""
echo "  Run manually:  sudo tailscale up"
echo ""
echo "  You will be given an auth URL. Open it in a browser to"
echo "  authenticate this device. After auth, the Pi will appear"
echo "  in your Tailscale admin console (https://login.tailscale.com)."
echo "================================================================"
echo ""
echo "Useful commands:"
echo "  sudo tailscale status       — show connection status"
echo "  sudo tailscale ip           — show Tailscale IP address"
echo "  sudo systemctl status tailscaled — check the daemon"
