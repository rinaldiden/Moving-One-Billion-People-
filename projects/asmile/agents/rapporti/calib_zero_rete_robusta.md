# Calib 15.000 unita': strada "la rete tollera la calibrazione" (2026-11-09)

Solo analisi sul Mac. Nessun Pi toccato. Prove fatte su video reali #001 (session_20261109_093216, soste col metro) con calib `logger/depth/calib_asmile-001.json`. Gli script di prova stanno in `/tmp/claude-501/s/` (volatili; i parametri sono scritti sotto).

## Risposta corta
1. **Una rete che "non ha bisogno di calibrazione" NON esiste per la scala metrica.** Misurato: una rete (FoundationStereo small) e SGBM tollerano bene gli errori di *rettifica* (dy fino a 4 px, rotazione 0.5 gradi, zoom 0.5%) sugli ostacoli. Ma NESSUNA delle due tollera un offset orizzontale di disparita' (d0): 1 px = 2.7% a 5 m. Quello non lo risolve ne' la rete ne' il training con domain randomization: e' un numero fisico, non una distorsione.
2. **Pero' la parte che "ammazza" la calibrazione in fabbrica sparisce:** restano solo 2 numeri per unita' (d0 e scala f*B), e la bici li puo' misurare DA SOLA mentre va: scala dal piano strada (misurato: tiene entro 1.8%), d0 dall'odometria dell'encoder ruota (simulazione: 0.5 px con 5 coppie di frame, 0.12 px con 100). Cosi' **noi non calibriamo niente**: ne' in fabbrica ne' in RSA. La bici si auto-registra nei primi chilometri.
3. Raccomandazione: **non allenare una rete nostra con domain randomization adesso.** Prima: barra rigida + SGBM/rete preaddestrata + auto-registrazione online di d0 e scala. La rete robusta serve solo come rinforzo ai bordi e sul "vicino" (vedi sezione 5).

