# Set delle manovre per il maestro — 25/11/2026

Autore: capo (lavoro sul Mac, nessun Pi né logger toccato). Obiettivo di Daniele: da tutti i video utili esce, per ogni frenata e sterzata, COME, DOVE, PERCHÉ, le classi della scena e le distanze dove valgono. Si fa una volta sola, e i casi che il maestro non capisce vanno a Daniele.

Legenda: **[verificato]** = misurato o guardato da me. **[presunto]** = non controllato.

## 1. Le 30 frenate del giro #001 del 25/11 09:50 (ripresa del lavoro di asmile-seg-situation)

Metodo (decisioni in `agents/decisioni/asmile-seg-situation.md`):
- La tassonomia è quella fissata alle 11:52.
- Per avere un riferimento ho guardato 4 fotogrammi per frenata: t-4, -2, -1 e 0 s, camera fisicamente destra. Ho scritto la mia lettura in `training/set_manovre/lettura_visiva_frenate_001_20261125.csv` alle 15:40, PRIMA di calcolare le regole.
- Le regole hanno soglie dichiarate e una priorità fissa (`training/set_manovre/perche_frenate_001.py`). Le ho ritoccate due volte guardando solo le prime 15 frenate. Le ultime 15 le ho contate una volta sola.
- Lo scettico (asmile-situation-scettico) ha dato **VETO parziale**. Ho applicato le sue note (`revisione_scettico_frenate_001.csv`): #26, #27, #29 e #30 tornano a Daniele, e #29 e #30 diventano un solo caso.

Risultato **[verificato]**:
- **Accordo regola–occhio: 13 su 30.** 6/15 sulle prime 15, 7/15 sulle ultime 15.
- Dichiarato: le ultime 15 davano 6/15 prima che aggiungessi il secondo file sensori. Le frenate 26-30 cadevano dopo la fine del primo file e non avevano sterzo né imbardata. La regola da sola è quindi debole.
- **Perché finale** (colonna `perche` di `training/set_manovre/perche_frenate_001_20261125.csv`):

| perché | quante | frenate |
|---|---|---|
| curva | 4 | #5, #13, #14, #17 |
| persona/bici | 1 | #4 |
| ostacolo in traiettoria | 1 | #19 (lettura visiva incerta: in coda) |
| rallentamento senza motivo visibile | 3 | #3, #12, #16 (tutte in coda) |
| **unknown (dubbio)** | **21** | regola e occhio non d'accordo, oppure lo scettico le ha rimandate |

