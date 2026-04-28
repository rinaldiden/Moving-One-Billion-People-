#!/bin/bash
# Setup script for a new Asmile Raspberry Pi 5
# Run from the config directory: sudo bash setup_new_raspi.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Asmile Raspi 5 Setup ==="

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
echo "Installing encoder service..."
cp "$SCRIPT_DIR/encoder-ssi.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable encoder-ssi.service

# Disable serial console (for VESC on UART0)
echo "Disabling serial console..."
systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
sed -i 's/ console=serial0,115200//' /boot/firmware/cmdline.txt 2>/dev/null || true

# Safe shutdown service (enable only — DO NOT start before hardware is wired)
echo "Installing safe shutdown service..."
cp "$SCRIPT_DIR/safe_shutdown.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable safe_shutdown.service
echo "  NOTE: safe_shutdown will arm only after GPIO sees battery HIGH."
echo "  If supercap + voltage divider are not wired yet, the service will"
echo "  run safely without triggering any shutdown."

# Bash alias for quick shutdown
if ! grep -q "alias off=" /home/asmile/.bashrc 2>/dev/null; then
    echo "" >> /home/asmile/.bashrc
    echo "# Asmile quick shutdown" >> /home/asmile/.bashrc
    echo "alias off='sudo shutdown -h now'" >> /home/asmile/.bashrc
fi

echo ""
echo "=== Done! Reboot to activate. ==="
echo "After reboot:"
echo "  - Encoder:  systemctl status encoder-ssi"
echo "  - GPS:      cat /dev/ttyAMA3 (38400 baud)"
echo "  - IMU:      i2cdetect -y 1 (expect 0x68)"
echo "  - VESC:     /dev/ttyAMA0 (115200 baud)"
echo "  - Shutdown: type 'off' or systemctl status safe_shutdown"