## 1. Cosa ho misurato (vero, riproducibile)
Dati: frame #001 alle soste 2, 3, 4, 5 m (frame 360, 810, 1020, 1350 del file `session_20261109_093216_{left,right}.h264`; ATTENZIONE: `order=RL`, il file "left" e' fisicamente la camera DESTRA, quindi in rettifica L = file right, R = file left; senza scambio la rettifica sembra sballata di ~118 px in dy, errore in cui sono caduto io stesso al primo tentativo).
Bersaglio: persona con foglio scacchiera, ~25.000 pixel di ostacolo per frame (maschera = pixel entro ±12% della disparita' mediana in un riquadro 180x240 px centrale).
Perturbazione applicata alla sola immagine DESTRA gia' rettificata (warpAffine, bilineare): dy 1/2/4 px, rotazione (roll) 0.2/0.5 gradi attorno al centro, zoom +0.5%, dx +1 px.
Metodi: SGBM (3WAY, blockSize 7, 176 disp, P1=8*49, P2=32*49, uniqueness 8) e FoundationStereo small ONNX `deployable_foundationstereo_small_320x736_v2.0.onnx` (crop nativo 736x320 attorno all'ostacolo, senza ridimensionare; vedi `training/depth/fs_onnx_depth.py:30-33` per il modello).
Metrica: errore % della distanza = disparita' mediana sull'ostacolo vs disparita' della tabella `banco_fisso_asmile-001.json` (131.3 / 86.9 / 65.27 / 52.0 px). Include l'errore di calibrazione di base (<1%).

Errore % di distanza sull'OSTACOLO (+ = stima troppo lontana):

| Perturbazione | SGBM 2 m | SGBM 3 m | SGBM 4 m | SGBM 5 m | FS 2 m | FS 3 m | FS 4 m | FS 5 m |
|---|---|---|---|---|---|---|---|---|
| nessuna | -0.44 | -0.40 | +0.13 | +0.73 | +0.48 | +0.29 | +0.54 | +0.92 |
| dy 1 px | -0.44 | -0.40 | +0.22 | +0.48 | +0.47 | +0.43 | +0.59 | +0.86 |
| dy 2 px | -0.39 | -0.40 | +0.13 | +0.36 | +0.47 | +0.45 | +0.57 | +0.91 |
| dy 4 px | +0.04 | -0.47 | +0.13 | +0.73 | +0.50 | +0.40 | +0.57 | +0.85 |
| roll 0.2 gradi | -0.25 | -0.11 | +0.42 | +1.34 | +0.70 | +0.62 | +0.97 | +1.52 |
| roll 0.5 gradi | +0.23 | +0.46 | +0.71 | +1.84 | +1.08 | +1.21 | +1.70 | +2.19 |
| zoom 0.5% | -0.53 | -0.26 | +0.32 | +1.09 | +0.32 | +0.31 | +0.64 | +1.12 |
| dx +1 px | +0.32 | +0.75 | +1.69 | +2.72 | +1.25 | +1.48 | +2.06 | +2.91 |

Letture:
- **dy fino a 4 px: nessun effetto sulla mediana dell'ostacolo**, con entrambi i metodi. SGBM perde pero' pixel validi (a 5 m: 25414 -> 21603, -15%) e la dispersione sale (MAD 0.62 -> 0.81 px). Il motivo e' semplice: un ostacolo largo ha bordi verticali, e un bordo verticale non "sente" lo spostamento verticale. NON VERIFICATO su strutture sottili ORIZZONTALI (sbarre, corde, catene): li' dy fa danni, non li ho testati.
- **Roll 0.5 gradi**: +1.1% a 5 m (aggiunto alla base), accettabile ma mangia meta' del budget del 2%.
- **dx 1 px = +2% a 5 m** con entrambi i metodi: e' la causa vera. 0.1 gradi di yaw tra le camere = 2.3 px (f rettificata 1312 px) = ~4.5% a 5 m. Nessuna rete lo vede, perche' una immagine traslata di 1 px e' un'immagine perfettamente valida.
- La rete (FS small) NON e' piu' robusta di SGBM su questi dati: stessa tolleranza, con 0.5-0.9% di bias in piu' (non e' calibrata sulle nostre OV9281 mono). Il vantaggio delle reti e' la densita' (100% pixel validi vs 29-50%) e le zone senza tessitura, non la tolleranza alla rettifica.
- Con il primo tentativo (rettifica sbagliata di ~118 px in dy) FS dava disparita' sballate di 15-25 px e SGBM no: *oltre* qualche pixel di dy una rete non addestrata a questo si rompe, quindi la tolleranza ha un limite basso e dipende da come e' addestrata (qui non verificato oltre 4 px).

## 2. Limiti della prova (onesta')
- Ostacolo al CENTRO immagine, vicino alla linea dell'orizzonte. Il roll sposta i pixel di y*sin(theta): a 250 px sotto il centro, 0.5 gradi = 2.2 px (4% a 5 m). Provato sul piano strada (SGBM, righe 650-730): roll 0.5 -> -2.6/-2.9 px negli angoli bassi. Quindi i **bordi in basso e in alto peggiorano** (il "piede" dell'ostacolo): NON VERIFICATO con un ostacolo vero ai bordi.
- Sul selciato (texture ripetuta) SGBM con dy 2-4 px ha dato outlier grossi (14-18 px) in alcune zone: le misure sul piano strada con calib sporca sono inaffidabili per SGBM; vanno filtrate (LR-check, lo fa gia' `stereo_depth.py:43-50`).
- 4 frame, 1 sessione, 1 unita'. Niente prove a 10 m (nessuna sosta nel set con maschera ostacolo valida) ne' di rete addestrata con domain randomization (non fatta: il training costa giorni di GPU e i risultati sopra mostrano che non risolverebbe il problema vero).
- FS small: ~10 s per coppia su CPU Mac (misurato, 320x736). Su Pi 5: NON VERIFICATO, e comunque non e' tempo reale.

## 3. Cosa fa la rete e cosa no (letteratura, solo fonti primarie lette)
- **CREStereo** (arXiv 2203.11483): dichiara di mitigare "erroneous rectification" con un "adaptive group correlation layer" (ricerca 2D invece che solo orizzontale). Conferma che la tolleranza a dy e' progettabile, non gratis. https://arxiv.org/abs/2203.11483
- **FoundationStereo** (arXiv 2501.09898): zero-shot forte, 1M coppie sintetiche; il testo non dichiara tolleranza a miscalibrazione. https://arxiv.org/abs/2501.09898
- **Fast-FoundationStereo** (arXiv 2512.11130): "real-time frame rate" dichiarato, ma l'abstract non da' hardware ne' fps: NON VERIFICATO su Pi 5 (probabile GPU NVIDIA). https://arxiv.org/abs/2512.11130
- **Stereo Anywhere** (arXiv 2412.04472): fonde stereo + prior mono per aree senza tessitura/specchi; non parla di calibrazione. https://arxiv.org/abs/2412.04472
- **RAFT-Stereo** (arXiv 2109.07547): correlazione 1D lungo la riga, quindi per costruzione sensibile a dy. https://arxiv.org/abs/2109.07547 (la parte "1D" viene dalla mia conoscenza del metodo, non da una frase dell'abstract: NON VERIFICATO nel testo).
- Ricerche arXiv per "unrectified stereo", "uncalibrated stereo network", "rectification-free": nessun risultato utile ottenuto dall'API (ricerca fragile). **Non ho trovato una fonte primaria che dimostri una rete per bici/robot che raggiunga <=2% a 5 m con calibrazione non nota.** Resta NON VERIFICATO che esista.
- **Tesla** ("niente calibrazione esplicita, auto-calib online"): non ho una fonte primaria verificata in questa sessione. Nel repo c'e' il piano `logger/depth/PIANO_DEPTH_A_RITROSO.md` con le "chicche", ma e' secondario. Cosa e' VERIFICATO e utile: il principio (la flotta si auto-allinea mentre guida) e' quello che propongo sotto, ma con la misura *nostra*, non una citazione.

## 4. La strada che funziona: tolleranza + auto-registrazione online
Il problema si spezza in 3 pezzi, ognuno con la sua cura:

| Pezzo | Effetto | Chi lo risolve | Stato |
|---|---|---|---|
| dy, roll, zoom (rettifica) | tollerati sull'ostacolo (tabella sopra) | SGBM/rete + filtro epipolare; rifinitura online di dy/roll da match SIFT (come `selfcalib_essential.py`) | misurato |
| scala metrica (f*B) | errore diretto in % | baseline fissa 200 mm della barra rigida + piano strada | misurato sotto |
| offset d0 (yaw/convergenza) | 1 px = 2% a 5 m | odometria encoder ruota (2 viste, spostamento noto) | solo simulazione |

### 4a. Scala dal piano strada (MISURATO, nessuna calibrazione)
Nel piano rettificato la disparita' della strada cresce linearmente con la riga: d = (B/h)*(y - y_orizzonte). La PENDENZA dipende solo da B/h (non da f ne' da d0). Fit robusto Theil-Sen sulle righe 520-780 escludendo la colonna della persona, SGBM, 4 soste:

