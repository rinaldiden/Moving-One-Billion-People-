#!/bin/bash
# ============================================
# Restore script for Arducam Camarray HAT
# Raspberry Pi 5 + Dual OV9281
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR"

echo "========================================="
echo " Arducam Camarray HAT - Restore Script"
echo " Source: RPi5 + Dual OV9281"
echo "========================================="
echo ""

# Check we're on a Raspberry Pi
if [ ! -f /boot/firmware/config.txt ]; then
    echo "ERROR: /boot/firmware/config.txt not found."
    echo "This script must run on a Raspberry Pi with standard boot partition."
    exit 1
fi

# Check running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash restore.sh"
    exit 1
fi

USER_HOME=$(eval echo ~${SUDO_USER:-pi})
USERNAME=${SUDO_USER:-pi}

echo "[1/7] Installing dependencies..."
apt-get update -qq
apt-get install -y -qq \
    python3-picamera2 \
    gstreamer1.0-libcamera \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-rtsp \
    libcamera-tools \
    rpicam-apps \
    python3-gi \
    gcc

echo "[2/7] Restoring boot configuration..."
# Backup existing config first
cp /boot/firmware/config.txt /boot/firmware/config.txt.bak.$(date +%Y%m%d%H%M%S)
cp "$BACKUP_DIR/boot/config.txt" /boot/firmware/config.txt
echo "  config.txt restored (old config backed up)"

# Restore overlay
if [ -f "$BACKUP_DIR/boot/arducam-pivariety.dtbo" ]; then
    cp "$BACKUP_DIR/boot/arducam-pivariety.dtbo" /boot/firmware/overlays/
    echo "  arducam-pivariety.dtbo restored"
fi

echo "[3/7] Restoring /etc configs..."
# Add tmpfs mounts if not already present
if ! grep -q "tmpfs /tmp" /etc/fstab; then
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=128m 0 0" >> /etc/fstab
    echo "  Added tmpfs for /tmp"
fi
if ! grep -q "tmpfs /var/log" /etc/fstab; then
    echo "tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,noexec,size=64m 0 0" >> /etc/fstab
    echo "  Added tmpfs for /var/log"
fi

# Add i2c-dev if not already present
if ! grep -q "i2c-dev" /etc/modules; then
    echo "i2c-dev" >> /etc/modules
    echo "  Added i2c-dev to /etc/modules"
fi

echo "[4/7] Setting up streaming directory..."
STREAM_DIR="$USER_HOME/streaming-setup"
mkdir -p "$STREAM_DIR"
cp "$BACKUP_DIR/streaming-setup/rtsp_stream.py" "$STREAM_DIR/"
cp "$BACKUP_DIR/streaming-setup/arducam_fix.c" "$STREAM_DIR/"
cp "$BACKUP_DIR/streaming-setup/mediamtx.yml" "$STREAM_DIR/"
cp "$BACKUP_DIR/streaming-setup/setup.sh" "$STREAM_DIR/"
chown -R "$USERNAME:$USERNAME" "$STREAM_DIR"
echo "  Streaming files copied to $STREAM_DIR"

echo "[5/7] Compiling arducam_fix.so..."
cd "$STREAM_DIR"
gcc -shared -fPIC -o arducam_fix.so arducam_fix.c -ldl
chown "$USERNAME:$USERNAME" arducam_fix.so
echo "  arducam_fix.so compiled"

echo "[6/7] Downloading MediaMTX..."
if [ ! -f "$STREAM_DIR/mediamtx" ]; then
    ARCH=$(uname -m)
    if [ "$ARCH" = "aarch64" ]; then
        MTX_ARCH="arm64v8"
    else
        MTX_ARCH="armv7"
    fi
    MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/v1.16.1/mediamtx_v1.16.1_linux_${MTX_ARCH}.tar.gz"
    echo "  Downloading from $MTX_URL"
    wget -q "$MTX_URL" -O /tmp/mediamtx.tar.gz
    tar xzf /tmp/mediamtx.tar.gz -C "$STREAM_DIR" mediamtx
    chmod +x "$STREAM_DIR/mediamtx"
    chown "$USERNAME:$USERNAME" "$STREAM_DIR/mediamtx"
    rm -f /tmp/mediamtx.tar.gz
    echo "  MediaMTX v1.16.1 downloaded"
else
    echo "  MediaMTX already present, skipping"
fi

echo "[7/7] Setting up bash aliases..."
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "stream-start" "$BASHRC"; then
    cat >> "$BASHRC" << 'ALIASES'

# Streaming aliases
alias stream-start='cd ~/streaming-setup && python3 rtsp_stream.py'
alias stream-stop='pkill -f rtsp_stream.py; pkill -f mediamtx; pkill -f gst-launch'
ALIASES
    echo "  Aliases added to .bashrc"
else
    echo "  Aliases already present in .bashrc"
fi

echo ""
echo "========================================="
echo " RESTORE COMPLETE!"
echo "========================================="
echo ""
echo " Next steps:"
echo "   1. Reboot: sudo reboot"
echo "   2. After reboot, test camera: libcamera-hello --list-cameras"
echo "   3. Start streaming: stream-start"
echo "   4. View stream: rtsp://$(hostname -I | awk '{print $1}'):8554/stream"
echo ""
