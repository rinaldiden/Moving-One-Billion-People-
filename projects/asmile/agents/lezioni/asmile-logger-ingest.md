# Lezioni di asmile-logger-ingest

Scritte da palla.py dai VETO dei contro-agenti. Leggile prima di ogni lavoro.

- 2026-11-09 **VETO** di asmile-ingest-critico su `agents/rapporti/L0.dati_indice_20261109.json` (gate L0.dati): Misure a campione OK (sha256, frame 180225R/170056R/163453L=2281, 0 byte 184541, destra assente 163453, 170056 nero visivo, nessun duplicato hash 30/10). MANCA: 3 sessioni presenti su disco ma NON nell'indice: asmile-001/session_20261107_145051 (327 s, L 19.5MB/R 19.9MB), session_20261107_161628 (L 10.4MB/R 10.6MB), session_20261108_164438 (354 s stereo completo, sync rpicam, frames L5184/R4564; probabile buona, la piu utile). Aggiungere: sha256, ffprobe frame L/R, luma, movimento, classe, motivo, + dichiarare buco: 164438 R=4564 vs L=5184 e right sync -41 s; indice 163453 manca nota file right assente. Poi ri-sottomettere.
  - 2026-11-09 risolto: PASSA di asmile-ingest-critico dopo 1 veto. v2 riverificata: sha256 e frame ricontati (ffprobe -count_frames) coincidono per 145051 (4868/4861), 161628 (2278/2277), 164438 (5176/4561; metadata 5184/4564, sfasamento right -41.366 s confermato da
