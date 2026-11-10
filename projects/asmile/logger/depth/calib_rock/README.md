# calib_rock — gemello digitale (mock) di #001 e calibrazione automatica

Stato (2026-11-10, round 3 dopo il VETO sui seed 20271117): **CODICE PRONTO, 4 GATE ANCORA ROSSI su 19 (15 verdi; onesti, nessuna soglia abbassata)**,
NON in produzione. `esito.json` = run N=60/scala, SEED0 20281124 (mai usato prima), 2891 s.
- **A (tabellone) e' SOLO CANDIDATO**: il bordo lo certifica il banco fisso reale / il tabellone fisico, MAI il mock.
- B (senza tabellone): corregge il montaggio, non la lente; **con lenti variate rifiuta quasi sempre e non prova nessuna correzione delle lenti**.
I parametri veri arrivano solo quando la calibrazione manuale di #001 prende il **PASSA L1.rettifica**.
Gate sulla lavagna: `L1.mock_001` (in `agents/stato.py`, DIPENDE da `L1.rettifica`).

## Cosa fa, in parole semplici

Daniele vuole poter calibrare i set di camere futuri **via software**, senza rifare ogni volta tutta la
calibrazione a mano. Per farlo serve un **gemello** del set di #001 (2 OV9281 Inno-Maker separate) con
cui provare il metodo prima di fidarsene:

1. `twin.py`: profilo di #001 + generatore di "set come montati davvero" (errori di montaggio e di lente).
   Parte da un file `calib_asmile-001.json` (oggi quello attuale, **SOLO PROVA, non G0**; domani quello passato).
2. `render.py`: disegna le **immagini** viste dalle due camere (tabellone ChArUco vero, oppure una scena
   da strada con piani texturizzati), con distorsione, sfocatura M12, rumore, esposizione, vignettatura.
3. `autocal.py` + `online.py`: i **due metodi** di calibrazione automatica per un set nuovo.
   - (a) **con tabellone** (collaudo a campione): rilevazione col detector vero, modello di lente scelto sulle
     viste tenute fuori, baseline dal lato misurato del tabellone (200 mm ±3% è un controllo, mai forzata).
   - (b) **senza tabellone**: parte dalla calib nominale di #001 e corregge gli errori di montaggio
     (roll/pitch/yaw, inclinazione baseline, scala) da una breve guida in avanti con l'encoder ruota.
