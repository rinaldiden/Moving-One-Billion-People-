# Asmile Driving Patterns & Anti-patterns

Patterns estratti dai dati reali di guida (19 sessioni, 671 frame, 6752+ righe sensori).

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
- **Esempio**: sessione 20260501_161106, t=16:21:45

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
- **Dataset**: 17% dei frame sono frenate

### P4: Passaggio stretto (narrow)
- **Vede**: muri su entrambi i lati, gap < 150 cm
- **Margini laterali**: < 20 cm per lato
- **Speed**: rallenta a < 1.5 m/s
- **Encoder**: micro-correzioni (delta ±5)
- **Dataset**: 18% dei frame sono "narrow"

### P5: Strada libera (clear)
- **Vede**: strada aperta, nessun ostacolo < 5m
- **Speed**: mantiene o accelera (2-5 m/s)
- **Encoder**: stabile attorno a 2750
- **Gyro_z**: < ±5°/s
- **Dataset**: 54% dei frame sono "clear"

### P6: Raddrizzamento dopo curva
- **Encoder**: torna verso 2750 (centro)
- **Gyro_z**: torna verso 0
- **Speed**: risale gradualmente
- **Esempio**: sessione 20260501_161106, t=16:25:00

### P7: Stop/fermata
- **Vede**: incrocio, stop, persona ferma davanti
- **Speed**: scende a 0
- **Accel_x**: positivo costante poi 0
- **Encoder**: stabile

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

---

## Note

- Centro encoder (dritto) = ~2750 — da calibrare per ogni bici
- Gyro_z positivo = rotazione antioraria (curva a sinistra vista dall'alto)
- Accel_x positivo = decelerazione (frenata), negativo = accelerazione
- I pattern migliorano con ogni sessione di guida aggiunta al dataset
