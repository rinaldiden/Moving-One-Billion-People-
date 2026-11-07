#!/usr/bin/env python3
"""
pull_from_loggers.py — scarica i video dai logger asmile sul Mac (PULL Mac<-Pi
via Tailscale/SSH), verifica il checksum, poi CANCELLA la clip dal Pi.

I video vanno in  projects/asmile/asmile-loggers/<logger>/  (LOCALE, mai su git).
Scarica solo i segmenti COMPLETI (esclude l'ultimo in scrittura). L'ultimo si
prende al giro successivo, quando il recorder l'ha chiuso.

"Si attiva quando ci sono video": lanciato periodicamente (launchd/cron) o a mano.
E' il pezzo di DOWNLOAD dell'agente asmile-logger-ingest; l'elaborazione (pipeline
sim2real per migliorare il modello) la fa l'agente / lo skill asmile-sim2real-pipeline.

Uso:  python3 pull_from_loggers.py          # un giro su tutti i logger
"""
import os, subprocess, hashlib, shlex, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))              # .../projects/asmile/loggers
DEST_BASE = os.path.abspath(os.path.join(HERE, "..", "asmile-loggers"))

# --- Scoperta flotta via TAILSCALE: prende TUTTI i logger ONLINE, anche fuori EOLO ---
TAILSCALE_BIN = shutil.which("tailscale") or "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
NAME_PATTERN = "logger"          # sottostringa (case-insens.) che identifica i logger della flotta
DEFAULT_USER = "asmile-logger"
SRC = "/data/recordings"
USER_MAP = {}                    # override utente per-host se serve: {"nomehost": "utente"}

# Bici della flotta con layout "sessions" (dual_cam_recorder: una cartella per sessione con
# video_left.h264 + video_right.h264 + metadata.json). Su #001 /data è la partizione
# persistente fuori dall'overlay. I CSV sensori si COPIANO (restano anche sul Pi).
FLEET = {
    "asmile-001": {"host": "100.75.198.118",          # IP Tailscale (fisso per nodo)
                   "user": "asmile", "layout": "sessions", "src": "/data/training_sessions",
                   "sensors": ["/data/logging/speed_limiter", "/data/logging/training_data_pi"]},
}

# Fallback statico se Tailscale non è disponibile (host = alias ssh o IP).
LOGGERS = [
    {"name": "asmile-logger", "host": "100.83.200.55",      # IP Tailscale
     "user": "asmile-logger", "src": SRC},
]

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new"]


def ssh(lg, cmd):
    return subprocess.run(["ssh"] + SSH_OPTS + [f"{lg['user']}@{lg['host']}", cmd],
                          capture_output=True, text=True)


def reachable(lg):
    return ssh(lg, "true").returncode == 0


def discover_loggers():
    """Logger ONLINE sulla tailnet che matchano NAME_PATTERN (li prende anche fuori EOLO)."""
    try:
        r = subprocess.run([TAILSCALE_BIN, "status", "--json"],
                           capture_output=True, text=True, timeout=15)
        data = json.loads(r.stdout)
    except Exception:
        return []
    found = []
    for p in (data.get("Peer") or {}).values():
        host = p.get("HostName") or ""
        ips = p.get("TailscaleIPs") or []
        if not (p.get("Online") and ips):
            continue
        if host in FLEET:
            found.append(dict(FLEET[host], name=host, host=ips[0]))
        elif NAME_PATTERN.lower() in host.lower():
            found.append({"name": host, "host": ips[0],
                          "user": USER_MAP.get(host, DEFAULT_USER), "src": SRC})
    return found


def complete_clips(lg):
    # tutti i .h264 tranne il piu' recente (in scrittura) e l'artefatto %05d
    r = ssh(lg, f"ls -t {lg['src']}/*.h264 2>/dev/null")
    files = [f.strip() for f in r.stdout.splitlines() if f.strip() and "%" not in f]
    return files[1:] if len(files) > 1 else []   # [0] = il piu' recente = in scrittura


