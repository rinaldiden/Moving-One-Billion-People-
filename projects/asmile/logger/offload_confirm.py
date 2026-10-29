#!/usr/bin/env python3
"""
offload_confirm.py — invia le clip del logger al Mac via Tailscale con PROVA di
ricezione (checksum confermato DAL MAC), poi CANCELLA la clip dal Pi.

Per ogni clip COMPLETA in /data/recordings:
  1. sha256 locale
  2. rsync (--partial --append-verify) al Mac via Tailscale/SSH
  3. ssh al Mac -> shasum -a 256 del file ricevuto
  4. se i checksum COINCIDONO -> cancella la clip dal Pi; altrimenti ritenta dopo
Una clip e' "completa" se NON e' l'ultimo segmento (il recorder scrive l'ultimo)
e non viene modificata da >SETTLE secondi.

Config (env):
  SRC        /data/recordings
  MAC_HOST   100.87.2.77        (IP Tailscale del Mac macbook-pro-di-daniele)
  MAC_USER   rinaldiden
  MAC_DEST   ~/asmile-data/video
  SETTLE     40    (sec di quiete prima di considerare completa una clip)
  INTERVAL   30    (loop in secondi; 0 = un solo giro)

PREREQUISITI (una volta): Tailscale attivo sul Pi (stesso tailnet del Mac) +
Mac con Remote Login ON + la chiave pubblica del Pi in ~/.ssh/authorized_keys
del Mac. Senza, lo script logga "Mac non raggiungibile" e ritenta.
"""
import os, sys, time, hashlib, subprocess, glob

SRC      = os.environ.get("SRC", "/data/recordings")
MAC_HOST = os.environ.get("MAC_HOST", "100.87.2.77")
MAC_USER = os.environ.get("MAC_USER", "rinaldiden")
MAC_DEST = os.environ.get("MAC_DEST", "~/asmile-data/video")
SETTLE   = int(os.environ.get("SETTLE", "40"))
INTERVAL = int(os.environ.get("INTERVAL", "30"))

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new"]
SSH = ["ssh"] + SSH_OPTS + [f"{MAC_USER}@{MAC_HOST}"]

def log(msg):
    print(msg, flush=True)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def complete_clips():
    now = time.time()
    files = [f for f in glob.glob(os.path.join(SRC, "clip_*.h264"))
             if "%" not in f and os.path.getsize(f) > 0]
    if not files:
        return []
    newest = max(files, key=os.path.getmtime)          # l'ultimo e' in scrittura
    return sorted(f for f in files
                  if f != newest and (now - os.path.getmtime(f)) >= SETTLE)

def mac_reachable():
    return subprocess.run(SSH + ["true"], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0

def offload_one(path):
    name = os.path.basename(path)
    local_hash = sha256(path)
    subprocess.run(SSH + [f"mkdir -p {MAC_DEST}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rc = subprocess.run(
        ["rsync", "-a", "--partial", "--append-verify",
         "-e", "ssh " + " ".join(SSH_OPTS),
         path, f"{MAC_USER}@{MAC_HOST}:{MAC_DEST}/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    if rc != 0:
        return False, "rsync fallito"
    r = subprocess.run(
        SSH + [f"shasum -a 256 {MAC_DEST}/{name} 2>/dev/null | awk '{{print $1}}'"],
        capture_output=True, text=True)
    remote_hash = (r.stdout or "").strip()
    if remote_hash and remote_hash == local_hash:
        os.remove(path)
        return True, f"confermato dal Mac ({local_hash[:12]}) -> cancellata dal Pi"
    return False, f"checksum DIVERSO (pi {local_hash[:12]} != mac {remote_hash[:12] or '---'})"

def run_once():
    if not mac_reachable():
        log("Mac non raggiungibile (Tailscale/SSH) - ritento")
        return
    clips = complete_clips()
    if not clips:
        return
    for f in clips:
        try:
            ok, msg = offload_one(f)
            log(f"{os.path.basename(f)}: {msg}")
        except Exception as e:
            log(f"{os.path.basename(f)}: errore {e}")

if __name__ == "__main__":
    while True:
        try:
            run_once()
        except Exception as e:
            log(f"errore ciclo: {e}")
        if INTERVAL <= 0:
            break
        time.sleep(INTERVAL)
