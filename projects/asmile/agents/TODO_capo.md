# TODO del capo — agenti fermati e passi successivi
Aggiornato 2026-11-10 sera. Daniele ha fermato gli agenti: domattina gira la 2ª ripresa di calibrazione di #001.
Ripresa: tutti gli agenti riprendono da qui.

## Agenti fermati (cosa stavano facendo)
- **asmile-calib-critico** su strumento `logger/depth/calib_charuco_dual.py` (commit 783769c2, md5 0481cfa6…)
  - Era a metà: rifaceva la regressione sui corner veri in `agents/prove/calib_critico_783769c2/` (regr.py, regr_nodrop.py). Nessun verdetto.
  - Da giudicare: (1) `sync_3pct` allentato (colore non vincolato); (2) scarto PnP mai nel blocco GATE;
    (3) regola "<12 corner" toglie le viste di bordo e falsa la copertura?; (4) regressione 001_180306 riproduce ROSSO
    (mono 0.567/0.550, stereo 0.573, |T| 197.1).
  - Ripartire: stesso brief, max 2 processi di fit.
- **asmile-calib**: lavoro chiuso (strumento + regressione 16/16, commit 783769c2), palla aperta presso il critico.
- **calib_rock** (mock OV9281 + autocal): in pausa a 15/19, riparte dopo L1.rettifica PASSA → fedelta.py sui corner veri → `run_all.py --produzione`.
- Percezione (ostacoli senza nome, L1.classi v2): ferme in attesa delle risposte di Daniele (sotto).

## Domattina (Daniele) — 2ª ripresa #001
Istruzioni date in chat il 2026-11-10: griglia 3x3 a 1,2 m e 0,8 m, inclinazioni, soste centro 1/2/5/10 m + lati 2 e 5 m.
- Prima: accendere #001 → io deployo `pi/camera/dual_cam_recorder.py --calib` (6 Mbps, commit a856e313, ha il "vai") con `deploy/registra_deploy.sh`.
- Se #001 non è raggiungibile: si registra a 500k (RMS mono resterà ~0.55 → gate 0.5 a rischio).

## Passi dopo la ripresa (in ordine)
1. Scaricare la ripresa, girare `calib_charuco_dual.py` (strumento corretto) → candidato, banco fisso con le soste.
2. Critico (asmile-calib-critico) → PASSA/VETO. Se PASSA: L1.rettifica verde, calib in uso su #001.
3. Calibro sulla distanza fra le camere (|T| stimato 197.3 mm, −1.3%).
4. Logger001: stessa procedura (Camarray SBS, altre altezze/inclinazione: misurarle prima, poi posizioni).
5. Depth: maestro sui video rettificati con la calib nuova, gate depth per zona (centro ≤2% fino a 5 m, ≤3% a 10 m; bordi ≤3% 2-5 m).
6. Mock OV9281 adattivo + autocal (calib_rock) sui corner veri → produzione.
7. Azionamenti in base alle distanze: freno sulla visione (TTC) dopo il freno calibrato con l'encoder ruota; poi sterzo.
   (L'altra sessione fa sterzo/VESC di #001: non toccare UART, VESC, sterzo, freno.)

## Decisioni che aspettano Daniele
- dy p95 calcolato sulle medie per vista (rumore dei corner rende D012 incoerente sul singolo punto).
- RMS mono al limite (0.5) se il dato resta h264.
- Ostacoli senza nome: opzioni A/B/C/D (consigliata D: filtro muri su giri nuovi).
- 3 casi cancelli: portone con grata, paletti con catena e ringhiera, porta scura.
- calib_rock: A mai VERDE senza banco fisso; rifacimenti a scala 2.
