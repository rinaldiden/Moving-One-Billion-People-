# Decisioni di asmile-flotta

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-09 18:54 [retro] **gestione del dato calibrazione** → la calib appartiene al MODULO camere (ID + QR + hash, EEPROM se fattibile), nome file = ID modulo, controllo all'accensione, nessun fallback, si cambia sempre il modulo intero. Perché: toglie la confusione #001/logger e ogni calibrazione manuale in RSA. Evidenza: `agents/rapporti/calib15000_flotta.md`.
