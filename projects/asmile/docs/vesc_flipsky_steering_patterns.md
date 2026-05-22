# VESC + Flipsky steering — pattern e antipattern

Lezioni emerse dal setup dello sterzo automatico asmile2 (VESC FSESC 6.7 Pro + Flipsky 6354 140KV con hall, encoder esterno Briter sulla colonna).

Database di "cosa fare / cosa NON fare" quando vuoi pilotare a basso RPM sotto carico variabile con feedback di posizione esterno.

---

## ✅ Pattern (cose che hanno funzionato)

### P1 — Usa SET_CURRENT, non SET_DUTY, per controllo posizione closed-loop

**Cosa**: il loop di controllo nel Pi calcola la corrente target (= coppia) e la manda al VESC con `COMM_SET_CURRENT`. Il VESC modula automaticamente il duty per produrre quella corrente.

**Perché**: SET_DUTY è un comando di "tensione equivalente" — sotto carico variabile la corrente fluttua e il motore può stallare. SET_CURRENT è invece "coppia diretta": il motore mantiene la coppia comandata indipendentemente dalla velocità o dal carico. Per sterzata reale (carico variabile da cavalletto a strada vera) è fondamentale.

### P2 — Architettura outer/inner loop separati

**Cosa**:
- **Outer loop nel Pi @ 50 Hz**: legge encoder esterno (Briter SSI), calcola error/velocity, manda comando di corrente al VESC
- **Inner loop nel VESC**: FOC con hall sensors gestisce la commutazione delle fasi

**Perché**: il VESC è ottimizzato per la commutazione FOC a frequenza alta (kHz). Il Pi è ottimizzato per logica di alto livello. Separare le due responsabilità: il Pi non si preoccupa di commutare le fasi, il VESC non si preoccupa di seguire una traiettoria di posizione.

### P3 — Per stall sotto corrente alta con hall apparentemente OK → Detect Hall Sensors

**Cosa**: se il motore eroga corrente (anche 12+ A confermati via UART) ma non ruota:
1. Non assumere che la Hall Table valida = mappatura corretta
2. Connetti VESC Tool, vai a `Motor Settings → FOC → Hall Sensors`, premi **"Detect Hall Sensors"**
3. Sterzata in posizione di mezzeria (per dare margine alla rotazione di detection)
4. Salva con "Write Motor Configuration"
5. Aspettati che la **direzione del comando possa essere invertita** dopo questa procedura — la nuova mappatura potrebbe ruotare il vettore di corrente in modo opposto

**Perché**: la Hall Table può avere valori NUMERICAMENTE plausibili (sequenza monotona di delta ~33 in scala 0-200) ma essere MAPPATA SBAGLIATA agli indici hall reali. Il FOC commuta tutto regolare ma il vettore corrente è offset di 60-120° elettrici rispetto al rotore → coppia oscillante o nulla → tipico "current alta, motore fermo, niente di rotto".

### P4 — Verifica direzione SEMPRE dopo modifiche FOC

**Cosa**: il segno del comando (`CURRENT_SIGN`, `DUTY_SIGN`) può cambiare ogni volta che:
- Si rifà la Detect Hall Sensors / Detect FOC
- Si cambia il cablaggio delle fasi motore
- Si cambia il cablaggio hall

Esempio reale 2026-05-22: dopo Detect Hall Sensors il motore è andato nella direzione opposta a quella attesa, quasi sbattendo contro il finecorsa SW prima dell'intervento manuale dello user.

**Procedura sicura**: dopo qualunque detection o cambio cablaggio, prima del primo test che pilota il motore:
1. Sterzata al CENTRO (non vicino ai finecorsa)
2. Mano sul tasto STOP di VESC Tool
3. Comando MINIMO (es. 2A SET_CURRENT per 200ms)
4. Verifica direzione encoder, eventualmente inverti `*_SIGN`

### P5 — Tach VESC come double-check dell'encoder esterno

**Cosa**: leggi `tach_abs` e `tach signed` da `COMM_GET_VALUES` (offset payload 44 e 48). Confronta direzione con encoder esterno.

