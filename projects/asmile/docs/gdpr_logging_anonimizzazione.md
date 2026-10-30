# Logging video GDPR-safe — come lo facciamo, e come lo dimostriamo

> Casa PROGETTO → DOTTRINA + KNOWLEDGE. Nasce dalla voce di Daniele (2026-10-30):
> *"come possiamo fare questo logging di video senza incappare nel GDPR … quando avremo
> degli hardware che faranno il logging dovremo anche dimostrare come lo facciamo."*
> Questo documento è la **prova di metodo**: il perché legale, la misura tecnica, e la
> traccia che esibiamo a un Garante/DPO. La pipeline tecnica vive in
> `projects/asmile/logger/anonymize/` (agenti `asmile-anon-*`).

## Macro → micro (il principio, non lo slogan)
Asmile registra video stereo dalla strada per imparare a guidare. Sulla strada ci sono
**Persone** e **veicoli**: i loro volti e le loro targhe sono **dato personale** (GDPR art. 4).
Non possiamo chiedere il consenso a chi incrociamo. Quindi la risposta non è "chiediamo
permesso" — è **togliere il problema alla radice**: il dato grezzo con PII **non deve
sopravvivere al logging**. Si anonimizza **alla sorgente**, prima che diventi un archivio.

Questo è il vincolo prima della raccolta: non raccogliamo PII che poi dovremmo proteggere —
ne raccogliamo una versione già priva di PII. Semplificazione (regola n.1): un dato
anonimo **esce dal campo di applicazione del GDPR** (Considerando 26). Niente PII, niente
problema.

## La catena della prova (cosa esibiamo)
Per "dimostrare come lo facciamo" servono quattro pezzi, tutti già previsti dalla pipeline:

1. **La misura tecnica** — oscuramento automatico e **irreversibile** di volti e targhe su
   ogni frame, con margine generoso e smoothing temporale (meglio over-blur che una faccia
   sfuggita). È una *misura tecnica adeguata* ai sensi dell'art. 32 (sicurezza) e del
   principio di **minimizzazione** (art. 5.1.c) e **privacy by design/by default** (art. 25).
2. **Il referto di conformità** — per ogni clip la pipeline scrive un `*.audit.json` che
   contiene **solo conteggi e parametri** (quante regioni oscurate, con che backend, con che
   margine, verdetto PASS/FAIL dell'auto-audit). **Mai la PII in chiaro.** È la prova
   documentale che l'anonimizzazione è avvenuta ed è stata verificata.
3. **La catena di custodia** — il grezzo con PII resta **locale e temporaneo**, confinato
   sull'hardware/sul Mac, e viene cancellato dopo l'anonimizzazione (retention minima). Solo
   la versione anonima entra nell'archivio di training. Il `source_sha256_12` nel referto lega
   l'anonimo al grezzo da cui nasce, senza conservare il grezzo.
4. **La decisione firmata** — la scelta "questo è il nostro trattamento" è registrata in
   `.collegio/DECISION_LOG.md` (D008) e firmata da Daniele, titolare del trattamento. L'auto-audit
   **propone** PASS; la **firma** sulla conformità resta umana.

## Base giuridica e DPIA-lite (inquadramento, non consulenza legale)
- **Base giuridica:** legittimo interesse (art. 6.1.f) — ricerca e sviluppo di un ausilio alla
  mobilità per Persone che non possono guidare da sole — **bilanciato** dall'anonimizzazione
  alla sorgente, che azzera l'impatto sugli interessati. In quanto anonimo, il dato di training
  **non è più dato personale**.
- **Minimizzazione:** registriamo solo ciò che serve alla guida (scena+sensori), non l'identità
  di chi incrociamo. Il volto e la targa non servono al modello → si tolgono.
- **DPIA-lite (sintesi):** trattamento = cattura video su suolo pubblico da veicolo in movimento;
  rischio = identificabilità di passanti/veicoli; mitigazione = anonimizzazione automatica +
  audit + retention minima del grezzo + storage locale; rischio residuo = recall del detector <100%
  → mitigato da margine, smoothing temporale, e revisione umana sui campioni marcati FAIL.
- **Non è consulenza legale.** Prima di un deploy pubblico su scala, far validare questo
  inquadramento a un DPO/avvocato. Vive accanto a `training/avvocatoguidaautonoma.md`
  ([[project_asmile_legal_framing]]).

## Regole dure (linee rosse del logging)
- **Mai archiviare un grezzo con PII oltre il tempo di elaborazione.** Il grezzo è transiente.
- **Oscuramento irreversibile** (blur forte / pixelate / box): la regione PII non dev'essere
  ricostruibile. Niente maschere reversibili, niente cifratura "da riaprire".
- **Recall prima di precisione:** in dubbio si oscura. Una faccia sfuggita è un incidente GDPR;
  un muro sfocato per errore non fa male a nessuno.
- **Il verdetto di conformità lo firma l'umano.** L'auditor propone PASS/FAIL; non attesta da solo.
- **I video restano locali.** Niente upload del grezzo né dell'anonimo senza decisione esplicita
  (coerente con `asmile-loggers/` gitignored, [[project_standalone_video_logger]]).

## Dove gira — oggi e sull'hardware
- **Oggi (Mac):** batch sui log già scaricati in `asmile-loggers/` (dopo `asmile-logger-ingest`),
  prima che entrino nella pipeline sim2real. È un gate di privacy a monte del training.
- **Domani (sul logger):** l'anonimizzazione **al momento della cattura**, sul Pi 5, così che il
  grezzo con PII non tocchi mai la SD — l'ideale GDPR. Backend edge (YOLO/ONNX) già compatibile
  con l'hardware del logger (vedi `README.md` della pipeline). È il motivo per cui la misura vive
  dentro il sistema `logger/`, non fuori.

## Prior art (non reinventiamo — vedi README della pipeline)
Il campo "oscura volti e targhe in video dashcam/egocentrici" è maturo e open-source:
**EgoBlur** (Meta, volti+targhe, egocentrico), **deface** (volti, CenterFace ONNX),
**DashcamCleaner** e **dashcam_anonymizer_v2** (volti+targhe, YOLO + smoothing temporale).
La nostra pipeline ne adotta il pattern (detector + redactor + smoothing) e ci aggiunge il
pezzo che a loro manca per la **prova**: il referto di conformità + il gate firmabile.

## Stato (2026-10-30)
Misura tecnica **costruita e testata** (smoke-test su log reali Tirano + Poschiavo: la catena
detect→redact→audit→referto gira end-to-end). **Da firmare** D008. Prima del deploy hardware:
backend di produzione (YOLO volti+targhe), validazione DPO, anonimizzazione on-device al capture.
