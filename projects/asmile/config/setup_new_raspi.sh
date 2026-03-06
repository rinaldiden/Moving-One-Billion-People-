#!/bin/bash
# Setup script for a new Asmile Raspberry Pi 5
# Run: sudo bash setup_new_raspi.sh

set -e
echo "=== Asmile Raspi 5 Setup ==="

# Packages
echo "Installing packages..."
apt update
apt install -y python3-lgpio python3-smbus python3-spidev python3-libgpiod libgpiod-dev i2c-tools
pip install pyserial 2>/dev/null || pip install --break-system-packages pyserial

# Boot config
echo "Installing boot config..."
cp boot_config.txt /boot/firmware/config.txt

# Systemd services
echo "Installing encoder service..."
cp encoder-ssi.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable encoder-ssi.service

# Disable serial console (for VESC on UART0)
echo "Disabling serial console..."
systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
sed -i 's/ console=serial0,115200//' /boot/firmware/cmdline.txt 2>/dev/null || true

echo ""
echo "=== Done! Reboot to activate. ==="
echo "After reboot:"
echo "  - Encoder: systemctl status encoder-ssi"
echo "  - GPS:     cat /dev/ttyAMA3 (38400 baud)"
echo "  - IMU:     i2cdetect -y 1 (expect 0x68)"
echo "  - VESC:    /dev/ttyAMA0 (115200 baud)"