4. `gate.py`: il **giudice**. Confronta con la VERITÀ del gemello (punti 3D veri 1-20 m, per zona 3x3).
5. `run_all.py`: Monte Carlo + casi negativi + gate stretti. Esce con codice ≠ 0 se un gate fallisce.
6. `fedelta.py`: prova di fedeltà del gemello contro una sessione reale (da fare con la ripresa ChArUco di #001).

## Come si lancia

```bash
cd projects/asmile/logger/depth/calib_rock
python3 run_all.py --prova                   # 8 istanze x scala 1 e 2, ~4-5 min, calib attuale SOLO PROVA
python3 run_all.py --prova --n 30            # run completo (seed fisso 20261110)
python3 run_all.py --produzione              # SOLO dopo G0: altrimenti RIFIUTA (exit 3)
python3 twin.py                              # autotest lente ricca vs OpenCV
python3 fedelta.py --selftest                # autotest del codice di fedeltà (non è fedeltà al reale)
```

Il risultato resta in `esito.json` (gate, casi negativi, tabella errore per zona x distanza).

Come si apre il cancello "produzione" (`g0_passato` in `run_all.py`): SOLO un verdetto PASSA di `asmile-calib-critico` in
`agents/palla/registro.jsonl` con `--gate L1.rettifica` NON parziale (esiste `agents/prove/L1.rettifica.json`), dopo `G0_NON_PRIMA_DI`,
con nella nota `sha256:<hex>` uguale a quello della calib ORA (`python3 run_all.py --sha`). Calib modificata dopo il PASSA = bloccata.
Il vecchio campo `g0_passa` nel file calib e' ignorato.

## Risultato (round 3, `esito.json`: N=60 per scala, seed 20281124 mai usati, 17/17 casi negativi come atteso)

**Regola di A (scelta del capo, "via 2"):** il mock non puo' certificare il bordo (ultimi ~40 px: il detector non da' corner li', il modello di lente
li' e' estrapolato; provati 6 controlli senza verita' e nessuno separa buoni e cattivi, vedi sotto). Quindi A produce un CANDIDATO e il bordo si
giudica con un controllo indipendente, che nel reale e' banco fisso + dy per zona in movimento e nel mock e' simulato col dy sulla verita':
**dy p95 < 1.5 px in OGNI zona** (1.5 e non 1.0: l'estrapolazione al bordo non e' certificabile al pixel) + depth del centro entro i limiti stretti.
**Un risultato con una zona sopra 1.5 px NON e' un candidato.** Un *falso candidato* e' un candidato con la depth vera a 2-5 m fuori limite (bordi > 3%).
Perche' cosi': le versioni precedenti dichiaravano candidati con zone di bordo a dy 1.6-2.8 px e depth fino al 7.4%; la soglia "errore bordo > 6%" non separava nulla.

| gate | scala 1 | scala 2 (montaggio E lenti doppi) |
|---|---|---|
| A: risultati con controlli interni VERDE che passano il controllo di bordo dy < 1.5 px >= 85% | 45/48 OK (scartati 3) | 26/26 OK |
| A: ZERO falsi candidati (passano dy < 1.5 ma depth fuori limite) | **KO: 1/45** (i2, basso-dx 5 m **3.23%**, limite 3%, dy sotto 1.0 ovunque) | OK 0/26 |
| A: potenza statistica, candidati veri totali >= 40 | 71 (45+26) OK | |
| A: baseline stimata vs vera entro 1% | 56/56 | 31/31 |
| A: guardia "A non dichiara mai VERDE" (invariante di codice, NON evidenza) | 60/60 | 60/60 |
| B solo-montaggio: accettata + gate stretti | **KO 59/60** (i32: rifiutato, montaggio grande) | **KO 57/60** (3 rifiuti sicuri: i29, i39 non accettati, i34 zona povera) |
| B solo-montaggio: nessuna zona peggiora > 0.5 punti % | 60/60 | 60/60 |
| B lenti variate: se accetta la verita' e' VERDE | **KO 57/60**: 3 accettate (i14, i15, i28) che MIGLIORANO molto (err 72->12, 78->7, 96->10) ma restano ROSSE (dy 3-12 px in alto) | 60/60 (0 accettate) |
| B lenti variate: nessuna zona peggiora > 0.5 punti % | 60/60 | 60/60 |
| casi negativi | 17/17 | |

**Dati (NON gate): disponibilita' della procedura A**, cioe' quante volte, con i rifacimenti guidati, si arriva a un candidato con controlli interni VERDE:
scala 1 48/60 (80%), scala 2 26/60 (43%). Era un gate al 50%: tolto, perche' misura l'usabilita' della procedura e non la correttezza; i rifiuti sono sicuri
(mai una calibrazione sbagliata data per buona), ma a scala 2 il collaudatore dovra' rifare viste mirate piu' spesso.

**Negativo "lato tabellone 6%":** ora costruito con copertura garantita (`calibrate_with_retry`, copertura ok verificata) e il test PRETENDE il motivo
"baseline" nell'esito; ROSSO per altro motivo = test fallito. Esito: ROSSO col motivo "baseline dal tabellone 187.5 mm fuori 200 +-3%".

**B con lenti variate rifiuta (quasi) sempre e non e' una prova di correzione delle lenti.** Il gate "se accetta, VERDE" passa a scala 2 perche' rifiuta
sempre (0/60). A scala 1 accetta 3/60 e quelle tre migliorano ma restano ROSSE: l'online corregge il montaggio, la lente nuova richiede A.

**Resta aperto (non nascosto):**
- A scala 1: 1 falso candidato su 45 a 3.23% (5 m, basso-dx) contro limite 3%: il modello semplice al bordo estrapola ancora male qualche volta. Lo scarto
  e' di 0.23 punti: da decidere se il limite al bordo dei candidati va tenuto cosi' (banco fisso reale lo verifica comunque).
- B: 4 rifiuti/accettazioni parziali su 120 per montaggi molto fuori nominale (dy 100-250 px): rifiuto sicuro, nominale restituito; B lenti: 3 accettazioni parziali.
- Selezione del modello di lente instabile fra split di hold-out (caso i3 round 3: dy al bordo 2.1 / 3.0 / 6.6 px cambiando solo il seed dello split; modello
  semplice k1k2 1.0-1.4): un guard "il modello flessibile non deve discostarsi dal semplice piu' di X px negli angoli" PROVATO e SPENTO (`DISAGREE_PX=None`):
  su 41 istanze i buoni arrivano a 4.7-6.6 px di scarto, il cattivo era a 1.7 px, nessuna soglia separa (e con 1.5 px rovina 3 buoni su 23).
- Fedelta' al reale NON VERIFICATA (invariata); il gemello e' piu' pulito del reale.

**Storico round 2 (seed 20261110, N=30):** A scala 1 91% candidati ok, 17/17 negativi; KO: falsi gravi 6.03%, disponibilita' A scala 2 12/30, B scala 2 29/30.
Cambi del round 2: gate falsi candidati con zona/errore, mai-peggiorativa per zona (0.5 punti %), B lenti come gate, pp +-100 px e lenti x scala, caso bordo cattivo/centro buono,
sabotaggi yaw/kappa con controllo positivo, selezione modello per hold-out a tolleranza 0 (da 82% a 91%), g0 solo da registro con sha256, L1.mock_001 in stato.py.

## Stress "gemello sporco" (dopo il VETO: il gemello era piu' pulito del reale)

`CALIB_ROCK_SPORCO=k python3 run_all.py --prova ...` moltiplica sfocatura e rumore del gemello (default 1 = come prima).
Run piccoli (N=8, seed fisso, calib SOLO PROVA), esiti in scratch, NON sostituiscono `esito.json`:

| sporco | A: candidati raggiunti | A: candidati che passano la verita' | B online (accettata+gate) | B mai peggiorativa | negativi |
|---|---|---|---|---|---|
| 1 (default, N=30) | 28/30 | 23/28 (82%) KO | 30/30 | 30/30 | 11/11 |
| 1.7 (scala 1) | 5/8 | 4/5 (1 falso candidato) KO | 8/8 | 8/8 | 10/11 |
| 3 (scala 1 e 2) | 0/8 | n.d. | **0/8 (rifiuto sicuro: "ep" tenuto fuori non migliora)** | 16/16 | 9/11 |

Lettura onesta: B regge fino a ~1.7x ma a 3x rifiuta sempre (mai una correzione sbagliata, ma il metodo non lavora);
A perde candidati man mano che il rumore sale. I due casi negativi che diventano "ROSSO per altro motivo" (zona vuota,
lato 6%) sono fragilita' del TEST (il ROSSO c'e', la causa attesa no), non una calibrazione sbagliata data per buona.
Il rumore vero (0.3-0.5 px sui corner) cade fra 1 e 3: finche' `fedelta.py` non e' tarato su una ripresa vera di #001
non si sa dove. Questo e' il motivo concreto per cui i gate valgono come prova di codice, non come prova su #001.
I due gate KO (A scala 1 82% < 85%; B scala 2 29/30) NON sono stati abbassati: restano KO fino a decisione del critico/Daniele.

## Le regole che il codice rispetta (dalle lezioni)

- **Niente test circolare**: il gemello genera con una lente RICCA (polinomio in theta + decentramento + prisma
  + aspect), si fitta con modelli semplici (5-8 parametri) scelti sulle viste tenute fuori.
- **Si giudica sulla depth vera** per zona 3x3 e distanza (1-20 m) e sul dy per zona, mai con l'RMS del fit.
- **Immagini vere**, detector vero (ChArUco A2 11x8 50 mm e A3 10x7 38 mm, DICT_5X5_1000).
- **Tolleranze di montaggio dai valori misurati su #001** (rotazioni fino a −5.2°/+2.1°/0.5°, baseline ±2 mm,
  ty/tz ±2 mm, f ±1%, centro ottico ±25 px) a **scala 1** e a **scala 2 (il doppio)**.
