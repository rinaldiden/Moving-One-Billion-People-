# Calibrazione logger02, giro 24/11 16:25 (dopo la rimessa a fuoco) - CANDIDATO v5

In parole semplici: dopo la nuova messa a fuoco le due camere erano storte di circa 2-3 pixel in altezza (con la calibrazione vecchia v4). Con la nuova v5 lo scarto verticale scende a circa 0,6-0,8 pixel su punti che non ho usato per calcolarla. La scala (quanti metri) NON e' ancora verificata: serve la foto col metro. Il file e' un CANDIDATO, non promosso.

## Dati e sincronia
- Giro: A 162459 + B 162506 + sensori 162459. Giro vero (vicoli, strada, prato, vicoli), IMU in moto 130-330 s e 390-715 s, fermo 330-360 s e 720-827 s.
- Escluso: i primi 130 s (sveglia, partenza, rotazioni forti) e 360-390 s. Dichiarato nel PREREG prima di misurare.
- Aggancio B: nessun reset di t_a_us in questa sessione. Coppie solo per t_a_us, soglia 0,1 ms. Di 13728 fotogrammi A ne tengo 13515 (1,55% scartati; 0,61% dopo che la B parte, a 16,7 s). Scarto tenuto: mediana 0,022 ms, p95 0,062, max 0,099. Scarto di tutte: mediana 0,023, p95 0,067. Instabile fra 17 e 30 s (p95 0,28 ms, max 9,6 ms), stabile dal 30 s: tutto dentro la parte esclusa.

## Cosa e' stato fatto (PREREG: agents/prove/asmile-calib_logger02_20261124_giro2/PREREG.md)
Blocchi da 60 s: fit sui pari, prova sui dispari, poi scambio. Liberi: Rx, Rz, Ty, Tz, cy destra. Fissi come v4: Ry, cx (spostano d0 e non si vedono dalla geometria epipolare), lente, focale. Modello con k1,k2 liberi provato, NON adottato (la regola chiedeva >=5% su mediana e p95: mediana +6/+13%, p95 +1/+2%).
Deviazione dichiarata: il primo giro lasciava liberi Ry e cx (errore mio di implementazione, il PREREG li diceva fissi): rifatto.

## Numeri (punti tenuti fuori, R fissa)
- dy mediana: dispari con R(pari) 0,80 px, pari con R(dispari) 0,79 px (v4 prima: 2,79). p95: 4,9 e 5,7 px.
- Finestre ferme mai usate in nessun fit (R finale): mediana 0,55 px, p95 1,83. Con i due fit parziali: 0,98 e 0,43.
- Verifica indipendente (remap + SIFT nuovo, coppie diverse): dispari 0,61 (v4: 2,40), pari 0,70 (v4: 1,57), ferme 0,53 (v4: 1,05). p95 4,3 / 5,0 / 1,6.
- Stabilita': Rx per blocco da 60 s, 10 blocchi: max-min 0,038 gradi (<0,05 OK). Salto massimo fra finestre da 30 s: 0,63 px (<1 OK).
- Per zona 3x3 (fit): mediane 0,5-1,4 px. NON tutte < 1: 4 zone su 9 nei dispari (1,18 1,28 1,13 1,03) e una nei pari (1,43). Soglia 2 NON soddisfatta. Nel remap indipendente solo una zona >1 (1,27, basso-destra nei pari).
- Il p95 alto in moto (5 px) cresce con la disparita' (oggetti vicini e bordi: 0,57 -> 1,03 mediana) e NON con la velocita' di rotazione: sembra residuo della lente ai bordi, non sincronia. NON VERIFICATO.
- Zona alto-sinistra delle finestre ferme: 143 punti con mediana 37 px = falsi match (cielo/muro), scartata.

