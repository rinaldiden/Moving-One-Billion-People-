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

## 2026-11-13 notte — fermato da Daniele (scelta B)
- Depth+seg sui video #001: FERMO. Riferimento = v10 (out_20261112_v10). v11/v12 non adottati: v12 VETO 3/3 (STERZA verso lato non misurato). Alla ripartenza: lato libero solo se MISURATO (brief sbagliato in agents/brief/brief_asmile-depth_v12_20261112.md), sbarra in avvicinamento, barile 3173.
- Correggere la frase ambigua in config/soglie_attuazione_001.json "azioni" ("o sterza se c'è spazio libero") → "solo se il lato è misurato libero".
- Soglie dalle guide: PROPOSTA in config/soglie_attuazione_001.PROPOSTA_guide.json (PASSA parziale), da validare Daniele; serve giro con limiter spento, ≥5 stop a 10/15/20 km/h, col vai.
- Encoder ruota: proposta 0.3477 (PASSA parziale), deploy solo col vai + D011; servono 2ª spinta 10 giri, giro >20 km/h, frenate decise.
- Sterzo #001: script con finecorsa dalla calib nuova pronto (b43c1981, sicurezza ALLOW condizionato), in attesa che #001 sia acceso per gli zeri.
- Registrazione: proposta 4-6 Mbps per camera (non toccato il Pi).
- 3 casi dubbi SAM 3 pronti in training/perception_pipeline/casi_dubbi/ (non spediti).
- Registro guide (agents/registro_guide/): #001 2 sessioni (15 frenate usabili per soglie), logger001 2 giri importati qualità bassa (segno IMU non verificato, 0 usabili; PASSA parziale scettico). Sblocco logger: ruota BLE accesa in guida (modifica sul Pi del logger, solo col vai).
- PROSSIMO con Daniele: tuning servosterzo (zeri encoder, script b43c1981) e servofreno su #001 acceso.

## 2026-11-13 — LUCE BASSA / CONTROSOLE sulle camere di #001 (problema aperto)
- Giri 13/11 15:03 e 15:14: col sole basso davanti l'immagine si sbianca e il contrasto crolla (flare, raggi, macchia chiara in basso a sx: sporco o riflesso sulla lente). Fotogrammi con >20% saturato: 5/193 e 5/193 (giro 1), 21/206 sx e 7/206 dx (giro 2). Esposizione già ~0.1 ms: il problema è la luce diretta nell'obiettivo. Sole alle spalle: ok.
- Rimedi in ordine: 1) paraluce stampato 3D sulle due camere; 2) pulizia lenti; 3) esposizione misurata sulla strada (metering/ROI basso) nel registratore — modifica sul Pi solo col vai di Daniele.
- Stesso tema per il logger (Camarray) da verificare.