| Frame | pendenza misurata | attesa B/h = 0.2/0.825 = 0.2424 | altezza camera implicita |
|---|---|---|---|
| 360 (2 m) | 0.2412 | | 0.829 m |
| 810 (3 m) | 0.2381 | | 0.840 m |
| 1020 (4 m) | 0.2380 | | 0.840 m |
| 1350 (5 m) | 0.2390 | | 0.837 m |

Altezza vera 0.825 m (`calib_asmile-001.json`, cam_height_m): scarto <=1.8%. **La baseline fissa + altezza camera fissa della barra rigida danno la scala senza calibrare**, su strada piana. Con dx +1 px la pendenza non cambia (0.2381 -> 0.2381), cambia solo la riga dell'orizzonte (+4.1 righe per px): quindi il piano strada NON vede d0 (d0 e' confuso con il beccheggio). Limite: serve strada piana e visibile (non su sterrato ripido, non con la strada coperta da persone).

### 4b. d0 dall'odometria encoder (SIMULAZIONE, non dati reali)
Idea: se la bici avanza di DX noto (encoder ruota, circonferenza 1.576 m, nota di memoria), fB/(d1-d0) - fB/(d2-d0) = DX. Con fB noto dalla barra rigida resta una sola incognita d0. Monte Carlo: Z1 in 3-8 m, DX in 0.5-2 m, rumore disparita' 0.3 px, 400 prove.

| Coppie di frame | std di d0 | errore resultante a 5 m |
|---|---|---|
| 1 | 1.13 px | ±2.2% |
| 5 | 0.53 px | ±1.0% |
| 20 | 0.26 px | ±0.5% |
| 100 | 0.12 px | ±0.2% |

