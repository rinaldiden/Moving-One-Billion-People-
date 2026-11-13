# Depth + segmentazione sui due giri di #001 del 13/11/2026 (notte)

Unita': asmile #001 (hw1). Giri: `session_20261113_150337` (396 s, 5804 fotogrammi) e `session_20261113_151400` (421 s, 6182). Camere: calib `logger/depth/calib_asmile-001.json` (B30), sterzo di oggi (centro 4112, sx 2028, dx 6168). Sensori: `sensors_20261113_145727.csv`, stesso `t_ms` dei fotogrammi. Nulla toccato sul Pi, pausa elaborazione automatica lasciata. Uscite (locali, mai su git): `training/depth/out_20261113_giri/`.

## Cosa e' stato fatto (e cosa NO)
- **Bici ferma tagliata**: si campiona solo con v>0.3 m/s (encoder, finestra 1 s). Giro 1: moto 90.5%, ferma ~38 s; giro 2: moto 87.1%, ferma ~54 s.
- **Tutto il giro a 1 Hz (stadio A classico `depth_video_001.py`, regole di distanza v5)**: 353 + 362 campioni, SAM 3 sugli stessi fotogrammi, depth SGBM + passata vicina, maschere SAM, tracking, controllo encoder. Video `d1hz/<sess>/depth_*.mp4`, CSV `frames.csv`/`objects.csv`.
- **Tratti a 15 fps con le regole v10 del modulo** (`video_fluido_001.py`, `VFMODE=v10`, corridoio da `pi/autonomous/corridoio.py`, soglie solo da `config/soglie_attuazione_001.json`): 5 tratti, 1.155 fotogrammi: frenata 1 (15:03:41-15:04:01, fotogrammi 0-223), frenata 2 + monovolume (15:08:42-15:09:02, f4438-4738), 3 tratti controsole (s1 f990-1169 e f2325-2504, s2 f3000-3269). SAM 3 a ogni fotogramma di questi tratti (~2.3 s/fotogramma su MPS, 1 processo).
- **NON fatto**: le regole v10 (bordi, FRENA/RALLENTA/STERZA, corridoio) NON girano sull'intero giro ma solo sui 5 tratti: SAM 3 a 15 fps su 12.000 fotogrammi sono ~7 ore. Sul resto del giro c'e' la depth a 1 Hz senza logica di attuazione.
- Fix al codice per le nuove sessioni: `ego_001.py` sceglie file sensori e centro sterzo per data (4112 dal 13/11, 6606 il 09/11) e filtra picchi encoder; `video_fluido_001.py` usa il centro/calib di oggi in `k_causale`; variabili d'ambiente per le cartelle d'uscita (`VD_OUT`, `VF_STUFF`, `STUFF_OUT`). Il 09/11 resta riproducibile.

## Velocita' ruota: filtro e dichiarazione
Daniele ha segnalato picchi fino a 83 km/h. **Nei due giri di oggi NON li ho trovati** nella colonna `enc_wheel_cum` di questo file: velocita' istantanea fra righe consecutive (50 Hz, 116.400 righe) max **18.7 km/h**, min -1.9; finestra 0.5 s max 17.7 km/h (giro 1) e 15.6 km/h (giro 2). Il contatore pero' e' irregolare: passi negativi 336 righe nel giro 1 e 865 nel giro 2 (fino a -518 conteggi = ~1.1 cm), salti positivi fino a 7.039 conteggi in una riga. Filtro applicato in `Ego`: velocita' da differenza centrata +-0.25 s, ogni campione fuori [-1, +12 m/s = 43 km/h] sostituito dalla mediana mobile di 1 s, poi v>=0. Campioni sostituiti: **0** (nessuno supera la soglia), quindi il filtro non ha cambiato nulla. Se i picchi 83 km/h sono in un'altra colonna (lim_speed, raw) o in un altro file: **NON VERIFICATO**, serve indicarmi dove li hai visti. Distanza percorsa dall'encoder: 977 m (giro 1), 1.051 m (giro 2). Controllo di coerenza Z-encoder (KLT su feature statiche, attesa 1.0): pendenza mediana 0.886 (giro 1, 22 tracce) e 0.972 (giro 2, 39 tracce).

