#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# setup.sh — Setup streaming stereo OV9281 (AVVIO MANUALE)
#             Arducam Camarray HAT + Raspberry Pi 5 (Bookworm)
#
# Uso:  chmod +x setup.sh && sudo ./setup.sh
# ═══════════════════════════════════════════════════════════════

INSTALL_DIR="/home/asmile/streaming"
MEDIAMTX_VERSION="v1.16.1"
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_arm64v8.tar.gz"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Asmile Stereo Streaming — Setup (manuale)"
echo "  Arducam Camarray HAT + 2x OV9281 → RTSP"
echo "══════════════════════════════════════════════════"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "[!] Esegui con sudo: sudo ./setup.sh"
    exit 1
fi

# 1. Aggiorna
echo "[1/7] Aggiornamento sistema..."
apt update -y
apt upgrade -y

# 2. Dipendenze
echo "[2/7] Installazione pacchetti..."
apt install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libcamera \
    gstreamer1.0-rtsp \
    gir1.2-gst-rtsp-server-1.0 \
    gir1.2-gstreamer-1.0 \
    libcamera-tools \
    rpicam-apps \
    gcc \
    ffmpeg \
    python3

# 3. Ottimizzazioni SD
echo "[3/7] Ottimizzazione SD..."
if ! grep -q "tmpfs /tmp" /etc/fstab; then
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=128M 0 0" >> /etc/fstab
fi
if ! grep -q "tmpfs /var/log" /etc/fstab; then
    echo "tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,size=64M 0 0" >> /etc/fstab
fi

# 4. Directory
echo "[4/7] Setup directory ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for f in arducam_fix.c rtsp_stream.py mediamtx.yml; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/"
    fi
done

# 5. Compila fix
echo "[5/7] Compilazione arducam_fix.so..."
cd "$INSTALL_DIR"
if [ -f arducam_fix.c ]; then
    gcc -shared -fPIC -O2 -o arducam_fix.so arducam_fix.c -ldl
    echo "  [✓] arducam_fix.so compilato"
else
    echo "  [!] arducam_fix.c non trovato!"
    exit 1
fi

# 6. MediaMTX
echo "[6/7] Download MediaMTX ${MEDIAMTX_VERSION}..."
if [ ! -f "$INSTALL_DIR/mediamtx" ]; then
    cd /tmp
    wget -q "$MEDIAMTX_URL" -O mediamtx.tar.gz
    tar xzf mediamtx.tar.gz mediamtx
    mv mediamtx "$INSTALL_DIR/mediamtx"
    chmod +x "$INSTALL_DIR/mediamtx"
    rm -f mediamtx.tar.gz
    echo "  [✓] MediaMTX scaricato"
else
    echo "  [✓] MediaMTX già presente"
fi

# 7. Permessi + alias
echo "[7/7] Permessi e alias..."
chown -R asmile:asmile "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/rtsp_stream.py"

# Aggiungi alias comodi in .bashrc
BASHRC="/home/asmile/.bashrc"
if ! grep -q "alias stream-start" "$BASHRC"; then
    echo '' >> "$BASHRC"
    echo '# === Asmile Streaming ===' >> "$BASHRC"
    echo "alias stream-start='cd $INSTALL_DIR && python3 rtsp_stream.py'" >> "$BASHRC"
    echo "alias stream-stop='pkill -f rtsp_stream.py; pkill -f mediamtx; pkill -f gst-launch'" >> "$BASHRC"
    echo "  [✓] Alias aggiunti: stream-start, stream-stop"
fi

# Verifica camera
echo ""
echo "══════════════════════════════════════════════════"
echo "  Verifica camera..."
echo "══════════════════════════════════════════════════"
if [ -e /dev/video0 ]; then
    echo "  [✓] /dev/video0 presente"
else
    echo "  [!] /dev/video0 NON trovato — verifica HAT"
fi

echo ""
echo "══════════════════════════════════════════════════"
echo "  SETUP COMPLETATO!"
echo "══════════════════════════════════════════════════"
echo ""
echo "  NON parte al boot. Avvio MANUALE:"
echo ""
echo "    stream-start          # avvia streaming"
echo "    stream-stop           # ferma streaming"
echo ""
echo "  Oppure:"
echo "    cd $INSTALL_DIR && python3 rtsp_stream.py"
echo ""
echo "  VLC: rtsp://<IP_RASPI>:8554/stream"
echo ""
echo "  Consiglio: riavvia per attivare tmpfs"
echo "    sudo reboot"
echo ""
