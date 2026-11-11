# Depth: Microduck / Pollen Robotics e famiglia (2026-11-09)

Metodo: clonati in sola lettura (nessuno script eseguito) pollen-robotics/microduck (da034a22 -> hash da34a22... vedi sotto), apirrone/Open_Duck_Mini (b23317a), apirrone/Open_Duck_Mini_Runtime (376de65), pollen-robotics/reachy_mini (25756e7), pollen-robotics/reachy2-sdk (eb42d1f). Microduck = commit da34a22 (`git log -1`, "da34a22").
Base: https://github.com/pollen-robotics/microduck

## 1. Risposta breve
- Microduck NON stima la profondita' degli oggetti dalla camera. Ha 1 camera RGB (IMX219 sulla alpha, GC2093 sulla beta) usata per streaming WebRTC e per un detector (altri Microduck, palla, animali). La distanza viene da un sensore ToF separato VL53L8CX (matrice 8x8), non dalla camera.
- La camera ha solo le INTRINSECHE (fx, fy, cx, cy). Servono per trasformare pixel in direzione (SLAM monoculare ecc.). Nessuna stima metrica monoculare appresa trovata.
- Le policy di camminata sono cieche (IMU + giunti), addestrate in sim (microduck_rl, non letto da me).
- Reachy 2: depth da camera RGB-D torso (Orbbec Gemini 336 secondo datasheet Pollen), teleop con stereo proprio (OAK FFC-4P, 2 IMX296 fisheye) calibrato con ChArUco + multical e scritto in EEPROM della camera.
- Per Asmile: di Pollen si copia il PROCESSO di calibrazione (ChArUco -> file -> EEPROM/per-unita' -> check epilinee), non la depth. Niente di quello che fanno e' una soluzione a depth metrica a 15-25 km/h.

## 2. Microduck: fatti con riga
1. Camera/ToF nell'architettura: `docs/design/architecture.md` righe 49, 89-90, 173: `mediad` = camera/audio/percezione; `tofd` = "the head's 8x8 depth matrix", "Nothing in the control loop reads depth".
2. ToF: `tof/Cargo.toml` riga 1: "an 8x8 depth matrix from a VL53L8CX". Uso: theremin (`docs/design/robotd-design.md` riga 1029), evitamento ostacoli (`docs/ideas/autonomous_behavior.md`, "ToF obstacle avoidance"). E' un sensore laser dedicato: costo e portata da bici NON verificati (portata VL53L8CX non letta da fonte primaria qui -> NON VERIFICATO).
3. Detector: `duck-detect/src/lib.rs` righe 1-5: modello 1 classe, 320x320, INT8 .rknn su NPU (Radxa Zero 3, RK3566 - `docs/faq.md` riga 8). Output = bounding box, nessuna distanza.
4. Intrinseche: `mediad/src/camera.rs` righe 1-30: derivate dal campo visivo (IMX219 ~62 gradi, fx ~1065 a 1280 px: `fx=(W/2)/tan(62/2)`); punto principale assunto centrale, "the part a real calibration corrects (the measured cy sits ~110 px low)". Mode di sensore bloccata con `media-ctl`; se non confermata NON pubblica intrinseche ("numbers quietly wrong are worse").
5. `docs/design/remote-webrtc.md` righe 516-540: "Without [intrinsics] a monocular reconstruction is scale-free"; flag `calibrated`: false = dati di progetto "good to a few percent"; true = misurata (per robot in `[media.intrinsics]`, o "family solve" per tutta la famiglia, perche' camera e lente sono lo stesso pezzo).
6. `docs/design/remote-access-design.md` riga 1163: calibrazione per-unita' NON fatta in produzione: "Measuring one robot and writing [media.intrinsics] closes it for that robot; a per-unit calibration in provisioning closes it for the family". Quindi Pollen stessa usa UNA calibrazione di famiglia + default di progetto, e ammette che per metrologia non basta.
7. Beta: `mediad/src/camera.rs` ~riga 367-374: GC2093 ~85 gradi, fx ~696 a 1280x720, "family solve" unita' sky-gtc 2026-10-28.
8. Tool usato per la family solve: NON TROVATO nel repo (nessun ChArUco/calibrateCamera nel repo microduck; ricerca grep vuota). NON VERIFICATO come l'hanno fatta.
9. Montaggio: nessuna calibrazione di estrinseche camera-corpo trovata; si usa la cinematica della testa (`docs/design/architecture.md` ~riga 187: riproiezione via head FK da `robot.state`).
10. Open Duck Mini (apirrone): `Open_Duck_Mini_Runtime/.../camera.py` righe 1-20: picamzero, cattura, resize 512x512, base64. Solo immagine, zero depth, zero calibrazione.

Risposta alla tua domanda "ha una sola cam": si', una camera. E non misura la distanza con essa.

## 3. Reachy Mini
- `reachy_mini/src/reachy_mini/tools/camera_calibration/README.md`: ChArUco DICT_4X4_1000, 11x8, quadrato 20.75 mm; 20-30 immagini a 3840x2592 variando distanza/angolo; modello di distorsione razionale; errore di riproiezione "< 0.5 px"; `scale_calibration.py` ricalcola per altre risoluzioni (crop ~11%).
- `reachy_mini.py` righe 776-822: `look_at_image` usa camera.K e D (intrinseche+distorsione) per girare la testa verso un pixel. Nessuna depth.
- Calibra: per la camera singola, ChArUco, tool nel repo, riusabile con OpenCV.

## 4. Reachy 2
- SDK `reachy2-sdk/src/reachy2_sdk/media/camera.py` righe 3-4, 122-148, 216-240: due camere: TELEOP (testa, stereo RGB) e DEPTH (RGB-D torso fissa). `get_parameters` da' intrinseche/distorsione, `get_extrinsics`, `get_depth_frame` ritorna uint16 + timestamp. La depth e' calcolata DALLA CAMERA/hardware e servita via gRPC; l'SDK non calcola nulla.
- Hardware (non nel repo): datasheet Pollen single-arm https://pollen-robotics.com/wp-content/uploads/2025/02/Reachy2-Single-Arm-mobile-Datasheet.pdf : torso "Orbbec Gemini 336", portata 0.26-3 m, FoV H90 V65, precisione <1.5%. Il datasheet dual-arm indica cifre diverse (640x480@45, <1%): incoerenza non risolta. Guida: https://docs.pollen-robotics.com/hardware-guide/specifications/vision/ (conferma RGB-D fisso nel torso senza nome del modello).
- Teleop stereo: Luxonis OAK FFC-4P, 2 IMX296, fisheye, baseline 64 mm: https://discuss.luxonis.com/d/6709-pollen-luxonis-modular-stereo-vision-for-low-latency-robot-teleoperation (fonte di terzi/forum, parziale).
- Calibrazione stereo (doc ufficiale): https://docs.pollen-robotics.com/help/faq/teleoperation-faq/ : fork `multical` + `pollen-vision`, ChArUco stampato A4 (nel packaging del robot), ~30 coppie, `multical calibrate` con flag fisheye -> `calibration.json`, `flash.py` scrive in EEPROM della camera (con backup, `restore_calibration_backup.py`), verifica `check_epilines.py`: score pendenza <0.1% accettabile, <0.05% ideale. La calibrazione e' di RICALIBRAZIONE su disallineamento, a cura dell'utente. Calibrazione di fabbrica: NON VERIFICATO (non descritta).
- Nota: la depth e' ~3 m max, robot fermo/lento. Orbbec Gemini 336 e' sensore commerciale pre-calibrato in fabbrica (calibrazione Orbbec: non letta, NON VERIFICATO).

## 5. Trasferibile ad Asmile / non trasferibile
Trasferibile (processo):
- Una calibrazione intrinseca per MODELLO di camera+lente ("family solve") + default da campo visivo, con flag `calibrated`, e rifiuto di pubblicare numeri se la modalita' sensore non e' confermata. Per la flotta: bloccare mode sensore, versionare le intrinseche per modello lente (OV9281 Inno-Maker #001 e' un set, Camarray del logger un altro: mai mischiare).
- Calibrazione stereo fisheye con ChArUco, ~30 coppie, check delle epilinee con soglia numerica (0.1% / 0.05% di pendenza) e scrittura del risultato nel dispositivo: criterio di accettazione automatico utile per i 15.000 pezzi. Copiabile come test di fine linea: il nostro validate.py puo' adottare la stessa soglia (da provare).
- Intrinseche-solo + calibrazione per unita' da fare in stazione di fabbrica, non a mano col metro.
Non trasferibile:
- Depth: Microduck non la fa dalla camera; usa ToF 8x8 corto raggio. Per ostacoli a 15-25 km/h (serve decine di metri) un ToF da giocattolo non basta.
- Reachy 2 depth <=3 m: fuori scala per una bici (frenata a 20 km/h ~ 10+ m).
- Monoculare appreso: Pollen non lo fa; quindi nessuna prova da loro che funzioni metrica. Per Asmile lo stereo con baseline nota 200 mm resta la scala metrica gratis.
- Camere RGB-D/Orbbec: costo/uso esterno non valutati; NON VERIFICATO sulla luce solare all'aperto.
- Microduck e' robot lento in casa, policy cieche: il paragone vale solo per l'ingegneria software (daemon, calibrazione di famiglia), non per la percezione.

## 6. Proposta (cosa provare, costo, prova attesa)
1. Introdurre `calib_family_<modello>.json` (intrinseche) + `calib_unit_<id>.json` (estrinseche stereo), flag `calibrated` e rifiuto se mode camera non confermata. Costo: mezza giornata di codice, nessun hardware. Prova: caricare su #001 e logger, fallire correttamente se si scambiano.
2. Aggiungere il test epilinee (pendenza media % sul ChArUco) come gate di accettazione, soglia 0.1%. Costo: ~1 ora, usa le immagini ChArUco gia' fatte (calib_001_20261109). Prova: il valore su #001 sotto soglia, e peggiora volutamente spostando una camera.
3. NON copiare Microduck per la depth: tenere stereo (SGBM/teacher) come lavoro del fronte stereo.

## 7. NON VERIFICATO
- Come Pollen ha fatto la family solve della camera Microduck (tool non nel repo).
- microduck_rl: non letto; l'affermazione "policy cieche" si basa su robotd-design.md riga ~11 (policy alpha_*) e sul fatto che il crate `robotd` non legge camera/depth (architecture.md riga 181); non ho aperto le osservazioni della policy.
- Calibrazione di fabbrica Reachy 2 e dell'Orbbec; modello preciso della camera torso (datasheet incoerenti).
- Portata/costo VL53L8CX, non cercato.
- Nessuna ricerca su LeRobot/HF oltre i repo sopra (depth/calibrazione camere non esaminate).

## Fonti
- https://github.com/pollen-robotics/microduck (da34a22)
- https://github.com/apirrone/Open_Duck_Mini_Runtime (376de65), https://github.com/apirrone/Open_Duck_Mini (b23317a)
- https://github.com/pollen-robotics/reachy_mini (25756e7)
- https://github.com/pollen-robotics/reachy2-sdk (eb42d1f)
- https://docs.pollen-robotics.com/help/faq/teleoperation-faq/
- https://docs.pollen-robotics.com/hardware-guide/specifications/vision/
- https://pollen-robotics.com/wp-content/uploads/2025/02/Reachy2-Single-Arm-mobile-Datasheet.pdf
- https://discuss.luxonis.com/d/6709-pollen-luxonis-modular-stereo-vision-for-low-latency-robot-teleoperation
