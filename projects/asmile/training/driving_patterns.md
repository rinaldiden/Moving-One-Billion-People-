# Asmile Driving Patterns & Anti-patterns

Aggiornato: 2026-05-05. Estratti da 23 sessioni, 263.345 frame, 3.690 eventi.

## Dataset

| Categoria | Rilevamenti | Note |
|---|---|---|
| person | 2.742 | Ottimo dataset |
| car | 2.369 | Ottimo |
| truck | 308 | Buono |
| bicycle | 271 | Buono |
| stop (da sensori) | 169 | Con segnaletica: 113 |
| lane markings | 22.482 frame | Strisce bianche rilevate |
| motorcycle | 55 | Sufficiente |
| cat | 42 | OK |
| bus | 42 | OK |
| dog | 7 | Pochi, servono più incontri |
| stop sign (cartello) | 0 | Non presente nei percorsi |
| traffic light | 0 | Non presente nei percorsi |

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

## Cosa manca

- **Semafori**: 0 rilevamenti. Servono giri in zona urbana con incroci semaforizzati
- **Cartelli stop verticali**: 0 rilevamenti YOLO. I percorsi hanno solo segnaletica orizzontale
- **Cani**: solo 7. Incontri casuali, verranno col tempo
- **Condizioni diverse**: pioggia, crepuscolo, controsole — serve variare orari e meteo

## Note

- Centro encoder (dritto) = ~2750 — da calibrare per ogni bici
- Gyro_z positivo = rotazione antioraria (curva a sinistra vista dall'alto)
- Accel_x positivo = decelerazione (frenata), negativo = accelerazione
- Stop line detection: soglia white > 1.5% nel road zone, confermata con Hough horizontal lines
- I pattern migliorano con ogni sessione di guida aggiunta al dataset
