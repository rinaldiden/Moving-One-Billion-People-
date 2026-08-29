# Il banco di prova virtuale — cosa abbiamo scavato in Microduck e come lo usiamo

> Approfondisce [`sim2real_microduck_playbook.md`](sim2real_microduck_playbook.md) e
> [`microduck_to_asmile_runner.md`](microduck_to_asmile_runner.md). Là la ricetta di
> Microduck diventa la **pipeline di training** (7 stadi, costruisce il modello nel
> simulatore). Qui la stessa ricetta chiude l'anello che a loro manca: il **banco di
> prova virtuale**, che *prova* un modello già fatto contro i video reali.
> Il valore è la ricetta, non la scocca del duck.

## Cosa ho scavato nei repo di Microduck (Pollen Robotics)

Fonti lette: `pollen-robotics/microduck_rl` (README, `AGENTS.md`, `tasks/mdp.py`,
`actuator/friction_dr_bam.py`), `pollen-robotics/microduck` (firmware Rust, `robotd`),
il paper BAM di Rhoban (arXiv 2410.08650), e il cugino open `apirrone/Open_Duck_Mini`
(`docs/sim2real.md`) + `Open_Duck_Playground`.

### Come imparano (il modello di auto-apprendimento)
- **Stack RL:** `mjlab` (MuJoCo **Warp**, GPU) + **PPO** via `rsl_rl`. Control loop **50 Hz**,
  lo stesso rate in sim e sul robot — è un vincolo duro del contratto, non un dettaglio.
- **Contratto di osservazione fisso** (61-D nel duck), condiviso da tutte le policy: gli
  slot di comando inutilizzati si **azzerano**, non si rimuovono → una policy si può
  hot-swappare dietro lo stesso contratto e **l'export ONNX non cambia**.