## Frenate forti
Velocita' ruota (finestra 1 s): frenata 1: 9.7 km/h alle 15:03:50 -> 0.9 alle 15:03:52. Frenata 2: 13.95 km/h alle 15:08:49 -> 0.9 alle 15:08:53 (fermo fino alle 15:08:58).
- **Monovolume nero (15:08:53)**: tracciato come veicolo dal fotogramma 4558 (12.6 m, TTC 3.6 s), 5.9 m a f4588 (RALLENTA, 15:08:50.5, v 2.1 m/s), 4.7 m a f4603 e 4.8 m a f4623 con la bici ferma. Coerenza con l'encoder: da f4558 a f4588 la bici percorre 5.85 m e Z scende di 6.7 m (il veicolo avanza di ~0.85 m); da f4588 a f4603 percorre 1.01 m e Z scende di 1.2 m; da f4603 a f4623 0.00 m e Z varia 0.1 m. RALLENTA sul monovolume ~8.1 m alle 15:08:48.6 e 7.5 m alle 15:08:50.8, prima o con la frenata umana (v comincia a scendere alle 15:08:49.5). Maschera pulita su tutta la sagoma. **Non** ho una misura col metro: la distanza assoluta del monovolume resta NON VERIFICATA.
- **FALSI FRENA nello stesso tratto, prima del monovolume**: 64 fotogrammi FRENA in 301, di cui **28 con Z<1 m** (0.3-1.0 m a 13-14 km/h): pali sottili al bordo immagine (paletto 1.0 m a sinistra, f4440; 'altro' 0.7 m a destra, f4524). Un FRENA a 14 km/h per un palo laterale che la bici e' passata senza toccare e' un falso: la Z dei pali sottili ai bordi non e' affidabile. Sul monovolume vero FRENA scatta solo dopo le 15:08:51.5 con Z 1.2 m (probabile blob/Z sbagliata, la maschera veicolo dice 5-6 m).
- **Frenata 1 (15:03:51, arco in vicolo, controluce)**: depth vede il vicolo; non ho visto un ostacolo reale sul percorso nei fotogrammi guardati (f70, f120, f187): ipotesi, NON VERIFICATA, che la frenata umana fosse per l'arco/curva. 5 FRENA, 47 STERZA (40 allarmi bordo sx, 7 dx: muri di vicolo a 0.0-0.5 m dal margine), 7 RALLENTA. I FRENA sono muri/sassi a sinistra letti come ostacolo (f187 'ostacolo 4.6 m', 'cat' 3 volte).

