# Depth + segmentazione giri 13/11 di #001 — giro 3 (dopo PASSA parziale di asmile-occhio)

Unita': asmile #001. Codice: `training/depth/video_fluido_001.py` (modo `v14`, default; `VFMODE=v13` riproduce il giro 2), lanciatore `training/depth/run_giri_v3.sh`. Uscite locali (mai su git): `training/depth/out_20261113_giri_v3/` (5 video `video_fluido_*.mp4` + `tracks_*.pkl` con azione, orario, stato 'in conferma'). Stadio A invariato. Fotogrammi guardati: `agents/rapporti/img/giri3_video_fluido_150337_f*.jpg` (18). Prima/dopo = pkl del giro 2 (`out_20261113_giri_v2`) contro v14 sugli stessi 1155 fotogrammi, stesse sessioni, stesso stadio A e stesso SAM.

## Regole fissate prima di rigirare (decisione registrata con `palla.py decido`)
1. **Salti di Z.** Una traccia e' 'da confermare' se la Z della maschera salta >3.0 m fra due misure consecutive (riportate a oggi con l'encoder) oppure e' >3.0 m lontana dalla previsione del filtro (traccia gia' stabile, >=5 misure). Finche' non ci sono >=3 misure coerenti (adiacenti entro 1.5 m = 2.5 sigma stereo a 16 m) la traccia NON e' candidato: niente banner di azione, niente FRENA/RALLENTA/STERZA. Una traccia nuova che nasce sullo stesso box (IoU>0.5, stessa famiglia) di una traccia viva ma con Z incompatibile (>30%) eredita 'da confermare'. Nel video: banner giallo "OSTACOLO IN CONFERMA (Z instabile: nessuna azione)" e etichetta "? (da confermare)"; non e' ne' 'strada libera' ne' 'NON MISURATO'.
2. **STERZA solo verso un lato MISURATO libero** (regola di Daniele): libero = `clear` del lato opposto presente e >= bordo_margine. Lato non misurato = non libero. Corretto sia nel ramo 'bordo' sia nel ramo 'oggetto sul percorso' (prima `oth is None` valeva libero). Se il lato non e' libero: FRENA (entro frena_entro) o RALLENTA con motivo "lato opposto NON MISURATO".
3. **'altro'/blob** agiscono solo se la maschera interseca la sagoma bici (arco o dritta, tolleranza 0.10 m), non per il solo margine laterale; 'altro'/blob la cui estensione fisica alla Z scritta e' <0.15 m non sono candidati (e non si disegnano).
4. **NON MISURATO** (era: saturo >25% oppure depth valida <0.15 nel corridoio senza maschere): ora saturo >25% oppure (tessitura nel corridoio >=8% e depth valida/tessitura <0.35) oppure (tessitura <8% e depth valida <5%). Tessitura = celle 4x4 a risoluzione piena con >=25% di pixel a gradiente >=8 livelli/px, esclusi i saturi. **In NON MISURATO l'azione da dichiarare e' RALLENTA (lato sicuro): scritta nel video come "PROPOSTA (non decisa)" e NON contata fra le azioni. Decisione di Daniele.**

## Risultati (1155 fotogrammi, 5 tratti)
| | giro 2 (v13) | giro 3 (v14) |
|---|---|---|
| FRENA | 28 | 46 |
| FRENA con Z<1 m | 0 | 0 |
| RALLENTA | 70 | 63 |
| STERZA | 65 | 42 (tutte 'via dal bordo' con lato opposto misurato) |
| NON MISURATO | 446 | 300 (261 saturi, 39 per tessitura) |
| Fotogrammi con 'ostacolo in conferma' | - | 147 |
Il FRENA sale da 28 a 46 perche' 23 STERZA verso lato non misurato sono diventati FRENA (come chiesto: FRENA/RALLENTA, non sterzare). Nel tratto monovolume: NON MISURATO 90 -> 22, RALLENTA 36 -> 26, FRENA 1 -> 0.

