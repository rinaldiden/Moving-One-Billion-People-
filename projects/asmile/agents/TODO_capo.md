# TODO del capo — agenti fermati e passi successivi
Aggiornato 2026-11-10 sera. Daniele ha fermato gli agenti: domattina gira la 2ª ripresa di calibrazione di #001.
Ripresa: tutti gli agenti riprendono da qui.

## 2026-11-11 tardo pomeriggio — MOTORE STERZO
- Motore 6354 montato sospetto guasto (R 29.0→23.5 mOhm, L 19.5→17 uH, flux FOC 2.3 mWb, frena a mano, puzza). Daniele monta il GEMELLO del banco sul VESC #001.
- Poi: calibrazione FOC completa A MOTORE LIBERO (prima di accoppiarlo alla riduzione): R, L, flux openloop, hall detect, guadagni corrente, observer. Scrivere solo col vai.
- TETTO CORRENTE: max 80 A per al massimo 5 s (Daniele). VESC l_current_max 80 + limite tempo nello script.
- Motore nuovo CALIBRATO e scritto (18:25): R 29.5 mOhm, L 19.5 uH, flux 4.918 mWb (openloop undriven = metodo VESC Tool), kp/ki/observer ricalcolati, hall rifatti, ±80 A.
- PRIMA di muovere: RIFARE ZERI encoder sterzo (Daniele l'ha smontato): centro, finecorsa veri, limiti in /data/steering_limits_asmile-001.json.
- Poi: script fluido di ieri (approvato_0911/sterzo_fluido_001_ieri_be80a131.py) e confronto col 09/11.
- Sensore suggerito sull'albero motore: AS5047P sulla porta encoder del VESC (fluidità a bassa velocità).
- Riduzione 1:20 ORDINATA (oggi 1:5): rifare fattori (count/giro el., ERPM per deg/s) quando arriva.
- Alternativa futura: CubeMars AK80-8 (agents/rapporti/motore_sterzo_ricerca_20261111.md).
- Registro prove 11/11: agents/prove/sterzo_001/REGISTRO_20261111.md.

## 2026-11-11 sera — PROSSIMA SESSIONE STERZO #001 (Daniele: "lo script di ieri girava perfetto fluido, rifare con quello, uno step alla volta")
- STATO VESC #001 (da verificare all'accensione): l_current ±70 A; foc_hall_interp_erpm = 100 (il ripristino a 500 NON è riuscito: Pi già spento). Backup: fleet/001/vesc_backup/ (500 = vesc_mcconf_backup_20261111_110926.bin).
- CORRETTO da Daniele (11/11 sera): il run FLUIDO era con foc_hall_interp_erpm = 20, NON 500. L'ho portato a 500 il 10/11 18:05 (commit 70fa844f) pensando di recuperare coppia: coppia invariata e da lì non è più fluido.
- Step 1: riportare foc_hall_interp_erpm a 20 (backup con 20 = vesc_mcconf_backup_20261110_180449.bin, fatto prima di scrivere 500), poi rifare IDENTICO lo sterzo APPROVATO del 09/11 17:37 (commit 3ba1edd2 "così è perfetto": sterzo_fluido_001 400 Hz, KD 0.6, kp 3, 15 deg/s; poi a3a72c6b default 20 deg/s, variazione 6-8%) e confrontare coi log agents/prove/sterzo_001/sterzo_fluido_vai_20261109_17*. Solo se identico: un cambiamento alla volta (la forza: corrente, non hall).
- Fatti misurati oggi: verso DX oscillazione 10-12% (= ieri), verso SX 27-46% con 2 picchi per giro elettrico (fase-locked, non meccanica, non interp). Ruota a terra: attrito 9-13 A, stallo a 70 A fra -26 e -9 gradi una volta; ruota sollevata 3-4 A.
- Gli script dello sterzo su #001 stanno in /tmp/steering (overlay: spariscono al riavvio) -> ricopiare dal repo.
- tach_encoder_map.py: confronto tach/encoder 1.4-1.7 gradi (4.3 in stallo); fallback non ancora collegato allo sterzo (TODO: soglie, avviso a chi guida/server).
- Servizio servofreno: acceso e enabled contro la regola; non comanda GPIO12. Daniele: "riprendiamo da zero il freno service" -> proporre disable.

## Calibrazione / mock
- #001: calib PROVVISORIA = B30 senza correzione (Daniele OK: borsa 0.88/0.90, muro 5.11/5.10). È la base per depth -> freno/sterzo.
- Mock (calib_rock) in corso con asmile-calib; poi critico; poi pagina artifact per Daniele (verde/rosso, gemello vs vero, autocal prima/dopo, video guida simulata).
- Logger001: PDF pronto agents/protocolli/protocollo_calib_logger001.pdf (darlo quando Daniele è pronto; ricalcolare altezze con altezza/pitch misurati).
- Dopo il mock: depth sui video in movimento (session_20261109_094146) con la calib B30.

## 2026-11-11 mattina
- 2ª ripresa #001 FATTA (6 Mbps): session_20261111_082437 / 083054 / 083632 scaricate e complete (L=R frame). Distanze soste NOMINALI da confermare.
- asmile-calib in corso sul candidato definitivo → poi asmile-calib-critico → se PASSA: promuovere calib_asmile-001.json + registra_deploy, poi mock (calib_rock: fedelta.py sui corner veri → run_all.py --produzione).
- Poi logger001: servono altezza camere da terra e inclinazione per dare i punti.
- VESC #001: vedi agents/rapporti/vesc_001_banco_motore_prova_20261111.md (flux config 4x sbagliato; resta da capire la coppia).

## Agenti fermati la sera del 10/11 (cosa stavano facendo)
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