**Perché**: l'encoder esterno è la verità per la posizione della colonna, ma se ci fosse slippage meccanico (cinghia/ingranaggio) la posizione encoder e i giri motore non sarebbero più consistenti. Discrepanza di segno = warning grave, ferma il comando.

Rapporto misurato per questo setup: `0.105 tach_motore / step_encoder` (verificato 220 step encoder → 24 tach).

### P6 — Deadband + exit, NIENTE controllo continuativo per "hold position"

**Cosa**: quando l'encoder entra nella deadband (±10 step ≈ ±0.9°), invia `SET_CURRENT 0` due volte (per ridondanza) ed esci dal loop. Lascia il motore in flottaggio.

**Perché**: tentare di mantenere attivamente la posizione causa oscillazione. Il manubrio ha forza di centraggio naturale (caster) che è meglio assecondare. Se serve davvero hold (es. tenere una sterzata contro forza laterale), implementa solo dopo aver risolto il caso "torna a centro" stabilmente.

### P7 — Velocity feedback affidabile = 2 sample consecutivi + EWMA, NON finestra temporale

**Cosa**: per stimare la velocità encoder, usa
```python
raw_vel = (pos - pos_prev) / dt_actual
actual_vel = 0.7 * actual_vel + 0.3 * raw_vel  # EWMA filter
```
e aggiorna `pos_prev`/`t_prev` ad ogni iter.

**Perché**: una finestra mobile temporale (es. ultimi 100ms) viene svuotata da blocchi I/O occasionali (es. `query_telemetry` che dorme 40-80ms su read seriale). Risultato: `actual_vel = 0` proprio nel ciclo in cui logghi o decidi — bug silenzioso. Il sample-pair + EWMA è robusto a slip del loop.

### P8 — CSV separato per ogni run di test

**Cosa**: ogni invocazione di uno script di controllo scrive un CSV in `~/wip/logging/vesc/<scopo>_<YYYYMMDD_HHMMSS>.csv` con timestamp ISO + tutte le colonne sensori e comandi a 50 Hz.

**Perché**: facile da mergere offline con `sensors.csv` del training_recorder via timestamp join. Tracciabilità completa di ogni esperimento per replay/analisi. Non sovrascrive sessioni precedenti.

---

## ❌ Antipattern (cose che NON funzionano in questo setup)

### A1 — SET_RPM con target basso (<100 ERPM)

**Cosa NON fare**: comandare `COMM_SET_RPM` con valori tipo 8 ERPM.

**Cosa succede**: il VESC non risponde affatto, il motore resta fermo. Il PID di velocità del FOC non si aggancia a velocità così basse perché il loop di controllo interno non è progettato per quel regime.

**Alternativa**: SET_CURRENT (P5) o SET_DUTY se proprio si vuole tensione costante. Per controllo di velocità a basso RPM, implementa un loop esterno nel Pi che genera SET_CURRENT da `target_velocity - actual_velocity`.

### A2 — Trust FOC params senza Detect

**Cosa NON fare**: assumere che `Motor R`, `L`, `Flux Linkage` siano corretti solo perché "ci sono dei valori plausibili" nel config.

**Cosa succede**: con FOC params di default o leggermente sbagliati, la coppia prodotta a parità di corrente comandata è ridotta (cos(φ) della differenza tra angolo stimato e angolo reale del rotore). Sintomi: high current, low torque.

**Cosa fare**: esegui sempre "Detect Motor R+L" (sicuro, non gira) e "Detect Flux Linkage" (gira pochi gradi) come primo step di un setup nuovo.

### A3 — Hard P-controller con duty/current FISSI fuori dalla deadband

**Cosa NON fare**: comandare sempre `duty = 0.020` (o `current = 8A`) fintanto che `|error| > deadband`, poi switchare brutalmente a `0` in deadband.

**Cosa succede**: il motore accelera per inerzia oltre il deadband e oscilla avanti/indietro. Tipico limit cycle.

**Cosa fare**: scala con `|error|` (P-controller proporzionale) E/O usa velocity feedback per frenare attivamente prima di entrare in deadband.

### A4 — Velocity cap basato solo su scaling di magnitudine

**Cosa NON fare**: se `actual_speed > target_speed`, riduci `current_cmd *= target_speed/actual_speed`.

