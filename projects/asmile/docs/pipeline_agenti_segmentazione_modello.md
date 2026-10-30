# Pipeline di agenti — dai video anonimi al modello di guida (segmentazione → modello)

> Stato: **BOZZA DA FIRMARE** (Daniele). Design + scaffolding. **Nessuno stadio è stato lanciato.**
> Si rivede appena arrivano **video freschi** da elaborare. Niente strada senza firma.
> Nasce dalla voce di Daniele (2026-10-30). Complementare — non alternativa — alla
> `pipeline_agenti_sim2real.md` e al `microduck_vtest_banco_virtuale.md`.

## Il punto: due pipeline sorelle sullo stesso corpus

Daniele ha chiesto, *accanto* alla pipeline che **oscura** facce e targhe (GDPR,
`gdpr_logging_anonimizzazione.md`), una **seconda** pipeline di agenti che fa in autonomia
tutta la parte di **segmentazione → verifica → capire le situazioni → gestione strada per
strada → estrazione del modello di guida**, con **sopra un orchestratore** che la porta al
risultato e che, **quando una situazione non è chiara, la manda a Daniele personalmente** da
valutare, per poi reinserire la sua decisione nel modello.

```
   video dai logger  ──►  [ANON: asmile-anon-*]  ──►  corpus ANONIMO (locale)
   (GDPR, già fatto)         oscura PII                      │
                                                             ▼
                              ╔══════════ QUESTA PIPELINE (segmentazione → modello) ══════════╗
                              ║                                                              ║
                              ║   [1] segmenter   ─►  [2] verifier  ─►  [3] situation        ║
                              ║   segmenta tutto      verifica la        capisce la          ║
                              ║   (full-coverage)     segmentazione      situazione/scena    ║
                              ║        │                   │                   │             ║
                              ║        └───────────────────┴─────────┬─────────┘             ║
                              ║                                       ▼                       ║
                              ║                            [4] router (strada per strada)    ║
                              ║                            raggruppa per via/percorso,        ║
                              ║                            costruisce il curriculum, trova    ║
                              ║                            i buchi e le ambiguità             ║
                              ║                                       │                       ║
                              ║                                       ▼                       ║
                              ║                            [5] modeler (bridge)               ║
                              ║                            consegna il curriculum curato      ║
                              ║                            alla pipeline sim2real → ONNX,      ║
                              ║                            pacchetto per «GamePlay»           ║
                              ╚═══════════════════════════════════════╪══════════════════════╝
                                                                      │
              ┌───────────── [0] ORCHESTRATOR (asmile-seg-orchestrator) ──────────────┐
              │ guida la catena, tiene lo stato, e a ogni «situazione non chiara»:     │
              │   → impacchetta il caso (cosa vedeva la bici, niente PII)              │
              │   → lo mette nella CODA CASI DUBBI e lo manda a DANIELE (Telegram)     │
              │   → attende il suo verdetto, lo reinietta come label/knowledge         │
              │   → e solo allora la catena prosegue / il modello impara               │
              └───────────────────────────────────────────────────────────────────────┘
```

## Perché questa forma (fedele alle regole di Daniele)
- **Macro → micro.** Prima si inquadra *tutta* la scena (segmentazione full-coverage), poi la si
  **verifica**, poi si capisce *che situazione è*, poi la si organizza **strada per strada**, e
  solo alla fine si estrae il modello. Non si parte dal modello.
- **Il perché prima del gesto** (eredità sim2real): la situazione (stadio 3) è il *perché* di una
  frenata/sterzata. La segmentazione da sola è il *cosa*; la situazione è il *contesto*.
- **L'umano dove il dato tace.** L'orchestratore **non indovina** sui casi ambigui: li gira a
  Daniele. "In dubbio, non ottimizzare: aspetta." La sua decisione diventa dato, non resta in chat.
- **Zero costo marginale.** Ogni nuova sessione = rilanciare la catena sul corpus anonimo, in
  autonomia. L'unico lavoro umano è decidere i **casi dubbi** — che è esattamente dove serve.
