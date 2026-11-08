# Agenti Asmile — verticali, contro-agenti, orchestratore (2026-11-08)

Obiettivo: far **guidare Asmile in sicurezza e in autonomia**, un livello alla volta.
Daniele fa la parte fisica (accendere, girare video, test su strada) e firma; gli agenti fanno il resto.

Fonde la proposta "Schema Groma / AGENTS_FULL.md" (ogni agente ha un contro-agente, schema fisso, linee rosse,
human gate, sicurezza, deploy/rollback, regressione, retrofit) con lo stato vero del repo (percezione per unità,
depth a ritroso, lavagna con gate misurabili, Telegram del Doppio). Niente è stato tolto agli agenti esistenti:
hanno solo ricevuto la sezione "palla".

## Scala di autonomia (la spina dorsale)
| Livello | Cosa fa la bici | Si sale con |
|---|---|---|
| L0 registra | solo logging | sync, sensori, calib col metro, dati puliti |
| L1 ombra | percepisce e decide, NON agisce; confronto con Daniele | banco fisso, rettifica, depth in moto, ostacoli senza nome, TTC, classi, 5 ombre |
| L2 freno di sicurezza | frena da sola solo su ostacolo nel corridoio | BAM freno, freno ≤60° garantito, watchdog, red team, **firma** |
| L3 sterzo assistito | corregge la traiettoria con limiti stretti | limiti sterzo #001, BAM sterzo + Speed PID, 5 ombre sterzo, **firma** |
| L4 autonomia su percorso | guida su percorsi definiti, velocità limitata | sim2real + banco virtuale senza regressioni, **firma** |

I gate sono in `stato.py` → `../.collegio/001_LAVAGNA.md`.

## Le verticali (produttore → contro-agente, ognuno con la sua lente)
**Governo** (trasversale)
- asmile-capo → asmile-capo-critico · asmile-sicurezza → asmile-sicurezza-redteam · Daniele = human gate (firma)

**Dati**
- asmile-logger-ingest → asmile-ingest-critico → asmile-log-harvester → asmile-dati-auditor
- asmile-human-loop → asmile-feedback-critico

**Percezione**
- asmile-calib → asmile-calib-critico → asmile-depth → asmile-occhio
- asmile-scene-reconstructor → asmile-occhio
- segmentazione (skill asmile-segmentazione-modello, orchestrata da asmile-seg-orchestrator → asmile-capo-critico):
  seg-segmenter → seg-verifier → seg-situation → situation-scettico → seg-router → router-critico → seg-modeler → regressione

**Attuazione**
- asmile-banco-hw → asmile-banco-critico → asmile-actuator-modeler → asmile-attuatori-avversario

**Guida**
- asmile-event-miner → asmile-event-scettico → asmile-sim-builder → asmile-sim-breaker →
  asmile-policy-trainer → asmile-policy-redteam → banco virtuale (vtest-curator/replayer/scorer → vtest-critic) →
  asmile-sim-validator → asmile-regressione → **Daniele**
- asmile-online-learner → asmile-regressione (dormiente fino a L1)

**Veicolo**
- asmile-pi-001 → asmile-pi-001-verifica · asmile-deploy → asmile-rollback-guardian
- asmile-monitor → asmile-anomalie · asmile-flotta → asmile-cross-bici

**Conoscenza**
- asmile-ricercatore → asmile-ricerca-scettico · asmile-retrofit → asmile-costi-scettico

## La palla
`palla.py passa` (produttore → critico) · `palla.py verdetto` (PASSA/VETO) · `palla.py stato`.
Un PASSA con `--gate` scrive la prova in `prove/`; la lavagna conta un gate chiuso solo con quella prova (o con un
controllo automatico in `stato.py`). 3 veto sullo stesso artefatto → il capo chiede a Daniele.

## Come il capo parla a Daniele
`avvisa.py info "..."` (Terminale sul Mac) · `avvisa.py chiedi "..."` · `avvisa.py fai "accendi #001" --perche "..."`.
Se non risponde entro 10 minuti → Telegram dal Doppio (`~/progetti/doppio/telegram-brain/scrivi_a_daniele.py`).
Tutto finisce in `registro_avvisi.md`.

## Come si lancia
- Un giro: `/asmile-capo` in Claude Code (skill runbook: il capo fa girare le verticali).
- In continuo: `/loop /asmile-capo` (si autoregola).
- Rigenerare gli agenti dopo una modifica: `python3 projects/asmile/agents/genera_agenti.py` poi
  `python3 ~/progetti/doppio/fusion/learn/link_all.py`.

## File
| file | cosa |
|---|---|
| `stato.py` | lavagna: livello, gate, azioni fisiche, video da lavorare, firme mancanti |
| `palla.py` | registro passaggi produttore → contro-agente, prove dei gate |
| `avvisa.py` | parlare a Daniele: Terminale, poi Telegram |
| `genera_agenti.py` | scrive agenti e contro-agenti (schema Groma); agli esistenti aggiunge solo la sezione palla |
| `prove/` `palla/` `lezioni/` `rapporti/` `ricerche/` `retrofit/` | memoria di lavoro degli agenti |