**Cosa succede**: riduci la coppia ma non FRENI. Il motore continua a girare per inerzia (coasting). Risultato: overshoot inevitabile.

**Cosa fare**: P-controller sul velocity error (può comandare corrente OPPOSTA per frenare attivamente):
```python
v_error = target_vel_signed - actual_vel_signed
i_cmd = Kv * v_error  # può essere negativo → freno
```

### A5 — Fidarsi della direzione "trovata" senza riverificare dopo Detect

**Cosa NON fare**: assumere che `CURRENT_SIGN = -1` (calibrato il 18/05) sia ancora valido dopo aver rifatto Detect Hall Sensors il 22/05.

**Cosa succede**: motore va nella direzione opposta a quella attesa. Su questo setup è successo letteralmente: lo script ha pilotato la sterzata verso il finecorsa anziché tornare al centro, fermato 9 step prima del safety cut grazie all'intervento manuale dell'utente.

**Cosa fare**: dopo OGNI Detect, riverifica la direzione con un comando MINIMO (P4) prima di permettere comandi pieni.

### A6 — Bloccare il loop di controllo per I/O lungo

**Cosa NON fare**: chiamare `query_telemetry` (che fa `time.sleep(0.04) + ser.read()`) sincronamente nel loop di controllo, e poi assumere che velocity/state misurati abbiano la stessa scala temporale del loop.

**Cosa succede**: il loop slipsa di 40-80ms, le strutture dati che dipendono da timestamp (finestre mobili, derivative, ecc.) vanno fuori asse → bug silenziosi.

**Cosa fare**: o sposta la telemetria su un thread separato, o usa misurazioni sample-by-sample (P7) che non dipendono da una finestra temporale precisa.

### A7 — Interpretare Sensored ERPM Start in modo invertito

**Cosa NON fare**: leggere "Sensored ERPM Start: 2500" come "i hall si attivano sopra 2500 ERPM" e quindi pensare di doverlo abbassare per usare hall a basso RPM.

**Verità**: significa "**SOTTO** questa soglia ERPM si usa SOLO sensored (hall). Sopra inizia a contribuire l'observer sensorless." Quindi 2500 è perfetto per uso low-RPM: tutto il range che ci interessa (0–100 RPM motore) usa solo hall.

**Antipattern reale**: abbassare a 0 farebbe entrare in zona di blend a bassissimo RPM, dove l'observer non funziona → peggio.

### A8 — Lanciare uno script che pilota il motore senza GO esplicito dell'utente

**Cosa NON fare**: dopo aver modificato qualcosa di significativo nel setup (es. nuova Detect, refactoring del controller), lanciare automaticamente lo script di test perché "ce l'avevamo già su questa sterzata".

**Cosa fare**: leggi posizione encoder corrente, dichiara all'utente la direzione attesa del movimento e il comando iniziale, ATTENDI "GO" / "vai" esplicito. Vale anche se la sessione è breve: una sola Detect basta a invertire la direzione e mandare la colonna verso il finecorsa.

---

## Bootstrap rapido per nuovo setup VESC + Flipsky 6354

1. **Cablaggio**: 3 fasi motore (U/V/W) → VESC, 5 fili hall (3 sensori + V+ + GND) → VESC hall port
2. **VESC Tool via USB**: connetti, verifica baseline (Sensor Mode: Hall, Current Limits sensati)
3. **Detect Motor R+L** (sicuro, non gira): popola R, L, Lq-Ld
4. **Sterzata al CENTRO** prima di passi successivi
5. **Detect Flux Linkage** (gira pochi gradi): popola flux linkage, observer
6. **Detect Hall Sensors** (gira ±10°): popola Hall Table
7. Setta `Sensored ERPM Start ≥ 2500` (per uso low-RPM)
8. **Write Motor Configuration** (salva in flash)
9. UART app abilitato a 115200 baud (Pi parla con VESC su `/dev/ttyAMA0`)
10. **Write App Configuration**
11. Test con `pi/steering/vesc_return_to_center.py` da sterzata storta → se direzione sbagliata, inverti `CURRENT_SIGN` nello script e in `steering_limits.json`