def sha256_local(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha256_remote(lg, path):
    return ssh(lg, f"sha256sum {shlex.quote(path)} | cut -d' ' -f1").stdout.strip()


def pull_logger(lg):
    dest = os.path.join(DEST_BASE, lg["name"])
    os.makedirs(dest, exist_ok=True)
    done = 0
    for remote in complete_clips(lg):
        name = os.path.basename(remote)
        local = os.path.join(dest, name)
        rc = subprocess.run(
            ["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
             f"{lg['user']}@{lg['host']}:{remote}", local]).returncode
        if rc != 0:
            print(f"  {name}: rsync fallito"); continue
        if sha256_local(local) == sha256_remote(lg, remote):
            ssh(lg, f"rm -f {shlex.quote(remote)}")     # libera il Pi dopo conferma
            done += 1
            print(f"  {name}: OK (checksum confermato) -> cancellato dal Pi")
        else:
            os.remove(local)
            print(f"  {name}: checksum DIVERSO -> ritento al prossimo giro")
    return done


def complete_sessions(lg):
    # sessioni CHIUSE: se il recorder non gira sono tutte chiuse (anche quelle troncate da
    # uno spegnimento, senza end_time); se gira, escludo la più recente (in scrittura).
    r = ssh(lg, f"ls -dt {lg['src']}/session_* 2>/dev/null")
    sess = [f.strip() for f in r.stdout.splitlines() if f.strip()]
    if ssh(lg, "pgrep -f [d]ual_cam_recorder.py >/dev/null").returncode == 0:
        sess = sess[1:]
    return sess


def pull_sessions(lg):
    """Layout #001: video piatti <sessione>_<cam>.h264 (per on_new_videos.sh) + sidecar in <sessione>/."""
    dest = os.path.join(DEST_BASE, lg["name"])
    os.makedirs(dest, exist_ok=True)
    done = 0
    for remote in complete_sessions(lg):
        sess = os.path.basename(remote)
        # Con l'overlay l'orologio riparte da un'ora finta a ogni boot (prima di NTP): lo
        # stesso nome può tornare in boot diversi -> se esiste già con contenuto diverso,
        # suffisso col checksum del video, mai sovrascrivere.
        loc = os.path.join(dest, f"{sess}_left.h264")
        if os.path.exists(loc) and sha256_local(loc) != sha256_remote(lg, f"{remote}/video_left.h264"):
            sess = f"{sess}_{sha256_remote(lg, remote + '/video_left.h264')[:8]}"
        side = os.path.join(dest, sess)
        os.makedirs(side, exist_ok=True)
        files = [f.strip() for f in ssh(lg, f"ls {shlex.quote(remote)}").stdout.splitlines() if f.strip()]
        ok = True
        for name in files:
            rem = f"{remote}/{name}"
            local = (os.path.join(dest, f"{sess}_{name[len('video_'):]}")
                     if name.startswith("video_") and name.endswith(".h264")
                     else os.path.join(side, name))
            rc = subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                                 f"{lg['user']}@{lg['host']}:{rem}", local]).returncode
            if rc != 0 or sha256_local(local) != sha256_remote(lg, rem):
                ok = False
                print(f"  {sess}/{name}: rsync/checksum KO -> ritento al prossimo giro")
        if ok:
            ssh(lg, f"rm -rf {shlex.quote(remote)}")       # libera il Pi dopo conferma di TUTTI i file
            done += 1
            print(f"  {sess}: OK ({len(files)} file, checksum confermato) -> cancellata dal Pi")
    sens = os.path.join(dest, "_sensors")
    for src in lg.get("sensors", []):
        os.makedirs(os.path.join(sens, os.path.basename(src)), exist_ok=True)
        subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                        f"{lg['user']}@{lg['host']}:{src}/", os.path.join(sens, os.path.basename(src)) + "/"])
    return done


def main():
    os.makedirs(DEST_BASE, exist_ok=True)
    loggers = discover_loggers()
    if loggers:
        print(f"Tailscale: {len(loggers)} logger online -> {', '.join(l['name'] for l in loggers)}")
    else:
        # da launchd la CLI di Tailscale.app prova ad aprire la GUI e fallisce ("CLIError 3"):
        # allora provo direttamente gli IP Tailscale noti (reachable() scarta chi è offline)
        loggers = LOGGERS + [dict(cfg, name=n) for n, cfg in FLEET.items()]
        print("Tailscale CLI non disponibile -> provo la lista statica: "
              + ", ".join(l["name"] for l in loggers))
    tot = 0
    for lg in loggers:
        if not reachable(lg):
            print(f"[{lg['name']}] non raggiungibile (Tailscale off?) - skip")
            continue
        n = pull_sessions(lg) if lg.get("layout") == "sessions" else pull_logger(lg)
        print(f"[{lg['name']}] scaricati+cancellati {n} segmenti")
        tot += n
    if tot:
        print(f"TOTALE {tot} nuovi segmenti in {DEST_BASE}")
        # Hook elaborazione: se esiste on_new_videos.sh, lancialo sui nuovi video
        hook = os.path.join(HERE, "on_new_videos.sh")
        if os.path.isfile(hook) and os.access(hook, os.X_OK):
            subprocess.run([hook, DEST_BASE])
    else:
        print("nessun nuovo video da scaricare")


if __name__ == "__main__":
    main()
