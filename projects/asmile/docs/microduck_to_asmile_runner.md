# Da Microduck al runner Asmile — la ricetta sim2real, trapiantata e resa eseguibile

> Approfondisce [`sim2real_microduck_playbook.md`](sim2real_microduck_playbook.md):
> dove il playbook dice *cosa rubare a Microduck*, questo file dice **dove quel
> pezzo vive ORA come codice/agente** nel runner `training/sim2real/`.
> Il valore e' la ricetta, non la scocca del duck.

## La corrispondenza uno-a-uno

| Pezzo di `microduck_rl` (Pollen Robotics) | Trapianto su Asmile | Dove vive nel runner |
|---|---|---|
| Raccolta + pulizia dei rollout | Ingest delle ore di logging (video stereo + `sensors.csv`) con gate qualita' | **`training/sim2real/harvest.py`** — stadio 1, ESEGUIBILE oggi |
| Reward/env costruiti dai comportamenti osservati | Eventi guida + **intento** (scena→azione = il perche') | agente `asmile-event-miner` (stadio 2) |
| Geometria del mondo per la sim | Depth stereo → muri, gap, margini, ostacoli | agente `asmile-scene-reconstructor` (stadio 3) |
| **BAM — Better Actuator Models** (legge in tensione + attrito) | **BAM sterzo VESC** (encoder→gyro_z non lineare, speed-dependent) + **BAM freno idraulico** (stallo/inchiodamento dopo contatto pad-disco) | agente `asmile-actuator-modeler` (stadio 4) — *il perno del transfer* |
| MuJoCo Warp (mjlab) + **PPO a 50 Hz** | Env MuJoCo/mjlab 50 Hz guidato dai BAM, reward dai pattern P1–P9 / anti-pattern A1–A7 | agente `asmile-sim-builder` (stadio 5) |
| Domain randomization per-env (tensione, ritardi, attrito) | 48 V che cala, latenza BLE/GPS, aderenza gomma | reward/DR nello stadio 5 |
| Export **ONNX** on-edge | Policy → ONNX sul Pi 5 | agente `asmile-policy-trainer` (stadio 6) |
| `AGENTS.md` = playbook reward | `driving_patterns.md` (P1–P9/A1–A7) + linee rosse del `GLOSSARIO.md` | letto dagli stadi 5–7 |
| Daemon Rust: **owner unico** dell'attuatore, JSON-RPC su Unix socket | La policy **non** tocca il GPIO: parla a `speed_limiter v2` (owner del GPIO12 + flag `/tmp/emergency_brake`) | vincolo in `CONTEXT.md` / `GLOSSARIO.md`; contratto da progettare (Q6) |
| `updaterd`: release firmate + rollback + health gate | Deploy policy sulla fleet solo dopo validator PASS + **firma umana** | dottrina `CONTEXT.md` + `DECISION_LOG.md` (D002) |

## Le tre lezioni di Microduck che il runner rende operative

1. **Senza attuatori fedeli il transfer non regge.** Per questo lo stadio 4 (BAM) e'
   il perno, non un dettaglio: il freno di Asmile *non e' ideale* — e' idraulico, si
   inchioda oltre 60°, e stalla appena il pad tocca il disco. Un freno ideale in sim
   produrrebbe una policy che su strada ribalta la bici. Il BAM freno deve modellare
   proprio quel regime (linea rossa `brake_angle > 60°` = terminazione).

2. **Tanti daemon piccoli con un owner unico, non un monolite.** Il nostro problema
   ricorrente (speed_limiter vs servofreno che litigano sul GPIO12) e' lo stesso che
   Microduck risolve con `robotd` owner del bus motori. La policy sim→reale eredita
   il pattern: **parla all'owner, non al pin**. In Python, non serve riscrivere in Rust.

3. **La sim prima della strada, la firma prima del campo.** Microduck fa girare PPO a
   50 Hz — lo stesso rate delle policy sul robot — cosi' la bici sbaglia gratis mille
   volte in simulazione. Su strada esce **solo** cio' che ha passato il validator
   (stadio 7) **e** la firma di Daniele. Nessuna scorciatoia.

## Cosa NON copiamo da Microduck

- La **scocca** del duck (CC-BY-SA-**NC**, kit a $399, niente STL/BOM pubblico): a noi
  serve il software+ricetta, non il biped. Il cugino full-open stampabile e' *Open
  Duck Mini v2* se un giorno servisse hardware di riferimento.
- Il **linguaggio** (Rust): prendiamo il *pattern* dei daemon (owner unico, socket),
  lo realizziamo in Python sopra gli script sterzo/freno gia' esistenti.

## Stato

- Stadio 1 (harvester) trapiantato e **girato** sui 38 log locali (~2.96 h in movimento).
- Stadi 2–7 mappati sugli agenti `asmile-*`, in attesa dei gate (Q1–Q6) e della firma
  D001. Vedi `training/sim2real/README.md` per il come-si-lancia e
  `.collegio/DECISION_LOG.md` per lo stato firme.
