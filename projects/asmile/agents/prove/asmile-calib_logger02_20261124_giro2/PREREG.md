# PRE-REGISTRAZIONE calib logger02 v5, giro 24/11 16:25 (scritta PRIMA di misurare qualsiasi dy)
Fatti visti prima (non sono dy): sync da CSV, IMU a finestre di 30 s, 14 fotogrammi a occhio, ffprobe 1280x800.

## Dati
- A = clip_20261124_162459_A_* (14 clip, t_us 8.9-827 s), B = clip_20261124_162506_B_* (14 clip), sensori = sensors_20261124_162459_*.
- Aggancio B: t_a_us della B in questa sessione NON ha reset (0 salti < -1 s); 13598 coppie, |dt| mediano 0.023 ms, p95 0.067 ms, offset frame 0 (sync.json). Le 130 A prima della prima B (t<16.7 s) escluse.
- Giro vero in bici/spinta nel paese e sulla strada fuori (fotogrammi: vicolo, strada con muro, prato, vicolo, cortile). IMU a finestre di 30 s: in moto 0-330 s e 390-715 s; FERMO 330-360 s (prato, scena lontana) e 720-827 s (muro vicino + ombrello: scena quasi piana, solo controllo).
- Esclusi da fit E da verdetto: t < 130 s (primi 2 min: sveglia a 9 s, partenza/maneggio, vicoli stretti con rotazioni forti); finestre 360-390 s (transizione).
- Messa a fuoco ~15:30: v1-v4 NON usate come verita'; v4 serve solo da punto di partenza della lente (k1,k2,k3 di #001-sx), cx, cy, f, R, T di v4 sono ricalcolati o dichiarati.

## Blocchi
- Blocchi di 60 s (indice floor(t/60)); validi quelli con t in [130,330) e [390,715).
- FIT: blocchi PARI (poi SCAMBIO: fit sui dispari, test sui pari). Candidato finale = fit su TUTTI i blocchi validi, ma la verifica e' fatta solo con i due fit parziali.
- TENUTI FUORI MAI USATI in nessun fit (controllo indipendente): finestre FERME 330-360 s e 720-827 s (R fissa, nessun refit).
- Verifica rettificata indipendente: cv2.remap + SIFT nuovo (non i match del fit) su 60 coppie dei blocchi tenuti fuori e 30 delle finestre ferme.

## Modelli (scelta fissata ora)
- RC = R (3) + direzione T (2) + cx,cy per camera (4); |T| = 200 mm non toccata. Ry non e' osservabile ne' separabile da d0: lasciata a v4 (dichiarato).
- RCL = RC + k1,k2 comuni (stesso set di lenti, modello k1k2k3 con k3 fisso). Si adotta RCL SOLO se in ENTRAMBE le direzioni (fit pari->test dispari e viceversa) mediana e p95 di dy tenuti fuori migliorano di >=5% rispetto a RC e nessuna zona 3x3 peggiora >10%; altrimenti RC.
- Focale: dal giroscopio (g1,g2,g4,g5 di logger02_v2) con la lente scelta; bias gyro dai tratti fermi di QUESTA sessione; R_imu->cam di v5-case (potrebbe essere cambiata col case riaperto: se s_rollio fuori da 1+-0.05 lo scrivo, ed e' un campo di sospetto). Coerenza: q su coppie pari vs dispari entro 3%.
- d0: NON misurabile da questa sessione senza scene a Z infinito certe; si prende d0 di v4 (-2.55 px) come PROVVISORIO, scritto tale (verra' esaminato con la foto col metro).

## Soglie (giudicano i blocchi tenuti fuori, R fissa, nessun refit per blocco)
1. mediana |dy| pool moto tenuti fuori < 1 px, in ENTRAMBE le direzioni (pari->dispari e dispari->pari);
2. mediana |dy| per zona 3x3 < 1 px (zone con >=15 punti; zone vuote = NON VERIFICATO, non verdi);
3. nelle finestre ferme mai usate: mediana < 1 px;
4. stabilita': Rx fittato per blocco di 60 s (solo Rx) max-min < 0.05 gradi, e nessun salto > 1 px nella mediana con segno fra finestre di 30 s consecutive;
5. remap+SIFT indipendente: mediana < 1 px;
6. p95 DICHIARATO (non condizione): H.264 SIFT ha un pavimento di 2-3 px; il gate p95<1 px di uscita non e' verificabile con SIFT su H.264 e lo scrivo come tale;
7. coerenza focale gyro vs pari/dispari entro 3%.
Verdetto: "fermo" solo se 1+2+3+4+5 insieme; altrimenti si dichiara quale fallisce. Il file e' CANDIDATO (non promosso): scala da esaminare con la foto col metro.

## AGGIUNTA (richiesta di Daniele via capo, prima di rilanciare l'estrazione ufficiale)
- Accoppiamento SOLO per t_a_us (orologio A, vicino piu' prossimo), mai per numero di fotogramma. Si usano SOLO coppie con |t_A - t_B| <= 0.1 ms.
- Misurato (sync.json): sul totale 13728 fotogrammi A, 13515 tenuti (1.55% scartati; 0.61% se si contano solo quelli dopo l'inizio della B a 16.7 s). Scarto delle tenute: mediana 0.022 ms, p95 0.062, max 0.099. Aggancio B: prima B a 16.67 s; instabile fra 17 e 30 s (p95 0.28 ms, max 9.6 ms), stabile da 30 s (p95 0.06). Tutto questo cade in t<130 s, gia' escluso.
- Un primo giro del fit (soglia 1 ms + offset frame, 868 coppie) e' stato fatto PRIMA di questa aggiunta ed e' solo esplorativo: i numeri ufficiali sono dal rilancio con soglia 0.1 ms. Le regole del PREREG non sono cambiate dopo averlo visto (RC adottato dalla regola RCL).

## DEVIAZIONE dichiarata (dopo il primo giro esplorativo, PRIMA del giro ufficiale)
Nel giro esplorativo il fit RC lasciava liberi Ry, cx e cy di entrambe le camere: Ry e (cx1-cx2) NON sono osservabili dall'epipolare e spostano d0 (Ry 0.0107 vs 0.0025 rad fra pari e dispari = 13 px di d0; cx1-cx2 4.6 vs -6.3 px). Il PREREG diceva gia' Ry=v4: era un errore di implementazione mio. Correzione: liberi SOLO Rx, Rz, Ty, Tz, cy della camera destra (relativo), + k1,k2 nel RCL. Ry, cx1, cx2, cy1 = v4 (cosi' d0 = -2.55 resta quello di v4, provvisorio). Soglie e regola RCL invariate.

## ROUND 2 (richiesta del capo dopo il PASSA parziale del critico; scritto PRIMA di misurare; v5 non si tocca, v6 solo se migliora)
### Punto 1: residuo di lente, giudicato PER ZONA 3x3 sui blocchi tenuti fuori
Stessi dati (lr_matches.pkl, 867 coppie |dt|<=0.1 ms), stessi blocchi (60 s pari/dispari + scambio), stesso fit di montaggio (liberi Rx,Rz,Ty,Tz,cy destra; Ry,cx1,cx2 = v4). Modelli, in aggiunta al RC di v5:
- K2: k1,k2 comuni (gia' provato nel giro 1);  K3: k1,k2,k3 comuni;  KC: k1,k2 per camera (4 par);  KCF: KC + rapporto di focale destra/sinistra (fx e fy della destra x (1+e));  KCFc: KCF + cy della sinistra libero con limite +-15 px.
Si ADOTTA un modello (solo come v6) SOLO se in ENTRAMBE le direzioni (pari->dispari e dispari->pari), contemporaneamente:
 a) il numero di zone con mediana |dy| > 1 px (solo zone con >=15 punti) non aumenta e almeno in una direzione diminuisce;
 b) nessuna zona peggiora di >10% in mediana |dy|; 
 c) il |segno mediano| della zona basso-destra (zona 8) scende di >=30%; 
 d) mediana globale non peggiora;
 e) i parametri restano fisici: |k1|,|k2|,|k3| entro 0.3/0.3/0.15 dal valore v5 e la mappa r_d(r_u) monotona fino a r_d=0.64; il rapporto di focale entro +-2%;
 f) effetto sulla scala: spostamento mediano della disparita' rettificata (dx) rispetto a v5, per zona, riportato; se > 1 px in una zona lo scrivo come costo (cambia Z lateralmente), non e' un criterio di scarto ma va in rapporto.
