# depth + segmentazione #001, giro 2026-11-09 (session_20261109_094146)
Solo #001 (2 OV9281, order RL, calib `logger/depth/calib_asmile-001.json` di oggi, PASSA del critico). Nessun dato del logger.

## Risposta: la depth e' perfetta? NO. E' buona al centro e da fermi, meno ai bordi e da vicino in moto
| prova | risultato | obiettivo | esito |
|---|---|---|---|
| a) banco fisso, pipeline vera (rettifica + SGBM, mediana disparita' ±10 cm sul tabellone), 1-15 m | |err| ≤1.2% fino a 12 m (verifica 4-6-8-12 m: +0.38 +0.36 -0.38 -0.57%); 15 m -2.78% | ±2% | OK fino a 12 m, 15 m NO (disparita' 18 px, 0.5 px = 2.8%) |
| b) moto, <5 m | MAE 5.8%, p90 11% (n=23, 10 tracce, auto/furgoni+oggetti fermi) | ±2% | NON RAGGIUNTO |
| b) moto, 5-10 m | MAE 3.9%, p90 9.1% (n=155, 26 tracce); solo pali/cartelli/recinzioni: MAE 4.9% | ±5% | OK sul MAE, p90 sopra |
| b) moto, 10-20 m | MAE 2.6%, p90 6.2% (n=469, 36 tracce); solo pali ecc.: MAE 6.4% | ±10% | OK |
| b) 20-30 m (extra) | MAE 4.9%, p90 10% (n=101) | - | - |
| c) bordi (tutte le fasce) | centro |u-cx|<200 px: MAE 2.1% p90 4.9%; 200-400: 4.4% / 10.6%; >400: 6.8% / 13.9% | - | bordi 3x peggio, coerente col dy 2-5 px della rettifica |
Dettaglio clip 3 min (frame 4500-7200, passo 3): stesse conclusioni (centro 1.8%, bordo >400 px 8.1%; 5-10 m MAE 1.8% su 15 tracce).

## Come e' misurato (b) — limiti dichiarati
- Oggetti fermi (pali, cartelli, cestini, recinzioni, cancello + auto/furgoni parcheggiati) seguiti nel tempo; per un oggetto fermo Z cala di c*S, S = metri dall'encoder ruota (2.1219e-5 m/count, ruota 15.76 m/10 giri), c=cos(7.4°)=0.992.
- Per traccia un solo parametro A (peso 1/Z²): Z_pred = A - c*S; errore = Z/Z_pred - 1 per fascia di Z PREDETTO. 12 tracce di pali/cartelli/recinzioni/cancelli + 26 di auto/furgoni (quelle con pendenza coerente). Il numero di tracce "fisse" ≥5 e' rispettato, ma:
  1. l'associazione fra frame accetta |Z - Z_pred| < 1 m + 12%: taglia gli errori grossi, quindi il MAE e' un po' OTTIMISTICO;
  2. "ferma" per auto/furgoni e' decisa dalla pendenza della traccia stessa (circolare): auto in moto escluse a mano non e' fatto;
  3. la fascia <5 m ha pochi punti utili: molti sono maschere tagliate dal bordo immagine (u≈1250) e danno +20..+50% (scartati dal calcolo solo se la traccia fallisce);
  4. errore di scala per traccia (pendenza libera): mediana +5.3%, MAE 10% su 38 tracce (poco peso: tracce corte, e S e Z si muovono insieme).
- Dall'encoder si controlla la DIFFERENZA di distanza, non la distanza assoluta: l'ancora assoluta resta il banco col metro.
- Pali sottili: la maschera SAM 3 prende lo sfondo, uso il percentile 70 della disparita' (sfondo = disparita' minore). Z>30 m (disparita' <9 px) non e' etichettata.

## Segmentazione (SAM 3, stessa pipeline `ThingsTeacher` del 2026-11-08, soglia conf≥0.5, maschere rettificate sul left fisico)
- Giro intero (frame 1800-10066, ogni 6 frame = 2.5 Hz, 2.27 s/passata su Mac): 10 827 detection, 4 577 con distanza ≤30 m. Classi con Z: auto 1030, pali 812, persone 746, bollard 666, cartelli 258, recinzioni 253, cestini 157, furgoni 141, **cancelli 123**, moto 98, barriere 63, panche 60.
- Aggiunti a THINGS "gate", "fence" (cancelli/recinzioni, TODO di Daniele). Provati e RIMOSSI "railing" e "metal grille": falsi positivi (spigoli edifici, calandra auto). Cancello visto davvero a frame 6900 (13.8 m, anta verde): vedi img.
- Falsi positivi visibili: "traffic sign" su finestre/ponteggio (frame 6900: 3 cartelli a 14-16 m su facciata). Da portare al critico: la distanza e' giusta per quello che SAM 3 ha segmentato, ma la classe e' sbagliata.
- NMS fra classi (IoU>0.7 -> 1 etichetta) ed esclusione disparita' invalida (n_valid<150).

## File (locali, MAI su git) in `training/depth/out_20261109/`
- `fuso_clip.mp4` 3 min (frame 4500-7200, 15 fps, SAM3 ogni 3 frame = 5 Hz, etichette tenute fra una passata e l'altra) — **video principale**
- `fuso_giro.mp4` giro intero in movimento (frame 1800-10066, SAM3 2.5 Hz; i primi 1800 frame sono soste di calibrazione e non inclusi)
- `objects_clip.csv`, `objects_giro.csv` (classe, conf, box, Z, Z_p25/p75, n_valid), `mov_clip.json`, `mov_giro.json`, `banco_sgbm.json`
- script: `training/depth/depth_seg_001.py` (run / banco), `training/depth/analisi_movimento_001.py`
- fotogrammi: `agents/rapporti/img/depth_seg_001_clip_{600,1700,2400}.jpg`

## Per il critico
Guarda: (1) frame ~1700 clip: auto 5.4/7.9 m a destra, 17.7-28 m a sinistra, plausibili? (2) frame 2400: cancello 13.8 m e falsi cartelli; (3) manca qualche ostacolo? SAM 3 perde auto bianca a sx e cartelli reali in alcuni frame; persone lontane >30 m non etichettate. Il "senno di poi" (etichette da 1-3 m riportate indietro) NON e' ancora fatto: qui solo la coerenza con l'odometria.
