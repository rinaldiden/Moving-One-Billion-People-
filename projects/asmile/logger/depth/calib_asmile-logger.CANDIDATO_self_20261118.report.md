# logger001 (asmile-logger) — candidato autocalibrazione 18/11/2026

- Metodo: `selfcalib_essential.py` (SIFT su 150 fotogrammi del giro 18/11 07:14, focale a priori 935 px dalla calib metro, |T| = 200 mm).
- Rotazione relativa trovata: rx 0.59°, ry −0.65°, rz −1.88°.
- Prova su un giro DIVERSO (18/11 06:37, 60 fotogrammi, mai usato nel fit), scarto verticale dopo rettifica:

| calibrazione | dy mediana | dy p90 | disparità > 0 |
|---|---|---|---|
| `calib_asmile-logger_metro.json` (in uso, 8/11) | 3.61 px | 10.70 px | 100% |
| **candidato self 18/11** | **1.14 px** | **3.18 px** | 100% |

- Lettura: le camere si sono mosse rispetto all'8/11 (la calib vecchia oggi sbaglia di 3.6 px di mediana). Il candidato
  migliora di 3× ma non arriva sotto 0.5 px: mancano focale vera e distorsione, che senza tabellone non si stimano.
- Stato: CANDIDATO, non in uso. Serve: ripresa ChArUco (tabellone A3/A2 o monitor) → `calib_charuco_dual.py` → banco fisso
  → asmile-calib-critico. L'elaborazione dei video del logger resta in pausa (`asmile-loggers/.pausa_elaborazione`).
