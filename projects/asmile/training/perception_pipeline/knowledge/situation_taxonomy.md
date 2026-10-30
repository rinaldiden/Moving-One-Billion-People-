# Tassonomia delle situazioni — Asmile (stadio 3: `asmile-seg-situation`)

> Vocabolario FISSO delle situazioni di guida. Lo stadio 3 classifica SOLO da qui; non inventa
> nuove situazioni. Una nuova situazione entra solo via **caso dubbio risolto da Daniele** (poi si
> aggiunge qui, con la sua firma in `DECISION_LOG`). Ereditata da `training/driving_patterns.md`
> (P1–P9/A1–A7) e da `categories.yaml`. **Tutti i trigger operano su corpus anonimo.**

## Come si legge una riga
`situazione` — trigger (classi seg + segnali sensori) → **risposta di guida attesa** (per il
reward sim2real) · *flag di incertezza* (quando mandare in `unknown`/caso dubbio).

## Situazioni di base (strada libera)
- **strada_aperta** — drivable `road` ampio davanti, nessun `person/vehicle/obstacle` nel corridoio
  → procedi, mantieni velocità nell'envelope. *Incerto se drivable frammentato/incoerente.*
- **curva** — strada che piega + `|gyro_z|` > 22°/s → sterza nei limiti (non lineare, speed-dependent).
  *Incerto se la curva non si legge nella scena ma solo nel gyro (possibile urto/scossa).*

## Situazioni con altri utenti
- **pedone_vicino** — `person` dentro o verso il corridoio, distanza stimata bassa → rallenta/pronto
  a fermarti. *Incerto su distanza grezza (`depth:coarse`) o persona parzialmente occlusa.*
- **veicolo_in_arrivo** — `vehicle` in avvicinamento (box che cresce / vy) nel semipiano opposto →
  tieni la destra, margine. *Incerto se fermo vs in moto senza depth affidabile.*
- **veicolo_sorpasso** — `vehicle` che transita lateralmente vicino → stabilità, non sterzare verso.
- **bici_pedone_gruppo** — più `person`/`bicycle` ravvicinati → prudenza, velocità bassa.
- **animale** — classe `animal` nel corridoio → rallenta/fermati (imprevedibile). *Spesso raro → flag.*

## Situazioni di spazio
- **passaggio_stretto** — drivable stretto fra due `wall`/`building`/`vehicle` (gap < soglia cm) →
  centra, rallenta. *Incerto se la larghezza dipende da depth grossolana.*
- **ostacolo_fermo** — `obstacle`/oggetto fermo nel corridoio → aggira se c'è margine, sennò fermati.
- **cordolo_marciapiede** — bordo `sidewalk`/cordolo nel corridoio → non salire, mantieni `road`.

## Situazioni di regola (segnaletica) — ⚠ gap classi
- **stop_richiesto** — stop line sotto + (full stop osservato) → fermati. *`stop_sign` NON è ancora
  in `categories.yaml` (vedi `segment_gate_jev_approach.md` §4): finché manca, molti di questi
  → `unknown` → caso dubbio.*
- **precedenza** — incrocio/immissione senza diritto chiaro → cedi. *Quasi sempre `unknown` oggi.*
- **semaforo** — `traffic_light` (classe mancante) → rosso/verde. *`unknown` finché non si aggiunge.*
- **incrocio** — convergenza di più `road`/direzioni → prudenza. *Ambiguo senza mappa → spesso caso dubbio.*

## Situazioni di stato del dato
- **low_light** — frame scuro (OV9281 di sera) → la scena è poco affidabile, peso basso. *Flag.*
- **gps_perso** — no fix GPS → non raggruppabile per strada con certezza (lo gestisce il router).
- **ferma** — bici immobile (static_rig o stop) → non è guida: separa (rumore per il training).
- **unknown** — nessuna situazione supera soglia, o due competono, o scena `novel`/`review` da monte
  → **caso dubbio per Daniele**. Non è un fallimento: è la risposta giusta quando non è chiaro.

## Regola d'oro
Meglio `unknown` + domanda a Daniele che una situazione comoda ma sbagliata. Un'etichetta finta fa
imparare al modello la logica sbagliata (anti-pattern A1–A7). La chiarezza si riconosce, non si forza.