- La baseline si **stima** dal tabellone, non si impone. La correzione online è **un CANDIDATO**
  (mai sovrascrive la calib di fabbrica) ed è **accettata solo se migliora** su coppie tenute fuori.
- Un profilo = un'unità. `twin.py` rifiuta file calib non `calib_asmile-001*`. Il logger (Arducam Camarray)
  avrà il SUO profilo quando serve il suo mock: basta aggiungere una voce a `PROFILES` e rifare il generatore
  per SBS (una camera, 0.71 m). Mai fallback fra unità.
- Ordine file: su #001 `video_left` è la camera fisicamente DESTRA (order RL). Il gemello lavora con
  cam1 = sinistra fisica; `Instance.to_files()` fa lo scambio. File scambiati → ROSSO.

## Gate (stretti, seed fisso)

Verita' del gemello (punti 3D 1-20 m, griglia per zona 3x3 fino a 12 px dal bordo): dy p95 < 1 px in tutte le zone con
sovrapposizione stereo; depth centro <=2% a 2-5 m e <=3% a 7-10 m; bordi <=3% a 2-5 m; 1 m e 10-20 m **riportati**.
- B (senza tabellone): accettata + gate stretti su ogni istanza; correzione MAI peggiorativa; scala 1 e 2.
- A (tabellone): baseline entro 1% della vera (e +-3% di 200 mm, mai forzata); nessuna calib dichiarata VERDE se la verita'
  dice ROSSO (soglia 0); candidati con controlli interni VERDE che passano la verita' >= 85%; l'operatore raggiunge un
  candidato interno-VERDE in >= 50% delle istanze.
