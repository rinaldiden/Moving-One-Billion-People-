# Asmile Driving Patterns & Anti-patterns

Aggiornato: 2026-05-05. Estratti da 23 sessioni, 263.345 frame.
Keyframe extractor: 20.131 frame selezionati (7.6%) — smart (sensori) + brute (CV frame-by-frame).

## Dataset (da keyframe extractor full-scan)

| Categoria | Rilevamenti | Metodo | Note |
|---|---|---|---|
| person | 11.643 | brute | Ottimo dataset |
| lane markings | 12.370 | brute | Strisce bianche verticali |
| stop lines | 12.355 | brute | Righe orizzontali |
| scene change | 4.437 | brute | Cambi scena |
| braking | 3.800 + 2.089 hard | smart | Decelerazione IMU |
| car | 3.367 | brute | Ottimo |
| steering | 2.877 + 205 hard | smart | Cambio encoder |
| truck | 2.395 | brute | Buono |
| strong stop line | 2.262 | brute | Hough confirmed |
| turning | 2.153 + 425 sharp | smart | Gyro_z curve |
| traffic light | 781 | brute | Trovati con scan completo! |
| bicycle | 783 | brute | Buono |
| bus | 304 | brute | OK |
| motorcycle | 293 | brute | OK |
| full stop | 169 | smart | Fermata completa sensori |
| dog | 98 | brute | Sufficiente |
| stop sign | 74 | brute | Trovati con scan completo! |
| cat | 35 | brute | OK |
| stop arrival | 24 | smart | Transizione moving→stopped |
| departure | 37 | smart | Transizione stopped→moving |

## Confronto Smart vs Brute

| | Smart (sensori) | Brute (visione) |
|---|---|---|
| Keyframe trovati | 5.636 | 18.657 |
| Esclusivi | 1.474 (7%) | 14.495 (72%) |
| Trovati da entrambi | 4.162 (21%) | 4.162 (21%) |
| Forza | frenate, curve, stop | persone, segnaletica, oggetti |
| Debolezza | non vede ostacoli | non vede decelerazione |

Il brute trova 10x più keyframe perché rileva oggetti visivi. Lo smart trova eventi che solo i sensori catturano (frenata, sterzata). **Servono entrambi.**

## Sensori

| Sensore | Significato | Range osservato |
|---|---|---|
| encoder_pos | Angolo sterzo | 2520-3051, centro ~2750 (dritto) |
| imu_gyro_z | Velocità rotazione | ±45°/s max |
| imu_accel_x | Accelerazione longitudinale | ±0.4g |
| gps_speed_ms | Velocità | 0-5.4 m/s (~19 km/h) |

## Dimensioni Asmile

- Larghezza: 110 cm
- Camera: 77 cm da terra, 30 cm dal muso
- Distanza frenata a 5 km/h: ~50 cm

---

## PATTERNS (cosa fare)

### P1: Curva a sinistra
- **Vede**: muro/edificio a destra, strada curva a sinistra
- **Encoder**: scende (2750 → 2550, delta -200)
- **Gyro_z**: positivo (+15 a +45°/s)
- **Speed**: rallenta (3 → 1.5 m/s)

### P2: Curva a destra
- **Vede**: muro/edificio a sinistra, strada curva a destra
- **Encoder**: sale (2750 → 2950, delta +200)
- **Gyro_z**: negativo (-15 a -45°/s)
- **Speed**: rallenta

### P3: Frenata per persona/ostacolo
- **Vede**: persona/cane/auto a < 3m centro frame
- **Accel_x**: positivo (decelerazione, fino a +0.4g)
- **Speed**: scende rapidamente
- **Encoder**: stabile (frena dritto)
- **Dataset**: rider rallenta 81%, frena 6% vicino a persone

### P4: Passaggio stretto (narrow)
- **Vede**: muri su entrambi i lati, gap < 150 cm
- **Margini laterali**: < 20 cm per lato
- **Speed**: rallenta a < 1.5 m/s
- **Encoder**: micro-correzioni (delta ±5)

### P5: Strada libera (clear)
- **Vede**: strada aperta, nessun ostacolo < 5m
- **Speed**: mantiene o accelera (2-5 m/s)
- **Encoder**: stabile attorno a 2750
- **Gyro_z**: < ±5°/s

