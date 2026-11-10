# Triage 15 sessioni #001 — 2026-11-10 (asmile-log-harvester)
Numeri completi in `triage_001_sessioni_20261110.json`. Solo misura, grezzi intatti, niente GPU.

## In moto e buone per test fissi ostacoli / TTC / held-out
- **session_20261109_094146** — 671 s, 1250 m da encoder ruota, v max 5.27 m/s, 5832 frame con v>0.3 (6.48 min, 57.9%), luma 104, sync L-R 0.03 ms medi, 0 gap, 10066 frame L=R. Usare solo i frame in moto. Index.json di `_solo_movimento` riusato (0.577 contro il mio 0.579).
- **session_20261030_180225** (con riserve) — 416 s su strada, GPS>0.3 nel 72% (~5 min in moto, max 3.75 m/s), luma 97. Niente encoder ruota affidabile, sync software non misurabile, sbarra verticale sfocata nel left. Va bene per held-out di percezione, NON per TTC.

## Solo calibrazione (ferme/lente apposta, non spazzatura, non vanno a valle per ostacoli)
- 20261109_093216 (301 s, v=0 da encoder: 100% ferma), 20261109_093909 (27 s, 10.8 m lenti), 20261109_153251 (173 s, bici ferma da IMU, persona col ChArUco; encoder ruota assente nel hub), 20261108_163453 (solo cam L, tabellone, 17 m a passo d'uomo).

## Da scartare e perché
| sessione | perché |
|---|---|
| 20261030_155729, _180019, _180023, _182802 | static_rig: officina, bici su cavalletto (GPS/IMU fermi, scena identica) |
| 20261030_180215 | 46 frame (3 s) |
| 20261030_184541 | file a 0 byte, mai partita |
| 20261107_165926 | muro bianco vicino + cavo; video nero dal frame ~372 di 789 |
| 20261107_170056 | video nero per tutta la sessione (luma 1.6) pur in movimento (GPS 96%) |
| 20261109_080401 | 31 s officina fissa, nessun sensore copre l'orario |

## Cose da sapere (per l'auditor)
- Riusati 3 index.json (093216, 093909, 094146); per gli altri 12 non esiste (080401 e 153251 hanno la cartella vuota).
- `sensors_20261030_180024.csv` non è contiguo: 24 s del 30/10, poi righe del 09/11 15:23-16:23 (file riusato su due boot). Per 153251 ho agganciato per ora locale.
- 180023 si sovrappone nel tempo a 180225 ma mostra officina per tutto il file: timeline incoerente, scartata.
- Prima del 07/11 nessun encoder ruota nei dati; limiter enc con circonferenza provvisoria. Velocità del 30/10 e 07/11 solo da GPS, indicative.
- Giudizi visivi su 4-8 frame per sessione.
- Totale in moto con dati affidabili: 6.48 min (094146) + ~5 min stimati (180225).