- **Reward potential-based:** pagano il *Δprogresso* (avvicinarsi all'obiettivo), mai lo
  stato assoluto; hard-gate (contatto, orientamento) invece di penalità morbide; niente
  "jackpot" (rate-limit sui reward "raggiungi X"). Sta scritto in `AGENTS.md`: *"RL
  optimizes the letter of the reward"* — ogni ambiguità verrà sfruttata.

### BAM — il perno del transfer (Better Actuator Models)
- L'attuatore **non** è un PD ideale: è un motore DC modellato con **legge in tensione +
  back-EMF** (`torque = kt·V/R − kt²·dq/R`) e un modello d'attrito esteso **M1→M6**
  (Coulomb-Viscoso → Stribeck → load-dependent → quadratico). MicroDuck usa **M6**.
- **Identificazione dai dati reali:** banco a pendolo, ~100 log da 6 s per attuatore,
  fitting con **CMA-ES/Optuna**, loss = **MAE** tra θ simulata e registrata,
  *simulation-in-the-loop*. Output → i campi MJCF `damping, kp, frictionloss, armature,
  forcerange`. M4/M6 riducono l'errore 2-3× rispetto al Coulomb-Viscoso.
- **Domain randomization:** tensione batteria, sag sotto carico, ritardo comando, scala
  d'attrito per-episodio, IMU zero-centered. Il **backlash** (gioco) è modellato come
  cerniera passiva ±1° in serie, non come rumore.

### Come validano PRIMA della strada — e il buco che lasciano
Il loro gate (da `AGENTS.md`): smoke test 64-env, test di regressione CPU sui **segni**
delle reward, monitoraggio del training, **eval headless + ispezione video** obbligatoria,
rehearsal dello switching di policy. Ma — punto chiave — **non c'è un replay/shadow
quantitativo contro dati reali held-out**. Chiudono il sim2real gap *a monte* (BAM fedele
+ DR + backlash) e lo verificano *a occhio* (video), senza una metrica sim-vs-real
numerica. È normale: un biped non ha un "guidatore umano registrato" da confrontare.

### Licenze
Codice `microduck_rl` e firmware: **Apache-2.0**. Meccanica/3D: **CC BY-SA-NC** (non
commerciale, niente STL/BOM pubblico, kit $399). A noi serve **software + ricetta**, non
la scocca. Il full-open stampabile è *Open Duck Mini v2*.

## Il buco è la nostra occasione: il banco di prova virtuale

Asmile ha quello che ai duck manca: ogni sessione è **video stereo + sensori
sincronizzati**. Quindi possiamo fare il pezzo di validazione che loro non fanno —
rigiocare il modello sulle osservazioni reali e **misurare** la distribuzione di
|azione_modello − azione_umana| su dati mai visti in training. Non "sembra guidare bene":
*ecco il gap, per pattern, con la coda*.

### La corrispondenza uno-a-uno

| Pezzo di Microduck | Nel banco virtuale Asmile | Dove vive |
|---|---|---|
| Eval headless + ispezione video (qualitativa) | **Replay/shadow held-out quantitativo** modello-vs-umano | `vtest/vtest.py` + `shadow_analyzer.py` |
| Split train/id degli attuatori (75/25) | Split **held-out per sessione** (anti-leakage) del corpus | agente `asmile-vtest-curator` / `vtest/holdout.py` |
| Contratto osservazione fisso + ONNX invariante | Contratto obs del modello (`(2,100,160)` + 2 scalari), stesso in sim e reale | `behavioral_cloning.py`, riusato dal replayer |
| Test di regressione sui **segni** delle reward | **Scheda pattern P1-P9 / anti A1-A7** + linee rosse | agente `asmile-vtest-scorer`, rubrica `driving_patterns.md` |
| Rehearsal avversariale prima del deploy | **Caccia ai casi peggiori** + verdetto go/no-go proposto | agente `asmile-vtest-critic` |
| `updaterd`: release firmate + rollback + health gate | Strada solo dopo verdetto PASS **+ firma umana** | `CONTEXT.md` + `DECISION_LOG.md` (D002/D004) |

### Le tre lezioni di Microduck, applicate al banco

1. **Contratto fisso, non si negozia.** Come loro azzerano gli slot di comando invece di
   rimuoverli, il nostro replayer usa il contratto obs esatto del modello (nessuna
   ipotesi): se un domani la BC diventa una policy ONNX, il banco la prova senza cambiare.
2. **Il momento che conta non è la media.** Loro rate-limitano i "jackpot" perché RL
   sfrutta la lettera del reward; noi rompiamo il gap **per pattern**, perché un errore
   medio basso può nascondere la frenata sbagliata per la persona (P3/A6/A7).
3. **La sim prima della strada, la firma prima del campo.** Loro provano mille volte in
   sim gratis; noi proviamo il modello mille frame gratis sui video. Su strada esce solo
   ciò che passa il critic **e** la firma di Daniele. Nessuna scorciatoia.

## Cosa NON copiamo
- La **scocca** del duck (licenza NC, kit chiuso): serve software+ricetta, non il biped.
- Il **linguaggio** (Rust): prendiamo il *pattern* (owner unico, contratto fisso, gate
  firmato), lo realizziamo in Python sopra gli strumenti già scritti (`shadow_analyzer.py`).
- Il loro **limite**: la validazione a occhio. Noi la rendiamo numerica.

## Stato
- Banco eseguibile in `training/vtest/` (`vtest.py` + `holdout.py`). Stadio 1 (curator)
  **girato** sul corpus: 9 sessioni held-out, ~0.6 h in movimento, leakage `non_verificato`.
- Stadio 2 (replayer) in attesa di `cv2` sul Mac; comandi `shadow_analyzer.py` già stampati.
- Stadi 3-4 (scorer, critic) mappati sugli agenti `asmile-vtest-*`. Verdetto = proposta.
  Strada dietro D002 + firma. Voce di adozione: **D004** nel `DECISION_LOG.md`.
