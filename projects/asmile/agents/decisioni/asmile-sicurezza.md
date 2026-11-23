# Decisioni di asmile-sicurezza

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-23 16:40 **speed_limiter v3 secondo giro** → ALLOW prova a banco con 6 condizioni; BLOCK deploy/strada (D1-D6). Perché: 7 punti chiusi nel codice con 91 test verdi + 2 scenari miei; restano flock v2/master, GPS writer che esisteva solo in v2, hw mai girato, segni IMU non verificati. Scartato: ALLOW pieno: hw.py/porta_a_zero/segni IMU mai provati; filtro |a| istantaneo 0.7-1.3 come chiesto prima: giudicato sbagliato, la media 1 s e' giusta. Evidenza: `projects/asmile/agents/rapporti/speed_limiter_v3_sicurezza.md`.