### P6: Raddrizzamento dopo curva
- **Encoder**: torna verso 2750 (centro)
- **Gyro_z**: torna verso 0
- **Speed**: risale gradualmente

### P7: Stop a segnaletica orizzontale
- **Vede**: riga bianca perpendicolare sulla strada, scritta STOP per terra
- **Speed**: scende a 0 m/s
- **Accel_x**: positivo costante poi 0
- **Durata fermata**: 1.9-613s (mediana ~5s)
- **White marking**: 1-47% del frame (soglia >1.5% = stop line rilevata)
- **Dataset**: 169 stop totali, 113 con segnaletica (67%)
- **8 stop con decelerazione chiara** (speed_before > 1 m/s + accel_x > 0.2g)

### P8: Lane keeping
- **Vede**: strisce bianche verticali (parallele alla direzione)
- **Encoder**: stabile, micro-correzioni
- **Dataset**: 22.482 frame con lane markings rilevate

### P9: Comportamento vicino a persone
- **Vede**: persona nel frame
- **Persona al centro**: 1.198 volte (44%)
- **Persona vicina**: 1.181 volte (43%)
- **Rider rallenta**: 81% dei casi
- **Rider frena attivamente**: 6%
- **Rider prosegue**: 16% (persona lontana o ai lati)

---

## ANTI-PATTERNS (cosa NON fare)

### A1: Frenata tardiva
- Ostacolo a < 1m e speed > 2 m/s
- Il modello deve frenare PRIMA: a 3m inizio frenata, a 1.5m fermo

### A2: Sterzata brusca
- Encoder delta > ±30 in un singolo campione (100ms)
- Sterzare progressivamente, non a scatto

### A3: Velocità in passaggio stretto
- Speed > 2 m/s con margini < 15 cm
- Rallentare a < 1 m/s in passaggi stretti

### A4: Non rallentare in curva
- Gyro_z > 20°/s e speed > 3 m/s
- Sempre rallentare prima della curva

### A5: Ignorare ostacolo laterale
- Muro/persona a < 30 cm laterale e nessuna sterzata
- Deve sterzare dall'altra parte O fermarsi

### A6: Accelerare verso persona
- Persona rilevata a < 5m e speed in aumento
- MAI accelerare verso una persona

### A7: Non fermarsi allo stop
- Riga bianca perpendicolare rilevata e speed > 0.5 m/s
- Deve rallentare e fermarsi completamente

---

## Soglie operative

| Situazione | Distanza trigger | Azione | Speed max |
|---|---|---|---|
| Persona davanti | 5m | rallenta | 2 m/s |
| Persona davanti | 3m | frena | 1 m/s |
| Persona davanti | 1.5m | stop | 0 |
| Passaggio stretto | qualsiasi | rallenta | 1.5 m/s |
| Passaggio < 120cm | qualsiasi | stop | 0 (non ci passa!) |
| Curva | inizio | rallenta | 2 m/s |
| Strada libera | > 5m | normale | 5 m/s |
| Stop line rilevata | approccio | rallenta | 1 m/s |
| Stop line sotto | 0m | stop completo | 0 |

---

## Steering-Vision Correlation

4.824 frame-pairs analizzati con optical flow + vanishing point vs encoder.

| Correlazione | Valore | Significato |
|---|---|---|
| encoder ↔ gyro_z | -0.66 to -0.83 (per sessione) | Forte — stessa misura, segni opposti |
| encoder ↔ optical_flow | 0.01 | Debole — flow grezzo non basta |
| encoder ↔ vanishing_point | 0.03 | Debole — linee irregolari nei vicoli |

Il modello Asmile deve imparare la relazione visione→sterzata che l'optical flow semplice non cattura.

## Cosa manca

- **Condizioni diverse**: pioggia, crepuscolo, controsole — serve variare orari e meteo
- **Più percorsi urbani**: abbiamo semafori e stop ma servono più esempi
- **Frenate documentate con decel**: solo 8 con speed_before>1m/s + accel_x>0.2g

## Note

- Centro encoder (dritto) = ~2750 — da calibrare per ogni bici
- Gyro_z positivo = rotazione antioraria (curva a sinistra vista dall'alto)
- Accel_x positivo = decelerazione (frenata), negativo = accelerazione
- Stop line detection: soglia white > 1.5% nel road zone, confermata con Hough horizontal lines
- I pattern migliorano con ogni sessione di guida aggiunta al dataset
