# Calibrazione a 15.000 unita': angolo SUL CAMPO (online, mentre la bici gira)

Data 2026-11-09. Solo analisi sul Mac, nessun Pi toccato, nessuno script modificato.
Hardware citato: #001 (2 OV9281 separate, baseline 200 mm, C ruota 1.576 m) e asmile-logger001 (Camarray SBS). Mai trasferire numeri dall'una all'altra.

## 1. Idea in parole semplici
La bici impara da sola a "mettere dritti gli occhi" nei primi km (stile Tesla), ma NON parte da zero. Parte da un file di fabbrica
(`calib_<unita>.json`) e l'online corregge solo poche cose che davvero cambiano: la rotazione tra le due camere e la scala.
Il metro lo sostituisce la ruota: l'encoder sa quanti metri ha fatto, e le camere devono vedere lo stesso numero.

## 2. Cosa osservano le camere in movimento (e cosa no)
Pixel: 1 px = 0.062 gradi (f ~930 px). Quindi dy < 1 px = rotazione relativa precisa a ~1 mrad.

| Parametro | Osservabile online? | Come |
|---|---|---|
| Roll/pitch relativo (dy) | SI, facilissimo | match L-R, dy residuo (`autorectify.py:97-111`, `selfcalib_essential.py:56`) |
| Yaw relativo = offset di disparita' d0 | SI ma DIFFICILE | NON si vede dal dy. Pesa tantissimo: 0.1 gradi di yaw = 1.6 px = ~4% a 5 m (d=37 px). Si vede solo con i punti lontani (disparita' ~0) o col moto (sezione 4) |
| Scala f·B | SI col moto | encoder vs distanza vista dalle camere (sezione 4) |
| Baseline B da sola | Parzialmente | piano strada (sezione 5); su #001 le camere sono montate a mano: la B va misurata una volta, non assunta |
| Focale f | Debole | si confonde con B nella scala; da fabbrica |
| Distorsione ai bordi, punto principale | NO (o molto debole) | vedi sezione 7 |