Un errore del 2% su fB sposta d0 di soli 0.55 px (bias). Stimare d0 *insieme* a fB invece e' mal condizionato (servono ~100 coppie per 0.4 px): meglio tenere fB fissato dalla barra rigida. Sono pochi minuti di marcia: la bici si registra da sola nei primi km, e il valore resta valido finche' `drift_monitor.py` non dice il contrario. **NON VERIFICATO su dati reali:** serve una sessione con encoder + video allineati (il `sensor_hub` a 50 Hz) e depth a 2 distanze note. Questo e' il test da fare.

### 4c. Cosa sparisce dalla fabbrica
- Niente stazione di calibrazione, niente cartello in RSA, niente ricambi calibrati.
- Resta UNA cosa meccanica: la barra rigida con baseline 200 mm stampata/lavorata una volta (se la baseline cambia di 1 mm = 0.5% di scala). Verificare la tolleranza costruttiva e' lavoro nostro ma non e' calibrazione.
- Le due camere montate sulla barra con tolleranza meccanica "ragionevole": gli errori di rettifica residui (rotazione sotto ~0.5 gradi, dy sotto ~4 px) sono tollerati dall'ostacolo; dentro il flusso, un passo software di rifinitura (match SIFT, mediana di dy) li riduce comunque.

## 5. Cosa gira su Pi 5 in tempo reale
- SGBM sul Pi: sì, e' il percorso gia' presente (`training/depth/stereo_depth.py`, EDGE/Pi). FPS su Pi 5: NON VERIFICATO in questa sessione (la nota in memoria dice che il Pi regge 15 fps nel mock, non 30).
- Reti stereo moderne (FoundationStereo, CREStereo): NO su Pi 5 CPU (FS small ~10 s/coppia su Mac CPU). Vanno usate OFFLINE sul Mac come maestro.
- Rete leggera allenata da noi con domain randomization: fattibile in teoria come allievo distillato dal maestro, **ma e' un lavoro grande** (dati, GPU, validazione per unita') e, come visto, non toglie il bisogno di d0 e scala. Da rimandare dopo il gate L1.ostacoli.
- Acceleratore sul Pi (Hailo-8L o simili): NON VERIFICATO, nessuna fonte letta.

## 6. Quanta calibrazione si puo' sbagliare restando <=2% a 5 m (sugli ostacoli, centro immagine)
Budget: 2% a 5 m = 1.04 px di disparita'. Errore base misurato oggi 0.7-0.9% (con tutta la calibrazione "buona").
- dy: fino a 4 px non pesa (ma attenzione a strutture orizzontali, non testate).
- roll: 0.2 gradi = +0.6% in piu', 0.5 gradi = +1.1% in piu' (centro). Ai bordi in basso peggio. Tetto pratico: **~0.3 gradi**.
- zoom: 0.5% = +0.4% in piu'. Tetto: **~0.5%**.
- dx/d0: **tetto 0.5 px** (1%). E' il vincolo vero; va corretto online (sezione 4b).
- scala f*B: errore diretto 1:1 sulla distanza; tenere sotto 1%: baseline barra (+-1 mm = 0.5%) + piano strada (+-1.8% misurato, come controllo grossolano).

## 7. Prossimi passi (nessuno richiede toccare Pi senza il "vai" di Daniele)
1. Registrare UNA sessione #001 con encoder ruota + video (gia' sincronizzati dal sensor_hub), passare in rettifica, e verificare 4b su dati veri: stima d0 da 20-100 coppie, poi confronto con le soste del metro. Se d0 viene entro 0.5 px: la strada e' chiusa.
2. Ripetere i test di perturbazione con un ostacolo AI BORDI (i frame `calib001_vicino_*_sx/dx` in `agents/rapporti/img/` sono il punto di partenza) e con strutture orizzontali sottili (sbarre).
3. Provare sulla barra rigida di un'altra unita' (asmile-logger001 o seconda bici) con la stessa auto-registrazione: la prova che "noi non calibriamo niente" vale solo se funziona su un'unita' diversa mai vista (calibrazione per-unita': mai fallback).
4. Solo dopo: valutare un allievo distillato dalla rete (domain randomization) per i bordi.

## Bozze
Nessuna email o messaggio inviato ne' proposto. Se servira' chiedere a Luxonis/Stereolabs sulla tenuta della calibrazione, la bozza sara' scritta dal Doppio e partira' solo col tap di Daniele.
