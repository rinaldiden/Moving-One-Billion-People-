# Sim-to-real per Asmile: quanto aiuta DAVVERO (valutazione 2026-11-09)

Autore: asmile-ricercatore. Gate: `obiettivo.sim2real`. Contro-agente: asmile-ricerca-scettico.
Legenda prova: **[V]** = letto in questa sessione su fonte primaria; **[S]** = visto solo su riassunto/abstract/secondaria; **[M]** = dalla mia memoria, NON riverificato qui; **[STIMA]** = numero mio, non di un paper.

## 0. Risposta corta

1. Il collo di bottiglia non e' il simulatore: sono le **ore di guida reale buone**. Oggi: 6.9 min in moto (30/10, `180225`) + 53 s (7/11, `165926`) su 22.4 min di video totali (`rapporti/L0.dati_20261109.md`). Qualunque sim costruita dai nostri video **eredita questa copertura**: non inventa posti, luci, persone, cancelli che non abbiamo visto.
2. Il modello che vogliamo e' **percezione leggera (segmentazione + depth) + planner con limiti fissi** (14.4 km/h, 0.5 g, freno 60 gradi). Il controllo e' per la maggior parte regole e limiti hardware, non una policy end-to-end da addestrare. Quindi la sim serve a poche cose: identificare gli attuatori, testare la logica di frenata, e (piu' avanti) fare recovery/validazione su scene reali perturbate.
3. Street View per training: **NO**. I termini Google lo vietano in modo esplicito [V] (sez. 6).
4. World model generativi (GAIA, Tesla): **NO**, servono ore di dati di tre ordini di grandezza sopra i nostri e non sappiamo validarne le allucinazioni.

## 1. Cosa vuole imparare il modello, e cosa serve per ciascun pezzo

| Capacita' | Da dove viene il segnale che manca oggi | La sim aiuta? |
|---|---|---|
| Segmentare ostacoli (persone, pali, cancelli, griglie, muri) | Immagini variate + etichette (oggi: SAM 3 teacher, allievo leggero) | Poco. Il gap e' di varieta' reale e di classi (cancelli/griglie), non di viste nuove. |
| Depth metrica 1-15 m | Calibrazione per unita' + metro (fatto: errore entro +-2.1% a 1-15 m sul logger, `d=180.6/Z+26.3`) | No. E' geometria + calibrazione misurata sul reale. |
| Frenare entro 0.5 g, freno <=60 gradi | Modello attuatore (latenza, saturazione, carico idraulico) + TTC | **Si**, ma serve identificazione dal reale (banco), non ore di guida. |
| Sterzare entro i limiti | Modello VESC sterzo + dinamica bici (non lineare, dipende dalla velocita') | Si, per identificare; RL no per ora. |
| Recovery dagli errori (covariate shift) | Dati fuori traiettoria umana | Si, **e' l'unico caso in cui la ricostruzione neurale ha senso**, ma solo dopo copertura. |

## 2. Opzione per opzione

### 2.1 Sim fisica MuJoCo + BAM (gia' scritta in `training/sim2real/`, ricetta Microduck)
- **Insegna**: controllo e attuatori. Non insegna percezione (non genera immagini).
- **Evidenza**: la ricetta (MuJoCo + PPO 50 Hz + BAM + domain randomization + ONNX) e' quella del playbook `docs/sim2real_microduck_playbook.md` (repo `microduck_rl`, Pollen) [S: letto il playbook interno, non il repo]. E' una ricetta per un robot a gambe: non c'e' alcun risultato pubblicato su una bici con sterzo automatico. Il nostro sistema (bici, instabile, freno idraulico) e' un altro problema.
- **Costo**: basso. Mac M-series, nessuna GPU esterna. Costo vero = **dati di identificazione** (passi di sterzo e di freno sulla bici su cavalletto e in moto lento, con wheel encoder calibrato e angolo freno).
- **Gap**: alto sulla dinamica della bici in moto (autostabilita', modello Whipple/Meijaard [M, non verificato]); basso sul solo attuatore.
- **Verdetto**: **SUBITO solo il pezzo "identificazione attuatori" (BAM) per freno e sterzo**, perche' serve comunque a validare decel <=0.5 g e freno <=60 gradi. Addestrare policy PPO: **DOPO** (trigger in sez. 8). Coerente con la sequenza gia' decisa: prima calibrare il freno col wheel encoder, poi frenata da visione, poi sterzata.
- Linee rosse: il banco prove freno/sterzo con motore o servo reali richiede il "vai" esplicito di Daniele; in sim nessun vincolo.

### 2.2 Ricostruzione neurale dai nostri video (3DGS / NeRF / neural sensor sim)
- **Insegna**: *recovery* e robustezza a spostamenti laterali/di yaw, e **valutazione in closed-loop sulle scene reali** (rigiocare la scena con una traiettoria diversa). Non insegna cose che non abbiamo visto.
- **Evidenza**:
  - UniSim (Yang et al., CVPR 2023) ricostruisce un log in sim multi-sensore (LiDAR+camera) con "small domain gap on downstream tasks" [V solo abstract: i numeri non li ho potuti leggere, il PDF supera il limite di download]. Usa **LiDAR** e sensori di auto; noi no.
  - NeuRAD (Tonderski et al., arXiv 2311.15260): stato dell'arte di novel view synthesis su 5 dataset di guida, camera+lidar, indica "data augmentation" come uso potenziale; l'abstract **non riporta** un guadagno misurato nel training di percezione [V abstract].
  - HUGSIM (arXiv 2412.01718): simulatore closed-loop 3DGS, 70+ sequenze, 400+ scenari da KITTI-360/Waymo/nuScenes/PandaSet. Gli autori ammettono artefatti (soprattutto su corsie e dettagli a terra) quando l'ego si allontana molto dalle viste di training. KID su viste estrapolate: HUGSIM 0.077 (Waymo) / 0.062 (nuScenes), NeuRAD 0.094 / 0.082, StreetGaussian 0.151 (Waymo). Sull'"unlocks the potential for fine-tuning" **non c'e' nessun esperimento di fine-tuning** nel testo letto [V, ho letto circa 100k dei 161k caratteri].
  - Sintesi onesta: la letteratura dimostra che **si valuta** bene in closed-loop con il reale ricostruito; che **si addestri** meglio grazie a queste viste sintetiche e' dichiarato come potenziale ma, nei testi che ho letto, non quantificato.
- **Perche' per noi e' piu' duro che per Waymo/nuScenes**: (i) camere **monocromatiche** OV9281 (nessun colore: ok per NeRF/3DGS ma i teacher pre-addestrati sono RGB); (ii) niente LiDAR: pose e geometria da stereo+COLMAP, baseline solo 200 mm; (iii) **una sola passata** per percorso nei dati attuali: 3DGS dalla sola traiettoria in avanti degrada fuori dal tubo di viste (HUGSIM); (iv) attori dinamici (persone, auto) richiedono box/segmentazione, che e' proprio cio' che stiamo ancora costruendo; (v) bici: camera bassa, vibrazioni, rollio. Vantaggio: OV9281 e' **global shutter** (niente rolling shutter da modellare) e abbiamo encoder/IMU/GPS per le pose.
- **Costo** [STIMA]: un percorso di 1-2 min (900-1800 frame stereo) = ore di training su GPU CUDA (nerfstudio/gsplat); su Mac MPS e' scomodo o lento. Server esterno a ore, costo euro a una o due cifre per scena. Il costo vero e' la **pipeline di pose + masking dei dinamici**, giorni di lavoro.
- **Gap**: medio-alto fuori da ~0.5 m dalla traiettoria registrata [STIMA, da verificare con il PoC qui sotto].
- **Verdetto**: **DOPO**. Trigger in sez. 8. Nel frattempo **SUBITO la versione povera**: *reproiezione laterale con la nostra depth stereo* (warp della vista di +-0.2-0.5 m con depth densa, come i frame spostati di Bojarski et al. 2016 [V in snippet: "il solo dato umano non basta, la rete deve imparare a recuperare", viste spostate/ruotate con etichetta sterzo corretta per tornare in 2 s]). Costa un'ora di script, nessuna GPU. Limite: buchi di occlusione, ok per piccoli spostamenti.
- **PoC consigliato (1 giorno, falsificabile)**: sulla sessione `20261030_180225` ricostruire un tratto di 20-30 s in 3DGS. Misura: renderizzare a +-0.5 m laterale e confrontare con un frame reale di un'altra passata sullo stesso punto. Se non c'e' un'altra passata, il PoC e' **non verificabile** su offset > 0 e va rimandato: serve almeno una seconda passata dello stesso tratto (e' il motivo n.1 del trigger).

### 2.3 Google Street View
- **Insegna**: solo percezione statica di strade europee; nessuna azione, nessun movimento, nessuna dinamica.
- **Vincoli tecnici**: camera sul tetto dell'auto (~2.5 m) contro la nostra bassa; panorami a intervalli, scatti statici non video; **a colori**, noi mono 1280x800; nessuna ciclabile/marciapiede alla nostra altezza.
- **Licenza/ToS** [V, testo corrente Google Maps Platform Terms of Service, sez. 3.2.3 "Restrictions Against Misusing the Services", letto 2026-11-09 da cloud.google.com/maps-platform/terms]:
  - (a) *No Scraping*: il Cliente non deve "export, extract, or otherwise scrape Google Maps Content for use outside the Services", ad esempio "(ii) bulk download Google Maps tiles, Street View images ..." e "(i) pre-fetch, index, store ... Google Maps Content outside the services".
  - Nello stesso elenco di esempi: "(vii) use Google Maps Content to improve machine learning and artificial intelligence models, including to train, test, validate or fine-tune the models".
  - Conclusione: scaricare Street View per training o validazione e' **vietato dai termini**, indipendentemente dal fatto che sia non commerciale. Non abbiamo accordi speciali. NON e' un parere legale; per un'eventuale deroga servirebbe scrivere a Google (bozza che parte col tap di Daniele), ma lo sconsiglio: il guadagno tecnico e' comunque basso.
- **Verdetto**: **NO**.

### 2.4 Dataset pubblici (Mapillary, KITTI, Cityscapes, BDD100K, dataset bici/marciapiede)
- **Insegna**: percezione generica urbana (strada, marciapiede, persone, auto, pali). **Non** il nostro contesto (Tirano: cancelli in ferro, griglie, vicoli, ciclabili) ne' le nostre camere.
- **Evidenza**: sono dati di auto/colore; la pratica standard e' usarli per pre-addestrare backbone. Noi **lo stiamo gia' facendo di fatto** usando SAM 3 come teacher e allievo leggero (pipeline percezione, `project_perception_shadow_pipeline_status`): quei pesi hanno gia' visto molti di questi dati.
- **Licenze**:
  - Cityscapes: non commerciale; "may not use the dataset or any derivative work for commercial purposes"; modelli addestrati sono ammessi come derivati "abstract" [V da cityscapes-dataset.com/license]. Resta una zona grigia se il modello finisce in un prodotto: **da chiarire** se Asmile sara' venduto.
  - Mapillary Vistas: CC BY-NC-SA 4.0 [S, citato da un paper CVPR 2022; immagini Mapillary generali sotto CC BY-SA secondo help Mapillary]. Non commerciale.
  - KITTI e BDD100K: non ho trovato il testo di licenza primario; KITTI e' di norma non commerciale [S/M]. **NON VERIFICATO**.
- **Costo**: scarico + conversione in scala di grigi; basso. Rischio: gap di dominio (altezza camera, colore, ottica) e licenza.
- **Verdetto**: **SUBITO** ma **solo come pesi pre-addestrati/inizializzazione e come banco di confronto**, non come pipeline di lavoro dedicata. Le etichette per le classi che ci interessano (cancelli, griglie) vanno fatte sui NOSTRI frame. Dataset bici/marciapiede: ne esistono di piccoli [M], da cercare uno a uno con licenza; **NON VERIFICATO**.

### 2.5 Simulatori classici (CARLA, ecc.)
- **Insegna**: logica di pianificazione e frenata in scenari scriptati; percezione solo con un forte gap sim-to-real (grafica sintetica). Dosovitskiy et al. 2017 [M]. Non c'e' modello di bici con sterzo automatico ne' il contesto di Tirano.
- **Costo**: alto per fare asset di Tirano, GPU di fascia gaming; bassa fedelta' per un guadagno che il mock Pi 5 (`pi/mock/asmile_pi5_mock.py`) e la sim MuJoCo gia' coprono per la logica.
- **Verdetto**: **NO**.

### 2.6 World model generativi (GAIA-1/-2, Tesla, UniSim neurale)
- **Insegna**: in teoria scene rare e "cosa succede se"; in pratica richiedono dati enormi.
- **Evidenza**: GAIA-1 (Wayve, arXiv 2309.17080) e' un modello generativo su video+testo+azioni; l'abstract non quantifica dati ne' training di una policy [V abstract]. Ordini di grandezza (miliardi di parametri, migliaia di ore di guida a Londra) [M, non riverificato]. GAIA-2 (arXiv 2503.20523) e' un latent diffusion condizionato su dinamica ego, agenti, ambiente, semantica stradale; dati non riportati nell'abstract [V]. Tesla (ICCV 2025, Elluswamy): "world simulator" per rigiocare incidenti e testare modelli; cifre ("500 anni di guida al giorno") sono **claim aziendali** riportati da fonti secondarie [S].
- **Per noi**: 0.1 ora di guida buona contro migliaia. Un world model generativo da pochi minuti produrrebbe allucinazioni senza modo di verificarne la fisica, e non e' accettabile per dimostrare sicurezza di frenata. Un modello video open pre-addestrato potrebbe servire per **brainstorming qualitativo** di casi limite, mai come dato di training o prova.
- **Verdetto**: **NO** (rivalutare solo se arriviamo a centinaia di ore *e* c'e' un modello open fine-tunabile con le nostre camere).

## 3. Tabella verdetti

| Opzione | Insegna | Verdetto |
|---|---|---|
| MuJoCo+BAM, identificazione attuatori | controllo (freno, sterzo) | **SUBITO** (solo ID; banco con "vai" di Daniele) |
| MuJoCo+PPO policy di sterzo/freno | controllo | **DOPO** |
| Reproiezione laterale con depth stereo (augment povero) | recovery piccolo | **SUBITO** |
| 3DGS/NeRF dai nostri video | recovery + validazione closed-loop | **DOPO** (trigger sez. 8) |
| Street View | percezione statica | **NO** (ToS vietano, [V]) |
| Dataset pubblici | pre-training | **SUBITO** come pesi/benchmark, non come progetto |
| CARLA e simili | logica scriptata | **NO** |
| World model generativi | scene rare | **NO** |

## 4. Rischi che nessuna sim risolve
- Validare il freno richiede prove reali con bersagli a distanza nota (muro-test, metro) e **shadow mode** su strada senza attuare: e' cio' che dimostra il sistema, non una sim costruita dagli stessi dati.
- Sim costruita su 7 minuti = test su dati di training. Per un esame onesto servono scene **held-out**, anche per la sim (gia' previsto da `vtest`).
- Policy in sim che "regge" non e' una prova per la strada: serve gate della lavagna + firma di Daniele in `DECISION_LOG.md`.

## 5. Ordine consigliato
1. **Dati reali**: regole di acquisizione prima di tutto (stesso tratto piu' passate, orari/luci diversi, cancelli/griglie presenti, camere entrambe vive, sync ok, video non neri). I problemi di L0 (camera destra morta, video nero, orologio) hanno costato piu' di qualsiasi sim.
2. Attuatori: identificazione freno (con wheel encoder calibrato) e sterzo VESC; BAM semplice in MuJoCo.
3. Pesi pre-addestrati pubblici + SAM 3 teacher + allievo; aggiungere classi cancelli/griglie con etichette nostre.
4. Reproiezione laterale con depth stereo per augment recovery (poche ore di lavoro).
5. Shadow mode su strada: confronto predizione/azione umana.
6. Solo poi: PoC 3DGS su un tratto con almeno 2 passate; se il PoC passa, 3DGS per le scene di evento (cancello, pedone).
7. Mai: Street View; CARLA; world model generativo.

## 6. Quante ore reali prima che una sim valga la pena (soglie [STIMA], da confermare col PoC)
- **Identificazione attuatori (BAM)**: servono ~30-60 minuti di banco, non ore di guida.
- **Policy PPO in MuJoCo**: dopo che l'ID e' validato e con >= 10 ore di guida **in movimento** (la soglia del piano gia' in memoria) con encoder ruota calibrato; oggi siamo a ~0.12 h.
- **3DGS/NeRF per recovery o validazione**: >= 10 ore di moto e almeno ~10 tratti di strada con **>= 3 passate ciascuno** (diverso offset laterale/ora). Senza passate multiple non si puo' verificare il rendering fuori traiettoria.
- **World model generativo**: centinaia di ore; non e' un obiettivo realistico per noi.
- Criterio d'uscita del PoC 3DGS (proposta): a +-0.5 m laterale, la depth ricavata (nostra stereo) sul render deve differire dalla depth del frame reale della seconda passata di meno del 5% a 1-10 m, e la segmentazione dell'allievo deve dare la stessa classe su >= 90% dei pixel di ostacoli.

## 7. Cosa NON ho potuto verificare
- Numeri di UniSim (PDF troppo grande), dati/parametri di GAIA-1, licenze primarie KITTI/BDD100K/Mapillary Vistas, esistenza e licenza di dataset bici/marciapiede, claim Tesla su fonte primaria (post X/ICCV).
- Tutti i costi in euro/ore e le soglie di sez. 6 sono mie stime.

## 8. Fonti
- Google Maps Platform Terms of Service, sez. 3.2.3 (a): https://cloud.google.com/maps-platform/terms (letto 2026-11-09, testo corrente).
- UniSim (Yang et al., CVPR 2023): https://arxiv.org/abs/2308.01898 (abstract).
- NeuRAD (Tonderski et al.): https://arxiv.org/abs/2311.15260 (abstract).
- HUGSIM: https://arxiv.org/abs/2412.01718 e https://arxiv.org/html/2412.01718 (testo parziale).
- GAIA-1: https://arxiv.org/abs/2309.17080 ; GAIA-2: https://arxiv.org/abs/2503.20523 (abstract).
- Bojarski et al., End to End Learning for Self-Driving Cars: https://arxiv.org/abs/1604.07316
- Ross, Gordon, Bagnell, DAgger (covariate shift in imitation learning): https://arxiv.org/abs/1011.0686 (abstract; la formula quadratica/lineare nell'orizzonte e' [M]).
- Cityscapes license: https://www.cityscapes-dataset.com/license/
- Mapillary licenze: https://help.mapillary.com/hc/en-us/articles/115001770409-Licenses [S]
- Tesla world simulator (ICCV 2025): solo fonti secondarie, es. https://news.futunn.com/en/post/63836230/tesla-s-world-simulator-arrives-1-day-of-learning-equals [S]
- Interne: `.collegio/CONTEXT.md`, `docs/sim2real_microduck_playbook.md`, `training/sim2real/README.md`, `agents/rapporti/L0.dati_20261109.md`.
