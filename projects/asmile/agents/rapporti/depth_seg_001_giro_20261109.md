# depth + segmentazione #001, giro 2026-11-09 — RAPPORTO v2 (dopo VETO 1/3 di asmile-occhio)
Solo #001. Calib `calib_asmile-001.json` (PASSA asmile-calib-critico). v1 sotto, in fondo, invariata ma SUPERATA nella parte "in moto".

## Risposta al veto
**1) Odometria SENZA filtro su Z, non circolare.** v1 sbagliava: associava le maschere SAM fra passate (IoU + filtro |Z-Zpred|) e decideva "fermo" dalla pendenza.
Ora: oggetti compatti scelti SOLO per classe/conf/posizione (palo, bollard, cestino); SAM 3 al frame di partenza, poi la maschera e' SEGUITA
frame per frame (15 fps) con KLT + similitudine (nessun uso di Z o encoder per seguire); per ogni frame SGBM rettificato + stessa misura Z della pipeline.
Z contro S (metri encoder ruota), componente lungo l'asse OTTICO, atteso cos(7.4°)=0.992 (pitch gestito). Script `training/depth/odometria_klt_001.py`.
- Giro intero, 40 oggetti avviati, **25 tracce utili (10 pali, 9 bollard, 6 cestini; ≥8 punti, ≥3 m percorsi; max 18 m)**. Nessuna esclusa nel conteggio sotto "TUTTE".
- **Pendenza ΔZ_stereo/Δs_encoder (Theil-Sen): mediana 1.007 (p25-p75 0.88-1.07)** su 25 tracce; 1.044 (0.98-1.10) sulle 21 con rms<3 m. Atteso 0.992.
  Tracce pulite: bollard f7674 pend 1.04 rms 0.05 m; bollard f6270 1.07 rms 0.14 m; bollard f9162 1.01 rms 0.14 m; palo f7434 0.98 rms 0.25 m; cestino f1806 1.16 rms 0.57 m (S 15.8 m, Z 24->6.3).
  4 tracce con rms 4-6 m (pali f2922, f6018, f6402; bollard f8724): il tracker KLT ha perso l'oggetto (maschera scivolata sullo sfondo / oggetto a <2 m); le tengo in "TUTTE".
- **Causa delle pendenze 0.27-0.34 del critico**: NON encoder ne' scala ne' pitch. Era l'associazione IoU fra passate SAM 3 su oggetti estesi/in fila
  (fence/gate/barrier, bollard allineati: la traccia salta da un elemento all'altro, Z cresce) + mediana su oggetto esteso che cambia con l'angolo.
  Con tracking continuo le stesse classi danno pendenza ~1 (vedi sopra). Controllo "estesi" (fence/gate/barrier, KLT, 5 tracce, 1 gate Z 21.9->2.9 m): TS mediana 0.99 (0.81-1.15); 1 su 5 fallita (persi punti, rms 5 m); le 3 barrier f6285-6318 sono lo stesso oggetto.
- Errore % per fascia di Z predetto (retta a pendenza fissa 0.992, A pesata 1/Z², TUTTE le tracce / senza i 4 tracker persi):
  | fascia | TUTTE (n punti) | senza 4 persi | obiettivo |
  |---|---|---|---|
  | <5 m | MAE 132%, bias +73% (37) | MAE 27.6%, bias +18% (14) | ±2% **NON VERIFICATO / non raggiunto** |
  | 5-10 m | MAE 29%, bias -0.9% (261) | MAE 6.5%, p90 15.7% (190) | ±5% **NON raggiunto** |
  | 10-20 m | MAE 10.1%, bias +1.9% (567) | MAE 5.4%, p90 12.4% (475) | ±10% ok sul MAE (p90 12-17%) |
  | 20-30 m | MAE 5.9% (159) | MAE 6.1% (135) | - |
  | bordi: centro <200 px / 200-400 / >400 | 4.5% / 27% / 25% | 4.2% / 5.5% / 11.8% | - |
  Il "3.9% a 5-10 m e 2.6% a 10-20 m" della v1 e' RITIRATO (filtro circolare). Numeri onesti: ~5-6% sotto 20 m al centro-medio, ~12% ai bordi, <5 m inaffidabile in moto
  (oggetti che escono dal frame con maschera tagliata + tracker che scivola quando l'oggetto cresce: non posso separare errore del tracker da errore stereo).
  La scala complessiva stereo-vs-encoder pero' torna (pendenza ~1.0-1.04): non c'e' un errore sistematico grosso di scala o di odometria.
- Banco fisso (a) invariato: |err| ≤1.2% fino a 12 m, 15 m -2.8% (`banco_sgbm.json`).

**2) Oggetti estesi: punto piu' vicino.** `fence, gate, barrier, bench`: disparita' percentile 85 (Z basso) invece della mediana (`coherent_disp`, `depth_seg_001.py`). Validato solo con le 5 tracce KLT sopra.
**3) Strato "ostacolo senza classe"** dalla disparita' densa (`obstacles()`): piano strada con pendenza nota dalla geometria (h cam 0.825 m, pitch 7.4°; solo l'orizzonte vh si stima, moda per frame),
altezza sopra strada y = h(d-d_g)/d ≥ 0.25 m, |X|≤3 m, Z 2-15 m, base a terra (esclude cornicioni), nuvola coerente in Z, non gia' coperta da maschere SAM. Magenta nel video, "ostacolo (senza classe)".
Clip v2: 909 rilevazioni "ostacolo" in 430 passate su 900. **Non trova ancora** botte/vasi/fioriere di frame 4600 (a destra, X≈2-3 m, disparita' al bordo non affidabile) -> NON risolto; l'auto davanti (9.7 m) la trova ma e' gia' coperta da SAM. Possibili falsi positivi (es. "2.6 m" a frame 5900: gradino/bordo?) non classificati: a te la lente.
**4) Maschere con sfondo**: Z = MODA dell'istogramma della disparita' (log) + mediana entro ±10%, maschera erosa 2 px (`coherent_disp`). Auto gialla (clip idx 1400): 4.7 m (v1 4.9 m); la maschera SAM include ancora l'edificio di sfondo ma la distanza no. Rimane da fare: tagliare la maschera anche graficamente.

## Da Daniele (non mi blocco)
- Banco <5 m fuori centro e ritaratura dei bordi: serve un video col metro (tabellone a 1-5 m a sinistra/destra del frame, non solo al centro). Servono anche soste a 15-20 m per stringere l'errore lontano.
- Con quel video si puo' anche tarare il dy ai bordi (oggi 2-5 px) e rifare i 6.8-12% ai bordi.

## File v2 (locali)
`training/depth/out_20261109/fuso_clip.mp4` (RIFATTO con punti 2-4; v1 in `v1/`), `odo_klt_giro.json`, `odo_klt_estesi.json`, `objects_clip.csv` (nuovo, include "ostacolo"),
`fuso_giro.mp4`/`objects_giro.csv` = v1 (non rigirati: 55 min; stesse misure Z con mediana, non con moda/percentile). Script: `odometria_klt_001.py`, `analisi_movimento_v2_001.py` (IoU-only, per riprodurre il veto), `depth_seg_001.py`.
Fotogrammi: `agents/rapporti/img/depth_seg_001_v2_clip_{100,1400,1700,2400}.jpg`.

---------------- v1 (2026-11-09 mattina), invariata sotto ----------------

## v1
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
