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
