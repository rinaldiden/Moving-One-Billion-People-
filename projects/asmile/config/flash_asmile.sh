#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Asmile — Flash completo Raspberry Pi 5
#
# Replica l'intera configurazione di asmile2 su un nuovo Pi.
# Prerequisiti: Raspberry Pi OS con SSH abilitato, user creato.
#
# Uso:
#   1. Flash SD con Raspberry Pi Imager (SSH on, WiFi configurato)
#   2. Boot e connetti via SSH
#   3. git clone https://github.com/rinaldiden/Moving-One-Billion-People-.git ~/wip/Moving-One-Billion-People-
#   4. cd ~/wip/Moving-One-Billion-People-/projects/asmile/config
#   5. sudo bash flash_asmile.sh
#
# Oppure one-liner da un altro PC:
#   ssh user@IP "git clone https://github.com/rinaldiden/Moving-One-Billion-People-.git ~/wip/Moving-One-Billion-People- && cd ~/wip/Moving-One-Billion-People-/projects/asmile/config && sudo bash flash_asmile.sh"
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ASMILE_DIR="$REPO_ROOT/projects/asmile"
USER_HOME=$(eval echo ~${SUDO_USER:-pi})
USERNAME=${SUDO_USER:-pi}

echo "═══════════════════════════════════════════════════════"
echo "  ASMILE — Flash Completo Raspberry Pi 5"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Repo:    $REPO_ROOT"
echo "  User:    $USERNAME"
echo "  Home:    $USER_HOME"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Eseguire come root: sudo bash flash_asmile.sh"
    exit 1
fi

# ─────────────────────────────────────────────────────────
# 1. SISTEMA BASE
# ─────────────────────────────────────────────────────────
echo "[1/10] Pacchetti di sistema..."
apt update -qq
apt install -y -qq \
    python3-lgpio python3-smbus python3-spidev python3-libgpiod \
    libgpiod-dev i2c-tools \
    python3-picamera2 python3-opencv python3-flask python3-numpy \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-rtsp \
    gstreamer1.0-libcamera \
    gir1.2-gst-rtsp-server-1.0 \
    libcamera-tools rpicam-apps \
    python3-gi ffmpeg gcc
pip install pyserial 2>/dev/null || pip install --break-system-packages pyserial
echo "  OK"

# ─────────────────────────────────────────────────────────
# 2. NODE.JS + CLAUDE CODE
# ─────────────────────────────────────────────────────────
echo "[2/10] Node.js e Claude Code..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt install -y nodejs
fi
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
fi
echo "  Node $(node --version), Claude $(claude --version 2>/dev/null || echo 'installed')"

# ─────────────────────────────────────────────────────────
# 3. BOOT CONFIG
# ─────────────────────────────────────────────────────────
echo "[3/10] Boot config (I2C, UART3, SPI1, Arducam)..."
if [ -f /boot/firmware/config.txt ]; then
    cp /boot/firmware/config.txt "/boot/firmware/config.txt.bak.$(date +%Y%m%d%H%M%S)"
fi
cp "$SCRIPT_DIR/boot_config.txt" /boot/firmware/config.txt

# Disable serial console (UART0 per VESC)
systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
sed -i 's/console=serial0,115200 //' /boot/firmware/cmdline.txt 2>/dev/null || true
echo "  OK"

# ─────────────────────────────────────────────────────────
# 4. TIMEZONE
# ─────────────────────────────────────────────────────────
echo "[4/10] Timezone Europe/Rome..."
timedatectl set-timezone Europe/Rome
echo "  OK"

# ─────────────────────────────────────────────────────────
# 5. SYSTEMD SERVICES
# ─────────────────────────────────────────────────────────
echo "[5/10] Servizi systemd..."

# Encoder SSI (SPI1)
cp "$SCRIPT_DIR/encoder-ssi.service" /etc/systemd/system/
systemctl enable encoder-ssi.service

# Safe shutdown (GPIO 26 power sense)
cp "$SCRIPT_DIR/safe_shutdown.service" /etc/systemd/system/
systemctl enable safe_shutdown.service

# Servofreno server (Flask :5000) — controllato dal master switch
cp "$SCRIPT_DIR/servofreno.service" /etc/systemd/system/
# NON abilitare — lo controlla il master switch

# Master switch (GPIO 17 toggle)
cp "$SCRIPT_DIR/master_switch.service" /etc/systemd/system/
systemctl enable master_switch.service

systemctl daemon-reload
echo "  encoder-ssi: enabled"
echo "  safe_shutdown: enabled"
echo "  servofreno: disabled (controlled by master switch)"
echo "  master_switch: enabled"

# ─────────────────────────────────────────────────────────
# 6. STREAMING (MediaMTX + GStreamer)
# ─────────────────────────────────────────────────────────
echo "[6/10] Streaming stereo cam..."
STREAM_DIR="$USER_HOME/streaming"
mkdir -p "$STREAM_DIR"

# Copy streaming files
for f in rtsp_stream.py arducam_fix.c mediamtx.yml; do
    if [ -f "$ASMILE_DIR/pi/vision/$f" ]; then
        cp "$ASMILE_DIR/pi/vision/$f" "$STREAM_DIR/"
    fi
done

# Compile arducam fix
if [ -f "$STREAM_DIR/arducam_fix.c" ]; then
    gcc -shared -fPIC -O2 -o "$STREAM_DIR/arducam_fix.so" "$STREAM_DIR/arducam_fix.c" -ldl
