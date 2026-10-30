---
name: asmile-segmentazione-modello
description: Runbook per la pipeline segmentazione→modello di guida Asmile — dal corpus video ANONIMO al modello ONNX candidato, passando per segmentazione, verifica, comprensione delle situazioni e gestione strada-per-strada, con un orchestratore che manda i CASI DUBBI a Daniele personalmente. Usa quando arrivano video freschi da elaborare o per ri-eseguire uno stadio. Orchestra i 6 agenti asmile-seg-* in .claude/agents/. NON porta nulla su strada senza firma di Daniele; i casi dubbi li decide Daniele uno per uno.
---

# Runbook — pipeline segmentazione → modello di guida Asmile

Orchestra i 6 agenti dedicati (`.claude/agents/asmile-seg-*`). Architettura e perché:
`projects/asmile/docs/pipeline_agenti_segmentazione_modello.md`. Tesi/vincoli ereditati:
`.collegio/CONTEXT.md` + `.collegio/GLOSSARIO.md`. Contratto deterministico + schemi:
`projects/asmile/training/perception_pipeline/README.md`.

> Stato 2026-10-30: **scaffolding a terra, nessuno stadio lanciato.** Si avvia sui primi video
> freschi, dopo firma `DECISION_LOG` D009. Complementare alla `asmile-sim2real-pipeline`.

## Prima di partire
1. **Il corpus deve essere ANONIMO.** Gira **prima** `asmile-anonimizza-log`. Mai dare in pasto
   video con volti/targhe in chiaro: la pipeline rifiuta e si ferma.
2. Leggi `CONTEXT.md` + `GLOSSARIO.md` (linee rosse = muri) e la tassonomia situazioni in
   `training/perception_pipeline/knowledge/situation_taxonomy.md`.
3. Verifica che `DECISION_LOG.md` D009 sia firmato se stai avviando l'esecuzione reale.

## Ordine di esecuzione (dipendenze)
```
0 orchestrator (sopra tutto, tiene lo stato + casi dubbi)
1 segmenter → 2 verifier → 3 situation → 4 router → 5 modeler → [voce DECISION_LOG da firmare]
                  │              │             │
                  └── review/novel ┴── unknown ┴── strada ambigua ──► casi_dubbi/queue → DANIELE
```

## Passi
1. **Segmenter** sul corpus anonimo: segmentazione full-coverage → `01_segmentation/index.json`.
2. **Verifier**: marca ogni frame `ok|review|reject` + `novel` → `02_verification/index.json`.
3. **Situation**: timeline di situazioni dalla tassonomia fissa, `unknown` dove non è chiaro →
   `03_situations/index.json`.
4. **Router**: raggruppa strada-per-strada, curriculum, data-gap, split held-out →
   `04_roads/index.json`.
5. **Modeler** (bridge): consegna il curriculum alla `asmile-sim2real-pipeline` (BC→PPO→ONNX) +
   banco `asmile-vtest-banco-virtuale`, impacchetta per GamePlay → `05_model/manifest.json`.
6. **Orchestrator**: a catena completa apre la voce `DECISION_LOG` da firmare. **Stop.** La strada
   la firma Daniele.

## I casi dubbi (il cuore della richiesta)
Ogni stadio che incontra l'ambiguità **non indovina**: propone un caso. L'orchestratore lo
impacchetta (`casi_dubbi_protocol.md` + `schemas/case.schema.json`), lo scrive in
`casi_dubbi/queue/<id>.json` e **lo manda a Daniele su Telegram** con una domanda precisa + opzioni.
- Daniele risponde → verdetto in `casi_dubbi/resolved/<id>.json` → reiniettato come label e, se
  regola generale, come **knowledge**. Poi la catena riprende da quello stadio.
- **Idempotenza:** caso già risolto (stesso hash) non si ri-chiede — si applica la regola salvata.
- Un caso aperto **blocca** solo la parte di catena che dipende da quella scena, non tutto.

## Ri-esecuzione parziale
Ogni stadio legge l'`index.json` del precedente: puoi rilanciare da un singolo stadio se a monte
non è cambiato nulla (es. nuova tassonomia → rilancia da 3). Additivo, mai sovrascrivere grezzi,
output vicini o modelli vecchi (versiona `_vN`).

## Linee rosse
- Input SOLO anonimo. Casi dubbi SENZA PII (solo contesto di scena).
- `unknown` è una risposta valida, non un fallimento: meglio chiedere che inventare.
- Il verdetto sui casi dubbi è di **Daniele**, uno per uno. L'uscita su strada è di **Daniele** (D002).
- In dubbio: non ottimizzare, aspetta, chiedi.
