# Pipeline anonimizzazione log video — volti + targhe (GDPR)

Oscura **irreversibilmente** le facce delle Persone e le targhe dei veicoli nei log
video di Asmile, così che il logging non incappi nel GDPR già all'inizio. È la **misura
tecnica** descritta in [`../../docs/gdpr_logging_anonimizzazione.md`](../../docs/gdpr_logging_anonimizzazione.md)
(il perché legale + come lo dimostriamo). Gira in **LOCALE**. I video d'uscita non vanno su git.

> Principio: si anonimizza **alla sorgente**. Il grezzo con PII è transiente; nell'archivio
> di training entra solo l'anonimo. Over-blur è sicuro; under-blur è il rischio.

## La catena (3 stadi = 3 agenti `asmile-anon-*`)

```
  video di logging (locale, es. asmile-loggers/<logger>/)
        │
  [1] asmile-anon-detector   ── trova le regioni PII in ogni frame
        │                        (facce persone + targhe veicoli), con confidenze
        ▼
  [2] asmile-anon-redactor   ── oscura IRREVERSIBILMENTE (blur/pixelate/box),
        │                        margine generoso + smoothing temporale (±N frame)
        ▼
  [3] asmile-anon-auditor    ── rigira il detector sull'OUTPUT: PII residua = 0?
        │                        scrive il referto *.audit.json, verdetto PASS/FAIL PROPOSTO
        ▼
     ┌───────────────────────────┐
     │  FIRMA UMANA (Daniele)    │  titolare del trattamento → DECISION_LOG D008
     └───────────────────────────┘
```

I tre stadi vivono in un unico modulo `anonymize.py` (le classi `*Detector`, `redact()` +
`TemporalSmoother`, `_audit_output()`), così il codice resta semplice (regola n.1) e gli
agenti ci mappano 1:1.

## Backend di detection (dal migliore al fallback offline)

| `--backend` | Cosa | Quando | Install |
|---|---|---|---|
| `yolo`    | YOLO persona/veicolo + modello targhe dedicato. Sulle persone oscura la **testa** (terzo superiore), non tutto il corpo. | **Produzione / on-device** | `pip install ultralytics` + pesi |
| `deface`  | CenterFace ONNX — solo volti, qualità alta, offline dopo install. Accoppia a un detector targhe. | Volti HQ su Mac | `pip install deface` |
| `haar`    | OpenCV Haar cascades **bundled** in `models/`. Zero download, ma recall basso. | **Solo smoke-test** | `pip install opencv-python` |

Il backend `haar` **non è conformità reale** (lo dice anche il referto): serve a verificare
che la catena giri. Per attestare il GDPR si usa `yolo`/`deface` + revisione umana.

## Come si lancia

```bash
cd projects/asmile/logger/anonymize

# smoke-test offline su un file (verifica che la catena giri)
python3 anonymize.py INPUT.mp4 -o /tmp/out_anon.mp4 --backend haar

# produzione: cartella ricorsiva, YOLO volti+targhe, blur forte
python3 anonymize.py ../../asmile-loggers/asmile-logger/ -o ../../asmile-loggers/_anon/ \
    --backend yolo --plate-model pesi_targhe.pt --style gaussian --margin 0.25 --window 3
```

Opzioni chiave: `--style {gaussian|pixelate|box}`, `--margin` (allarga le box),
`--window` (smoothing ± frame), `--no-faces`/`--no-plates`, `--audit-stride` (densità audit).
Accetta file o cartella (ricorsiva), `.mp4/.mov/.avi/.mkv/.m4v` e `.h264` grezzi (remux
automatico via ffmpeg). Per ogni video scrive `*_anon.mp4` + `*.audit.json` (il referto).

## Il referto `*.audit.json` (la prova)
Contiene **solo** conteggi e parametri, **mai PII**: nome+`sha256` del grezzo, backend,
stile, margine/finestra, frame totali, frame con PII, n. volti/targhe oscurati, e l'esito
dell'auto-audit (`audit_residual_*` deve essere 0) con `verdict` PASS/FAIL. È il documento
che si esibisce per dimostrare come anonimizziamo. Exit code ≠ 0 se almeno un video è FAIL.

## Dove gira
- **Oggi (Mac):** batch sui log scaricati, **dopo** `asmile-logger-ingest` e **prima** della
  pipeline sim2real — gate di privacy a monte del training.
- **Domani (logger Pi 5):** al momento della cattura, così il grezzo con PII non tocca la SD.
  Backend `yolo`/ONNX già portabile sull'edge.

## File
| File | Cosa |
|---|---|
| `anonymize.py` | la pipeline (detector → redactor+smoothing → auditor → referto) |
| `models/` | Haar cascades per il fallback `haar` (scaricati, gitignored) |
| `requirements.txt` | dipendenze per backend (minime per `haar`) |
| `.gitignore` | i video anonimizzati e i modelli restano LOCALI |

## Note
- **GDPR:** i video (grezzi e anonimi) restano locali — mai su git. Vedi la dottrina in
  `../../docs/gdpr_logging_anonimizzazione.md`. La firma sulla conformità è di Daniele (D008).
- **Recall > precisione:** di default margine 0.25 + finestra ±3. Alza entrambi se l'auditor
  marca FAIL, o passa a un backend migliore. Meglio un muro sfocato di una faccia sfuggita.
- **OpenCV 5.0** ha rimosso i Haar `CascadeClassifier`: per il backend `haar` serve opencv **4.x**
  (`pip install "opencv-python-headless==4.10.0.84"`). `yolo`/`deface` non ne dipendono.
