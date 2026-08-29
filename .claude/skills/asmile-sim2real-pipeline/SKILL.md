---
name: asmile-sim2real-pipeline
description: Runbook per lanciare la pipeline sim2real di guida autonoma Asmile — dai video di logging al modello ONNX validato. Usa quando si vogliono trasformare nuove ore di guida in dataset+sim+policy, o ri-eseguire uno stadio. Orchestra i 7 agenti asmile-* in .claude/agents/. NON porta nulla su strada senza firma di Daniele.
---

# Runbook — pipeline sim2real Asmile

Orchestra i 7 agenti dedicati (`.claude/agents/asmile-*`). Tesi/vincoli:
`projects/asmile/.collegio/CONTEXT.md`; linee rosse: `.collegio/GLOSSARIO.md`; diagramma:
`projects/asmile/docs/pipeline_agenti_sim2real.md`.

## Prima di partire
1. Leggi `CONTEXT.md` e `GLOSSARIO.md` (linee rosse = muri, non penalità).
2. Controlla `QUESTIONI_APERTE.md` (Q1 dati, Q2 MuJoCo/Mac, Q4 Speed PID, Q5 stereo).
3. Verifica che `DECISION_LOG.md` D001 sia firmato se stai avviando l'esecuzione reale.

## Ordine di esecuzione (dipendenze)
```
1 harvester ── poi in parallelo ── 2 event-miner   3 scene-reconstructor
                                          │              │
                                          │              └─→ 4 actuator-modeler (dipende da 1, usa 3)
                                          └──────────────┬──────────────┘
                                                         └─→ 5 sim-builder (aspetta 2+3+4)
                                                                 └─→ 6 policy-trainer (aspetta 5)
                                                                         └─→ 7 sim-validator (aspetta 6)
```

## Passi
1. **Harvester** su una cartella sessioni (`~/wip/recorder/session_*`): sincronizza, gate qualità,
   `corpus_index`. Scarta static_rig/low_light. → conferma minuti-in-movimento prima di proseguire.
2. **Event-miner** ∥ **Scene-reconstructor** sul corpus indicizzato: dataset con intento +
   geometria guidabile. Girano in parallelo.
3. **Actuator-modeler**: fitta BAM sterzo + BAM freno + range domain randomization. Verifica che
   il tratto freno >60° sia saturazione/terminazione.
4. **Sim-builder**: monta l'env MuJoCo/mjlab 50Hz, reward dai pattern, DR. Ogni voce di reward
   deve tracciare a un pattern reale o a una linea rossa.
5. **Policy-trainer**: BC warm-start → PPO fine-tune → export ONNX. Nuova versione `_vN`, non
   sovrascrivere.
6. **Sim-validator**: held-out reali + shadow vs umano + test anti-pattern A1–A7. Scrive
   `shadow_mode/iteration_00N_analysis.md` + verdetto proposto.
7. **Se go proposto**: apri voce da firmare in `DECISION_LOG.md`. **Stop.** La strada la firma
   Daniele — mai avviare test su strada in autonomia.

## Ri-esecuzione parziale
Ogni stadio legge l'output indicizzato del precedente: puoi rilanciare da un singolo stadio se a
monte non è cambiato nulla (es. solo nuovo reward → rilancia da 5). Additivo, mai sovrascrivere i
grezzi né i modelli vecchi.

## Se qualcosa è strano
Regola n.1 di Daniele: se il risultato è complicato/degenere, il problema è mal inquadrato a monte.
Torna allo stadio giusto, non tappare a valle. In dubbio: non ottimizzare, aspetta, chiedi a Daniele.
