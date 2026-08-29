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

---

## D003 — Rendere ESEGUIBILE la pipeline e avviare lo stadio 1 sui video locali
**Data proposta:** 2026-08-29 · **Autore:** doppio di Daniele (Claude) · **Stato:** DA FIRMARE

**Scelta proposta.** La pipeline non resta un disegno: aggiungere un **runner eseguibile**
(`training/sim2real/pipeline.py` + `harvest.py`) che replica la ricetta sim2real di Microduck e
**avvia da solo lo stadio 1 (harvester)** sui video di guida gia' in locale sul Mac. Lo stadio 1 e'
l'unico che il runner esegue in autonomia — e' data-processing puro e additivo (indicizza, non tocca
strada / hardware / denaro / grezzi). Gli stadi 2–7 restano lavoro di agente dietro i gate (Q1–Q6 +
firma D001); la strada resta dietro D002. Il runner li elenca e li gaterizza, non li lancia.

**Evidenza (primo run, 2026-08-29).** Harvester girato su `segmentazione/da_segmentare/`:
**38/38 sessioni ammesse**, 0 static_rig, 5 low_light, 6 dropout, molte con sync_drift.
**~2.96 h in movimento** su 4.58 h registrate → `training/sim2real/corpus/corpus_index.json`
(+ manifest per sessione). Implicazione **Q1**: sopra la soglia per il **BC**, sotto ~5 h per un
**PPO** fedele → servono altre ore in movimento prima di fidarsi della fase 2. Mappatura completa
Microduck→runner in `docs/microduck_to_asmile_runner.md`.

**Deroghe/limiti.** Nessuno stadio oltre l'1 e' stato eseguito. Nessun modello addestrato, nessuna
policy prodotta, nessun test su strada. I gate 4–7 dipendono ancora da D001 non firmata e da
Q2 (MuJoCo/Mac), Q3 (frenate forti), Q4 (Speed PID), Q5 (stereo).

**Cosa serve per firmare.** Daniele conferma: (a) che lo stadio 1 possa girare in autonomia sui log
locali a ogni nuova sessione (zero costo marginale); (b) da quale stadio far ripartire la catena
(proposta: `asmile-event-miner` + `asmile-scene-reconstructor` sul corpus appena prodotto).

**Firma:** ______________________  **Data:** __________

---

## D004 — Banco di prova virtuale: rigiocare il modello sui video reali held-out
**Data proposta:** 2026-08-29 · **Autore:** doppio di Daniele (Claude) · **Stato:** DA FIRMARE

**Scelta proposta.** Aggiungere un **banco di prova virtuale** (`training/vtest/`) che rigioca in
OPEN-LOOP il modello di guida che abbiamo gia' (`asmile_model_v4`) sui video di logging gia'
registrati e misura, frame per frame, quanto diverge dal guidatore umano. E' l'anello di
validazione che a Microduck **manca**: loro chiudono il sim2real gap a occhio (eval video,
rehearsal), senza metrica sim-vs-real; noi abbiamo video+sensori sincronizzati e possiamo
misurarlo. Catena di 4 agenti (`.claude/agents/asmile-vtest-*`): curator (held-out) → replayer
(shadow) → scorer (scheda P1-P9/A1-A7) → critic (verdetto go/no-go PROPOSTO). Complementare, non
alternativo, alla pipeline di training a 7 stadi (D001): quella costruisce il modello nel
simulatore, questo prova un modello gia' fatto contro la realta'.

**Evidenza (primo run, 2026-08-29).** Stadio 1 (curator) girato sul corpus: **9 sessioni held-out**,
~**0.6 h in movimento** tenute da parte, split per sessione deterministico, condizioni scarse
(`no_gps_fix`, `dropout`) incluse a forza. Stadio 2 (replayer) riusa `shadow_analyzer.py`, gira su
CPU senza torch (fallback numpy), in attesa di `cv2` sul Mac (comandi gia' stampati). Mappatura
Microduck→banco in `docs/microduck_vtest_banco_virtuale.md`; runbook: skill
`asmile-vtest-banco-virtuale`.

**Deroghe/limiti (dichiarati, non nascosti).** (1) **Leakage:** v4 e' stato addestrato prima dello
split → held-out `non_verificato` → il gap misurato e' un **limite inferiore** (ottimistico); per
un held-out pulito serve ri-addestrare tracciando le sessioni. (2) **Poche ore held-out** (~0.6 h):
statistiche fragili sui pattern rari. (3) **Depth grossolana** finche' non si ricalibra lo stereo
(Q5). Il banco e' OFFLINE: legge video, scrive report, **non pilota niente**.

**Cosa serve per firmare.** Daniele conferma: (a) che il banco possa girare in autonomia (curator +
replayer) su ogni modello candidato, essendo puro data-processing; (b) che il verdetto del critic
resti una PROPOSTA che alimenta D002 (strada) — nessuna policy esce dal banco alla strada senza
firma umana. **Linea rossa invariata:** una violazione non verificata (freno >60°, envelope
velocita'/decel, comando GPIO diretto) = no-go automatico.

**Firma:** ______________________  **Data:** __________