- **Non rifà ciò che esiste.** Riusa gli strumenti di `training/segmentation/`, `training/*.py`,
  `segmentazione/`, e **consegna** alla pipeline sim2real già scritta invece di ri-allenare da capo.

## Mappatura sugli strumenti già esistenti (non reinventare)
| Stadio | Riusa |
|---|---|
| 1 segmenter | `training/segmentation/infer_segmentation.py`, `auto_segment.py`, `pretrained_segment.py`, `categories.yaml`, `depth_segmentation.py`, `segmentazione/` |
| 2 verifier | `categories.yaml` (coerenza classi), Energy-OOD dal `segment_gate_jev_approach.md`, consistenza temporale maschere |
| 3 situation | `training/driving_patterns.md` (P1–P9/A1–A7), tassonomia in `training/perception_pipeline/knowledge/situation_taxonomy.md` |
| 4 router | CSV GPS (`training/training_data/`, `training/driving_events_analysis.csv`), clustering per via |
| 5 modeler | **pipeline sim2real** (`asmile-event-miner`→…→`asmile-policy-trainer`→`asmile-sim-validator`) + banco `asmile-vtest-*` |
| 0 orchestrator | stato in `training/perception_pipeline/pipeline_state.json`, coda `casi_dubbi/`, Telegram del doppio |

## Il contratto deterministico (la "palla" che passa di mano)
Ogni stadio **legge** l'`index.json` dello stadio precedente e **scrive** il proprio, conforme a
uno schema in `training/perception_pipeline/schemas/`. Nessuno stadio indovina il formato del
vicino: lo schema È il contratto. Dettaglio in `training/perception_pipeline/README.md`.

```
segmenter → 01_segmentation/index.json   (schema: segmentation.schema.json)
verifier  → 02_verification/index.json   (schema: verification.schema.json)
situation → 03_situations/index.json     (schema: situations.schema.json)
router    → 04_roads/index.json          (schema: roads.schema.json)
modeler   → 05_model/manifest.json       (schema: model_package.schema.json)
qualunque stadio → casi_dubbi/queue/<id>.json (schema: case.schema.json)
```

## La catena (6 agenti dedicati, prefisso `asmile-seg-`)
Vivono in `.claude/agents/`, portabili (universali, mai roba di una singola sessione):
`asmile-seg-segmenter`, `-verifier`, `-situation`, `-router`, `-modeler`, `-orchestrator`.
Runbook: skill **`asmile-segmentazione-modello`**.

## Confine automazione ↔ umano (dottrina)
Gli agenti **costruiscono e propongono**: segmentano, verificano, classificano situazioni,
curano il curriculum, preparano il pacchetto modello. **Due firme restano a Daniele**: (a) il
verdetto sui **casi dubbi** (uno per uno, è il cuore della richiesta); (b) l'uscita su **strada**
di qualunque modello (invariata, `DECISION_LOG` D002). In dubbio: non ottimizzare, aspetta, chiedi.

## Linee rosse (invariate + specifiche di qui)
- Input SOLO corpus **anonimo**: la pipeline gira **dopo** `asmile-anon-*`. Mai PII nei casi dubbi.
- Il caso dubbio contiene **contesto di scena** (classi, posizioni, distanze, sensori), **mai** il
  frame con volti/targhe in chiaro.
- Nessuna label di situazione **inventata**: se non è chiara → `unknown` → coda casi dubbi, non un
  tiro a indovinare (come `intent:unknown` dell'event-miner).
- Freno ≤ **60°**, envelope velocità/decel, owner GPIO = `speed_limiter` v2: ereditate dal
  `GLOSSARIO.md`. Questa pipeline **non attua** nulla: produce dati e un modello candidato.
- «GamePlay» (il bersaglio di deploy) va **confermato da Daniele** — vedi `QUESTIONI_APERTE` Q9.

## Stato (2026-10-30)
Pipeline **progettata + scaffolding deterministico a terra** (6 agenti, skill, doc, schemi,
knowledge, cartelle deliverable, coda casi dubbi). **Nessuno stadio lanciato.** Si rivede e si
avvia sul primo blocco di **video freschi**. Da firmare: `DECISION_LOG` **D009** + chiarire Q9/Q10.