fi

# Download MediaMTX
if [ ! -f "$STREAM_DIR/mediamtx" ]; then
    MTX_VERSION=$(curl -sL https://api.github.com/repos/bluenviron/mediamtx/releases/latest | grep '"tag_name"' | sed 's/.*"v/v/' | sed 's/".*//')
    MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MTX_VERSION}/mediamtx_${MTX_VERSION}_linux_arm64.tar.gz"
    echo "  Downloading MediaMTX ${MTX_VERSION}..."
    wget -q "$MTX_URL" -O /tmp/mediamtx.tar.gz
    tar xzf /tmp/mediamtx.tar.gz -C "$STREAM_DIR" mediamtx
    chmod +x "$STREAM_DIR/mediamtx"
    rm -f /tmp/mediamtx.tar.gz
fi

# Start script
cat > "$STREAM_DIR/start.sh" << 'STARTEOF'
#!/bin/bash
cd ~/streaming
pkill -9 -f mediamtx 2>/dev/null
pkill -9 -f gst-launch 2>/dev/null
sleep 1
export LD_PRELOAD=~/streaming/arducam_fix.so
./mediamtx mediamtx.yml &
sleep 2
/usr/bin/gst-launch-1.0 -e \
  libcamerasrc ! "video/x-raw,width=1280,height=400,framerate=15/1" ! \
  videoflip method=rotate-180 ! \
  videoconvert ! "video/x-raw,format=I420" ! \
  openh264enc bitrate=500000 ! \
  "video/x-h264,profile=baseline" ! \
  h264parse ! \
  rtspclientsink location=rtsp://127.0.0.1:8554/stream &
IP=$(hostname -I | awk '{print $1}')
echo "Stream: rtsp://${IP}:8554/stream"
STARTEOF
chmod +x "$STREAM_DIR/start.sh"

chown -R "$USERNAME:$USERNAME" "$STREAM_DIR"
echo "  OK"

# ─────────────────────────────────────────────────────────
# 7. DIRECTORIES
# ─────────────────────────────────────────────────────────
echo "[7/10] Directory di lavoro..."
mkdir -p "$USER_HOME/wip/recorder"
mkdir -p "$USER_HOME/wip/calibration/images"
mkdir -p "$ASMILE_DIR/pi/logging/servofreno"
mkdir -p "$ASMILE_DIR/pi/logging/training_data"
chown -R "$USERNAME:$USERNAME" "$USER_HOME/wip"
echo "  OK"

# ─────────────────────────────────────────────────────────
# 8. GIT CONFIG
# ─────────────────────────────────────────────────────────
echo "[8/10] Git config..."
cd "$REPO_ROOT"
sudo -u "$USERNAME" git config user.email "art.bike.tirano@gmail.com"
sudo -u "$USERNAME" git config user.name "Daniele Rinaldi"
sudo -u "$USERNAME" git config pull.rebase true
echo "  OK"

# ─────────────────────────────────────────────────────────
# 9. BASH ALIASES
# ─────────────────────────────────────────────────────────
echo "[9/10] Bash aliases..."
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "# === Asmile ===" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'ALIASES'

# === Asmile ===
alias off='sudo shutdown -h now'
alias stream-start='cd ~/streaming && bash start.sh'
alias stream-stop='pkill -f gst-launch; pkill -f mediamtx'
alias asmile='cd ~/wip/Moving-One-Billion-People-/projects/asmile'
alias status='echo "=== Services ===" && systemctl is-active master_switch.service servofreno.service encoder-ssi.service safe_shutdown.service && echo "=== Encoder ===" && cat /tmp/encoder_position 2>/dev/null && echo "" && echo "=== Sensors ===" && curl -s http://localhost:5000/stato 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "servofreno not running"'
ALIASES
fi
echo "  OK"

# ─────────────────────────────────────────────────────────
# 10. VERIFICA
# ─────────────────────────────────────────────────────────
echo "[10/10] Verifica..."
echo ""

IP=$(hostname -I | awk '{print $1}')

echo "═══════════════════════════════════════════════════════"
echo "  FLASH COMPLETO!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Reboot necessario: sudo reboot"
echo ""
echo "  Dopo il reboot:"
echo "    SSH:        ssh $USERNAME@$IP"
echo "    Freno web:  http://$IP:5000 (switch ON)"
echo "    Stream:     stream-start → rtsp://$IP:8554/stream"
echo "    Status:     status"
echo "    Claude:     claude --dangerously-skip-permissions"
echo ""
echo "  Hardware da verificare:"
echo "    IMU:      i2cdetect -y 1 (expect 0x68)"
echo "    GPS:      timeout 3 cat /dev/ttyAMA3 (38400 baud)"
echo "    Encoder:  cat /tmp/encoder_position"
echo "    Cam:      LD_PRELOAD=~/streaming/arducam_fix.so rpicam-hello --list-cameras"
echo ""
echo "  Switch master (GPIO 17, Pin 11 → GND Pin 9):"
echo "    ON         = freno rilasciato + logging"
echo "    ON-OFF-ON  = follow-me mode"
echo "    OFF        = freno bloccato"
echo ""
echo "  Servizi installati:"
echo "    master_switch  — controlla tutto"
echo "    encoder-ssi    — lettura encoder SPI1"
echo "    safe_shutdown   — spegnimento sicuro su power loss"
echo "    servofreno     — server Flask :5000 (via master switch)"
echo ""
