# Shadow Mode — Iteration 001

*Prima raccolta dati per il training di guida autonoma Asmile.*
*Come Tesla shadow mode: l'AI osserva il guidatore umano e impara, senza intervenire.*

**Data:** 16-17 Aprile 2026
**Dataset:** 32,092 campioni, 6 sessioni, ~53 minuti totali (24 min in movimento)
**Sensori:** GPS 10Hz, IMU 10Hz (accel + gyro), encoder sterzo 10Hz, video stereo 15fps

---

## 1. Sterzo

| Parametro | Valore |
|---|---|
| Encoder neutro (dritto) | ~3923 (mediana 4034) |
| Range sinistra forte | 2048–2348 → gyro_z = -25°/s |
| Range dritto | 3750–4050 |
| Range destra | > 4050 |
| Dead zone | ~3850–4034 |

**Pattern chiave:** A velocità > 3 m/s lo sterzo si stabilizza — variazione encoder scende a 166 step (vs 638 a bassa velocità). Il guidatore naturalmente riduce le correzioni ad alta velocità.

**Steering rate max a velocità:** 340 encoder counts/sec (p99 a 3-6 m/s).

**Per il training:** Encoder → gyro_z è non-lineare. Usare lookup table o MLP, non regressione lineare. Il modello deve imparare: più velocità → meno sterzo.

---

## 2. Velocità

| Categoria | Range | % del tempo |
|---|---|---|
| Fermo | 0–0.3 m/s | 54.6% |
| Lento | 0.3–1 m/s | 11.1% |
| Passo | 1–2 m/s | 13.5% |
| Crociera | 2–3 m/s (7-11 km/h) | 9.3% |
| Veloce | 3–4 m/s | 10.1% |
| Sprint | 4–5.5 m/s | 1.4% |

- **Velocità max:** 5.5 m/s (19.9 km/h)
- **Crociera tipica:** 7-11 km/h
- **54% fermo:** profilo urbano stop-and-go

---

## 3. Frenata

| Categoria | Decelerazione | Frequenza |
|---|---|---|
| Dolce | -0.1 a -0.3g | 11.3% |
| Moderata | -0.3 a -0.6g | 3.8% |
| Forte | -0.6 a -1.0g | 1.3% |
| Estrema | < -1.0g | 0.9% |

- **38 campioni a -2.0g** (sensore in saturazione) — evento di impuntata registrato
- Il guidatore **non frena prima delle curve** — entra a velocità di crociera
- Accelerazione tipica: 0.2–0.5g

---

## 4. Superficie stradale (da vibrazioni IMU)

| Velocità | az stdev | Qualità strada |
|---|---|---|
| 0.3–1 m/s | 0.12 | Rumore sensore |
| 1–2 m/s | 0.22 | Texture leggera |
| 2–3 m/s | 0.35 | Vibrazioni moderate |
| 3–6 m/s | 0.39 | Vibrazioni alte |

Sessione 181452: az_stdev = 0.44 (strada ruvida) vs altre sessioni ~0.22.

**Per il training:** Rolling window az variance (2s) come feature di input. Il modello impara: vibrazioni alte → riduci velocità.

---

## 5. Curve

- **101 curve** nella sessione migliore (20 min)
- **Velocità in curva:** 2.09 m/s (7.5 km/h) — quasi uguale al rettilineo
- **Raggio minimo:** ~5.7m a 2 m/s
- **Nessuna frenata pre-curva** — il guidatore mantiene velocità costante

| Tipo curva | |gyro_z| | Velocità media |
|---|---|---|
| Dolce | 10–20°/s | 2.1 m/s |
| Moderata | 20–40°/s | 2.0 m/s |
| Stretta | 40–80°/s | 2.6 m/s |

---

## 6. Evento critico: impuntata

**18:22:02** — A 13 km/h (3.6 m/s):
- ax = **-2.0g** (sensore saturo, reale probabilmente > 2g)
- az = **-0.04g** (gravità scompare — ruote posteriori in aria)
- gyro_y = **+193°/s** (pitch violento in avanti)
- gyro_z = **-37°/s** (sterzata correttiva)
- Durata oscillazione: ~2 secondi

---

## 7. Limiti di sicurezza osservati

| Parametro | Osservato | Limite autonomo |
|---|---|---|
| Decelerazione max | -2.0g (saturo) | -0.5g normale, -0.8g emergenza |
| Velocità max | 19.9 km/h | 14.4 km/h |
| Gyro_z max affidabile | ~35°/s | |
| Gyro_z noise floor | ±22°/s (3-sigma) | Soglia curva: >22°/s |
| Steering rate a velocità | 340 enc/s | |
| Encoder travel | 2048–4095 | |

---

## 8. Correlazioni per il training

| Input → Output | r | Note |
|---|---|---|
| encoder → gyro_z | 0.26 | Non-lineare, forte solo sotto 2348 |
| speed → encoder variance | -0.22 | Più veloce = sterzo più stabile |
| speed → |gyro_z| | 0.08 | Debole — curve a qualsiasi velocità |

---

## 9. Ricetta di training

| Input modello | Cosa impara |
|---|---|
| encoder_pos → gyro_z | Funzione di trasferimento sterzo (non-lineare) |
| speed + encoder_pos | A velocità > 3 m/s, penalizza deviazioni > 200 counts |
| az rolling variance → target speed | Vibrazioni alte → riduci velocità |
| storia velocità (10 campioni) → ax | Frenata anticipatoria |
| [enc, speed, ax, gz, gx, gy, az] → next_enc | Behavioral cloning da 32k campioni |

**Sessioni prioritarie:** 181452 (20 min, più diversa) e 192955 (15 min, 80% in movimento).

---

## 10. Cosa manca per l'iterazione 002

- [ ] Calibrazione stereo migliorata (2560x800, 30+ foto, errore < 2%)
- [ ] Più ore di dati (servono ore, non minuti)
- [ ] Correlazione video ↔ sensori (il modello deve "vedere" la strada)
- [ ] Buzzer per follow-me
- [ ] Test follow-me con --dry-run
- [ ] Misura distanza frenata reale dai log

---

## Software Tools

Pipeline di training in `projects/asmile/training/`:

| Tool | File | Scopo |
|---|---|---|
| Frame Extractor | `frame_extractor.py` | Estrae frame video sincronizzati con CSV sensori, split stereo left/right |
| Depth Extractor | `depth_extractor.py` | Calcola mappe di profondita da coppie stereo con calibrazione e StereoSGBM |
| Training Dataset | `training_dataset.py` | Crea dataset (frame + depth + label) per behavioral cloning, split train/val |
| Visualizer | `visualizer.py` | Crea frame/video annotati con depth overlay, sterzo, velocita, frenata |
| Behavioral Cloning | `behavioral_cloning.py` | CNN proof-of-concept: input visivo + sensori -> sterzo + frenata (PyTorch/NumPy) |
| Shadow Analyzer | `shadow_analyzer.py` | Confronta predizioni modello vs guidatore umano, identifica edge case |

Dipendenze: Python 3, OpenCV, NumPy. PyTorch opzionale (necessario solo per il training).

---

*Asmile Shadow Mode — l'AI osserva, il guidatore guida. Un passo alla volta.* 🚲
