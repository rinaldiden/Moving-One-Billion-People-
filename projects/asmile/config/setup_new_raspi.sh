#!/bin/bash
# Setup script for a new Asmile Raspberry Pi 5
# Run from the config directory: sudo bash setup_new_raspi.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASMILE_USER="${SUDO_USER:-$(whoami)}"
ASMILE_HOME="/home/$ASMILE_USER"
echo "=== Asmile Raspi 5 Setup (user: $ASMILE_USER) ==="

# Packages
echo "Installing packages..."
apt update
apt install -y python3-lgpio python3-smbus python3-spidev python3-libgpiod libgpiod-dev i2c-tools
pip install pyserial 2>/dev/null || pip install --break-system-packages pyserial

# Boot config (with backup)
echo "Installing boot config..."
if [ -f /boot/firmware/config.txt ]; then
    cp /boot/firmware/config.txt "/boot/firmware/config.txt.bak.$(date +%Y%m%d%H%M%S)"
    echo "  (backed up existing config.txt)"
fi
cp "$SCRIPT_DIR/boot_config.txt" /boot/firmware/config.txt

# Systemd services (enable only, start after reboot)
# Replace %USER% placeholder with actual user in service files
echo "Installing services for user $ASMILE_USER..."
for svc in encoder-ssi.service master_switch.service safe_shutdown.service servofreno.service steering.service; do
    if [ -f "$SCRIPT_DIR/$svc" ]; then
        sed "s|%USER%|$ASMILE_USER|g" "$SCRIPT_DIR/$svc" > /etc/systemd/system/$svc
        echo "  Installed $svc"
    fi
done
systemctl daemon-reload
systemctl enable encoder-ssi.service

# Disable serial console (for VESC on UART0)
echo "Disabling serial console..."
systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
sed -i 's/ console=serial0,115200//' /boot/firmware/cmdline.txt 2>/dev/null || true

# Safe shutdown (already installed above, just enable)
systemctl enable safe_shutdown.service
echo "  NOTE: safe_shutdown will arm only after GPIO sees battery HIGH."
echo "  If supercap + voltage divider are not wired yet, the service will"
echo "  run safely without triggering any shutdown."

# Bash alias for quick shutdown
if ! grep -q "alias off=" $ASMILE_HOME/.bashrc 2>/dev/null; then
    echo "" >> $ASMILE_HOME/.bashrc
    echo "# Asmile quick shutdown" >> $ASMILE_HOME/.bashrc
    echo "alias off='sudo shutdown -h now'" >> $ASMILE_HOME/.bashrc
fi

# Fleet ID — prompt for ID if not already set
if [ ! -f $ASMILE_HOME/asmile_id.conf ]; then
    echo ""
    read -p "Enter Asmile Fleet ID (e.g. 001): " FLEET_ID
    read -p "Enter location (e.g. tirano): " FLEET_LOC
    cat > $ASMILE_HOME/asmile_id.conf << IDEOF
ASMILE_ID=${FLEET_ID:-001}
ASMILE_NAME=asmile-${FLEET_LOC:-unknown}
ASMILE_LOCATION=${FLEET_LOC:-unknown}
ASMILE_HW_VERSION=hw1
IDEOF
    chown $ASMILE_USER:$ASMILE_USER $ASMILE_HOME/asmile_id.conf
    echo "  Fleet ID set: ${FLEET_ID:-001} @ ${FLEET_LOC:-unknown}"
fi

echo ""
echo "=== Done! Reboot to activate. ==="
echo "After reboot:"
echo "  - Encoder:  systemctl status encoder-ssi"
echo "  - GPS:      cat /dev/ttyAMA3 (38400 baud)"
echo "  - IMU:      i2cdetect -y 1 (expect 0x68)"
echo "  - VESC:     /dev/ttyAMA0 (115200 baud)"
echo "  - Shutdown: type 'off' or systemctl status safe_shutdown"
