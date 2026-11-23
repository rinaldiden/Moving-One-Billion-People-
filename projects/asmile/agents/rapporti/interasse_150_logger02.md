# Interasse 150 mm per i logger HW3: simulato sui video di logger02 (23/11, giro2)

Dati: logger02 giro2, A=sinistra, B=destra, 16 finestre da 9 fotogrammi consecutivi (t 465-1000 s, di cui 12 in moto, 4 da fermo), calib v3 (f rettificata 1219 px). SGBM 1280x720, numDisparities 288 (min -16), controllo L-R. Script: `training/depth/interasse_prep.py`, `interasse_noise.py`, `interasse_sim.py`. Immagine: `interasse_150_logger02.png` (sinistra | Z 200 | Z 150 simulato | differenza).

## 1. Rumore di disparita' MISURATO (px), tre stimatori indipendenti
| stimatore | mediana | p95 |
|---|---|---|
| temporale (residuo fit quadratico tracce LK su 9 frame), tracce in moto (2232) | 0.24 | ~0.5 |
| temporale, tracce ferme (5907) | 0.09 | 0.3 |
| spaziale (residuo piano su patch 16x16, 54000 patch) | 0.22 | 0.61 |
| per fascia Z (spaziale) 1-3 / 3-7 / 7-12 / 12-18 / 18-30 m | 0.21 / 0.24 / 0.22 / 0.22 / 0.21 | 0.60 / 0.60 / 0.62 / 0.64 / 0.60 |
| per zona 3x3 (spaziale, mediana) | 0.20-0.28 (peggio in basso a dx/centro, 0.27-0.28) | 0.50-0.69 |
| campo lontano (pixel con Z>150 m, deviazione std) | 0.47 (include struttura vera) | 0.90 |
Il rumore NON dipende dalla distanza: e' costante in px (come previsto). Uso sigma_d = 0.24 px (centrale) e 0.61 px (pessimista).
Prova dy sul SGBM reale (R spostata di 0 / 0.5 / 1 / 2 px in verticale): sigma 0.229 / 0.229 / 0.239 / 0.256, validi L-R 50.0 / 49.9 / 49.3 / 46.3%, bias di disparita' ~0 (-0.02). Quindi un dy residuo di 0.5-1 px costa quasi nulla; quello che pesa e' un offset di disparita' (yaw/Ry, d0 = -2.55 +-0.5 px), che e' un bias diretto.

## 2. Errore % di distanza, dZ/Z = Z*sigma/(f*B) (f=1219 px)
sigma 0.24 px (centrale):
| B | 2 m | 5 m | 10 m | 15 m | 20 m |
|---|---|---|---|---|---|
| 200 | 0.2 | 0.5 | 1.0 | 1.5 | 2.0 |
| 150 | 0.3 | 0.7 | 1.3 | 2.0 | 2.6 |
| 100 | 0.4 | 1.0 | 2.0 | 3.0 | 3.9 |
Con in piu' un offset di montaggio/yaw di 0.5 px (somma quadratica): 200: 0.5/1.1/2.3/3.4/4.6; 150: 0.6/1.5/3.0/4.6/6.1; 100: 0.9/2.3/4.6/6.8/9.1. Con 1 px: 200: 0.8/2.1/4.2/6.3/8.4; 150: 1.1/2.8/5.6/8.4/11; 100: 1.7/4.2/8.4/12.7/16.9.
Con sigma pessimista 0.61 px a 10 m: 200 = 2.5%, 150 = 3.3%, 100 = 5.0%.
Il passaggio 200->150 costa sempre x1.33; 200->100 costa x2.

## 3. Simulazione su oggetti reali (13 oggetti da SGBM 200 mm: bollard, furgone, fioriere, auto, muri, pilastro, arco, siepe, blocco cemento; 20000 estrazioni ciascuno)
Disparita' a B: d_ref x B/200 + rumore misurato (+ offset casuale +-0.5 px dove indicato). Percentuale media di estrazioni oltre +-2% / +-5%, e p95 dell'errore (mediana sugli oggetti):
| set | B | >2% | >5% | p95 err % |
|---|---|---|---|---|
| oggetti <=10 m (5), sigma 0.24 | 200 / 150 / 100 | 0 / 1 / 4 | 0 / 0 / 0 | 0.7 / 0.9 / 1.4 |
| <=10 m, sigma 0.24 + offset 0.5 px | 200 / 150 / 100 | 2 / 5 / 14 | 0 / 0 / 1 | 1.0 / 1.4 / 2.0 |
| <=15 m (9), sigma 0.24 | 200 / 150 / 100 | 5 / 10 / 21 | 0 / 0 / 2 | 1.5 / 2.0 / 2.9 |
| <=15 m, sigma 0.24 + offset 0.5 px | 200 / 150 / 100 | 15 / 23 / 36 | 0 / 2 / 9 | 2.2 / 3.0 / 4.5 |
| <=15 m, sigma 0.61 (pessimista) | 200 / 150 / 100 | 28 / 37 / 51 | 5 / 11 / 21 | 3.7 / 5.0 / 7.5 |
| tutti (13, fino a 27 m), sigma 0.24 | 200 / 150 / 100 | 15 / 23 / 34 | 1 / 3 / 10 | 2.3 / 3.1 / 4.6 |
Distanza minima misurabile (disparita' max 270 px con numDisparities 288): B=200 0.89 m, B=150 0.67 m, B=100 0.45 m (a meta' risoluzione sul Pi circa il doppio).

## Verdetto per un logger
150 mm va bene: fino a 10 m l'errore resta ~1.3% (p95 1%) e a 15 m ~2% (4.6% con 0.5 px di offset), sempre sotto il 5% nei casi centrali; si guadagna la distanza minima (0.67 contro 0.89 m). 100 mm no oltre ~10 m. Il limite vero non e' la baseline ma l'offset di disparita' d0 (+-0.5 px = 2% a 10 m): la calibrazione conta piu' del passaggio 200->150.

## Limiti (onesti)
- Il rumore a 150 mm NON e' misurato su hardware a 150 mm: e' assunto uguale in px a quello misurato a 200 (e' una buona ipotesi per SGBM, non una prova). Servirebbe un giro con due camere a 150 mm.
- La "verita'" di ogni oggetto e' la distanza SGBM a 200 mm (scala +-5%, focale non risolta), non il metro: l'errore e' relativo a questa, quindi misura la stabilita', non l'accuratezza assoluta.
- Il rumore e' misurato su tracce/patch lisce: bordi di oggetti e superfici senza tessitura (cielo, muri lisci) non rientrano. Nel campo lontano la disparita' vera media risulta +0.8 px sopra d0 (selezione troncata, da non leggere come bias): un d0 residuo di 0.5-1 px e' plausibile.
- Solo il tratto dopo 390 s, 4 finestre da fermo e 12 in moto lento/medio.
