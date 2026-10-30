# Protocollo "casi dubbi" — il gate umano (orchestratore → Daniele)

> Il cuore della richiesta di Daniele: *"quando una situazione non è ben chiara o non è definita,
> mi manda personalmente la situazione da valutare e capire, per poi passarla al modello."*
> Questo file definisce **quando** si apre un caso, **cosa** contiene, **come** arriva a Daniele e
> **come** la sua risposta rientra nel modello. Lo applica `asmile-seg-orchestrator`.

## Quando si apre un caso (chi lo propone)
- **verifier** → frame `review` ad alto peso o `novel` (OOD) su classe critica.
- **situation** → `situation = unknown` sopra soglia, o due situazioni in conflitto.
- **router** → segmento-strada con troppi `unknown`/`novel` o situazioni contraddittorie.
- Regola: si apre un caso **solo quando il dato tace**. Dove la pipeline è sicura, non disturba Daniele.

## Cosa contiene un caso (schema: `schemas/case.schema.json`)
- `id` — hash stabile (sessione + range frame + stadio): stesso dubbio = stesso id (dedup).
- `session`, `frame_range`, `stage`, `created` (timestamp passato dal chiamante, non generato qui).
- `scene_summary` — **cosa vedeva la bici**, SENZA PII: classi presenti + posizione (centro/lato) +
  distanza stimata + mappa drivable + segnali sensori (decel, gyro, velocità, GPS).
- `candidate_interpretations` — le letture possibili con confidenza (es. "pedone che attraversa 0.45"
  vs "persona ferma a lato 0.4").
- `question` — **la domanda precisa** per Daniele, in italiano, breve.
- `options` — opzioni proposte (+ sempre "Altro" libero): Daniele sceglie o scrive.
- `is_general` — il chiamante propone se la risposta è una **regola generale** (→ knowledge) o solo
  per questa scena (→ label locale).

## Niente PII — mai
Il corpus è già anonimo (`asmile-anon-*`), ma per prudenza il caso porta **solo contesto di scena**
(classi, box, distanze, sensori), **mai** il frame con volti/targhe in chiaro. Un eventuale
riferimento al frame è un path **locale**, non un'immagine incorporata.

## Come arriva a Daniele
1. L'orchestratore scrive `casi_dubbi/queue/<id>.json`.
2. Lo **segnala su Telegram** (canale del doppio): messaggio con `question` + `options`, link al
   path locale del frame. Uno per volta, chiaro. **Non decide al posto suo.**
3. In attesa, la catena **blocca solo** la parte che dipende da quella scena; il resto prosegue.

## Come rientra nel modello (reiniezione)
1. Daniele risponde (opzione o testo libero).
2. L'orchestratore scrive `casi_dubbi/resolved/<id>.json` con il verdetto + `applied_as`:
   - `label` → corregge il record in `03_situations`/`04_roads` e riprende la catena da lì;
   - `rule` (se `is_general`) → aggiorna la **knowledge** (`situation_taxonomy.md` o
     `road_curriculum_policy.md`) **con una nota + voce `DECISION_LOG`** per la firma di Daniele.
3. Il modello, al prossimo giro del modeler, impara dalla scena corretta. Il dubbio è diventato dato.

## Idempotenza — "se lo chiedi due volte, hai fallito"
Un caso con id già presente in `resolved/` **non si ri-manda**: si applica la regola salvata. La
coda si dedup sull'id. Chiedere due volte la stessa cosa a Daniele è un bug, non un comportamento.

## Confine
Il verdetto è **sempre** di Daniele — l'orchestratore propone interpretazioni e opzioni, non sceglie.
In dubbio: non ottimizzare, aspetta.