## 2026-11-13 sera — RIPRENDERE DA QUI (Daniele spegne #001)
- STERZO #001: zeri nuovi (centro 4112, sx 2028, dx 6168; /data/steering_limits_asmile-001.json + fleet/001/data). Script = approvato_0911/sterzo_fluido_001_ieri_zeri.py (finecorsa dalla calib, tolleranze ruota, t_ms CLOCK_MONOTONIC nei log, stop al tetto di corrente 0.5 s, anti-strappo, stop duro 45 deg/s, controllo "bici in movimento" SPENTO). Ultimo risultato: 10 giri ±35° a 20 deg/s, 20/20 arrivati, osc 10-12%, 8-11 A, motore 17 °C. Con Daniele seduto da fermo: 30 A stallo, 45-60 A a strappi (36 A medi) → servono riduzione 1:20 (ordinata) o sterzo in movimento. Asimmetria DX>SX di attrito da capire. Prossimo: Daniele trattiene il manubrio a 80 A per sentire la forza con l'anti-strappo; poi encoder AS5047P sul motore (lista pezzi + cablaggio per piedino) e rilevamento hall col motore montato (scrive mcconf: serve vai). Script "campo" (open-loop) accantonato: a 12 A perde il passo.
- Gli script dello sterzo stanno in /tmp/steering sul Pi (overlay): al riavvio vanno ricopiati dal repo (approvato_0911/ + pi/steering/safety_001.py, vesc_return_to_center_duty.py).
- FRENO #001: pilotare SOLO col metodo asmile2 (/tmp/freno_asmile2.py = classe Servo di autonomous/speed_limiter.py) + pin davvero in ingresso a fine movimento (pinctrl set 12 ip pn: su Pi 5 gpio_free lascia OUTPUT LOW). Corrente di tenuta a pin libero: 60° 175 mA, 70° 320 mA, 80° ~0.6 A (il servo tiene da solo contro l'olio). Servizio del freno da RIFARE DA ZERO (servofreno enabled contro la regola, speed_limiter disabled). Stazionamento (master su 0) a corrente zero = togliere i 6 V al servo (EN Pololu su GPIO) + verificare che il freno resti chiuso.
- ANTI-IMPUNTATA: regola ferrea scritta; proposta soglie in config/soglie_attuazione_001.PROPOSTA_anti_impuntata.json (PASSA parziale: n=2, contraddice "rilascio al solo sollevamento"; fuori campione 1/min) → misurare latenza servo a banco, giro in ombra 30 min con etichette.
- STANOTTE: depth+seg sui giri 13/11 (asmile-depth → asmile-occhio) in corso.
- CORRIDOIO: pi/autonomous/corridoio.py pronto per shadow mode (PASSA parziale), da provare col primo giro con gli zeri nuovi + costo su Pi + deploy dopo asmile-sicurezza.
- LOGGER: download sistemato (niente sovrascritture fra boot, hook staccato); elaborazione in PAUSA (asmile-loggers/.pausa_elaborazione) fino alla calib camere del logger (servono altezza lenti e inclinazione). Recorder del logger riscrive i nomi a ogni boot (orologio): fix nomi sul Pi solo col vai. Schema HW v2 in logger/hw_v2/README.md (4 punti rossi).
- NOTTE 13→14/11 depth giri 13/11: v2 (FRENA 174→28, Z<1 m 0, NON MISURATO grigio) e v3 (modo v14: conferma 3 fotogrammi sui salti Z, STERZA solo verso lato misurato, NON MISURATO 446→300) → asmile-occhio PASSA parziale (0 ostacoli veri persi su 4 sospetti). Restano: tetto alla conferma lunga (traccia 50 fotogrammi), furgone liscio non classificato (094146 f2400/f5961/f5976), flicker f2383, f1037, ritardo RALLENTA 1.1 s sul monovolume → proposta ttc_avviso 4 s DA VALIDARE Daniele; proposta RALLENTA in NON MISURATO DA VALIDARE Daniele. Rapporti agents/rapporti/depth_seg_giri_20261113_v2.md / _v3.md, video training/depth/out_20261113_giri_v3/.

