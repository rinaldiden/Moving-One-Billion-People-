# Pipeline di agenti — dai video di logging al modello di guida autonoma (sim2real)

> Deriva da `sim2real_microduck_playbook.md`. Trasforma le ore di logging di Asmile
> nell'**ambiente di training** del modello vero, si allena **in simulazione**, e verifica
> **prima di uscire su strada**. Gli agenti vivono in `.claude/agents/` (portabili). Tesi e
> vincoli in `.collegio/CONTEXT.md`; linee rosse in `.collegio/GLOSSARIO.md`.

## La catena (7 stadi, 7 agenti dedicati)

```
  video+sensori grezzi
        │
  [1] asmile-log-harvester      ── sincronizza video↔sensori, gate qualità, indicizza
        │                          (scarta static_rig / low_light / dropout, NON cancella grezzi)
        ├──────────────┐
        ▼              ▼
  [2] event-miner   [3] scene-reconstructor
   dove+PERCHÉ        geometria guidabile
   (smart+brute,      (depth → muri, gap,
    intento)           margini, ostacoli)
        │              │
        │              ├──────────────┐
        │              ▼              │
        │        [4] actuator-modeler │   ── BAM sterzo (encoder→gyro_z non lineare) +
        │         (fisica reale)      │      BAM freno idraulico (stallo >60°) + range DR
        │              │              │
        └──────┬───────┴──────────────┘
               ▼
        [5] sim-builder              ── MuJoCo/mjlab 50Hz, scene reali + BAM,
               │                        reward dai pattern P1–P9 / anti-pattern A1–A7,
               │                        domain randomization, linee rosse = terminazioni
               ▼
        [6] policy-trainer           ── BC warm-start (demo umane) → PPO fine-tune in sim
               │                        → export ONNX per il Pi 5
               ▼
        [7] sim-validator            ── held-out reali + shadow vs umano + test anti-pattern
               │                        → verdetto go/no-go PROPOSTO
               ▼
     ┌───────────────────────────┐
     │  FIRMA UMANA (Daniele)    │  ── DECISION_LOG.md → solo dopo, test su strada
     └───────────────────────────┘
```

## Perché questa forma
- **Macro → micro** (regola di Daniele): prima l'ambiente globale (log = mondo, sim2real =
  metodo), poi il singolo attuatore, poi la policy. Non si parte dal modello.
- **BAM al centro** (lezione microduck): senza attuatori fedeli il transfer non regge. Lo stadio 4
  è il perno, non un dettaglio.
- **Il perché prima dell'azione** (stadio 2): la policy impara la logica, non solo i gesti.
- **La sim prima della strada**: la bici sbaglia gratis mille volte; su strada esce solo ciò che
  ha già passato il validator E la firma umana.
- **Zero costo marginale**: aggiungere ore di guida = rilanciare la catena sui log, senza lavoro
  manuale per sessione. Gli stadi riusano gli strumenti già scritti (`training/*.py`,
  `segmentazione/*`, `follow_me/asmile_config.yaml`), non li riscrivono.

## Mappatura sugli strumenti già esistenti (non reinventare)
| Stadio | Riusa |
|---|---|
| 1 harvester | `training/frame_extractor.py`, `training/keyframe_extractor.py` |
| 2 event-miner | `training/keyframe_extractor.py`, `segmentazione/` (YOLO), `driving_patterns.md` |
| 3 scene-reconstructor | `training/depth_extractor.py`, `training/build_dataset_v2.py`, `config/stereo_calibration.yaml` |
| 4 actuator-modeler | log CSV, `config/vesc_steering_config_asmile2.md`, memoria brake_mechanical_setup |
| 5 sim-builder | `microduck_rl` (AGENTS.md, BAM), MuJoCo/mjlab, `driving_patterns.md` |
| 6 policy-trainer | `training/behavioral_cloning.py`, `training/train_v4.py`, dataset event-miner |
| 7 sim-validator | `training/shadow_analyzer.py`, `shadow_mode/iteration_*` |

## Come si lancia
Vedi la skill **`asmile-sim2real-pipeline`** (`.claude/skills/`) per il runbook passo-passo.
In breve: si invoca lo stadio 1 su una cartella di sessioni; ogni agente passa il testimone al
successivo e scrive il proprio output indicizzato. Gli stadi 2 e 3 girano in parallelo dopo l'1;
4 dipende da 1 (+3 per le distanze); 5 aspetta 2+3+4; 6 aspetta 5; 7 aspetta 6.

## Stato (2026-08-29)
Pipeline **progettata e definita** (agenti + doc + casa progetto). **Da firmare** da Daniele prima
dell'esecuzione reale e prima di qualsiasi test su strada. Prerequisiti aperti in
`.collegio/QUESTIONI_APERTE.md` (Speed PID VESC, ricalibrazione stereo, MuJoCo su Mac, ~10h dati).

## Aggiornamento (2026-08-29) — la pipeline diventa ESEGUIBILE
La catena ha ora un **runner** in `training/sim2real/` (`pipeline.py` orchestratore + `harvest.py`
stadio 1). Lo **stadio 1 e' stato girato** sui 38 log locali del Mac (`segmentazione/da_segmentare/`):
**38/38 ammesse, ~2.96 h in movimento**, marcate 5 low_light + 6 dropout + varie sync_drift →
`training/sim2real/corpus/corpus_index.json`. Gli stadi 2–7 restano dietro i gate (Q1–Q6) e la firma
D001. Vedi `training/sim2real/README.md`, `docs/microduck_to_asmile_runner.md` e `DECISION_LOG.md` D003.
