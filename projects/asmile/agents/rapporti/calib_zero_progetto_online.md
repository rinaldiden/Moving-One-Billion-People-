# Strada "calibrata dal progetto + si finisce da sola in strada" (2026-11-09)

Autore: asmile-calib. Solo analisi sul Mac, nessun Pi toccato, nessun messaggio inviato.
Script e numeri: `agents/prove/calib_zero_online/` (servono i file di lavoro `m.pkl`, `triples.pkl`, `cum.npy` generati da `ext.py`, `plan.py`, `t3.py` nella scratchpad; i video restano locali).

## 1. Idea in breve
- Il fornitore ci da un modulo monoblocco (un PCB/barra, lenti fisse incollate, baseline 200 mm fissata dal pezzo). Noi NON mettiamo scacchiere, stazioni, pan/tilt.
- Nel firmware c'e' una calibrazione NOMINALE di modello (uguale per tutte le unita').
- La bici la rifinisce da sola guidando, in 3 stadi:
  1. **dy** dai match L-R: stima pitch/roll/distorsione (niente bersaglio).
  2. **moto + ruota**: due frame a ~1 m di distanza (encoder ruota) danno la profondita' SENZA usare focale ne' offset di disparita'. Confrontata con la disparita' stereo da' **focale f** e **offset d0** (yaw/centratura).
  3. **controllo di coerenza** e gate: finche' i 3 indicatori non sono verdi, la depth e' "non validata" e non frena.
- Cio' che non si stima in strada va messo nella **specifica d'acquisto** al fornitore (sezione 6), con collaudo a campione fatto da LUI.

## 2. Tolleranze e quanto pesano a 5 m se NON si calibra (misurato)
Metodo: prendo i 88.456 match reali L-R della corsa #001 094146 (frame in movimento, `agents/prove/calib_zero_online/t1.py`), uso `calib_asmile-001.json` come "verita'" (e' validata col metro ±1% sul centro), la sporco con UN errore alla volta, e ricalcolo la Z dei punti che per la verita' stanno tra 2 e 8 m. Disparita' a 5 m = fB/Z ≈ 46 px. Errore % mediano:

| Errore di montaggio (un solo parametro) | Z centro | Z bordi | spostamento verticale dy |
|---|---|---|---|
| yaw ±0.05° | 1.8% | 2.9% | 0.03 px |
| yaw ±0.1° | 3.5% | 5.8% | 0.06 px |
| yaw ±0.3° | 10.7% | 17.9% | 0.17 px |
| centro-ottica x destra ±3 px (9 µm) | 5.4% | 8.0% | 0.05 px |
| centro-ottica x destra ±8 px (24 µm) | 14.6% | 22.2% | 0.12 px |
| centro-ottica x destra ±17 px (51 µm) | 33.5% | 56.3% | 0.26 px |
| focale L/R diversa di 1% | 1.9% | 12.6% | 2.7 px |
| focale L/R diversa di 3% | 5.7% | 33.8% | 8.1 px |
| focale comune ±3% | 0.9% | 0.7% | 3.3 px |
| k1 L/R diverso di 0.05 | 0.6% | 13.8% | 1.3 px |
| k1 comune ±0.05 | 0.4% | 2.3% | 1.3 px |
| pitch ±0.3° | 0.2% | 0.8% | 6.3 px |
| roll ±0.3° | 2.6% | 2.1% | 0.9 px |
| centro-ottica y ±8 px | 0.15% | 0.24% | 8.5 px |

Nota sulla focale comune: pesa poco qui (0.9% per 3%) perche' nel mio modello cambiare f cambia anche la correzione della distorsione e si compensano in parte; in generale Z scala come f, quindi f sbagliata del 3% = errore di scala fino al 3%. Non fidarsi di questo 0.9% come regola.

Lettura semplice:
- **Chi ammazza la depth e NON si vede in dy**: yaw e centratura x (cioe' l'offset di disparita' d0). Bastano 3 px (9 µm, meno di un capello) per 5%. Nessuna tolleranza meccanica realistica li tiene: vanno stimati in strada. La dy non li vede (0.03-0.26 px).
- **Chi si vede in dy** (pitch, roll, centro y): si stima online facilmente dai match, e pesa poco sulla Z.
- **Chi rovina i bordi**: focale diversa tra le due lenti e distorsione diversa. Si vedono in parte in dy (2.7 px, 1.3 px) ma non basta a fissarli.
- Le tolleranze tipiche di lenti M12 (focale ±x%, centratura, angoli sul PCB) NON le ho verificate da fonte primaria: **NON VERIFICATO**. Le ho coperte con tabelle a 3 livelli (sopra) e con perturbazioni in prova (sezione 4). Da chiedere al fornitore (bozza in sezione 6).

## 3. Cosa si stima online dal moto e cosa NO
| Grandezza | Online? | Come | Misurato |
|---|---|---|---|
| pitch, roll, centro y | SI | dy dei match (`selfcalib_essential.py` va bene per la posa; qui un fit robusto con prior) | dy mediana 0.9 px |
| yaw + centratura x (d0) | SI, ma NON dalla sola geometria epipolare | profondita' da moto+ruota vs disparita' | d0 sd 0.10-0.14 px |
| focale (scala) | SI, serve una scala assoluta | stessa regressione, scala data dall'encoder ruota | bias -2.3%, sd 1.2% (115 coppie), 2.7% (30), 4.3% (15) |
| baseline | no, ma non serve | fissata dal pezzo (0.2 mm su 200 = 0.1%) | — |
| k1 L/R, focale L/R a bordo immagine | SOLO IN PARTE | dy lo vede un po', serve prior stretto | bordi mediana 3-4%, p90 ~11% |
| rx e centro-y insieme | NO (degeneri) | stesso effetto sul dy: si fissa centro-y al nominale e rx assorbe | senza fissarlo il fit scappa a rx +5°, dcy +90 px |

Cose che ho provato e FALLITO (da sapere):
- Solo dy con tutti i parametri liberi: dy scende a 0.54 px (meglio della calib attuale!) ma la depth e' sbagliata di 30-100%: il fit scappa su soluzioni con yaw di ~11° e focale +400 px. dy da solo non basta e non e' un giudice.
- Fissare yaw e centro-x al nominale e lasciar assorbire tutto a d0 funziona; fissare anche centro-y e' necessario.
- La "regola del cielo" (la disparita' dei punti piu' lontani = 0) NON basta: nei dati il 3° percentile delle disparita' corrisponde a ~150 m (1.5 px), il 5° a ~100 m (2.2 px). Dipende dal percorso (in citta' stretta sarebbe molto peggio). Sbaglia d0 di 1-3 px = 2-6% a 5 m. Non usarla da sola.
- Regressione semplice d vs 1/Z con Z da moto: f sbagliata del -12% (diluizione per rumore su Z). Selezionare i punti per DISPARITA' (grandezza pulita) e non per Z da moto riporta il bias a -2.3%.

## 4. Prova offline sui dati veri (nostri)
Dati: corsa #001 `session_20261109_094146`, 10.066 frame, 402 frame con match SIFT stereo (88.456 match) + 115 coppie temporali (frame a ~1 m di distanza, scelte dove l'encoder da' >2 m/s). Camere dichiarate L = file `*_right`, R = file `*_left` (come in `m4_moving_sift.py`).

**4a. Profondita' da moto vs stereo (principio)**, intrinseche della calib attuale, scala spazio da encoder ruota calibrato sul GPS (vedi limiti):
- Z_moto / Z_stereo per Z tra 3 e 12 m: 1.025, 1.030, 0.973 (mediane per fascia); 12-20 m: 0.97; 20-40 m: 0.94.
- Scarto per punto: 7-18%. Non serve: con migliaia di punti si media (sotto).
- Stima f: 1127 px contro 1153.5 della calib (−2.3%), d0 = −0.19 px.
- Sensibilita' alle intrinseche usate lato moto (f ±3%, k1 ±0.05): f stimata cambia di 1-4%, d0 di <0.7 px.

**4b. Pipeline completa da calibrazione nominale sporcata.** Parto da `calib_asmile-001.json` con errori casuali (6 estrazioni per livello): angoli, f L/R, k1 L/R, centro-ottica. Poi stadio 1 (dy con prior), stadio 2 (f e d0 da moto), e confronto con la calib attuale su match mai usati nel fit, punti tra 2 e 8 m:

| Livello di sporco (1 sigma) | Errore Z PRIMA (centro / bordi, mediana) | DOPO centro: mediana (p90) | DOPO bordi: mediana (p90) |
|---|---|---|---|
| piccolo: 0.2°, f 1%, k1 0.02, pp 5 px | 5.7% / 13.8% | 1.1% (1.8%) | 3.2% (11.0%) |
| medio: 0.5°, f 2%, k1 0.03, pp 10 px | 30.5% / 39.9% | 1.9% (2.8%) | 3.0% (10.6%) |
| grande: 1°, f 4%, k1 0.05, pp 20 px | 61.1% / 39.9% | 1.75% (2.9%) | 3.7% (11.6%) |

Cioe': partendo da un nominale con errori che da soli darebbero 30-60% (rotto), la pipeline riporta il **centro a ~1-2% mediano (p90 ≤3%)**, quasi indipendentemente da quanto era sporco il punto di partenza. I **bordi** restano a ~3-4% mediano e ~11% p90: NON raggiungono il gate (±2% <5 m).

Ripetibilita': f estratta da moto sui 6 casi del livello medio: 1110-1210 px (ref 1153), cioe' ±4% con 115 coppie; con ~600 coppie (circa un'ora di guida) l'errore statistico scenderebbe a ~0.5%, ma resta il bias di scala di cui sotto.

## 5. Limiti onesti (da leggere prima di fidarsi)
1. Il "vero" e' `calib_asmile-001.json`: valido col metro sul centro (±1% a 1-15 m), **non provato ai bordi**. Gli errori "bordi" sono differenze da quella calib, non da un metro. Per i bordi serve il banco fisso con bersagli ai lati (c'e' `banco_fisso_asmile-001_vicino_bordi.json`, non usato qui).
2. Scala assoluta da ruota: nei dati `enc_wheel_cum` ha una unita' che non quadra con le specifiche (58,8 milioni di tick per ~1230 m): **NON VERIFICATO** come ticks per giro. Ho calibrato metri/tick con la distanza GPS della stessa corsa (±qualche %). Quindi il bias −2.3% su f contiene anche l'errore di scala GPS. Con l'encoder e la circonferenza misurata col metro (1.576 m/giro, memoria progetto) la scala sarebbe indipendente: da rifare quando l'unita' dell'encoder e' chiarita.
3. Un solo percorso (Tirano, una unita', camere montate a mano). Su monoblocco gli angoli sono meno sporchi, ma questo non e' provato. In ambienti poveri (muro, buio) le 115 coppie non si trovano.
4. Il mio triangolatore da moto e' grezzo (niente bundle adjustment). Un metodo migliore dovrebbe abbassare lo scarto per punto.
5. dy mediana 0.9 px, p95 3.4 px: il gate e' p95 < 1 px. Ma la calib attuale sugli STESSI match da' 1.01 / 5.26: parte e' rumore dei match SIFT (soglia 2 px). Il gate va rimisurato con match sub-pixel prima di dire qualcosa.
6. Il prior stretto su centro-y e yaw al nominale e' una scelta mia (altrimenti il fit scappa). Con un monoblocco vero va giustificato con la specifica al fornitore.
7. `calib_asmile-001.json` e' per #001; per un logger o un monoblocco nuovo ogni numero qui e' un ordine di grandezza, non una calib (regola per unita').

## 6. Il modo piu' furbo per togliere la parte non stimabile, senza nostra stazione
Obiettivo: nessuna stazione nostra. Tre mosse, tutte lato fornitore o lato software.

1. **Specifica d'acquisto del modulo** (la fa il fornitore, con collaudo a campione suo, non nostro):
   - lenti con focale EFL ±1% e k1 L/R nello stesso lotto (stesso stampo/stesso lotto, tabella di distorsione del lotto in dotazione);
   - centro-ottica relativo tra i due sensori ≤ ±20 µm (= 7 px): con l'online (d0 ±0.15 px) resta largamente coperto, ma tiene il fit lontano da soluzioni degeneri;
   - lenti in VETRO o barilotto metallico per f stabile con la temperatura (plastica: f e fuoco derivano con ±30 K; NON VERIFICATO);
   - barra in un pezzo (alluminio) con i due sensori sullo stesso PCB: baseline fissa, angolo relativo ≤ 0.3°.
   Tolleranze realmente ottenibili: **NON VERIFICATE**, da chiedere (bozza qui sotto).
2. **Scala f dal "binning" per lotto**: il fornitore misura l'EFL di un campione per lotto (non 15.000 unita'), noi carichiamo la f di lotto come nominale. In strada la scala si raffina con encoder (±1-3% come misurato). Cosi' l'errore di f da ±3-5% scende verso ±1%.
3. **Evitare di cercare la precisione dove non serve**: la depth che serve a frenare e' sul corridoio davanti (centro immagine). Il centro raggiunge ~1-2% (p90 ≤3%) con questa pipeline. I bordi (3-4%, p90 11%) servono per l'avvertimento laterale, dove ±10% a 5 m e' accettabile (gate attuale: ±5% 5-10 m, ±10% 10-20 m). Proposta: il gate ±2% <5 m vale sul corridoio centrale, i bordi hanno il loro gate piu' largo. **Decisione di Daniele**, non mia.

Per chi non puo' fare nulla di tutto cio' (logger senza encoder): la scala resta ancorata dalla baseline e dalla velocita' IMU/ruota BT; non e' il verticale della frenata.

**Bozza (NON inviata, parte solo col tap di Daniele)** al fornitore del modulo:
> Buondi, per un modulo stereo monoblocco con due OV9281 (baseline 200 mm su un unico pezzo) ci servirebbero questi dati: tolleranza EFL delle lenti M12 per lotto, centratura lente-sensore in µm, disallineamento angolare tra i due sensori in gradi, disponibilita' di tabella di distorsione per lotto, possibilita' di allineamento attivo. Quali sono i valori garantiti e come li collaudate? Con profonda gratitudine 🙏 Daniele MM

## 7. Costo per unita'
- Calibrazione in fabbrica nostra: 0 minuti, 0 infrastruttura.
- Costo indiretto: specifica piu' stretta sul fornitore (prezzo del modulo piu' alto, da chiedere: NON VERIFICATO) + ~6-10 minuti di guida per la convergenza completa (115 coppie in una corsa di 11 minuti; 30 coppie ≈ 1.5 minuti dava f ±2.7%).
- Elaborazione: gira in pochi secondi sul Mac per la prova; sul Pi non misurato (NON VERIFICATO).

## 8. Giudizio
- La strada regge **per il centro**: da un nominale rotto riporta a ~1-2% senza bersagli (prova su dati veri, 18 estrazioni).
- Non regge ancora **ai bordi** (3-4% mediano, p90 11%) e la scala assoluta e' ancora ancorata al GPS: due cose da chiudere prima di dire "non calibriamo niente".
- Il metodo dipende da due ipotesi da provare su un monoblocco vero: (a) angoli piccoli, (b) lente stabile in temperatura.
- Non e' ancora un gate: mancano il banco fisso con soste del metro mai usate sul percorso e il giudizio di asmile-calib-critico.