## 2026-11-14 — SEPARAZIONE ONLINE/OFFLINE + WATCHDOG INTEGRITÀ (domanda di Daniele, verificato: NON esiste ancora)
Stato vero su #001: una sola rootfs (p2) in overlay read-only + /data (p3) scrivibile; Tailscale/wifi attivi sempre; root via ssh può `remount,rw` → oggi chi è "online" può cambiare il codice di guida. Nessun controllo hash a runtime (fleet/001/codice_sul_pi.sha256 è solo una foto manuale, e differenze_dal_repo.txt mostra già file ≠ repo e speed_limiter "solo-Pi"). RAUC+cosign (deploy/rauc, ota_update.sh, verify_release.sh) è uno scheletro mai installato e il suo slot B = p3 = oggi /data → da riprogettare.
Da fare (in ordine, ognuno col suo contro-agente; ogni modifica al Pi solo col vai):
1. [ ] Decidere il confine: guida (percezione+attuazione) = processo/slot "offline"; rete/OTA/telemetria = lato "online". Proposta: modo DRIVE vs IDLE (systemd target): in DRIVE wifi+tailscale giù (rfkill) e OTA mascherata; online solo da fermo. (asmile-deploy + asmile-sicurezza)
2. [ ] Manifest firmato del codice di guida (sha256 di ogni file + modello ONNX, firmato cosign sul Mac). All'armo della guida un verificatore controlla hash+firma: se una riga cambia → guida NON parte, buzzer + Telegram. (asmile-deploy, contro: asmile-rollback-guardian)
3. [ ] Watchdog indipendente su ESP32 (fuori dal Pi): heartbeat dal Pi con hash del manifest + comandi; se heartbeat manca/hash diverso/comando oltre linee rosse → freno sicuro (≤60°) e taglio VESC. (asmile-sicurezza-redteam)
4. [ ] A/B vero: slot guida A/B su /data (dir + symlink, oppure rpi tryboot) con rollback all'ultimo noto-buono; rifare system.conf RAUC (p3 non è più libera). 
5. [ ] Chiudere la porta: niente sudo senza password per l'utente di rete, chiave ssh solo deploy, remount rw solo in IDLE.
Domande aperte per Daniele: Q-A) offline = rete spenta del tutto in guida, o solo "nessuno può scrivere"? Q-B) watchdog su ESP32 a bordo o secondo micro dedicato? Q-C) in futuro due schede separate (guida air-gapped + scheda rete) stile Tesla?
**→ Tutto il ragionamento su sicurezza e ridondanza è raccolto in `agents/sicurezza/ARCHITETTURA_SICUREZZA.md` (15/11): partire da lì per irrobustire.** Decisioni di Daniele (15/11): un solo firmatario (lui dal Mac, OTA solo in IDLE) per scheda di guida ed ESP32; l'ESP32 deve poter prendere il controllo di freno (e sterzo) per frenare in sicurezza; ridondanza = 2 schede dedicate con Asmile OS + ESP32 (non due Raspberry).

### 2026-11-15 — NOTA PER L'IRROBUSTIMENTO: l'ESP32 di sicurezza è indipendente solo se il Pi NON lo può riprogrammare (da Daniele, via Doppio)
Se l'ESP32 è collegato al Pi via USB o UART con EN e IO0 cablati, chi entra dalla rete nel Pi lo riflasha con esptool in pochi secondi e il guardiano non c'è più. Daniele chiede di scrivere nei 5 passi (passo 3, watchdog su ESP32) **tre cose**:
- [ ] **3a. Fra Pi ed ESP32 solo un filo dati** (UART TX/RX + massa), **senza linee di reset (EN) e boot (IO0)** e nessun USB del Pi sull'ESP32. Nessun piedino di strapping dell'ESP32 (IO0, IO2, IO12, IO15, EN) arriva al Pi. Il connettore di flash resta sull'ESP32, raggiungibile solo a mano da Daniele.
- [ ] **3b. Secure Boot v2 sull'ESP32, con la chiave sul Mac** (mai sul Pi). Serve un chip che lo supporti (ESP32 rev ≥ v3.0, oppure S3/C3): da verificare quale c'è a bordo. Insieme: download mode via UART disattivato o "secure download mode" (eFuse), JTAG spento, OTA via wifi tolta dal firmware di sicurezza.
- [ ] **3c. L'ESP32 ferma la bici da solo** — freno (posizione sicura ≤60°, regola anti-impuntata) **e taglio del motore** (alimentazione/EN VESC) — **se dal Pi non gli arriva più il battito**, senza chiedere niente al Pi.
**Buco già trovato nel repo (15/11):** l'ESP32 che abbiamo (`esp32/esp32_wifi/esp32_wifi.ino`) ha **ArduinoOTA via wifi con password in chiaro nel repo** (`esp32/flash_ota.sh`: "otabike", rete SpadaBike) → chiunque sulla stessa rete lo riflasha, peggio del cavo. Così com'è **non può fare da guardiano**: firmware di sicurezza nuovo, senza wifi/OTA, oppure micro dedicato (Q-B). Anche l'Arduino ponte encoder si flasha DAL Pi (`pi/steering/flash_encoder_arduino.sh`, /dev/ttyACM0): va bene finché è solo un sensore; regola generale proposta → **nessun micro con autorità su freno/motore deve essere flashabile dal Pi.**
Dettaglio e domande in `agents/sicurezza/ARCHITETTURA_SICUREZZA.md` §8. Ordine: passa da asmile-sicurezza → asmile-sicurezza-redteam; niente sul Pi né eFuse bruciati senza il vai di Daniele (gli eFuse sono IRREVERSIBILI).