- **Certe e fuori coda: 5** (#4, #5, #13, #14, #17). **In coda per Daniele: 25 frenate in 24 casi** (#29 è unita a #30).
- Che cosa dice il mio occhio sulle 30, come indicazione e non come verità: curva 10, incrocio/immissione 5, auto ferma di lato 4, auto in arrivo 3, persona 2, ostacolo 1, senza motivo 5. Il rapporto ombra aveva notato le cose a 8-20 m: lo confermo. Correggo però alcune letture del rapporto ombra: #1 era un camion fermo, non una persona; #12 è un cartello di pericolo (dosso?) con il limite 40.
- Dove sbaglia la regola **[verificato]**:
  - La stereo a 500 kbps dà pali a "2 m" che in realtà stanno a 10 m, e muri lunghi chiamati "barriera". Li ho filtrati con "a terra" (il fondo del box sulla riga della strada) e con il controllo d'altezza.
  - SAM 3 vede una giacca appesa come "persona" (#15) e probabilmente la testa di un lampione come "stop" (#11, ritaglio guardato: dubbio).
  - L'auto in arrivo si perde quando è a 15-20 m: lì ci sono pochi punti stereo validi.
  - L'incrocio non si riconosce dai bordi del guidabile.

## 2. Inventario (`training/set_manovre/inventario.py` → `inventario_sessioni.csv`; asmile2 → `sessioni_asmile2.csv`)

| unità | sessioni | ore video | ore in moto misurate | usabili per manovre | note |
|---|---|---|---|---|---|
| asmile #001 | 80 | 8,40 | **0,89** (encoder ruota) | 4 sì (0,46 h video) + 20 forse (5,77 h, freno automatico da separare) | video ~540 kbps; sensori con data finta 30/10 = altri giorni (rimessi a posto) |
| asmile-logger001 | 71 | 14,79 | 0,10 (solo 2 sessioni con ruota BLE) | 2 sì + 42 forse (moto non misurato) | nessun GPS; IMU assente fino all'08/11 |
| logger02 | 366 (A+B) | 36,87 (~18 h reali) | non misurate (nessuna velocità) | 0 sì, 219 forse | solo segmentazione e situazioni; molte sessioni buie |
| asmile2 (apr–mag 2026) | 98 (38 da_segmentare + 60 Desktop) | 6,28 | **1,88** (GPS, v>1 m/s) | 66 leggibili | encoder sterzo vero; video SBS 2560x800 (aprile 1280x400) |

- **[verificato]** Il tempo in moto di #001 coincide con quello del limiter (71,5 contro 71,6 s). Gli scarti video↔sensori stanno entro 3 ms.
- **[verificato]** Su asmile2 la mia soglia di moto, più severa di quella di harvest.py, dà 1,66 h su da_segmentare contro le 2,96 h di harvest.py.
- **[presunto]** Soglie dell'inventario: buio sotto luminosità 15, video corto sotto 60 s.
- Mancano sul Mac:
  - i sensori di #001 del 25/11 dopo le 14:35 e del 24/11 tra le 14:20 e le 15:13;
  - il 07/11 c'è solo il CSV del limiter (non estratto).
- L'encoder ruota il 24/11 pomeriggio è sospetto: segna 1 s in moto, mentre il GPS ne segna 162.

## 3. Le manovre del set (`training/set_manovre/set_manovre.jsonl` / `.csv`, ordinato e rigenerabile con `build_set.py`)

Soglie dichiarate prima (`agents/decisioni/asmile-event-miner.md`):
- #001: le stesse di `soglie_dalle_guide.py`, già passate dallo scettico il 13/11.
- asmile2: GPS a 10 Hz, quindi soglie più severe.
- logger001: eventi del registro guide del 13/11.

| unità | frenate di Daniele | frenate del limiter (escluse dallo stile) | sterzate | qualità |
|---|---|---|---|---|
| asmile #001 | 210 | 35 | 92 | alta (encoder ruota e sterzo); 248 con video agganciato |
| asmile-logger001 | 19 | – | 19 | bassa (IMU, assi non verificati con la ruota); 19 con video |
| asmile2 | 289 (34 stop) | – | 63 | frenate media (GPS), sterzate alta (encoder sterzo) |
| logger02 | 0 | – | 0 | non estratte: IMU della A senza convenzione assi né velocità |
| **totale** | **518** | 35 | **174** | **727 righe** |

Ogni riga contiene:
- COME: v0/v1, durata, decelerazione media e di picco, spazio, sterzo (ampiezza, velocità, imbardata, curvatura);
- DOVE: sessione, video, fotogramma, ora (con il flag `ora_affidabile`), GPS se c'è il fix;
- PERCHÉ: regola o regola+occhio, regole scattate, confidenza, `precisione_regola_30` per tipo;
- le CLASSI SAM 3 della finestra -4/+1 s, con la Z minima stereo solo per #001 dal 25/11 (`distanze_valide`).
- Prima del 25/11 per #001, e sempre per logger001 e asmile2, ci sono solo le classi, senza distanze: la calib di #001 è validata sul montaggio del 25/11 e mai si usa la calib di un'altra unità.

Copertura finale **[verificato]**. SAM 3 è girato su 5 fotogrammi per manovra (t-3, -2, -1, 0, +1 s), circa 1700 fotogrammi; mai più di 2 processi pesanti insieme.

| unità / tipo | manovre di Daniele | con classi | con distanze stereo |
|---|---|---|---|
| #001 frenate | 210 | 171 | 146 (solo 25/11) |
| #001 sterzate | 92 | 77 | 52 |
| logger001 frenate | 19 | 19 | 0 |
| logger001 sterzate | 19 | 0 (nel registro non c'è l'ora: nessun aggancio al video) | 0 |
| asmile2 frenate | 289 | 3 (classi non lanciate sulle frenate) | 0 |
| asmile2 sterzate | 63 | 61 | 0 |

PERCHÉ su #001 (solo #001 ha le regole; per le altre unità il perché è vuoto):
- **Frenate (210):** curva 47, senza motivo visibile 92, unknown 21 (quelle in coda del 25/11), ostacolo 6, persona 4, auto ferma di lato 1, vuoto 39 (senza video o senza fotogrammi).
- **Sterzate (92):** curva 71, ostacolo 4, persona 1, senza motivo 1, vuoto 15.
- **Attenzione:** fuori dalle 30 controllate sono etichette di SOLA regola (conf "bassa"), con la `precisione_regola_30` accanto. "Senza motivo visibile" vuol dire soprattutto che la regola non vede, non che il motivo non ci sia.

## 4. Coda casi dubbi (`training/perception_pipeline/casi_dubbi/queue/`, immagini in `casi_dubbi/frames/`)

29 casi nuovi (più i 6 che c'erano già), tutti `status: open`. Ognuno ha i fotogrammi, i dati, la domanda e le opzioni (+ Altro):
- **24 sul perché** delle frenate del 25/11 (stage `3-situations`): 5 fotogrammi rettificati per caso con classi e distanze.
- **4 sulle classi deboli** (griglia, ringhiera, segnaletica orizzontale, buca/gradino/animali).
- **1 cosa nuova**: un'insegna di negozio.
- Nessun messaggio inviato: l'invio a Daniele lo prepara il capo.

## 5. Classi (lista di Daniele 25/11)

- Ora c'è un unico elenco: `training/segmentation/classi.json`, letto da `seg_teacher_student.py` e quindi da tutta la pipeline. Si allunga in fondo.
- Nuove cose: ringhiera, porta a vetri, vetrina, catena, sbarra, griglia, buca, gradino, segnaletica orizzontale, uccello, cavallo, animale.
- Nuovi sfondi: linee stradali, ringhiera (separata dai muri), animale, veicolo, persona, palo/cartello, bidone.
- Le vetrate hanno `depth_affidabile=false`.

Come le trova SAM 3. Prova su 15 fotogrammi veri (8 #001, 3 logger001, 4 logger02, in `asmile-loggers/_seg_sam3/prova_classi_20261125/`); i logger erano in officina, quindi contano gli 8 di strada **[verificato a occhio]**:
- **vetrina / porta a vetri: discreta.** Vetrine e porte dei negozi a 0,4-0,55; anche le finestre normali escono come "vetrina", che per la depth è comunque vetro.
- **griglia: debole.** Inferriate vere a 0,8-0,95, ma anche finestre senza inferriata a 0,4-0,7. → caso.
- **ringhiera: debole.** Balconi a 0,3-0,5, più qualche falso. → caso.
- **segnaletica orizzontale: media.** Prende strisce e liste di pietra chiara, ma anche il bordo del marciapiede. → caso.
- **buca, gradino, animale, uccello, cane: solo falsi.** Nessun esempio vero nei fotogrammi. → caso.
- **catena, sbarra, cavallo: non giudicabili.** Nessun esempio vero; catena dà un falso su un cavo in officina.
- Il giro del 25/11 è stato elaborato con l'elenco di prima, perché il processo era già partito. Dal giro dopo vale la lista nuova.

**Registro delle cose nuove** (`training/segmentation/classi_nuove.jsonl`, script `training/set_manovre/cose_nuove.py`):
- Cerca le regioni che sporgono dal piano strada (stereo) senza nessuna classe, le raggruppa (tracce + CLIP) e propone un nome.
- Primo giro (soglie dichiarate): 952 regioni, quasi tutte asfalto e muri. Scartato, perché il piano fisso non regge il beccheggio.
- Secondo giro: 3 tracce. 1 vera, un'insegna di negozio a 9 m (caso per Daniele). 2 sono errori stereo nel cielo, marcati "scartato".
- Fatto sulle finestre delle 30 frenate e poi su tutte le altre 12 sessioni #001 del 25/11. Lì è uscita 1 sola traccia: una macchia al bordo dell'immagine, scartata. In totale 4 righe nel registro: 1 da confermare, 3 scartate.
- CLIP ViT-B/32 sui ritagli in bianco e nero non distingue niente (dice "nothing"): il nome l'ho dato io guardando.

## 6. Cosa manca / da fare

1. **Risposte di Daniele ai 29 casi**, poi reiniezione (`casi_dubbi/resolved/` → label o regola).
2. **Il perché di sola regola è debole** (13/30). Servono:
   - classi in movimento: auto e persone tracciate con la velocità propria, oggi l'auto a 15-20 m si perde;
   - incrocio dalla forma della strada, non dai bordi;
   - un maestro visivo (VLM) che oggi non c'è sul Mac.
3. **Logger02: nessuna manovra.** Serve la convenzione degli assi IMU della A e una velocità (flusso ottico o ruota BLE). **Logger001**: solo i 2 giri del 09/11; gli altri 42 "forse" richiedono il gate moto dal flusso ottico (`run_flow.py`), non lanciato.
4. **asmile2:**
   - gradi di sterzo solo in passi encoder (l'1:1 sul manubrio non è verificato);
   - 1 ampiezza a 1930 passi = probabile giro dell'encoder;
   - classi fatte solo sulle sterzate, non sulle frenate;
   - nessuna distanza: la calib di asmile2 non è stata controllata.
5. **#001:**
   - sensori del 25/11 pomeriggio e del 24/11 14:20-15:13 da scaricare;
   - il 07/11 (solo CSV del limiter) da estrarre;
   - la calib per le sessioni prima del 25/11 non è dimostrata;
   - 54 manovre di Daniele su 302 senza video agganciato (sessione video mancante sul Mac o scarto di orologio diverso).
6. **Barra sfocata sulla camera sinistra fisica e video a ~540 kbps:** restano i limiti principali della distanza.
7. Note tecniche:
   - il modello di sfondo Mask2Former carica con alcuni pesi di normalizzazione "MISSING" (avviso di transformers): da controllare;
   - il registro delle cose nuove va esteso a tutte le sessioni.
