# Lezioni di asmile-calib

Scritte da palla.py dai VETO dei contro-agenti (e a mano dal capo quando manca il `passa`). Leggile prima di ogni lavoro.

- 2026-11-09 **VETO** di asmile-calib-critico su `logger/depth/calib_asmile-001.json` (gate L0.calib_001): i tape_points sono gli STESSI punti del fit (d0, f·B: 2 parametri su 6 punti) → residui, non verifica. 15 m +2.66% (>2%), 10 m −1.95% al limite, manca 1 m. Focale fit 1306 vs ChArUco 1131 vs nominale 933 e d0=98 px: probabilmente d0 compensa rotazione/pitch. → REGOLA: fitta su un sottoinsieme (es. 2-5-10 m) e verifica su soste MAI usate (1-3-7-15 m); dy misurato su tutta l'immagine (4 angoli + centro), non sul solo valore mediano.
  - 2026-11-09 risolto: PASSA di asmile-calib-critico dopo 1 veto. Rifatto da h264 con Calib.rectify (focale rett 1312.49, B 0.2): disparita ZNCC indipendente (mio codice, ROI e metodo diversi) err% 5m +0.93, 6m +0.52, 7m +0.97, 8m +0.43, 10m +0.08, 12m -0.71, 15m -0

## 2026-11-09 — bordi #001
- Scala dai quadretti senza inclinazione = errore ~12% in Z: usare solvePnP.
- Bordo sinistro #001: dy -4 px a x<430 identico mattina/pomeriggio = distorsione non radiale non modellata; fit joint coi
  parametri contro i limiti (dcy 40-80 px) = segnale che il modello è sbagliato, non che servono più punti centrali.
- Fit fatto quasi solo con punti centrali: ai bordi il modello è libero. Servono viste che coprano TUTTE le 9 zone.

## 2026-11-09 sera — consigli di Daniele (dettagli: rapporti/calib_consigli_daniele_REVISIONE_20261109.md)
- La baseline NON si impone: |T| esce dal tabellone (lato misurato) e si controlla contro 200 mm ±3%. Riscalare T nasconde l'errore di scala.
- RMS conta solo sulle viste tenute fuori: mono <0.5 px, stereo <1 px. RMS del fit = residuo, non prova.
- Il modello si sceglie dal FOV MISURATO, non dal "tipico": #001 è ~58° → rational/prism/tilted, non fisheye.
- Bersaglio rigido e piatto prima di tutto (foglio a mano = no). Shutter corto + gain fisso nella clip di calib.
- Griglia depth 1-2-5-10 m × sx/centro/dx con la posizione laterale misurata in cm: ai bordi la Z nominale mente.
- Librerie semplificate (calibrating, flusso Luxonis) = seconda opinione sugli stessi video, mai il giudice.
