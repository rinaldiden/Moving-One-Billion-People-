# Decisioni di asmile-pi-001

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-12 14:27 **Valore encoder ruota da proporre: 0.3477 o scala efficace in marcia** → Proporre 0.3477 (metro) con incertezza +-1.5%, non il valore GPS ~0.343. Perché: Il metro e' l'unico riferimento indipendente (0.06%); GPS e carico ciclista non si separano coi dati; 1.4% di differenza e' dentro il criterio 5%. Scartato: 0.343 da GPS: dipende da errore GPS e raggio sotto carico non distinguibili. Evidenza: `agents/rapporti/L0.encoder_ruota_20261112.md`.
