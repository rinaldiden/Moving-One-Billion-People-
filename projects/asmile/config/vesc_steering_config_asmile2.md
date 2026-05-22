# VESC Steering Config — asmile2

Snapshot della configurazione VESC che fa funzionare lo sterzo automatico su asmile2.
**Hall detection rifatta 2026-05-22** — la mappatura precedente era disallineata e il motore stallava sotto corrente.

## Hardware

- **Motore**: Flipsky 6354 140KV, BLDC outrunner, hall sensors integrati
- **VESC**: FSESC 6.7 Pro (chip DRV8301)
- **Encoder esterno**: Briter SSI 12-bit (4096 step/rev) sulla colonna di sterzo (NON sul motore — letto via SPI dal Pi)
- **Trasmissione**: rapporto motore↔colonna ~0.105 tach_motore / step_encoder (tipo 1:10)
- **Alimentazione**: pacco batteria ~46.5V

## Motor Settings → FOC → General

| Parametro | Valore | Note |
|---|---|---|
| `Sensor Mode` | Hall Sensors | NON sensorless. NON encoder. |
| `Motor Resistance (R)` | **46.8 mΩ** | detectato |
| `Motor Inductance (L)` | **55.86 µH** | detectato |
| `Motor Inductance Difference (Lq - Ld)` | **18.18 µH** | saliency positiva |
| `Motor Flux Linkage (λ)` | **5.037 mWb** | detectato |
| `Current KP` | 0.0544 | auto da R,L |
| `Current KI` | 42.36 | auto da R,L |
| `Observer Gain (x1M)` | 38.88 | default |

## Motor Settings → FOC → Hall Sensors (calibrazione 2026-05-22)

| Parametro | Valore |
|---|---|
| `Sensored ERPM Start` | **2500** (NON metterlo a 0! sotto 2500 ERPM = solo hall) |
| `Sensorless ERPM` | 4000 |
| `Hall Interpolation ERPM` | 500 |
| `Hall Table [0]` | 255 (sempre 255: hall=000 invalid) |
| `Hall Table [1]` | **38** |
| `Hall Table [2]` | **177** |
| `Hall Table [3]` | **15** |
| `Hall Table [4]` | **111** |
| `Hall Table [5]` | **76** |
| `Hall Table [6]` | **143** |
| `Hall Table [7]` | 255 (sempre 255: hall=111 invalid) |
| `Hall Sensor Extra Samples` | 3 |

Verifica validità: i 6 valori intermedi ordinati formano una sequenza ~equispaziata di 33 (60° elettrici): `15, 38, 76, 111, 143, 177` con delta `23, 38, 35, 32, 34`.

**Valori precedenti (sbagliati, all'origine dei stall del 2026-05-18)**: [1..6] = 108, 41, 74, 175, 141, 8. Numericamente plausibili (delta ~33) ma indici↔angolo scambiati rispetto alle motor phase → FOC produceva corrente senza coppia utile.

## Motor Settings → Current (limiti)

| Parametro | Valore |
|---|---|
| `Motor Current Max` | 43.46 A |
| `Motor Current Max Brake` | -43.46 A |
| `Absolute Maximum Current` | 65.19 A |
| `Battery Current Max` | 99.00 A |
| `Battery Current Max Regen` | -60.00 A |
| `DRV8301 OC Mode` | Current Limit |
| `DRV8301 OC Adjustment` | 16 |

## Encoder (presente in config ma INATTIVO — Sensor Mode è Hall)

| Parametro | Valore |
|---|---|
| `Encoder Offset` | 180.00 |
| `Encoder Ratio` | 7.00 |
| `Encoder Inverted` | False |

Questi valori sono lì perché qualcuno aveva sperimentato con encoder esterno sul VESC, ma non vengono usati con Sensor Mode = Hall Sensors.

## Software direction signs (verificati 2026-05-22)

In `projects/asmile/config/steering_limits.json`:

- `vesc_duty_sign_for_return = +1` (era -1 prima della nuova hall detection)
- `vesc_current_sign_for_hold = +1` (era -1)

Convenzione: con `error = pos - 3800`, `direction = -1 if error > 0 else +1`, il comando è
`target = SIGN * magnitude * direction`. Verificato: `error > 0` (DX) → corrente negativa → encoder diminuisce.

## Calibrazione finecorsa colonna

| Parametro | Valore |
|---|---|
| `encoder_center_raw` | 3800 |
| `encoder_sx_max_raw` | 3565 (∆ -235 step ≈ -20.66°) |
| `encoder_dx_max_raw` | 4046 (∆ +246 step ≈ +21.63°) |
| `tach_per_encoder_step` | 0.105 |

Software safety cut: `SAFETY_MARGIN = 20` step oltre i finecorsa fisici (3545 / 4066).

## Come ripristinare questo stato

1. In VESC Tool: importa una `.vescbackup` esportata da asmile2 (se ne fai una)
2. **Oppure**: setta a mano i valori sopra in:
   - `Motor Settings → FOC → General` (R, L, Lq-Ld, λ — o premi "Detect Motor R+L+λ" se vuoi rifare da zero)
   - `Motor Settings → FOC → Hall Sensors` → premi **"Detect Hall Sensors"** col motore al centro (gira di ±10°)
   - `Motor Settings → Current` (limiti come sopra)
3. Premi **"Write Motor Configuration"** (icona freccia su) per salvare in flash
4. Verifica con `pi/steering/vesc_hall_diag.py`: ruota il manubrio a mano, controlla che `tach_abs` cresca monotono e che `tach signed` segua la direzione dell'encoder.

## Bootstrap di una nuova Pi/VESC

Sequenza completa per setup da zero:
1. Connetti VESC Tool al VESC via USB
2. `Motor Settings → FOC → "Detect Motor R+L"` (motore può rimanere montato, NON gira)
3. `Motor Settings → FOC → "Detect Flux Linkage"` (motore gira di pochi gradi — sterzata al centro!)
4. `Motor Settings → FOC → Hall Sensors → "Detect Hall Sensors"` (gira ±10°, idem)
5. `Motor Settings → Current → Motor Current Max = 43A` (o quello che vuoi)
6. Imposta limiti app → Tab `App Settings → UART` → baud 115200, abilitato
7. **Write Motor Configuration** + **Write App Configuration**
8. Test con `pi/steering/vesc_return_to_center.py` da sterzata storta → verifica direzione
9. Se direzione sbagliata: cambia `CURRENT_SIGN` / `DUTY_SIGN` nello script e in `steering_limits.json`
