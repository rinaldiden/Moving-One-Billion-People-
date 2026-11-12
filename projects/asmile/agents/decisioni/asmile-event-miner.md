# Decisioni di asmile-event-miner

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-12 22:08 **Come separare guide di Daniele da freno del limiter nelle frenate 08-09/11** → stop completi (v finale<2 km/h) = umano; servo>=5 gradi e non stop = limiter escluso; frenata proposta = fit lineare pooled n=15 + offset p75, valida solo 5-12 km/h. Perché: il speed_limiter (target 10, cap 12) frenava col servo in quasi tutti i km usati; sotto 8 km/h rilascia e non puo fermare. Scartato: decel costante unica: la decel cresce con v (0.4->1.1); IMU: offset ay 0.7 m/s2 e pitch non compensato. Evidenza: `training/eventi/soglie_report.py`.
