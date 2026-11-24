# PRE-REGISTRAZIONE calib logger02 24/11 (scritta PRIMA di misurare qualsiasi dy)
Fatti gia' visti prima di scrivere (non sono dy): sync da CSV (sync.py/sync.json), IMU, 5 fotogrammi a occhio, ffprobe.

## Cosa sono davvero i dati di oggi (dichiarato, cambia il protocollo)
- S1 = A140339 / B140323 (14:03, 13 clip, t 9-854 s con buchi 129-147 e 520-652): **NON e' un giro**. Logger appoggiato su un tavolo davanti a un portatile (scena vicina, quasi piana). IMU ferma ovunque tranne 360-450 s (maneggio, gyro fino a 250 dps).
- S2 = A143247 / B143252 (14:32, 15 clip, 9-889 s): officina (tornio, finestra, profondita' vera). IMU in movimento (portato in mano/spostato) 9-540 s, poi fermo 540-889 s. E' la sessione con "moto" vera: e' il blocco di fit.
- M = A103842 / B103743 (10:37, 2 clip, 129 s): RIFERIMENTO DEBOLE (2 clip), solo diagnostica.
- Nessuna sessione di strada in bici. "In moto" = IMU in movimento (finestra 30 s: scarto max giroscopio dalla mediana >5 dps OPPURE std accel >0.02 g). Il giro in bici vero NON c'e' oggi: NON VERIFICATO in strada.
- Video 1280x800 (ffprobe). v3 e' 1280x720: base = v3 con size [1280,800] e cy+40 su ENTRAMBE le camere (nota del capo; file di lavoro, v1-v3 non toccati).
- Firmware: nei file salute/errori NON c'e' la versione fw. Prova indiretta: sessioni tutte del 24/11 (OTA 941d249d il 23/11 19:47) e sync A/B 0.02 ms mediano (prima del fix era 0-30 ms). NON VERIFICATO con hash.

## Sync (condizione 3)
Coppia = nearest per t (B in clock A). Soglia per il dy: |dt| <= 1 ms e numero frame A-B uguale a quello modale. Scarto mediano/p95 e % sfasati: da sync.json.

## Esclusioni (condizione 5)
Finestra di 30 s esclusa dal VERDETTO se: (a) IMU ferma (criterio sopra); (b) scena degenere: <1000 punti L-R validi oppure <6 delle 9 zone con >=15 punti. Le finestre ferme-ma-ricche vengono riportate a parte (non nel verdetto "fermo").
Punti: SIFT sui grezzi, gate |dy|<25 px e 1<dx<500 dopo rettifica v3 (gate largo, non tronca), r_d<0.64.

## Blocchi
- FIT: S2 t in [9, 69.6] s (primo clip, primo blocco in moto), Rx,Rz fittati (Ry = v3, d0 invariato), Sampson soft_l1. Nient'altro.
- TENUTI FUORI (misura principale, R fissa): TUTTO il resto: S2 t>69.6, S1 intero, M. Nessun refit per blocco.
- Diagnostica Rx per blocco di 60 s (solo Rx fittato blocco per blocco): NON entra nel verdetto.
- Riportati: dy con v3 cosi' com'e' (cy+40), dy con R fissa del blocco FIT.

## Soglie "fermo"
1. mediana |dy| (pool finestre di verdetto tenute fuori, R fissa) < 1 px;
2. nessun salto > 1 px nella mediana con segno fra finestre di 30 s consecutive (senza buchi >5 s);
3. Rx per blocco 60 s: max-min < 0.05 gradi (= ~1 px);
4. p95 riportato (gate calib p95<1 px: SIFT H.264 ha pavimento ~2-3 px, vedi 23/11: dichiarato non condizione di "fermo").
Verdetto: "fermo" solo se 1+2+3 insieme; altrimenti "si muove ancora". Se nessuna finestra IMU-in-moto dopo il blocco FIT e' valida: NON VERIFICATO.

## CORREZIONI DEL CAPO (ricevute prima di qualsiasi dy misurato; extract.py gia' lanciato ma produce solo match grezzi, nessuna statistica dy)
1. Il capo (dopo aver guardato i fotogrammi) conferma: S1 (14:03) e M (10:37) = logger FERMO sul banco davanti al portatile (<1 m), scena vicina quasi piana. Sono SOLO controllo da fermo + sync + stabilita' nel tempo. Mai nel verdetto "fermo in bici". Per S1/M dichiaro numero punti e spread in profondita' (disparita'): se degenere lo scrivo.
2. Daniele: il GIRO col case fissato e' S2 = A143247 / B143252 (15 clip ciascuna) + sensors_143247. Gyro sd per clip da 60 s: 3.3,1.9,0.9,0.4,4.6,5.7,7.3,7.5,2.1, poi ~0 (fermo dal clip 9). Officina all'inizio, strada (facciata con inferriata) circa clip 4-7, poi officina. Strada breve (~4-5 min): dichiarato. Il verdetto principale usa S2 (blocco FIT = S2 t<69.6 s come gia' scritto; tenuti fuori: resto di S2). Accoppiamento per sessione A143247<->B143252 (gia' cosi').
3. v4 candidato (pari/dispari + scambio, 1280x800) SOLO se S2 esce "fermo" secondo le soglie sopra; sempre senza promozione: scala non verificata, giro corto.
4. Il mio criterio IMU "in moto" resta come filtro in S2 (dopo ~540 s l'officina e' ferma: finestre ferme riportate a parte).

## ESITO (scritto dopo la misura)
Verdetto pre-registrato: "si muove ancora" (blocco FIT t<69.6 s dentro un transitorio: dy v3 -8.5 -> -22 -> -7 px; R fissa dava 13 px; salti 13-15 px; Rx range 0.67 gradi su tutti i blocchi). Lettura post-hoc ESPLORATIVA (v4.py, t>=120 s pari/dispari): med 0.51 / swap 0.49, salto max 0.39 px, Rx per blocco t>=60 range 0.03 gradi. Il verdetto formale non e' stato cambiato.
