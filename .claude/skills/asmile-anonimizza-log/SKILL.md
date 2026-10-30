---
name: asmile-anonimizza-log
description: Runbook per anonimizzare i log video di Asmile — oscura in modo irreversibile volti delle Persone e targhe dei veicoli, così che il logging non incappi nel GDPR. Usa quando arrivano nuovi video di logging e vanno resi privacy-safe prima di entrare nell'archivio/training, o per produrre il referto di conformità. Orchestra i 3 agenti asmile-anon-* in .claude/agents/. I video restano LOCALI; la firma sulla conformità resta a Daniele.
---

# Runbook — anonimizzazione log video Asmile (GDPR)

Orchestra i 3 agenti dedicati (`.claude/agents/asmile-anon-*`). Dottrina e inquadramento
legale: `projects/asmile/docs/gdpr_logging_anonimizzazione.md`. Pipeline e opzioni:
`projects/asmile/logger/anonymize/README.md`.

> Principio: si anonimizza **alla sorgente**. Il grezzo con PII è transiente; nell'archivio
> entra solo l'anonimo. Over-blur è sicuro; under-blur è il rischio. I video restano LOCALI.

## Prima di partire
1. Leggi la dottrina (`docs/gdpr_logging_anonimizzazione.md`): perché legale + come si dimostra.
2. Scegli il backend: `yolo`/`deface` per conformità reale, `haar` solo per smoke-test.
3. Assicurati che i video siano **locali** (es. `asmile-loggers/<logger>/`, gitignored).

## Ordine di esecuzione (3 stadi, 1 comando)
```
1 anon-detector  ──  2 anon-redactor  ──  3 anon-auditor  ──  [FIRMA UMANA: Daniele]
   trova la PII       oscura irrevers.      verifica+referto      conformità → DECISION_LOG D008
```
I tre stadi sono implementati in `logger/anonymize/anonymize.py`; un singolo comando li
esegue in catena e scrive `*_anon.mp4` + `*.audit.json` (il referto).

## Lancio
```bash
cd projects/asmile/logger/anonymize

# smoke-test offline (verifica che la catena giri)
python3 anonymize.py INPUT.mp4 -o /tmp/out_anon.mp4 --backend haar

# produzione: cartella ricorsiva, YOLO volti+targhe
python3 anonymize.py ../../asmile-loggers/asmile-logger/ -o ../../asmile-loggers/_anon/ \
    --backend yolo --plate-model pesi_targhe.pt --style gaussian --margin 0.25 --window 3
```

## Collocazione nel flusso
Gira **dopo** `asmile-logger-ingest` (download dei video dai logger) e **prima** della
pipeline `asmile-sim2real-pipeline` (training): è il gate di privacy a monte del modello.
In prospettiva, la stessa misura va **on-device** sul logger Pi 5, al momento della cattura.

## Lettura del referto (la prova)
Per ogni video, `*.audit.json`: `verdict` PASS/FAIL, `audit_residual_*` (deve essere 0),
conteggi volti/targhe, backend, margine/finestra. Contiene **solo conteggi**, mai PII.
Se qualche video è FAIL → alza `--margin`/`--window` o passa a un backend migliore e rilancia.

## Linea rossa
- Il verdetto di conformità lo **firma Daniele** (titolare del trattamento): l'auditor propone.
- Backend `haar` = smoke-test, **non** conformità reale.
- I video (grezzi e anonimi) restano **locali**, mai su git, mai upload senza decisione esplicita.
