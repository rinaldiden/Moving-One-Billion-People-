# sim2real/ — il runner eseguibile della pipeline di guida autonoma Asmile

> Qui la pipeline **smette di essere solo un disegno** e comincia a girare sui video
> di guida che abbiamo gia' in locale sul Mac. Replica la ricetta sim2real di
> **Microduck** (Pollen Robotics) e la trapianta su Asmile.
>
> Tesi e vincoli: [`../../.collegio/CONTEXT.md`](../../.collegio/CONTEXT.md) ·
> linee rosse: [`../../.collegio/GLOSSARIO.md`](../../.collegio/GLOSSARIO.md) ·
> diagramma: [`../../docs/pipeline_agenti_sim2real.md`](../../docs/pipeline_agenti_sim2real.md) ·
> runbook agenti: skill `asmile-sim2real-pipeline`.

## Cosa c'e' qui

| File | Cosa fa |
|---|---|
| `pipeline.py` | Orchestratore: definisce il DAG dei 7 stadi + i gate, esegue lo stadio 1, si ferma davanti a ogni stadio non ancora sbloccato. |
| `harvest.py` | **Stadio 1 (asmile-log-harvester) eseguibile.** Scopre le sessioni locali, sincronizza video↔sensori, applica i gate di qualita', scrive il corpus indicizzato. Solo stdlib (+ ffmpeg/ffprobe opzionali). |
| `corpus/` | Output additivo dell'harvester: `corpus_index.json` + `manifests/<sessione>.json`. **Non** contiene grezzi, non li duplica: li indicizza. |

## Come si lancia

```bash
cd projects/asmile/training/sim2real

python3 pipeline.py --plan        # stampa il DAG completo + lo stato dei gate (non esegue)
python3 pipeline.py               # stampa il DAG ed ESEGUE lo stadio 1 sui video locali
python3 harvest.py --no-video     # solo stadio 1, gate CSV, veloce (salta brightness/probe)
python3 harvest.py --roots ~/wip/recorder   # aggiunge altre cartelle di sessioni
```

## Cosa e' automatico e cosa no (il confine)

- **Stadio 1 (harvester) = AUTO.** E' data-processing puro e additivo: legge i log,
  scrive un indice, **non tocca** strada / hardware / denaro / grezzi. E' il
  *"iniziano a testarlo su tutti i video in locale"* chiesto da Daniele.
- **Stadi 2–7 = AGENTE + GATE.** Sono lavoro degli agenti `.claude/agents/asmile-*`
  (event-miner, scene-reconstructor, actuator-modeler, sim-builder, policy-trainer,
  sim-validator) piu' la toolchain sim (MuJoCo/mjlab). Il runner li **elenca e li
  gaterizza**, non li lancia da solo: partono quando cadono i prerequisiti aperti
  (Q1–Q5 in `QUESTIONI_APERTE.md`) e quando **D001 e' firmata** in `DECISION_LOG.md`.
- **Strada = MAI in autonomia.** Nessuna policy esce dal validator alla strada senza
  PASS dei gate **e** firma di Daniele (D002). Il validator propone, l'umano firma.

## I gate di qualita' dell'harvester (perche' esistono)

| Flag | Regola | Perche' |
|---|---|---|
| `static_rig` | < 2% righe in movimento (gps<0.3 m/s ∧ \|gyro_z\|<3°/s ∧ encoder fermo) | Bici sul cavalletto = rumore. E' l'errore del 2026-05-18 (GB di video statici). Se 100% static_rig, l'harvester **si ferma** su quella sessione. |
| `low_light` | brightness media (YAVG) < 60 | Notte / `gst-launch` scuro. Le OV9281 rendono male al buio (CLAUDE.md). Si marca, non si butta. |
| `dropout` | buco fra campioni > 500 ms | Gap CSV/frame. Si marca per spezzare in sotto-clip a valle. |
| `sync_drift` | \|durata_video − durata_sensori\| > 1.5 s | Video e sensori vanno riallineati prima di accoppiare scena→azione. |
| `no_gps_fix` | < 5% righe con fix GPS | GPS assente: gyro + encoder restano validi, ma niente path following. |

**L'harvester marca, non cancella mai i grezzi.** La retention e' decisione umana
(memoria: log rotation).

## Stato al primo run (2026-08-29)

Harvester eseguito su `segmentazione/da_segmentare/` (38 sessioni locali):
- **38/38 ammesse**, 0 static_rig, 5 low_light, 6 dropout, molte con sync_drift.
- **~2.96 h in movimento** su 4.58 h registrate.
- Implicazione **Q1**: sopra la soglia per il **BC** (behavioral cloning gia' utile),
  sotto la soglia ~5 h per un **PPO** fedele. Servono altre ore in movimento.

Rilanciando dopo nuove sessioni, il corpus si aggiorna da solo: **zero costo
marginale** per sessione, come vuole la tesi.
