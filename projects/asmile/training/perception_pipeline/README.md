# perception_pipeline/ — deliverable + contratto deterministico

> Casa dei **deliverable** della pipeline segmentazione→modello (`asmile-seg-*`).
> Doc/architettura: `../../docs/pipeline_agenti_segmentazione_modello.md`.
> Runbook: skill `asmile-segmentazione-modello`. Stato: **scaffolding, nessuno stadio lanciato.**

## Il contratto (la "palla" deterministica)
Ogni stadio **legge** l'`index.json` del precedente e **scrive** il proprio, conforme a uno schema
in `schemas/`. Lo schema È l'interfaccia: nessuno stadio deve indovinare il formato del vicino.

| Stadio | Agente | Legge | Scrive | Schema |
|---|---|---|---|---|
| 1 | `asmile-seg-segmenter` | corpus anonimo | `01_segmentation/index.json` | `schemas/segmentation.schema.json` |
| 2 | `asmile-seg-verifier` | `01_segmentation/index.json` | `02_verification/index.json` | `schemas/verification.schema.json` |
| 3 | `asmile-seg-situation` | `02_verification/index.json` | `03_situations/index.json` | `schemas/situations.schema.json` |
| 4 | `asmile-seg-router` | `03_situations/index.json` + CSV GPS | `04_roads/index.json` | `schemas/roads.schema.json` |
| 5 | `asmile-seg-modeler` | `04_roads/index.json` | `05_model/manifest.json` + ONNX | `schemas/model_package.schema.json` |
| 0 | `asmile-seg-orchestrator` | tutti + `casi_dubbi/` | `pipeline_state.json`, `casi_dubbi/{queue,resolved}/*.json` | `schemas/case.schema.json` |

## Cartelle
```
perception_pipeline/
├── README.md                ← questo file (il contratto)
├── pipeline_state.json      ← stato della catena (lo scrive l'orchestrator) [LOCALE]
├── schemas/                 ← i contratti JSON Schema (versionati su git)
├── knowledge/               ← tassonomie e policy condivise (versionate su git)
├── 01_segmentation/         ← output stadio 1 [LOCALE, gitignored]
├── 02_verification/         ← output stadio 2 [LOCALE]
├── 03_situations/           ← output stadio 3 [LOCALE]
├── 04_roads/                ← output stadio 4 [LOCALE]
├── 05_model/                ← modello candidato + manifest [LOCALE]
└── casi_dubbi/
    ├── queue/               ← casi aperti per Daniele [LOCALE]
    └── resolved/            ← verdetti di Daniele, reiniettati [LOCALE]
```

## Cosa va su git e cosa no
- **Su git:** `README.md`, `schemas/`, `knowledge/` — il contratto e la dottrina, piccoli e stabili.
- **Locale (gitignored):** gli output degli stadi (maschere, index per-frame, modelli, casi dubbi).
  Dati, non codice; alcuni pesanti; i casi dubbi, pur senza PII, restano locali per prudenza.

## Invarianti
- Input SOLO corpus **anonimo** (dopo `asmile-anon-*`).
- Additivo: versiona (`_vN`), mai sovrascrivere l'output di un altro stadio né i grezzi.
- `unknown`/`novel`/`review`/data-gap si **dichiarano**, non si tappano inventando.
- Casi dubbi: **mai PII**, solo contesto di scena. Verdetto = Daniele. Strada = Daniele (D002).
