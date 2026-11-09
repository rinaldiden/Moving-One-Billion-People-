# Lezioni di asmile-calib

Scritte da palla.py dai VETO dei contro-agenti (e a mano dal capo quando manca il `passa`). Leggile prima di ogni lavoro.

- 2026-11-09 **VETO** di asmile-calib-critico su `logger/depth/calib_asmile-001.json` (gate L0.calib_001): i tape_points sono gli STESSI punti del fit (d0, f·B: 2 parametri su 6 punti) → residui, non verifica. 15 m +2.66% (>2%), 10 m −1.95% al limite, manca 1 m. Focale fit 1306 vs ChArUco 1131 vs nominale 933 e d0=98 px: probabilmente d0 compensa rotazione/pitch. → REGOLA: fitta su un sottoinsieme (es. 2-5-10 m) e verifica su soste MAI usate (1-3-7-15 m); dy misurato su tutta l'immagine (4 angoli + centro), non sul solo valore mediano.