## Casi richiesti
- **Monovolume f4530-4550**: nessuna azione sul monovolume prima di 11.7 m; la traccia 198 (veicolo) e la 320 (nata sullo stesso box a f4540) sono 'in conferma' (f4534-4541 e f4543-4554), **f4542 non e' piu' FRENA** (era 7.3 m: traccia 320 a 8.7, 11.3, 7.0). Prima azione stabile sul monovolume: f4569 RALLENTA a 8.9 m (f4569 visto: la sagoma del monovan occupa il corridoio, 8.9 m plausibile). Resta un RALLENTA a f4536 su un 'altro' (cassonetto?) a 8.6 m sul bordo sinistro del corridoio, fotogramma visto: forma di bidone, non so se vero (NON VERIFICATO).
- **f1142-1157 (paletti)**: guardate le tracce: **non c'e' un salto di Z della stessa traccia**. Il "primo ostacolo" passa da un paletto al successivo (id 457 a 2.4 m -> 459 a 5.1 m -> 457 a 1.5 m per l'isteresi): sono paletti diversi in fila (visto f1145: 6 paletti a 4.5-10.9 m). Il FRENA resta sui paletti veri nel corridoio. Dubbio: f1145 FRENA a 1.5 m sul paletto al bordo destro dell'immagine con corridoio che curva a sinistra (X~+0.6 m, borderline).
- **f2381-82, f2385-86**: non sterza piu' a sx: FRENA (vaso 'altro' a 7.4 m nel corridoio, palo 5.7-6.6 m; visti f2380, 2381, 2385). Le sorgenti: ramo 'oggetto sul percorso' con lato opposto non misurato.
- **f4474**: "altro 1.5 m" non e' piu' candidato (semaforo/insegna 36x74 px = 0.08 m a 1.5 m, 'tiny', e fuori dalla sagoma): primo ostacolo = persona ~13 m, nessuna azione (visto).
- **NON MISURATO tratto monovolume** f4465, f4499, f4729 (strada leggibile, visti): ora verde "nessun ostacolo misurato". Attenzione: la tessitura a risoluzione piena e' quasi zero sulla strada liscia (0.000-0.05) mentre la depth valida e' 5-13%: la regola 4 quindi di fatto vale "NON MISURATO se saturo o tessitura presente ma non misurata"; la soglia 5% non e' mai scattata. E' una regola debole: un ostacolo liscio e non saturo (muro bianco, furgone bianco) in strada senza tessitura NON viene piu' dichiarato non misurato. NON VALIDATA con verita' a terra.

## Prontezza (monovolume)
- Inizio decelerazione umana: v scende sotto 3.78 m/s a f4552 = 15:08:49.6 (da ~3.9 m/s: 4543 3.87, 4550 3.81).
- Primo RALLENTA stabile: f4569 = 15:08:50.7 (8.9 m): **ritardo ~1.1 s (17 fotogrammi)**. Nel giro 2 stesso f4569; i RALLENTA precedenti (f4536-4541, 4548-4551) erano su Z saltate (8.2, 11.3, 10.9 m per un'auto a >12 m): ora tolti.
- Cause misurate: (a) fra f4546 e f4554 la traccia e' 'in conferma' (misure 14.9->10.7->9.4 m che non sono dell'auto) e a f4555-4562 c'e' ma rallenta_entro cala con la velocita' (11.7 -> 10.2 m a 3.4 m/s) mentre la Z scritta e' 12.8-11.2: la formula con v*ttc_avviso (3 s) si abbassa proprio quando l'umano rallenta. (b) A v costante il TTC a f4555-4560 e' 3.5 s, sopra ttc_avviso 3.0 s.
- Proposta (per Daniele, non implementata): TTC sulla traccia con Z coerente (filtro) e ttc_avviso 4.0 s (rallenta_entro = max(1.5 frena_entro, v*4)). Contro-fattuale fatto sui pkl: RALLENTA a f4555 (15:08:49.8, 12.8 m) = 0.2 s dopo l'inizio della decelerazione umana invece di 1.1 s. Costo: +54 fotogrammi RALLENTA su 1155 (monovolume 33, di cui persona a 13-15 m con Z da dimensione; controsole_b 9 paletti a 10-12 m; frenata1 4, controsole_a 4); contati con il gate sagoma, non guardati uno a uno. Alternativa piu' sicura: ttc_avviso 3.5 s. La soglia va decisa con la tabella `config/soglie_attuazione_001.json` (v1 SEGNAPOSTO).

## Ostacoli veri <5 m persi?
Confronto automatico: fotogrammi in cui il giro 2 aveva il primo ostacolo <5 m e ora nessuno o >1 m piu' lontano: 4 su 1155. f4474 (il falso 1.5 m, voluto) e 3 'in conferma' di tracce nuove con <=4 misure (f187 'ostacolo' 4.6 m, f4709 palo 3.5 m, f4737 paletto 1.6 m al bordo sinistro fuori dalla sagoma: visto, nessuna azione dovuta). f187 e f4709 non guardati a occhio. Il costo della conferma e' 1-2 fotogrammi (0.07-0.13 s) sui nuovi.

## Limiti dichiarati (NON VERIFICATO)
- Nessuna distanza a terra col metro: la correzione e' di coerenza (encoder, dimensioni), non di errore %.
- Soglie 3.0/1.5/3 m, 0.15 m, 8%/0.35/5% scelte prima ma su pochi casi e sugli stessi 5 tratti: non validate su altre sessioni; regressione 12/11 non girata.
- Z grezza della maschera auto a 12-18 m oscilla di 4-6 m (raw 14.1, 16.8, 19.0, 17.0, 14.9, 13.7, 10.7, 9.4 a f4528-4537): il vero problema e' lo stadio A, la conferma lo nasconde senza correggerlo.
- 147 fotogrammi 'in conferma' (non agiscono): mai guardati tutti; 15 cestino/bollard campionati.
- STERZA 42 con margine misurato, ma 'misurato' = presenza del bordo laterale, non validato.

## Per asmile-occhio
(a) f4530-4552: nessuna azione sul monovolume prima di 11.7 m? f4536 RALLENTA su 'altro' 8.6 m: vero o falso? (b) f2381/2385: FRENA invece di sterzare giusto? (c) f4465/4499/4729 ora verdi: corretto? (d) manca un ostacolo vero in 'in conferma' (f187, f4709)? (e) proposta ttc_avviso 4.0 s: da approvare?
