#!/bin/bash
# Messa a fuoco del logger001 (21/11/2026): ferma la registrazione, streaming a risoluzione piena con gli stessi flip dei
# video, poi rimette la registrazione (a 12 Mbps fino al riavvio). Niente di permanente: lo streaming gira da /tmp.
#   bash fuoco_logger001.sh fuoco     → streaming http://100.83.200.55:8080/ + nitidezza dal vivo (Ctrl-C per finire)
#   bash fuoco_logger001.sh registra  → chiude lo streaming e riparte la registrazione a 12 Mbps
#   bash fuoco_logger001.sh fine      → riaccende l'autospegnimento e torna a 0,5 Mbps (o basta un riavvio)
# Durante fuoco e registra l'AUTOSPEGNIMENTO è fermo (Daniele 21/11: se no dopo 5 minuti fermo si spegne a metà pose).
set -u
H=asmile-logger@100.83.200.55; QUI="$(cd "$(dirname "$0")" && pwd)"
SSH="ssh -o ConnectTimeout=8 -o BatchMode=yes $H"
PW="${PI_PW:-asmile}"
sudo_pi() { $SSH "echo '$PW' | sudo -S -p '' bash -c $(printf %q "$1")"; }
case "${1:-}" in
fuoco)
    sudo_pi "systemctl stop logger_autospegni.service; systemctl stop logger-recorder.service logger-stream.service 2>/dev/null; true"
    $SSH "systemctl is-active logger_autospegni.service" | grep -q '^active' && { echo "!! autospegnimento ancora attivo: mi fermo"; exit 1; }
    scp -q -o BatchMode=yes "$QUI/../stream_logger.py" $H:/tmp/stream_fuoco.py
    F=$($SSH "systemctl show logger-recorder.service -p Environment; grep -h '^FLIP=' ~/logger/*.conf 2>/dev/null" | grep -o 'FLIP=1' | head -1)
    F=${F#FLIP=}; echo "flip come la registrazione: ${F:-0}  (verifica: copri UNA lente con la mano, guarda quale metà diventa nera)"
    $SSH "pkill -f stream_fuoco.py; cd ~ && W=2560 H=800 FPS=10 QUALITY=92 FLIP=${F:-0} nohup python3 /tmp/stream_fuoco.py >/tmp/stream_fuoco.log 2>&1 &"
    sleep 4; echo "streaming: http://100.83.200.55:8080/"
    ~/.asmile_depth_venv/bin/python "$QUI/fuoco_live.py" http://100.83.200.55:8080/stream ;;
registra)
    $SSH "pkill -f stream_fuoco.py; true"
    sudo_pi "systemctl stop logger_autospegni.service; mkdir -p /run/systemd/system/logger-recorder.service.d && printf '[Service]\nEnvironment=BR=12000000\n' > /run/systemd/system/logger-recorder.service.d/calib.conf && systemctl daemon-reload && systemctl restart logger-recorder.service"
    sleep 4; $SSH "pgrep -a rpicam | grep -o 'bitrate [0-9]*'; echo autospegnimento: \$(systemctl is-active logger_autospegni.service)" ;;
fine)
    sudo_pi "rm -f /run/systemd/system/logger-recorder.service.d/calib.conf; systemctl daemon-reload; systemctl restart logger-recorder.service; systemctl start logger_autospegni.service"
    sleep 4; $SSH "pgrep -a rpicam | grep -o 'bitrate [0-9]*'; echo autospegnimento: \$(systemctl is-active logger_autospegni.service)" ;;
*) sed -n 2,6p "$0" ;;
esac