## 2026-11-16 — LOGGER HW v2: prima accensione a banco (RIPRENDERE QUANDO DANIELE LO RIMONTA SULLA BICI, con calma)
- Fatto: circuito montato; 5 V dal buck solo col ponticello WAKE→3,3 V (atteso: IMU mai programmata, HOLD non configurato). Pi acceso, IMU MPU6050 0x68 risponde (WHO_AM_I 0x68). C2 (100 nF su A0) tolto per decisione di Daniele.
- GPIO26 alzato SOLO a mano (`pinctrl set 26 op dh`, sparisce al riavvio). Riga `dtoverlay=gpio-poweroff,gpiopin=26,active_low=1` NON ancora in config.txt.
- Prova movimento (`pi/sensors/imu_wake.py prova`, soglia 20 LSB, durata 40 ms): **MOT_INT mai scattato** anche con picchi di 578 mg; durante lo scossone l IMU si è **resettata** (registri a valori di accensione, I2C Remote I/O error) → falso contatto VCC/GND IMU, Daniele ha ricontrollato i fili ("fatto").
- Da fare al rimontaggio, una cosa alla volta e col vai: 1) prova con soglia minima (`prova 60 1`) e colpetti, poi tarare la soglia sulla bici; se non scatta nemmeno al minimo rivedere la programmazione MOT (DHPF/MOT_DETECT_CTRL); 2) riga gpio-poweroff in config.txt (root in overlay: scrivere in /boot/firmware) + `config/imu_wake.service` (sveglia al boot prima di sensor_hub, arma allo spegnimento); 3) riavvio SOLO quando lo dice Daniele, col ponticello (durante il riavvio HOLD scende per qualche secondo: senza ponticello/INT la corrente si stacca); 4) collaudo: togli ponticello → resta acceso; spegni → 5 V a zero; muovi → si riaccende; 5) sensor_hub era inactive su questo avvio: capire perché.
- Punto aperto di progetto: ogni riavvio (non spegnimento) del logger rischia di staccare la corrente → valutare condensatore su WAKE o pulsante di prima accensione nello schema.

