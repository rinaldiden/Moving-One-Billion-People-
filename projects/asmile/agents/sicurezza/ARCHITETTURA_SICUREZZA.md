# Asmile — architettura di sicurezza e ridondanza (punto di partenza per irrobustire)

Raccolta del 2026-11-15 di tutto quello che è stato detto su sicurezza, separazione online/offline e ridondanza dei segnali.
Fonti: verifica del Doppio del 14/11 (agents/TODO_capo.md, sezione 14/11, commit 60a2f0bb), discussione di Daniele con "zio" (14/11 e 15/11), prove del capo su freno e sterzo del 13/11.
**Guida di Daniele: "Tesla insegna".**
Stato: **niente è ancora implementato sul Pi.** Ogni passo segue la palla (produttore → contro-agente), passa da asmile-sicurezza, e va sul Pi solo col vai di Daniele.

## 1. Stato vero di #001 (14/11)
- Una sola rootfs (p2) in overlay di sola lettura + /data (p3) scrivibile. Protegge la SD dagli stacchi di corrente, **non** da chi entra dalla rete.
- Wifi e Tailscale sempre accesi; root via ssh può fare `remount,rw` e cambiare il codice di guida. Niente lo impedisce e niente se ne accorge.
- `fleet/001/codice_sul_pi.sha256` è una foto manuale scattata dal deploy, non un controllo a runtime; `differenze_dal_repo.txt` mostra già file diversi dal repo (speed_limiter solo sul Pi).
- Scheletro A/B firmato (RAUC + cosign: `deploy/rauc`, `deploy/ota_update.sh`, `deploy/verify_release.sh`, `deploy/asmile-ota.service`) mai installato; lo slot B era p3, che oggi è /data → da riprogettare.
- Regole del 30/10 (guida offline, aggiornamenti spenti in guida, watchdog indipendente) rimaste sulla carta.
- Freno (13/11): unico padrone GPIO12 = speed_limiter, ma oggi **speed_limiter è disabled e servofreno.service è enabled** (contro la regola); su Pi 5 `gpio_free` lascia il pin OUTPUT LOW (serve `pinctrl set 12 ip pn`). Il servo SER0062 tiene la posizione da solo anche senza segnale (175 mA a 60°, ~0.6 A a 80°). **Servizio del freno da rifare da zero.**

## 2. Decisioni di Daniele (14-15/11)
1. **Un solo firmatario: Daniele dal Mac, OTA solo in IDLE**, sia per il computer di guida sia per l'ESP32. La chiave privata sta solo sul Mac, mai sul Pi.
2. **L'ESP32 deve poter prendere il controllo** del servofreno, e dello sterzo, per frenare in sicurezza quando serve.
3. **Ridondanza fisica: 2 schede di calcolo + ESP32.** Non due Raspberry: **due schede dedicate su cui gira direttamente il sistema operativo Asmile** (stesso software firmato). Una primaria e una secondaria che può subentrare se la prima si brucia.

## 3. I 5 passi (ordine proposto; priorità: 1 e 2 prima)
1. **DRIVE / IDLE** come target systemd. In DRIVE: `rfkill block all`, Tailscale e `asmile-ota.service` mascherati, nessun demone di rete; rete solo a bici ferma in IDLE. (asmile-deploy + asmile-sicurezza)
2. **Manifest firmato del codice di guida**: sha256 di ogni file + modello ONNX, firmato cosign sul Mac. All'armo il Pi verifica hash e firma: se cambia una riga la guida non parte, buzzer + Telegram. Chiude il buco "file ≠ repo". (asmile-deploy, contro: asmile-rollback-guardian)
3. **Watchdog esterno su ESP32** (dominio di sicurezza separato, vedi §4).
4. **A/B vero**: due copie immutabili della guida (dir + symlink su /data, oppure rpi tryboot) con rollback automatico all'ultima versione buona; rifare la config RAUC. Più avanti **dm-verity** (root hash firmato) e **secure boot del Pi 5 legato a una chiave di Daniele scritta nell'OTP**.
5. **Chiudere la porta**: niente sudo senza password per l'utente di rete, ssh solo con chiave di deploy, scrittura sul sistema solo in IDLE e solo via update firmato.

