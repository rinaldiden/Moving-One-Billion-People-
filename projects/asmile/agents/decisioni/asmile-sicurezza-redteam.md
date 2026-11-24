# Decisioni di asmile-sicurezza-redteam

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-23 16:38 **verdetto speed_limiter_v3 secco** → VETO su 6 punti. Perché: master/v2 sul GPIO12, assenza watchdog, anti-impuntata cieca a 10 Hz, fonte singola che frena fino a fermare la bici. Evidenza: `agents/prove/asmile-sicurezza-redteam_360921bd/redteam_v3.py`.