## Verdetto pre-registrato
Soglie 1 (mediana <1), 3 (ferme), 4 (stabilita'), 5 (remap): OK. Soglia 2 (ogni zona <1): NO. p95<1 px: non raggiungibile con SIFT su H.264 (dichiarato). Quindi non "fermo" pieno: R stabile nel tempo, ma zone di bordo ancora 1-1,4 px.

## Focale e scala
- Giroscopio: NON coerente. Bias gyro di questa sessione (-1,04; 0,48; -0,94) (y era 0,85). Imbardata 1,02 stabile; beccheggio 0,93 (dispari) - 1,07 (pari): q = 0,973 vs 1,044, differenza 7% > 3%. Rollio 1,065 (dovrebbe stare 1+-0,05: forse la rotazione IMU->camera e' cambiata con il case riaperto, o il giroscopio ha scala diversa). La gravita' non basta (1 transizione) per tarare il giroscopio. Focale lasciata uguale a v4, +-5%. NON VERIFICATO.
- d0 = -2,55 px copiato da v4: PROVVISORIO (era misurato col fuoco di prima).
- Scala: da esaminare con la foto ferma col metro (comando sotto). Non ho ricalibrato la baseline (200 mm resta).

## Comando per la foto col metro (logger02 acceso e fermo, camere raggiungibili)
python3 projects/asmile/logger/depth/calib_rock/logger02_v2/foto_metro.py projects/asmile/logger/depth/calib_logger02.CANDIDATO_v5_20261124.json projects/asmile/asmile-loggers/logger02/foto_metro_v5_20261124 --host <IP del logger02, il default 192.168.1.122 NON verificato>
Poi Daniele misura col metro dal centro fra le due lenti i punti numerati; si confronta l'errore % per distanza. Da quei punti si fissano d0 e focale (esame, non fit).

## File
- Candidato: projects/asmile/logger/depth/calib_logger02.CANDIDATO_v5_20261124.json (v1-v4 non toccati)
- Prove: projects/asmile/agents/prove/asmile-calib_logger02_20261124_giro2/ (PREREG.md, sync.py/json, extract.py, fit.py, fitlib.py, remap_check.py, fit_v5.json, remap_v5.json)
- Gli script giroscopio sono copie temporanee con bias nuovo (scratch, non salvati nel repo); risultati nel JSON del candidato.

## AGGIORNAMENTO (round 2, dopo il PASSA parziale del critico; v5 non toccata, v6 NON scritta)
PREREG aggiornato prima di misurare (sezione ROUND 2). Script: lens2.py, procrustes.py; risultati lens2.json, procrustes.json nella cartella prove.

1) Residuo di lente in basso a destra, giudicato per zona 3x3 sui blocchi tenuti fuori (pari->dispari e dispari->pari). Provati: k1,k2 comuni (K2), + k3 (K3), k1,k2 per camera (KC), + rapporto di focale (KCF), + cy sinistra libero (KCFc). Segno mediano zona 8: da -0,67/-1,27 px (v5) a -0,52/-0,70 con K2, -0,36/-0,36 con KC. Ma nessun modello passa le regole scritte prima: K2 e K3 non scendono del 30% in entrambe le direzioni; KC e varianti peggiorano zona 0 (+17%) e portano a 2 le zone sopra 1 px nei pari. Zone sopra 1 px: v5 4 e 1; K2 1 e 1 (il migliore, ma non basta). Costo di scala: con KC la disparita' laterale cambia fino a 1,1 px in zona 2. Conclusione: il residuo in basso a destra c'e' ed e' ridotto da k1,k2, ma non in modo che regga su entrambe le meta'; v5 resta. K2 (parametri k1 -0,001/-0,006, k2 -0,038/-0,042, stabili fra le due meta') e' il candidato per un v6 col prossimo giro (piu' dati ai bordi), non ora.

2) R_imu->camera: NON e' cambiata in modo dimostrabile. Procrustes (441 coppie): angolo fra la nuova e quella del case v5 1,87 gradi, ma l'errore tenuto fuori cala solo del 7-11% (serviva 20%) e la Rc per blocco da 60 s balla di 3-10 gradi (blocchi mal condizionati: poche rotazioni diverse). Quindi niente nuova R_imu e focale non rifatta con una nuova R.
Spiegazione del rollio 1,065 (esplorativa, post-hoc, non pre-registrata): con la Rc vecchia, imbardata 1,065 e rollio 1,070, uguali fra pari e dispari (1,069/1,072 e 1,059/1,068). Il rollio non dipende dalla focale, quindi il giroscopio legge ~6,5% in piu' (o la scala visiva e' 6,5% diversa) su tutti gli assi. Rapporto imbardata/rollio = 0,998 (pari) e 0,992 (dispari): la focale di v5 e' coerente entro ~1% sull'imbardata. Il beccheggio (0,83-1,03) e' instabile (si confonde con la traslazione) ed e' quello che dava la q incoerente 0,973-1,044. Resta NON VERIFICATO col metro: la focale si decide con la foto col metro.