## 4. ESP32 come safety MCU
- **Firmware firmato, aggiornabile solo da Daniele** in IDLE (mai dal Pi, mai da solo). Il watchdog non deve poter essere disabilitato o riscritto da chi controlla il Pi.
- **Collegamento Pi ↔ ESP32**: UART dedicata (heartbeat ogni 50-100 ms: t_ms, hash del manifest, armato sì/no, velocità, ultimi comandi freno/sterzo) + 2-3 GPIO discrete: ALIVE (Pi→ESP32), FAULT/ESTOP_REQUEST (ESP32→Pi), OVERRIDE (ESP32 → arbitraggio attuatori). Alimentazione ESP32 separata o filtrata, massa comune.
- **Interviene se**: heartbeat mancante per N cicli, hash del manifest diverso, comando oltre le linee rosse (freno >60°, corrente sterzo oltre tetto, ecc.).
- **Freno (prioritario)**: arbitraggio hardware del PWM del servo (mux/OR con priorità all'ESP32 quando OVERRIDE è attivo) → l'ESP32 porta il freno a una posizione sicura **≤60°** senza passare dal Pi. In più l'ESP32 comanda l'**EN del Pololu D24V55F6** (6 V del servo): serve anche al freno di stazionamento a corrente zero (master su 0: freno chiuso, poi 6 V tolti — da verificare che il freno resti chiuso senza alimentazione).
- **Sterzo**: niente controllo fine dall'ESP32 (il VESC FOC è complesso). L'ESP32 può **togliere potenza al VESC** (EN o MOSFET/relè sull'alimentazione) e, solo come ultima risorsa, mandare uno stop via UART. Da decidere con Daniele, che chiede la presa di controllo anche dello sterzo: cosa fa il manubrio a VESC spento (libero?) mentre si frena, e se serve un "tieni dritto" minimo.
- **Coerenza con le regole di frenata**: la frenata d'emergenza dell'ESP32 deve rispettare la **regola ferrea anti-impuntata** (rilascio appena il posteriore si alza, ripresa con meno forza) → l'ESP32 ha bisogno della sua IMU o di un segnale IMU indipendente dal Pi. Soglie in `config/soglie_attuazione_001.json` → "anti_impuntata" (proposta, n=2 impuntate).
- Va aggiornata la regola "GPIO12 padrone unico": diventa "un solo padrone per livello" (Pi in guida normale, ESP32 con priorità hardware in emergenza).
- Esiste già `esp32/esp32_wifi/` nel repo (firmware wifi): verificare se è lo stesso ESP32 a bordo e se è troppo intrecciato col resto; se sì, micro dedicato (STM32/RP2040).

## 5. Separazione online/offline e futuro a 2 schede (stile Tesla)
- Nella Tesla l'A/B serve ad aggiornare e tornare indietro; **la separazione vera è fisica**: computer di guida e computer connesso sono schede diverse.
- Finché è un solo Pi: chi entra dalla rete con root può modificare anche un watchdog software sullo stesso processore → per questo il watchdog va sull'ESP32 e la rete va spenta in DRIVE.
- Da valutare: **rete solo sul router 4G o su un secondo processore**, con la scheda di guida senza credenziali di rete.
- Architettura obiettivo: **scheda A (primaria: percezione, guida, controllo fine) + scheda B (secondaria: monitor e subentro) + ESP32** con autorità fisica ultima su freno d'emergenza e taglio potenza. Heartbeat reciproco A↔B e verso l'ESP32; arbitraggio degli attuatori in hardware.

## 6. Domande ancora aperte (da Daniele)
- **Q-A** offline in DRIVE = rete spenta del tutto? Proposta (zio): sì, rete spenta del tutto (rfkill); solo in IDLE torna.
- **Q-B** ESP32 a bordo o micro dedicato? Proposta: quello a bordo se è isolabile come dominio di sicurezza, altrimenti dedicato.
- **Q-C** risposta di Daniele: sì, 2 schede dedicate + ESP32 (§2.3); tempi e scelta delle schede da definire.
- Sterzo con l'ESP32: solo taglio potenza o anche "tieni dritto"?

## 7. Collegamenti
- TODO del capo: `agents/TODO_capo.md` (sezione 2026-11-14).
- Linee rosse: `.claude/agents/asmile-sicurezza.md` (freno ≤60°, anti-impuntata, GPIO12, vai, firma, reboot).
- Memoria: `project_asmile001_overlay_watchdog_arch.md`.
- Freno: `agents/prove/sterzo_001/REGISTRO_20261112.md` (corrente di tenuta, pin hi-Z), `pi/autonomous/speed_limiter.py` (classe Servo).
- Schema HW del logger v2 (stesso tema accensione/spegnimento/autoritenuta): `logger/hw_v2/README.md`.
