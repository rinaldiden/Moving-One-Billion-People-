# QUESTIONI APERTE — pipeline sim2real Asmile

> Tensioni irrisolte / prerequisiti. Append-only. Le decisioni prese migrano in DECISION_LOG.md.

## Q1 — Quanti dati bastano per far partire il PPO?
La memoria fissa il trigger sim-to-real a ~10h di guida (`project_simulator_approach`); Karpathy-style
autoresearch a ~50h. Oggi abbiamo ~53 min shadow (iteration_001) + sessioni successive. **Aperto:**
soglia minima per BC utile (fase 1) vs PPO fedele (fase 2). Proposta: BC già ora, PPO quando il
corpus pulito (post-harvester) supera ~5h in movimento.

## Q2 — Ambiente sim: MuJoCo/mjlab su Mac o su altro?
microduck_rl usa MuJoCo Warp (mjlab) + PPO. **Aperto:** gira su Mac (training) e poi ONNX sul Pi?
Verificare toolchain mjlab/Warp su Apple Silicon. Alternativa: MuJoCo classico se Warp non regge.

## Q3 — BAM freno con pochi campioni di frenata forte
Solo ~8 frenate con decel chiara (speed_before>1m/s + accel_x>0.2g). Il BAM freno rischia di
estrapolare nel regime pericoloso. **Aperto:** raccogliere sessioni mirate di frenata (in sicurezza)
prima di fidarsi del modello sopra 0.5g? Vedi anche driving_patterns §"Cosa manca".

## Q4 — Speed PID VESC non ancora configurato
`COMM_SET_RPM` non ha effetto senza Speed PID (TODO memoria 2026-05-26). Il BAM sterzo modella
"cosa la bici sa fare oggi" (closed-loop posizione OK, DUTY_SIGN +1). **Aperto:** aspettare il
Speed PID per il controllo velocità in sim, o modellare solo posizione+duty per ora?

## Q5 — Calibrazione stereo (errore depth)
Depth oggi ~7.8%, obiettivo 1–2% (2560x800 + 30 foto + multi-distanza — `project_stereo_calibration_plan`).
**Aperto:** lo scene-reconstructor deve girare già ora con `depth:coarse` o aspettare la ricalibrazione?
Proposta: girare ora marcando l'incertezza, ri-processare dopo.

## Q6 — Interfaccia policy→attuatore reale
La policy in sim agisce su target sterzo + comando freno mediati dall'owner (speed_limiter).
**Aperto:** definire il contratto socket/flag tra policy ONNX e speed_limiter v2 (refactor GPIO su
socket-owner ispirato ai daemon microduck — vedi playbook passo 3). Non ancora progettato.

## Q7 — Condizioni scarse nei dati (crepuscolo, pioggia, controsole)
driving_patterns segnala che mancano. La domain randomization aiuta ma non sostituisce dati reali.
**Aperto:** pianificare sessioni in condizioni diverse prima di dichiarare la policy pronta per la
strada in quelle condizioni.
