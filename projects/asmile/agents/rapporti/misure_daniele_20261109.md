# Misure fatte a mano da Daniele — asmile #001 — 2026-11-09

- **10 giri completi di ruota = 15.760 mm** (segno sulla valvola, bici spinta a mano) → circonferenza ruota reale **1.576 m**.
  Riferimento INDIPENDENTE per l'encoder ruota (gate L0.encoder_ruota): confrontare con Δ enc_wheel_cum nel CSV sensori
  nel tratto della spinta (prova A3, sessioni del 2026-11-09 mattina, fra le 09:30 e le 09:55).
  Nota: `wheel_circum_m=0.3374` in /var/lib/asmile/encoder_calibration.json è in realtà metri per GIRO DI ENCODER
  (l'encoder fa più giri per giro ruota): 1.576/0.3374 = 4.67 giri encoder per giro ruota → da verificare coi conteggi.
- Ordine prove dato (Telegram): A1 metro 1-2-3-4-5-6-7-8-10-12-15 m, A2 scacchi 29 mm, A3 10 giri ruota, B giro 10 min.
- **asmile-logger001: stessa ruota/circonferenza di #001 → 1,576 m** (Daniele 2026-11-09). Vale per il CooSpo BK467 montato sul logger001.
- **12:01:55 servofreno #001 portato a 0° (rilascio)** col "vai" di Daniele: un impulso 50 Hz duty 12.50% (2500 µs) per 1.0 s su GPIO12, poi PWM off + gpio_free; speed_limiter inactive, interruttore 0, servo non ancora montato sotto la leva. Corrente (INA219, sensor_hub): >100 mA per 0.92 s con picco 3200 mA (= fondo scala INA219 0.1 Ω, saturato) → il servo NON era a zero e si è mosso; dopo: 26.6 mA a riposo, pin hi-Z. Il movimento è finito prima della fine dell'impulso (1.0 s basta).
