# Policy "strada per strada" e curriculum — Asmile (stadio 4: `asmile-seg-router`)

> Come si raggruppano le situazioni per via/percorso e come si costruisce il curriculum di
> training. Parametri **deterministici** (stessa input → stesso output). Da calibrare sui primi
> video freschi. Ereditata dalla logica di split per-sessione del `asmile-vtest-curator`.

## 1. Clustering geografico (segmenti-strada)
Input: timeline situazioni (stadio 3) + CSV GPS (`training/training_data/`,
`driving_events_analysis.csv`: `gps_lat,gps_lon,gps_heading`).
- Raggruppa punti consecutivi con **prossimità** (distanza < `R_m`, default 25 m) **e heading
  coerente** (Δheading < `H_deg`, default 35°) nello stesso **segmento-strada**.
- Un cambio netto di heading/posizione apre un nuovo segmento (incrocio, svolta).
- **GPS assente/perso** → segmento `no_gps` marcato (non buttato): lo si potrà agganciare a mano
  o via visione in futuro.
- Niente reverse-geocoding online di default (nessuna chiamata esterna): il segmento è
  identificato da centroide+bbox GPS, non da un nome di via.

## 2. Scheda per segmento-strada
Per ciascun segmento registra:
- istogramma delle **situazioni** (dalla tassonomia) e minuti/frame in movimento;
- **condizioni scarse**: `low_light`, `no_gps_fix`, `dropout`, `depth:coarse`;
- quota di **`unknown`/`novel`/`review`** ereditati da monte (quanto il segmento è "capito").

## 3. Curriculum (facile → difficile)
Ordina i segmenti da esporre al training:
1. strada_aperta / curve dolci (tanti esempi, bassa incertezza) →
2. altri utenti a distanza →
3. passaggi stretti / ostacoli / pedoni vicini →
4. situazioni di regola (stop/precedenza/incrocio) — oggi **scarse** per i gap-classe.
Il curriculum è un **ordine proposto**, non un filtro: niente viene buttato, solo pesato/ordinato.

## 4. Data-gap (si dichiarano, non si tappano)
- Segmento con troppo poche situazioni di un tipo → **gap** → input per pianificare sessioni
  mirate (es. "serve frenata forte", "serve crepuscolo"), **non** si gonfia con padding.
- Classi di regola mancanti (`stop_sign`/`traffic_light`/`give_way`) → gap noto (Q apertura).

## 5. Split train / held-out — per STRADA, mai per frame
- L'held-out si tiene **a livello di segmento-strada** (come il vtest fa per sessione): così il
  modello non "ha già visto" quella strada. Niente leakage per frame.
- Includi a forza nell'held-out le **condizioni scarse** (altrimenti non le valuti mai).

## 6. Ambiguità → caso dubbio
Un segmento con troppi `unknown`/`novel`, o situazioni in conflitto lungo la stessa strada, →
l'orchestratore apre un caso dubbio: "questa strada non la capisco, guardala tu". La risposta di
Daniele può correggere lo split o aggiungere una regola qui.

## Regola d'oro
Il curriculum serve a **bilanciare e vedere i buchi**, non a nascondere ciò che manca. Un gap
dichiarato è una sessione da registrare; un gap tappato è un modello che crede di sapere e non sa.
