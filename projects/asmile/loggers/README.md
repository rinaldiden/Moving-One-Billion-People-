# Agente ingestione logger asmile (locale, sul Mac)

Chiude l'anello **logger -> modello**: scarica i video dai logger asmile in campo,
li verifica/cancella dal Pi, e li avvia nella pipeline sim2real per migliorare il
modello di guida. Vedi l'agente `.claude/agents/asmile-logger-ingest.md`.

## Pezzi
- `pull_from_loggers.py` — DOWNLOAD: pull Mac<-Pi via Tailscale, prova checksum,
  cancella dal Pi. Video -> `../asmile-loggers/<logger>/` (LOCALE, gitignored).
- `com.asmile.loggers-ingest.plist` — launchd: lancia il pull ogni 30 min ("si
  attiva quando ci sono video").
- `on_new_videos.sh` (opzionale) — hook: se presente+eseguibile, pull_from_loggers.py
  lo lancia sui nuovi video (es. per triggerare la pipeline sim2real).

## Attiva l'auto-ingest (ogni 30 min)
```bash
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"   # root M1BP
sed "s|__REPO__|$REPO|g" com.asmile.loggers-ingest.plist > ~/Library/LaunchAgents/com.asmile.loggers-ingest.plist
launchctl load ~/Library/LaunchAgents/com.asmile.loggers-ingest.plist
# log: tail -f /tmp/asmile-loggers-ingest.log
```

## A mano (un giro)
```bash
python3 pull_from_loggers.py
```

## Note
- Prereq: Tailscale sul Pi + alias ssh del logger nel `~/.ssh/config` (o IP Tailscale).
- I video NON vanno MAI su git (gitignore `asmile-loggers/`, `*.h264`, `*.mp4`).
- Scarica solo segmenti completi; l'ultimo in scrittura si prende al giro dopo.
- Aggiungi logger nella lista `LOGGERS` di `pull_from_loggers.py`.
