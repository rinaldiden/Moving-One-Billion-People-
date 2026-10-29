#!/usr/bin/env python3
"""
cleanup.py — cancella le clip piu' vecchie di RETENTION_DAYS da /data/recordings
cosi' la SD non si riempie mai. Lanciato da un timer systemd giornaliero.

Due regole:
  1. ETA': cancella le clip piu' vecchie di RETENTION_DAYS (default 10 giorni).
  2. SPAZIO (rete di sicurezza): se il libero scende sotto MIN_FREE_PCT, cancella
     le piu' vecchie (anche se < RETENTION) finche' non si rientra. Evita il
     riempimento se si registra piu' veloce di quanto si offloada.

Config (env):
  SRC             /data/recordings
  RETENTION_DAYS  10
  MIN_FREE_PCT    10
"""
import os, time, glob, shutil

SRC            = os.environ.get("SRC", "/data/recordings")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "10"))
MIN_FREE_PCT   = int(os.environ.get("MIN_FREE_PCT", "10"))

def free_pct(path):
    u = shutil.disk_usage(path)
    return 100.0 * u.free / u.total

def clips_oldest_first():
    files = [f for f in glob.glob(os.path.join(SRC, "clip_*.h264")) if "%" not in f]
    return sorted(files, key=os.path.getmtime)

def main():
    if not os.path.isdir(SRC):
        print(f"cleanup: {SRC} assente", flush=True); return
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed = 0
    # 1) per eta'
    for f in clips_oldest_first():
        if os.path.getmtime(f) < cutoff:
            try: os.remove(f); removed += 1
            except OSError: pass
    # 2) per spazio (safety)
    while free_pct(SRC) < MIN_FREE_PCT:
        files = clips_oldest_first()
        if not files: break
        try: os.remove(files[0]); removed += 1
        except OSError: break
    print(f"cleanup: rimossi {removed} file (>{RETENTION_DAYS}gg / spazio), "
          f"libero ora {free_pct(SRC):.0f}%", flush=True)

if __name__ == "__main__":
    main()
