# DECISION LOG — pipeline sim2real Asmile

> Append-only. Ogni voce = scelta + evidenza + eventuale deroga. **La firma la mette Daniele**
> (umano). Finché `Firma:` è vuota, è una PROPOSTA, non una decisione presa.

---

## D001 — Adottare la pipeline a 7 agenti sim2real dai log
**Data proposta:** 2026-08-29 · **Autore:** doppio di Daniele (Claude) · **Stato:** DA FIRMARE

**Scelta proposta.** Trattare le ore di logging (video stereo + sensori) come ambiente di training
e costruire una catena di 7 agenti dedicati (`.claude/agents/asmile-*`):
harvester → event-miner ∥ scene-reconstructor → actuator-modeler(BAM) → sim-builder(MuJoCo 50Hz) →
policy-trainer(BC→PPO→ONNX) → sim-validator(shadow + anti-pattern). Metodo rubato a microduck_rl.

**Evidenza.** `docs/sim2real_microduck_playbook.md` (ricetta completa e leggibile); dataset già
prodotto (iteration_001: 32k campioni, pattern P1–P9/A1–A7 in `training/driving_patterns.md`);
strumenti già scritti (`training/*.py`, `segmentazione/`) riusati come stadi. Coerente con la
memoria: `project_simulator_approach`, `project_autonomous_driving_pipeline`.

**Deroghe/limiti.** Nessuna esecuzione avviata: la pipeline è definita, non lanciata. Prerequisiti
aperti in `QUESTIONI_APERTE.md` (Q1 dati, Q2 MuJoCo/Mac, Q3 BAM freno, Q4 Speed PID, Q5 stereo,
Q6 contratto policy↔owner, Q7 condizioni scarse).

**Cosa serve per firmare.** Daniele conferma: (a) forma della catena, (b) i vincoli/linee rosse in
`GLOSSARIO.md`, (c) da quale stadio partire per primo (proposta: harvester + event-miner sui log
esistenti, così il dataset con intento cresce mentre si risolvono Q2/Q4).

**Firma:** ______________________  **Data:** __________

---

## D002 — Nessuna policy va su strada senza gate validator + firma
**Data proposta:** 2026-08-29 · **Stato:** DA FIRMARE

**Scelta proposta.** Regola permanente: una policy esce su strada **solo se** `asmile-sim-validator`
passa i gate (zero violazioni di linea rossa non verificate) **e** Daniele firma una voce dedicata
qui. Il validator propone go/no-go; non decide.

**Evidenza.** Linee rosse in `GLOSSARIO.md` (freno >60° inchioda; owner unico GPIO; envelope
velocità/decel). Principio guida del doppio: "in dubbio, non ottimizzare, aspetta".

**Firma:** ______________________  **Data:** __________