## 2026-11-17 — logger: batteria e prossimi logger
- logger001: ogni giro di download (launchd 5 min) legge la batteria (ADS1115 A0, partitore 100k/33k). Sotto 10 V → Telegram a Daniele, ripete ogni 6 h finché non torna sopra 10,3 V. SOLO su logger001.
- logger001 resta così: niente condensatore/pulsante di prima accensione (se l'IMU perde alimentazione serve il ponticello WAKE→3V3).
- Prossimi logger (HW3 ESP32-P4): LED di stato all'accensione (colore = recording / batteria scarica / errore); ripensare la prima accensione senza ponticello.
- 2026-11-17 logger001: ritorno di corrente sul 3,3 V del Pi spento dal modulo ADS1115 → togliere le 2 pull-up 10k del modulo (SDA/SCL). Verifica: pin 1 a logger spento ≈ 0 V; poi rileggere IMU 0x68 + ADS 0x48. HW3: moduli sul bus I2C senza pull-up proprie se c'è un dispositivo sempre alimentato.
- 2026-11-17 logger001: 1117 del 3V3_SEMPRE dà 7,8 V (forse rotto). Sostituire (1117-3.3 con 1 kΩ di carico, oppure HT7533), verificare IMU WHO_AM_I + risveglio, poi rifare la prova di spegnimento (LED tutto spento) con ADS e soglia di stamattina.
- 2026-11-17 14:00 ✅ logger001 RISOLTO (Daniele): il 7,8 V era il condensatore sull'uscita del 1117. Daniele l'ha tolto e ha messo 1 kΩ in serie fra 3V3_SEMPRE e VCC dell'IMU → uscita 3,3 V, IMU ok (dati puliti, 0 errori I2C). Prova: spegnimento automatico PERFETTO (LED spento), al tocco riparte. Configurazione da tenere: soglia IMU di stamattina + hook del 16/11 + ADS senza pull-up SDA/SCL. Da riportare su schema/montaggio logger/hw_v2.
- 2026-11-17 logger001: CONFERMATO da Daniele: a logger spento il 1117 dà 6,7 V (senza 1 kΩ). Colpevole = 1117 senza carico minimo (o difettoso). Subito: 1 kΩ fra uscita e GND (se resta >4-5 V → rimettere 1 kΩ in serie all'IMU). Definitivo: sostituire con HT7533 (12,6 V in ingresso, Iq ~3 µA, nessun carico minimo); carrello solo su richiesta, niente acquisto senza ok.
- 2026-11-17 logger02 (HW3): TUTTO con timestamp sullo stesso orologio della A (frame A/B, IMU, batteria, CooSpo BLE ruota). Idea di Daniele: stimare la velocità dai pixel (stereo, baseline nota → metrica; + IMU = VIO) e togliere il BLE. Decisione: tenere il BLE come verità finché la velocità visiva non è misurata (< ~5% di errore anche con buio/asfalto liscio/folla); poi toglierlo dai logger successivi. Calcolo offline sul Mac. Esternamente logger02 = UN apparecchio: solo IP della A (.122) + Tailscale "logger02"; B dietro la A (proxy /b/...), wifi di B solo interno (video + OTA).
- 2026-11-17 [CODA logger02, da Daniele] usare la seconda porta MIPI (quella del display, DSI) per la seconda camera, così una sola scheda legge le due cam. VERIFICARE PRIMA: la P4 ha 1 solo ricevitore CSI (camera); la porta DSI è un trasmettitore (manda dati al display), quindi a firmware non può ricevere da una camera. Alternative da valutare: due camere sullo stesso CSI con un moltiplexer/aggregatore MIPI (tipo Arducam Camarray: SBS 2560×720 sul solo CSI, come il logger001) oppure restare a 2 schede (oggi sync camere 3 µs medi).

## 2026-11-17 sera — logger02: chiave Tailscale nel .bin (avviso GitHub) → D015
- Chiave esposta già morta (monouso, consumata; pannello: nessuna auth key valida, solo le 5 macchine note).
- Firmware nuovo (chiave in NVS, `/tskey`) compilato, NON caricato. Primo OTA: farlo IN CASA (se Tailscale non
  torna a chiave vuota, la A resta su 192.168.1.122 → `LOGGER02_HOST=192.168.1.122 bash logger02/ota.sh rollback`).
- Da firmare: `FIRMA=D015 bash logger02/purga_storia_bin.sh` (force push, solo commit 02e5b2a3) → poi rebase locale,
  avviso GitHub chiuso come «Revoked».

## 2026-11-18 mattina — logger02 (decisioni di Daniele)
- **Consumo misurato** (Daniele, banco 5 V): set completo in registrazione (A+B+2 cam+IMU) **0,45 A ≈ 2,3 W**. Deep sleep: DA MISURARE.
- **Batteria:** una Samsung 35E diretta + step-up 5 V con protezione nello stesso modulo (niente 3s2p). ≈4,5-5 h di registrazione a 2,3 W. Step-up ≥2 A (picchi wifi). Partitore da rifare 100k/100k (cella max 4,2 V) + firmware: sotto ~3,3 V chiude i file e dorme.
- **WIFI SOLO QUANDO SERVE (Daniele):** acceso solo a fine giornata per mandare i dati, oppure a bici ferma tornata alla base. In giro: wifi spento su A e B (C6 in reset) → meno consumo. DA FARE: come capire "base" (es. rete di casa visibile a bici ferma da X min) e "fine giornata"; streaming e OTA solo in quei momenti. Firmware: prima su logger02, flotta solo con ok di Daniele (regola ferrea).
- **Crash A (panic, riavvio 4)** due volte mentre scaricavo file della B attraverso il proxy /b della A → riprodurre con la A sul cavo USB e leggere il backtrace.
- **Sync camere** dopo l'aggancio: mediana 37 µs, p95 92, max ~140 (obiettivo ≤45 come #001) + 20% coppie con numero di fotogramma sfasato fra A e B → da sistemare.
- Fotogrammi bianchi (A 99/1020) RISOLTI: AE scrive solo se cambia + group hold 0x3208.
- 07:45 FUOCO: A e B a fuoco (nitidezza centro A 72, B 78; prima A 17). Luminosità giusta dopo aver spento la pipeline ISP Espressif (A 102, B 67, stessa esposizione). Camere ancora ruotate fra loro (~35°): al montaggio parallele + baseline col metro, poi registrazione ChArUco → `logger02/accoppia_stereo.py` → `calib_charuco.py --size 1280x720 --no-flip`.
- Crash A: log seriale della A attivo dal cavo USB (usbmodem1101; aprire la porta resetta la A). Crash visti solo con streaming/download dalla A.
- 07:45 CRASH A = esp_hosted SDIO streaming: buffer RX da 23 KB non allocabile (RAM interna frammentata) durante streaming/download dalla A. RX_MAX_SIZE rompe il wifi dopo ~60 s (provato, tornato indietro via USB). DA FARE: preallocare/riservare RAM interna DMA all'avvio o ridurre le allocazioni interne (JPEG, httpd, H.264) + guardia OTA che conferma solo dopo 5 min di rete con traffico vero.

## 2026-11-19 — CALIBRAZIONE CAMERE (con Daniele, con calma)
- Ripresa ChArUco col PDF che c'è già (logger/depth/board_charuco_A2_11x8_50mm.pdf o A3 10x7 38mm), logger001 che registra, 2 min: vicino/lontano, inclinato, tutti gli angoli.
- Poi: calib_charuco_dual.py → banco fisso → asmile-calib-critico. Partenza: candidato self 18/11 (dy fuori campione 1.14 px; calib 8/11 = 3.61 px, le camere si sono mosse).
- Daniele: «così l'abbiamo per hw3» → la calib di logger001 fa da base per logger02/HW3 col mock (stesse camere), baseline diversa dalle misure.
- Firmware HW3 definitivo: tag hw3-def-20261118 (rilasci/HW3_DEF_20261118, flasha_nuovo lo usa).

## 2026-11-23 sera — logger02 calibrazione IN PAUSA (Daniele)
- FERMO: Daniele fissa meglio il case (si muoveva tutto). Poi giro nuovo e test dy inizio/metà/fine: se resta <1 px senza salti → il dy 9,5 px (Rx -0,435°, salto 5 px a 330 s) era il case che si piegava sul supporto; altrimenti problema dentro il case (v6: camere sulla stessa piastra rigida).
- Candidato attuale: calib_logger02.CANDIDATO_v3_giro2_20261123.json (ARANCIO). Video 17:00/17:51 (1280×800) scaricati e pronti; cartella giro 14:06 completa in asmile-loggers/logger02 (giro2 era stata montata con download incompleto).
- STANDBY (Daniele): calibrazione/valutazione con BASELINE 150 mm da rifare QUANDO la calibrazione di logger02 è top (VERDE: metro 2-4-8 m + dy stabile). Base di partenza: agents/rapporti/interasse_150_logger02.md (simulazione 200/150/100 su giro 13:46). Serve per decidere l'interasse del case v6.

## 2026-11-24 — case logger HW3 v7 (interasse 150) DISEGNATA, doc NON salvato
- Doppio: fusion/progetti/case-logger-hw3/STAMPA_v7.md (commit doppio a42b5b2). Scatola 203x64,3x52, camere a 150, pacco nella tasca
  del coperchio, viti esterne M2.5x6 + inserti M2.5x4, O-ring 164x2, 2 asole fascette nell'aggancio.
- Da Daniele: «salva» in Fusion quando gli va bene; misure vere HW-775 (25x20x6 stimato) e posizione del suo LED.
- Quando si monta: camere GIRATE di 180 -> girare l'immagine nel firmware/pipeline logger HW3 v7 e rifare la calibrazione
  (collegato allo STANDBY calib baseline 150).
- Carrello (solo preparare): 12 inserti M2.5x4, 12 viti M2.5x6 ISO 4762, O-ring NBR 164x2.


## 2026-11-24 pomeriggio — logger02 col case fissato (Daniele: "guarda se la calib viene ottima")
- GIRO col case fissato = sessione 14:32 (A 143247 / B 143252): officina → strada (clip 4-7) → officina, fermo dal clip 9. È la sessione principale del test dy. Le sessioni 10:37 e 14:03 sono invece il logger FERMO SUL BANCO davanti al portatile: misurano solo sync A/B col fw 941d249d e stabilità da fermo + quanto si è mosso il montaggio rispetto al v3. asmile-calib al lavoro (PREREG + rapporto agents/rapporti/calib_logger02_20261124.md) → poi asmile-calib-critico. Per dire "il case ora è fermo in bici" serve un giro vero.
- CONTROLLO COL METRO (richiesta Daniele): `logger/depth/calib_rock/logger02_v2/foto_metro.py <calib.json> <out>` prende un fotogramma da A (:81/stream) e da B (:82/b/stream), rettifica (720→800: cy+40), SGBM con controllo sinistra-destra, scarta riflessi e bordi, segna 6-8 punti con la distanza diretta (dal punto di mezzo fra le lenti). Provato a secco: funziona, ma la scena deve avere oggetti fra ~1 e 10 m con texture (sotto 0,93 m è fuori portata con 256 px di disparità). logger02 era in sleep alle 14:5x: serve svegliarlo.
- Obiettivo di Daniele: mock → calibrazione di ogni asmile logger (e delle prossime asmile) senza tabellone; i numeri del metro sono la verità che serve per tarare focale e d0 del mock.
- 24/11 sera: calib-critico PASSA PARZIALE su v4 (provvisorio). Per PASSA pieno: giro ≥15 min su strada con urti; R fissata da blocco stabile pre-registrato scartando i primi 2 min dopo il maneggio; test su sessione DIVERSA dal fit; metro ≥6 punti a 3/5/10 m sx-centro-dx.
- FRENO #001 24/11 (URGENTE): limiter v3 attivo inchioda. Log: al comando 0° la corrente servo va a 3,2 A per ~10 s e la bici si ferma (14:53:02, 14:55:36). GPIO12 trovato `op dl` (gpio_free = OUTPUT LOW su Pi 5) + impulso di ritorno 0,15 s. Proposta: pin in ingresso come asmile2, ritorno lungo, guardia corrente dopo rilascio, servo_ma nel registro, banco ruota sollevata. Chiesto a Daniele: vai per limiter in OMBRA subito + velocità target (15?). Log in agents/prove/freno_001_20261124/.
- 24/11 15:13 DEPLOY freno fix su #001 (3a3551ad, registra_deploy 8d89ef47). Sicurezza ALLOW condizionato (condizioni fatte), rollback-guardian PASSA parziale: backup/rollback ok; MANCA: se il limiter muore (kill -9) col freno chiuso nessuno libera il pin -> il master deve controllare che il limiter sia vivo e, se morto, impulso 0 per 1,5 s + pin in ingresso + avviso (da fare e provare a banco col servo, col vai). Rollback solo a bici ferma e master OFF.
- Dopo il giro di prova di Daniele: confrontare attivo_*.csv (ora con ina_ma) con sensor_hub (encoder, IMU, GPS, servo_ma); verificare dt del ciclo dopo ogni pinctrl.
- 24/11 sera DECISIONE Daniele: firmware logger02 di stasera (sveglio mentre scarica + scarico affidabile, se passa) = firmware FLOTTA dal 26/11 SE in 2 giorni: nessuno spegnimento durante lo scarico, wifi mai giù, sempre raggiungibile da acceso. Da verificare coi CSV salute/errori + log ingest (/tmp/asmile-loggers-ingest.log) il 26/11 e riferire a Daniele prima di ota_flotta.sh.
- 24/11 sera FRENO #001 — stato: sul Pi = fix rilascio (3a3551ad). PRONTI non deployati: (1) master guardia limiter-morto + niente doppio limiter (main, sicurezza ALLOW condizionato, condizioni fatte); (2) regolatore a fascia di contatto sul ramo `proposta/freno-fascia-contatto` (9a2a6156): 0 inversioni in sim, discesa ripida 16-16.7 a regime; sicurezza ALLOW solo banco, BLOCK strada finché contatto/lavoro non misurati; condizioni: misura sfiora a riposo, avvicinamento <=12 gradi/s se contatto basso, test PI con fonti di riserva/IMU morta, Daniele accetta il compromesso discese. (3) PROPOSTA soglie calme (main, config/...PROPOSTA_calmo) superata dal regolatore. PROSSIMO: misura sfiora/lavora con pi/braking/prova_contatto_001.py (protocollo agents/protocolli/freno_contatto_001_20261124.md, banco-critico PASSA parziale; primo giro --salite 1 --senza-discesa, master su ON, pgrep vuoto, vai di Daniele).
- 25/11 DOMANI con Daniele: foto col metro logger02 (1-2-5-10 m, sx/centro/dx; foto_metro.py con CANDIDATO_v5, UNA lettura, niente streaming) → esame scala/focale/d0 di v5. Poi ricetta "calib dal primo giro senza metro" da rendere ripetibile per tutti i prossimi logger/Asmile (script unico + gate). Zona basso-dx: candidato lente K2, chiudere coi prossimi giri (più bordi) — deve essere <1 px come il resto. IMU fissa con due viti (Daniele): R_imu invariata.
- 24/11 sera DA FARE (Daniele): mettere il suo CONTROLLO sui loop che il capo esegue con gli agenti (vedi schema asmile/capo dato in chat 24/11 e memoria project_controllo_daniele_loop_agenti).
- 24/11 19:06 TARATURA batteria logger02 (Daniele col tester): lettura 2,03 ↔ 1,90 V (cella scarica, ferma) e lettura ~3,24 ↔ 3,33 V (in carica). Retta a 2 punti: V = 1,19 × lettura − 0,52 (a 3,0 V veri il logger legge ~2,96). Il fattore unico 0,936 della protezione 3 V (commit 2f8cad2e, VETO del guardiano non ancora corretto, lavoro FERMATO da Daniele) va sostituito con guadagno+offset dopo un TERZO punto a cella carica (~4,0-4,1 V). Riprendere solo su ordine di Daniele.
- 24/11 BMS 1S scelto in carrello (non comprato): AliExpress Choice 10 pz 3 A DW01A+FS8205 2,24 € (logger/hw3_acquisti_bms/carrello.md). Cablaggio: B+/B- alla cella, P+/P- a step-up E caricatore.
- 24/11 19:20 logger02 sveglio: NON era il rilevatore di fermo (Daniele: prima andava in sleep perfetto, non cambiare niente). Lo tenevano sveglio le mie richieste ripetute (/api/files, /del, /api/stato contano come scarico nel fw ac6d8974) + probabilmente tocchi col tester. Mandato a dormire con /dormi.
- 25/11 08:45 TERZO PUNTO batteria logger02 (Daniele col multimetro, cella carica): lettura grezza 4,05 ↔ 4,16 V veri (fw 17:05, senza taratura). Fra 3,2 e 4,2 V la lettura è quasi 1:1: V = 1,025 × lettura + 0,01 (punti 3,24↔3,33 e 4,05↔4,16); il punto 2,03↔1,90 (cella sovrascarica) è fuori retta (ADC ESP32 non lineare in basso). Il fattore 0,936 del 2f8cad2e è SBAGLIATO in questa fascia: spegnerebbe a ~3,2 V veri e rifiuterebbe l'avvio sotto ~3,3 V. Da sostituire con guadagno+offset dai 2 punti alti. Firmware NON toccato (lavoro fermato da Daniele): solo su suo ordine.