## Tratti controsole: quanta depth valida si perde
Misura di sbiancamento a 1 Hz (`controsole_*.csv`: luma, % pixel saturi >=250). Giro 1: luma >=150 in 18 s; giro 2: 49 s consecutivi (t=197-247 s, luma 180-195, 35-46% di saturi nel terzo alto).
- Quota di depth valida (SGBM+vicina, disparita' >4 px) nella zona bassa-centro (strada): luma<120: **0.211**; luma>=150: **0.317** (maggiore, non minore: scena e pavimentazione diverse, non confrontabile 1:1).
- **Dentro le zone sature** (luma>=250 rettificato, ogni 5 fotogrammi, `controsole_valid.json`): valida dentro vs fuori: tratto a (6.8% di area satura) 0.32 vs 0.33; tratto b (9.1%) **0.26 vs 0.35**; tratto c giro 2 (20.6% di area satura, strada bianca) **0.17 vs 0.30**. Perdita relativa dentro il saturo: 3% / 24% / 43%; nel tratto c la perdita sull'intera immagine e' ~0.206*(0.30-0.17) = 2.7 punti percentuali di quota valida, concentrata proprio dove c'e' la strada bianca.
- Il vero danno e' sull'ostacolo non segmentato: nel tratto c (f3150, immagine quasi bianca) il banner dice "corridoio: nessun ostacolo misurato" su una strada coperta di luce: e' assenza di misura, non strada libera. SAM 3 a luma>=150: dettagli ancora presenti (14-24 detection/fotogramma), ma maschere su veicolo parcheggiato tagliato dal bordo; nel tratto b persone/mercato ok.
- Nei tratti controsole 15 fps: FRENA 75/180 (a), 26/180 (b), 4/270 (c); di questi Z<1 m: 7, 10, 0. Falsi visti: f1022 il **fondo strada** segmentato 'altro' a 2.9 m dentro il corridoio (FRENA); f2481 maschera 'veicolo' a sinistra con Z=0.3 m (FRENA, clamp minimo); f1124 'paletto 0.6 m' (FRENA, nessun oggetto a quella distanza visibile).

## SAM 3 (classi non-unknown)
1 Hz: giro 1 26.1 detection/fotogramma (pole 977, car 647, person 597, bollard 452, trash can 175, barrier 174), giro 2 21.1 (car 846, pole 814, person 397, bollard 320, barrier 200). 15 fps nei tratti: frenata 2 29.3 det/fotogramma, frenata 1 5.4 (vicolo scuro; 'cat' 102 e 'dog' 37 su muri/ombre: **falsi probabili**, nessun animale visto).

## Numeri riassuntivi (1 Hz, tutto il giro, bici in moto)
| | giro 1 | giro 2 |
|---|---|---|
| campioni | 353 | 362 |
| primo ostacolo in corridoio <2 / 2-5 / 5-10 / >=10 m | 25 / 125 / 95 / 89 | 11 / 138 / 73 / 127 |
| quota depth valida (zona bassa) | 0.227 | 0.319 |
| oggetti con classe | 4.029 righe | 3.938 righe |

Limite: sono misure senza verita' a terra col metro; il controllo e' solo la coerenza con l'encoder (sopra). Nessun numero di errore % per fascia in questo giro.

## Fotogrammi rappresentativi (`agents/rapporti/img/`)
1. `giri1113_f4558_monovolume_12m.jpg` monovolume a 12.6 m, TTC 3.6 s
2. `giri1113_f4588_monovolume_rallenta.jpg` monovolume a 5.9 m, RALLENTA
3. `giri1113_f70_frenata1_arco.jpg` frenata 1: arco in controluce, 'ostacolo 7.8 m' (blob sulla parete)
4. `giri1113_f187_falso_frena_muro.jpg` FRENA su sasso a sinistra (muro)
5. `giri1113_f4440_falso_frena_palo_1m.jpg` FRENA per palo sottile a 1.0 m a sinistra
6. `giri1113_f1022_falso_frena_strada_altro.jpg` fondo strada letto come 'altro' 2.9 m
7. `giri1113_f2380_controsole_mercato.jpg` controsole: mercato con persone/pali (ok)
8. `giri1113_f2481_falso_frena_03m.jpg` 'veicolo' 0.3 m a sinistra (falso FRENA, luce forte)
9. `giri1113_s2_f3012_controsole.jpg` giro 2, 21% saturo, auto a dx 4.6 m
10. `giri1113_s2_f3150_bianco.jpg` giro 2, immagine bianca: nessun ostacolo misurato

## Per asmile-occhio (cosa guardare)
Verifica: (a) i FRENA con Z<1 m del tratto frenata 2 e controsole a/b: sono tutti falsi? (b) le Z del monovolume (12.6/5.9/4.7 m) sono plausibili sulle strisce? (c) nei tratti bianchi il banner 'nessun ostacolo' su strada illuminata e' accettabile? (d) 'cat'/'dog' nel vicolo scuro.
Da correggere in un giro successivo (non fatto qui): Z minima su pali sottili al bordo, 'altro' sul fondo strada, clamp 0.3 m, quota minima di depth valida come condizione di 'strada libera' in controsole.
