#!/bin/bash
# ============================================
# Restore script for Arducam Camarray HAT
# Raspberry Pi 5 + Dual OV9281
#
# Run from repo: sudo bash projects/asmile/config/restore_camera.sh
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VISION_DIR="$REPO_ROOT/projects/asmile/pi/vision"
CONFIG_DIR="$SCRIPT_DIR"

echo "========================================="
echo " Arducam Camarray HAT - Restore Script"
echo " Source: RPi5 + Dual OV9281"
echo "========================================="
echo ""

# Check we're on a Raspberry Pi
if [ ! -f /boot/firmware/config.txt ]; then
    echo "ERROR: /boot/firmware/config.txt not found."
    echo "This script must run on a Raspberry Pi."
    exit 1
fi

# Check running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash restore_camera.sh"
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
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-rtsp \
    gir1.2-gst-rtsp-server-1.0 \
    libcamera-tools \
    rpicam-apps \
    python3-gi \
    python3-opencv \
    gcc \
    ffmpeg

echo "[2/7] Restoring boot configuration..."
cp /boot/firmware/config.txt /boot/firmware/config.txt.bak.$(date +%Y%m%d%H%M%S)
if [ -f "$CONFIG_DIR/boot_config.txt" ]; then
    cp "$CONFIG_DIR/boot_config.txt" /boot/firmware/config.txt
    echo "  config.txt restored (old config backed up)"
else
    echo "  boot_config.txt not found in repo, checking current config..."
    if grep -q "arducam-pivariety" /boot/firmware/config.txt; then
        echo "  arducam overlay already in config.txt"
    else
        echo "dtoverlay=arducam-pivariety" >> /boot/firmware/config.txt
        echo "  Added arducam-pivariety overlay"
    fi
fi

echo "[3/7] Restoring /etc configs..."
if ! grep -q "tmpfs /tmp" /etc/fstab; then
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=128m 0 0" >> /etc/fstab
    echo "  Added tmpfs for /tmp"
fi
if ! grep -q "tmpfs /var/log" /etc/fstab; then
    echo "tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,noexec,size=64m 0 0" >> /etc/fstab
    echo "  Added tmpfs for /var/log"
fi
if ! grep -q "i2c-dev" /etc/modules; then
    echo "i2c-dev" >> /etc/modules
    echo "  Added i2c-dev to /etc/modules"
fi

echo "[4/7] Setting up streaming directory..."
STREAM_DIR="$USER_HOME/streaming"
mkdir -p "$STREAM_DIR"

# Copy streaming files from repo
for f in rtsp_stream.py arducam_fix.c mediamtx.yml; do
    if [ -f "$VISION_DIR/$f" ]; then
        cp "$VISION_DIR/$f" "$STREAM_DIR/"
    else
        echo "  WARNING: $f not found in $VISION_DIR"
    fi
done
chown -R "$USERNAME:$USERNAME" "$STREAM_DIR"
echo "  Streaming files copied to $STREAM_DIR"

echo "[5/7] Compiling arducam_fix.so..."
cd "$STREAM_DIR"
if [ -f arducam_fix.c ]; then
    gcc -shared -fPIC -O2 -o arducam_fix.so arducam_fix.c -ldl
    chown "$USERNAME:$USERNAME" arducam_fix.so
    echo "  arducam_fix.so compiled"
else
    echo "  ERROR: arducam_fix.c not found!"
    exit 1
fi

echo "[6/7] Downloading MediaMTX..."
if [ ! -f "$STREAM_DIR/mediamtx" ]; then
    MTX_VERSION="v1.16.3"
    ARCH=$(uname -m)
    if [ "$ARCH" = "aarch64" ]; then
        MTX_ARCH="arm64v8"
    else
        MTX_ARCH="armv7"
    fi
    MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MTX_VERSION}/mediamtx_${MTX_VERSION}_linux_${MTX_ARCH}.tar.gz"
    echo "  Downloading from $MTX_URL"
    wget -q "$MTX_URL" -O /tmp/mediamtx.tar.gz
    tar xzf /tmp/mediamtx.tar.gz -C "$STREAM_DIR" mediamtx
    chmod +x "$STREAM_DIR/mediamtx"
    chown "$USERNAME:$USERNAME" "$STREAM_DIR/mediamtx"
    rm -f /tmp/mediamtx.tar.gz
    echo "  MediaMTX ${MTX_VERSION} downloaded"
else
    echo "  MediaMTX already present, skipping"
fi

echo "[7/7] Setting up bash aliases..."
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "stream-start" "$BASHRC"; then
    cat >> "$BASHRC" << 'ALIASES'

# === Asmile Streaming ===
alias stream-start='cd ~/streaming && python3 rtsp_stream.py'
alias stream-stop='pkill -f rtsp_stream.py; pkill -f mediamtx; pkill -f gst-launch'
ALIASES
    echo "  Aliases added to .bashrc"
else
    echo "  Aliases already present in .bashrc"
fi

# Verify camera
echo ""
echo "========================================="
echo " Verifica camera..."
echo "========================================="
if [ -e /dev/video0 ]; then
    echo "  /dev/video0 presente"
else
    echo "  /dev/video0 NON trovato — verifica HAT e riavvia"
fi

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "========================================="
echo " RESTORE COMPLETE!"
echo "========================================="
echo ""
echo " Next steps:"
echo "   1. Reboot: sudo reboot"
echo "   2. Test camera: LD_PRELOAD=~/streaming/arducam_fix.so rpicam-hello --list-cameras"
echo "   3. Start streaming: stream-start"
echo "   4. View in VLC: rtsp://${IP}:8554/stream"
echo ""