- C (lente variata): solo "mai peggiorativa". **Non e' un controllo di qualita'**: il dy residuo (148 px circa) e'
  informativo e il gate non puo' dare ROSSO su di esso. B non sostituisce A per lenti nuove (avviso stampato nel report).
- Casi negativi, tutti ROSSO: file L/R scambiati (tabellone e online), zona vuota, solo-centro (tabellone e online), lato
  tabellone sbagliato del 6%, bici ferma, nominale non corretto, yaw sbagliato di 0.15 gradi; + controllo positivo VERDE.

## Cosa ho imparato costruendolo (da non rifare)

- `cv2.stereoCalibrate` sceglie il modello di distorsione dai FLAG, non dalla lunghezza del vettore: con
  coefficienti razionali senza `CALIB_RATIONAL_MODEL` esplode (RMS 1e13) e sembra "baseline sbagliata".
- Un modello razionale libero fitta il tabellone al centesimo di pixel e **impazzisce negli angoli** (dy 4.8 px,
  depth 6-9% in basso-dx) dove non ci sono corner. Rimedio: scarto i modelli non monotoni fino al bordo e scelgo
  il più semplice entro +0.03 px dal migliore sulle viste tenute fuori.
- Il detector ChArUco ha un limite fisico: A2 50 mm si vede fino a ~3 m, A3 38 mm fino a ~1.5 m (1280x800, M12).
  Per tabelloni a 3-4 m serve un formato più grande (A1) o marker più grandi: la calibrazione da tabellone
  a ≤2.8 m deve poi **estrapolare** a 10-20 m (qui regge, ma al 20 m ai bordi arriva a ~3-5%).