Se piu' modelli passano: il piu' semplice (meno parametri). Poi verifica indipendente remap+SIFT (coppie k%12==6) sui blocchi pari/dispari/ferme con il modello scelto: mediana per zona.
### Punto 2: R_imu->camera per blocco (Procrustes)
Dati: coppie A-A vicine (g1, 667, rotazione gyro 1.5-20 gradi, solo t 130-330 e 390-715), rotazione visiva da matrice essenziale (cv2.findEssentialMat/recoverPose su punti normalizzati con la lente v5), rotazione giroscopio integrata con bias di QUESTA sessione (-1.04, 0.48, -0.94). Modello: rotvec_vis = -s * Rc * rotvec_gyro (convenzione di g2/g4: Rrel = Rc Rg^T Rc^T). Kabsch pesato per |rot| con scala s isotropa per blocco di 60 s, e Rc di v5-case come confronto.
Criteri "Rc cambiata": (i) angolo fra Rc_nuova (tutti i dati) e Rc_v5case > 1.5 gradi; (ii) errore angolare mediano relativo sui blocchi tenuti fuori (fit su pari, test su dispari e viceversa) cala >= 20% rispetto a Rc_v5case; (iii) dispersione fra blocchi della Rc (angolo dalla mediana) < 1 grado. Se (i)+(ii)+(iii): uso la Rc nuova e rifaccio focale dal giroscopio (g4 per asse, pari/dispari). Se no: Rc invariata e il rollio 1.065 resta spiegato come scala giro/lente, NON verificato.
Coerenza focale dopo: q pari vs dispari entro 3% e s_rollio in 1+-0.05; altrimenti focale NON VERIFICATA (resta v5, +-5%).

### ESITO ROUND 2 (scritto dopo la misura; criteri non cambiati)
Punto 1: NESSUN modello passa, v6 NON scritta. Zone con mediana>1 (dispari, pari): RC 4,1; K2 1,1; K3 1,1; KC 1,2; KCF 1,2; KCFc 1,2. Segno mediano zona 8 (RC -0.67/-1.27): K2 -0.52/-0.70 (-23%/-45%: fallisce c su dispari); K3 -0.54/-0.71 (-19%/-44%: fallisce c); KC -0.36/-0.36 (-47%/-71%: c ok) ma fallisce a (pari: 1->2 zone>1) e b (zona 0 pari 0.95->1.12, +17%). Costo scala (dx vs v5) fino a 1.1 px in zona 2 con KC.
Punto 2: Rc NON cambiata secondo i criteri: (i) angolo 1.87 gradi >1.5 SI; (ii) calo errore tenuto fuori 6.6% e 10.6% (<20%) NO; (iii) dispersione blocchi mediana 3.3 max 9.8 gradi (>1) NO (blocchi mal condizionati, cond fino a 470). Esplorativo post-hoc: pendenze per asse con Rc v5-case: imbardata 1.065, rollio 1.07, beccheggio 0.83-1.03 (instabile).