Nota sul codice: `selfcalib_essential.py` mette distorsione = 0 e stessa K per le due camere (righe ~93-95 del JSON in uscita) e `|T|` = baseline nota
(riga ~84). Cioe' fa gia' bene la rotazione, ma eredita f e distorsione "a priori": il suo dy mediano ~0.9 px lo prova solo al centro.
`drift_monitor.py:50,57` misura la MEDIA su tutto il frame e la MEDIANA nel tempo: non vede un bordo sbagliato (il bordo sx di #001 ha dy -4 px, vedi lezione asmile-calib 2026-11-09) e non separa urto da usura.

## 3. Come gira l'autocalibrazione (macchina semplice)
Condizioni per raccogliere match (tutte dai sensori gia' loggati, sensor_hub 50 Hz): velocita' encoder > 1.5 m/s, sterzo vicino al centro, gyro basso, scena con texture.
Si accumula in "secchi" per 9 zone dell'immagine; si calcola solo quando ogni zona ha abbastanza match (es. >= 150).

Passi:
1. Seme: `calib_<unita>.json` di fabbrica (per #001 quella attuale con tape, per il logger quella metro). Mai fallback fra unita'.
2. Rotazione: stima 3-DoF su match robusti (RANSAC) con cv2.recoverPose, come `selfcalib_essential.py`, ma con K fissata dal seme e con limiti stretti (es. +-1 gradi dal seme, +-0.3 gradi fra una finestra e l'altra).
3. Mappa dy per zona: oltre alla rotazione, un correttore liscio di basso ordine di dy(x,y) (polinomio 2-3 gradi) stimato da migliaia di match. Corregge il dy ai bordi (verticale), NON la disparita' orizzontale.
4. Scala e d0 col moto + encoder (sezione 4).
5. Accetta solo se: (a) migliora dy su match tenuti da parte (non usati nel fit), p95 compreso, in OGNI zona; (b) scala resta entro +-3% dal seme; (c) due finestre successive concordano. Altrimenti scarta (stessa regola del banco fisso: se peggiora un punto, si scarta).
6. Doppio slot A/B: si tiene sempre l'ultima calibrazione buona; la nuova diventa attiva solo dopo l'accettazione.

Dove gira: la raccolta e il monitor sono leggeri e stanno sul Pi (log insieme ai sensori); il fit pesante si puo' fare dopo sul Mac dai log (come gia' si fa per la depth). Cosi' non si carica il Pi mentre guida.

## 4. Il trucco principale: l'encoder come metro (scala + d0)
Idea: se la bici avanza di D metri (encoder) e un punto fermo passa da distanza Z1 a Z2 = Z1 - D, allora
`fB/(d1-d0) - fB/(d2-d0) = D`. Con tanti punti si ricavano f·B e d0 insieme. Non serve il metro, ne' i punti a distanza nota, ne' il cielo.

PROVA (simulazione mia, NON dati reali, rumore gaussiano, moto dritto, niente distorsione, niente outlier):
f=930, B=0.2 m, d0 vero 1.5 px, encoder sbagliato di 0.5%. Script: /private/tmp/claude-501/s/sim.py (scratchpad, non nel repo).
| punti | tratto D | rumore disp. | Z usati | errore f·B | d0 trovato (vero 1.5) |
|---|---|---|---|---|---|
| 3000 | 3 m | 0.3 px | 4-12 m | +1.35% | 1.35 |
| 3000 | 3 m | 0.15 px | 4-12 m | +0.72% | 1.46 |
| 3000 | 4 m | 0.15 px | 4-10 m | +0.69% | 1.47 |
| 3000 | 3 m | 0.3 px | 4-30 m | +11% (!) | 0.3 (sbagliato) |
Lezioni: (1) funziona se si usano solo punti VICINI (<= ~12 m): i punti lontani (disparita' piccola, rumore grosso) sbilanciano il fit; (2) l'errore sull'encoder passa quasi 1:1 sulla scala, quindi la ruota va tarata (C=1.576 m misurato 10 giri, regola Daniele; i 0.3374 sono m/giro ENCODER, non la ruota); (3) un tratto di 1 m e' troppo corto (errore 73%): servono tratti >= 3 m con punti vicini.
Fonte pratica: serve la direzione del moto nel riferimento camera (la ricavano le stesse camere con recoverPose; il pitch 7.4 gradi di #001 e' gia' dentro R).
Cosa puo' andare storto nella realta' (NON VERIFICATO): slittamento ruota in frenata/curva (si scartano finestre con accel alta e sterzo), distorsione non modellata ai bordi che sporca d1/d2 (si usano solo zone centrali per scala/d0, bordi solo per dy), oggetti in moto (RANSAC sul movimento rigido), erosione/pressione gomme (C cambia: si ritara con 10 giri o si accetta una deriva lenta vista dal confronto).

Controllo incrociato odometria: odometria visiva (somma dei |T| fra frame) contro encoder su 50-100 m: se il rapporto resta 1.00 +-1% = tutto ok; se scivola nel tempo = gomma/ruota; se salta = urto o camera mossa. E' lo stesso numero, usato come allarme.

## 5. Piano strada (altezza camere nota): controllo, non fonte primaria
La strada e' un piano: in una stereo rettificata la disparita' del suolo sale linearmente con la riga v: d = (B/h)(v - v_orizzonte) circa. La pendenza dipende da B/h, NON da f.
Uso: h camere (altezza fissa dal telaio, stessa per tutte le Asmile se il supporto e' stampato/stesso) e B -> controllo di coerenza della scala; il v_orizzonte da' il pitch.
Limiti onesti: richiede asfalto vero e visibile (nelle RSA: pavimento lucido, riflessi, tappeti: poco affidabile); pendenze e dossi cambiano il piano; la bici in curva rolla. Quindi: serve come "secondo parere" che alza un allarme se discorda dall'encoder oltre 3%, non come calibrazione.

## 6. Deriva, urti, smontaggio: cosa fa la bici
Misura continua leggera (ogni secondo, su 200 match): dy p95 per zona + rotazione residua + rapporto encoder/visione. Come `drift_monitor.py` ma per zona e con p95, non media.
Distinguere:
- Salto netto (> 0.1 gradi = ~1.6 px) legato a un picco IMU: URTO. Si ricalcola subito alla prima finestra buona.
- Scorrimento lento (termico/vibrazione): corregge in silenzio se resta entro i limiti.
- Camera smontata/rimontata o sostituita: la rotazione esce dai limiti (+-1 gradi dal seme) -> ROSSO (non si "inventa" una calib: serve la procedura di fabbrica/ripristino).

Semaforo (soglie iniziali da tarare, NON VERIFICATE):
| Stato | Condizione | Cosa fa la bici |
|---|---|---|
| VERDE | dy p95 < 1 px in tutte le 9 zone, scala encoder/visione 1.00 +-2% | normale |
| GIALLO | dy p95 1-2 px, o scala +-2-4%, o una sola zona fuori | usa la depth solo nella zona centrale e entro ~5 m; limite velocita' piu' basso; si ricalibra da sola; avviso discreto allo staff |
| ROSSO | dy p95 > 2 px, scala > 4%, rotazione fuori limiti, o nuova calib scartata 3 volte | la depth NON comanda piu' freno/sterzo; resta il limitatore da encoder (solo velocita' bassa/passo d'uomo) o stop; avviso chiaro "Chiamare assistenza" |
Mai silenzio: ogni passaggio di stato si scrive nel CSV con t_ms e arriva allo staff. Le soglie di sicurezza (velocita', cosa comanda il freno) sono decisioni di sicurezza: servono i gate della lavagna e la firma di Daniele nel DECISION_LOG. Io le propongo, non le firmo.

## 7. Cosa l'online NON puo' fare (onesto) -> cosa deve venire da PRIMA
1. Distorsione e punto principale ai bordi. Dal bordo sinistro #001 (dy -4 px identico mattina e pomeriggio, rapporto calib_001_vicino_bordi) e' un errore del MODELLO, non del dato. Online si corregge il dy verticale con la mappa liscia, ma la parte orizzontale (che falsa la depth) non si separa dalla profondita' reale con soli match L-R. Con moto in avanti la self-calibration da video e' debole (moto quasi tutto lungo l'asse ottico: focale e distorsione quasi indistinguibili). Quindi: intrinseche + distorsione di ogni camera devono arrivare da una misura fatta UNA volta, in fabbrica, con una sagoma fissa (non l'operatore RSA).
2. Focale vera (si confonde con B nella scala): da fabbrica. Online si tiene solo il PRODOTTO f·B.
3. Baseline vera sulle unita' con camere montate a mano (#001): da fabbrica o supporto rigido stampato a B fissa. Se il supporto e' rigido e uguale per tutte, B e' nota.
4. Serve moto e scena: bici ferma in un corridoio bianco, al buio o con pavimento senza texture = nessuna calibrazione. I primi km sono "da fabbrica", non "garantiti".
5. Lente M12 non fissata (vite che gira): l'online segue le rotazioni, non uno spostamento della messa a fuoco/focale. Bloccare le lenti con frenafiletti.
6. Precisione ai bordi <=2% e dy<1 px in tutte le 9 zone NON e' dimostrata online: nessuna prova su dati reali. Solo la simulazione della sezione 4 (centro, ideale).
Quindi la divisione onesta: FABBRICA = intrinseche + distorsione + baseline + montaggio (una volta, rapido, con sagoma). CAMPO = rotazione fine, d0, scala f·B, deriva, allarme. Il resto dei colleghi dell'angolo fabbrica deve chiudere la prima meta'.

## 8. Rischi
- Un'autocalibrazione che si sbaglia in silenzio e' peggio di una calib vecchia: perche' accettazione con dati tenuti da parte, limiti stretti, slot A/B.
- Taratura encoder sbagliata = scala sbagliata di pari entita' (mitigazione: ritaratura 10 giri per unita'; confronto visione-encoder come spia).
- Ambiente RSA (corridoi lucidi, bassa luce OV9281): pochi match. Soluzione: accumulare per giorni; adesivi/texture sul percorso di taratura notturna.
- Ogni unita' impara solo per se': niente copia fra unita' (linea rossa).

## 9. Prossimi passi concreti (tutti sul Mac, con i log gia' registrati)
1. Estendere il test in simulazione con outlier, slittamento e distorsione; poi provarlo sui video del giro #001 sync (encoder ruota + SBS gia' loggati stesso t_ms): stimare f·B e d0 col moto e confrontare col banco fisso (punti 4,6,8,12 m mai usati nel fit). Se non coincide entro 2%, si scarta l'idea.
2. Scrivere `calib_online.py` nuovo (non modifica gli esistenti): dy per 9 zone p95, rotazione, d0/scala dal moto, semaforo VERDE/GIALLO/ROSSO.
3. Per ogni unita' nuova: giro di prova di 5 minuti in cortile, nessuna procedura manuale; l'operatore vede solo verde/giallo/rosso.
4. Decidere con Daniele le soglie di degrado (firma).

## Fonti
- Codice: logger/depth/selfcalib_essential.py (metodo E, righe 1-16, 56, 84-112); autorectify.py (rotazione 3-DoF, righe 97-118; ispirato a ICRA-2024 e brevetto Tesla US 12470683 come dichiarato nel file); drift_monitor.py (righe 26-60).
- Lezioni: agents/lezioni/asmile-calib.md (bordo sx dy -4 px; punti mai usati nel fit); agents/lezioni/daniele.md (C ruota 1.576 m; hardware per unita').
- Simulazione: /private/tmp/claude-501/s/sim.py (mia, numpy+scipy; non fonte esterna).
- Fatti esterni (Tesla flow-guided rectification, ICRA-2024): citati dal commento di autorectify.py:5-8,15-18, NON riverificati online da me.