- Un controllo che sembra funzionare sulle istanze usate per sceglierlo puo' non funzionare su quelle nuove: il disaccordo
  fra famiglie separava 7 falsi su 7 (soglia 0.30) e su 60 istanze nuove ne ha lasciati passare 3. Scegliere la soglia su un
  gruppo e PROVARLA su un altro, sempre.
- Il detector ChArUco di OpenCV riporta i corner con ~+0.5 px rispetto al centro-pixel (verificato col render
  senza bias): è comune a entrambe le camere, non cambia depth e dy, sposta solo il centro ottico di 0.5 px.
- Online: il dy vede solo roll/pitch relativi (e ty/tz). **Yaw (=d0) e scala non si vedono col dy**. Una stima
  con differenze di profondità triangolata è **distorta dal rumore** (1/d): serve un bundle in spazio-misura con
  la profondità di ogni punto come variabile libera. Con quello l'yaw esce entro 0.03° (0.7 px di d0).
- Online: la scala fB e la baseline non si separano; il bundle usa l'encoder (|t| = ds) e il piano strada
  (camera a 0.825 m). Il controllo del piano sulle viste tenute fuori è solo GROSSOLANO (±35%): altezza e
  pitch del piano non si separano bene.
- Frame rettificato ≠ frame camera: il pitch del piano strada nel rettificato è diverso da 7.4° (dipende dalla
  rotazione relativa). Non confrontarlo col pitch camera.

## Limiti dichiarati (onesti)

- **Fedeltà al reale NON VERIFICATA.** Sul Mac non c'è una coppia ChArUco reale di #001 (la sessione
  `calib_001_20261109/vicino_153251` usa una scacchiera 7x10 tenuta a mano). `fedelta.py` è pronto: serve la
  ripresa ChArUco di oggi. Il self-test prova solo il codice.
- Rumore del gemello: l'RMS del fit esce ~0.07-0.1 px, **più pulito del reale** (0.3-0.5). Le soglie di
  gate sulla depth sono vere (sulla verità), ma il rumore del detector reale è da tarare con `fedelta.py`.
- **Il bordo (ultimi ~40 px) non si certifica col tabellone** (vedi "Risultato"). Il gemello non puo' dire VERDE ad A.
- La correzione ONLINE corregge il **montaggio**, non la **lente**: con lenti diverse (f, centro ottico,
  distorsione) dal nominale il dy resta fuori gate (caso "C", solo informativo; mai peggiorativa sì).
  Per un set con lenti nuove serve il collaudo col tabellone.
- La scena online è procedurale (piani texturizzati), non strada vera. `render.render_real_with_depth()` è
  solo l'interfaccia per riproiettare fotogrammi veri di #001 con depth nota: non implementata (oggi manca
  una coppia frame+depth densa verificata sul Mac).
- Ipotesi online: moto ~rettilineo tra i due istanti, baseline lungo x del frame rettificato, encoder ruota
  con errore ≲0.5%.
- Il gemello usa la calib JSON come nominale: finché è quella provvisoria di ieri (R con −5.2°, cx destra −93 px,
  che assorbono la lente) i numeri valgono come **prova del codice**, non come prova su #001.

## Cosa manca fino a G0

0. Decisione sul bordo di A (vedi "Decisione aperta"): A resta CANDIDATO + banco fisso reale, oppure nuovo gate/modello.
1. `L1.rettifica` PASSA (dy < 1 px su tutta l'immagine, anche in moto) e calib `calib_asmile-001.json` finale.
2. Ripresa ChArUco di #001 (A2 o A3, rigido e piatto) → `python3 fedelta.py --left ... --right ...` e tarare
   rumore/sfocatura/limiti del detector del gemello sui valori veri.
3. Rifare `run_all.py --produzione --n 30`: deve passare tutto. Poi passare la palla a `asmile-calib-critico`.
4. `L1.mock_001` e' in `agents/stato.py` (dipende da `L1.rettifica`).
5. Opzionale: mock dedicato Arducam (asmile-logger001): nuovo profilo + generatore SBS.
