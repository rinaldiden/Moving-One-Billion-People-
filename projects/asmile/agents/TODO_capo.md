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
