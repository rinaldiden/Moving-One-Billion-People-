# Protocollo sterzo + freno asmile #001 — v2 (dopo VETO 1) (bozza, Pi spento, NIENTE ancora eseguito)
Solo #001. Mai riusare numeri di asmile2 (centro 3800/3565/4046 = 12 bit, altra unità). Bici su cavalletto, ruota libera, strada non serve.
Linee rosse: nessun motore/freno senza "vai" scritto da Daniele (prima leggo pos e dichiaro la direzione); freno ≤60°; niente reboot.

## Pre-test (tutti)
Batteria carica; freno meccanico/idraulico ok (leva libera); servo sotto la leva montato e a 0°; sensor_hub attivo (`enc_steer_raw`, `brake_out_*`, `servo_ma` nel CSV); /tmp/encoder_steer fresco (<100 ms); Daniele con mano libera vicino allo stacco. Bici FERMA: /tmp/encoder_wheel (o enc_wheel nel sensor_hub) non cambia per 1 s (lo script rifiuta altrimenti). UART del VESC libera: fermare power_steering.py e ogni altro uso (`sudo systemctl stop`/kill del processo, mai reboot) e verificare con `fuser /dev/ttyAMA0` = vuoto (lo script lo controlla e rifiuta). Su cavalletto, nessuno davanti al manubrio.

## A. VESC: tetto di corrente
**Via di DEFAULT: VESC Tool** (Daniele): prima esporta backup XML della Motor Config, poi imposta i limiti sotto, poi riesporta e confronta. Lo script `vesc_mcconf_limiti_001.py` resta in SOLA LETTURA finche' Daniele non ha confrontato il suo `leggi` con VESC Tool e creato `~/wip/vesc_leggi_validato_vesctool`. Ogni uso legge prima COMM_FW_VERSION (rifiuta se != 5.2) e controlla signature+lunghezza del blob (anche in ripristina).
Sotto: la procedura con lo script (solo dopo validazione).
1. Leggi (sicuro, subito): `python3 pi/steering/vesc_mcconf_limiti_001.py leggi` → salva backup in ~/wip, stampa l_current_max/min, l_in_current_max/min, l_abs_current_max. PRIMA PROVA: se dice "layout NON plausibile" gli offset fw5.2 non valgono: stop, verifica con VESC Tool (NON VERIFICATO).
2. `scrivi` senza flag = dry-run, mostra il diff.
3. Valori iniziali proposti: motore +8/−8 A, batteria +5 A, rigenerazione −2 A, abs max invariato. Motivo: power steering oggi 0.5 A/step con tetto 5 A (power_steering.py ha però MAX 15 nel codice: da allineare); 8 A dà margine allo spunto, non spinge sul finecorsa. Lo script rifiuta di ALZARE un limite. Si sale solo a passi, dopo test.
4. Con vai di Daniele: `scrivi --apply --vai`; rilettura automatica. Se diff ≠ solo i 4 campi: `ripristina <backup.bin> --apply --vai`.
Nota: SET_MCCONF in fw5.2 salva in flash: il backup è l'unico ritorno.

## B. Encoder sterzo: centro + finecorsa (solo lettura, nessun vai motore)
`python3 pi/steering/calibrate_steering_limits.py` (default #001: 14 bit, /tmp/encoder_steer). Daniele muove a mano: dritto → tutto sx → tutto dx → dritto. Scrive /data/steering_limits_<unità>.json. Accetta solo se ripetibilità centro ≤1° e `encoder_pos_increases_to` annotato. Ripeti 2 volte: centro entro ±5 count. Il manubrio dritto lo giudica Daniele (ruota allineata al telaio).

## C. Ritorno al centro (MOTORE = vai a ogni stadio)
Prerequisiti: A fatto, B fatto. Daniele sposta a mano il manubrio ~10° dal centro, poi:
`python3 pi/steering/vesc_return_centro_001.py` (prima `--dry-run`).
- Stadio 0: legge, dichiara direzione attesa. Stadio 1 (vai): micro-impulso 20 ms, misura il verso reale duty↔encoder (su #001 non noto: DUTY_SIGN va misurato, non copiato). Stadio 2 (vai): gradini 60 ms duty 0.02, pausa 150 ms, rilettura.
- Stop automatico: encoder vecchio, salto encoder >200 count in un passo, fuori finecorsa−40 count, |i_motor|>5 A LETTA DURANTE l'impulso (ogni ~30 ms; se la lettura VESC manca → STOP), fermo dopo 3 impulsi, centro attraversato, 20 s, Ctrl-C.
- Daniele osserva: movimento fluido, nessun cigolio, nessun urto al finecorsa; ferma se dubbio. Se non si muove: NON alzare duty da soli, si torna a Daniele. Sequenza di crescita (solo con nuovo vai): 10° → 20° → 40° di errore iniziale.
- Registrare il giro (CSV in ~/wip/logging/vesc + sensor_hub) per asmile-actuator-modeler.
Aperti: Speed PID del VESC (note memorie: serve per SET_RPM; qui si usa duty); tempi/risposta reali da misurare; script mai provato su #001.

## D. Freno: prima partenza con interruttore su 1
Servo già a 0°. Daniele monta il servo sotto la leva: prima di tutto a interruttore OFF, controllare a mano che la leva non sia in tiro a 0° (nessun trascinamento pad).
Poi interruttore su 1, bici ferma su cavalletto: guardare nel CSV sensor_hub `brake_out_cmd`, `brake_out_deg` (mai >60), `servo_ma`, `servo_v` (tensione non deve crollare). Osservare: a riposo servo_ma ≈ 0 (pulse-and-free, nessuna corrente continua); nessun movimento spontaneo; flag /tmp/emergency_brake solo con vai. Stop immediato (interruttore OFF) se: servo caldo/rumore di stallo, brake_out_deg >60, servo_ma alto con gradi fermi (stallo idraulico dopo contatto pad: tagliare subito, non insistere), movimento senza comando.
Regola stallo: se servo_ma resta alto mentre brake_out_deg non cambia per >0.3 s → rilascio a 0 e stop (a mano: interruttore OFF).
Primo comando freno: gradini 0→15→30° con vai a ogni gradino, rilascio a 0 tra uno e l'altro, registrare servo_ma vs gradi (punto di contatto pad). Oltre 45° solo con nuovo vai e mai >60°. Poi, se Daniele vuole, `encoder_taratura_metro.py` per la decelerazione.

## Cosa registrare (per il modello attuatore)
Comando + encoder + IMU + corrente allo stesso t_ms (sensor_hub, 50 Hz); per lo sterzo: enc_steer_raw, steer_out_*, i_motor; per il freno: brake_out_*, servo_ma/v, vel ruota.

## Script
pi/steering/vesc_mcconf_limiti_001.py, pi/steering/vesc_return_centro_001.py (nuovi); riusati calibrate_steering_limits.py, vesc_config_backup.py, vesc_return_to_center_duty.py. Test locale fatto: solo sintassi + round-trip codifica float32_auto del VESC; layout mcconf e hardware NON VERIFICATI.

## Proposta (NON applicata)
`agents/rapporti/power_steering_max5A.diff`: MAX_CURRENT 15→5 A. Da applicare solo col si' di Daniele (modifica al funzionamento).
