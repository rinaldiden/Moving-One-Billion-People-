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
- 2026-11-10 **VETO** di asmile-calib-critico su `logger/depth/calib_charuco_dual.py` (gate L1.rettifica): 9zone VERDE solo col seed del produttore: seed 1,2,3 = ROSSO (p95 dy hold-out 1.37-1.41 px su zone con 17-27 punti, verita' 0.43-0.48 px). Eseguire: regressione >=5 seed con criterio fissato prima (>=4/5 VERDE, 0 falsi verdi); statistica dy stabile (n>=60 punti/zona o bootstrap); modello/stereo scelti fuori dal blocco del gate. Non rifatti da me: file_scambiati, sync, tilt, export (lenti). A3 e scala OK.
- 2026-11-10 **VETO** di asmile-calib-critico su `logger/depth/calib_rock/esito.json`: Rifatto in scratch (seed nuovo 20271117, esito.json non toccato). B (senza tabellone) REGGE: 11/12 per scala, 0 celle peggiorate >0.5 punti, lenti variate 0/12 accettate (rifiuto = gate che passa per vacuita', dichiarato). A NON regge: scala1 11/16 candidati con 1 falso 3.66%; scala2 9/16 candidati, falsi 2/9 (22%): alto-sx@5m 5.9% e basso-dx@5m 7.4%, quindi >85% KO e la soglia 'grave' 6% non separa nulla (coda fino a 7.4%; sommando i due run falsi s2 3/21=14%, s1 3/34=9%; falsi tutti al bordo con dy p95 1.6-2.8 px). Caso negativo 'lato 6%' con seed nuovo esce ROSSO-per-altro-motivo (copertura): il controllo baseline non e' esercitato, test fragile. Blocco produzione: run_all --produzione esce 3 (verificato) ma il PASSA e' una riga che chiunque scrive con palla.py --critico X: limite di sistema, non del codice. Per il PASSA: (1) 0 falsi gravi su >=40 candidati A con seed mai usati, oppure A dichiarato 'solo candidato + banco fisso' nel README e gate di bordo spostato su dy p95<1.5 px motivato; (2) negativo lato 6% costruito con copertura garantita e motivo 'baseline' obbligatorio; (3) soglie 6% e 50% motivate (50%: A scala2 e' disponibilita' non sicurezza -> riportare, non gate) ; (4) README: dichiarare che B-lenti e' sempre rifiuto. Rosso (a)(b)(c) = limiti accettabili SOLO se (1) o (2) chiusi: decide Daniele sul bordo di A.
  - 2026-11-10 risolto: PASSA di asmile-calib-critico dopo 1 veto. Rifatta da me la regressione completa (14/14): 9zone 4/5 VERDE sui seed del criterio, zero falsi verdi, seed 31/32 miei ROSSO per RMS mono 0.519; soglie D012 invariate; zona con <60 punti/6 viste = RO
