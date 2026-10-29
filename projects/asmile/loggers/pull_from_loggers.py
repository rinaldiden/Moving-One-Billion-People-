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
import os, subprocess, hashlib, shlex

HERE = os.path.dirname(os.path.abspath(__file__))              # .../projects/asmile/loggers
DEST_BASE = os.path.abspath(os.path.join(HERE, "..", "asmile-loggers"))

# Flotta logger. host = alias ssh o IP Tailscale. Aggiungine quando ce ne sono.
LOGGERS = [
    {"name": "asmile-logger", "host": "asmile-logger",
     "user": "asmile-logger", "src": "/data/recordings"},
]

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new"]


def ssh(lg, cmd):
    return subprocess.run(["ssh"] + SSH_OPTS + [f"{lg['user']}@{lg['host']}", cmd],
                          capture_output=True, text=True)


def reachable(lg):
    return ssh(lg, "true").returncode == 0


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


def main():
    os.makedirs(DEST_BASE, exist_ok=True)
    tot = 0
    for lg in LOGGERS:
        if not reachable(lg):
            print(f"[{lg['name']}] non raggiungibile (Tailscale off?) - skip")
            continue
        n = pull_logger(lg)
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
