# Sterzo #001 lento e fluido — come comandare il VESC (2026-11-09)

Fonte primaria: codice vedderb/bldc **tag 5.02** (scaricato e letto: `mcpwm_foc.c`, `confgenerator.c`,
`datatypes.h`, `commands.c`, `encoder.c`, `hwconf/hw_60.h`, `mcconf/mcconf_default.h`). Numeri di riga = tag 5.02.
Nessun comando al motore, nessuna scrittura sul VESC in questa ricerca.

## Risposta corta
**Il loop resta sul Pi con l'AMT22 (opzione d), ma rifatto**: 200 Hz invece dei ~40 Hz reali di oggi, molla rigida
sul ritardo da un riferimento a trapezio + smorzatore + feedforward d'attrito appreso + dither solo da fermo.
**Nessun parametro VESC da scrivere** per questa via. Script: `pi/steering/sterzo_fluido_001.py` (`vai` / `tieni`).

## Le 5 opzioni, verificate sul codice 5.02

### (a) Speed PID interno (COMM_SET_RPM) — NO a 58 ERPM con gli hall
- `mcpwm_foc_get_rpm()` (r.1128) = `speed_rad_s` = **velocità della PLL** sulla fase (`pll_run`, r.3229; kp 2000 /
  ki 30000 di default). In modo HALL la fase viene da `correct_hall()` (r.3918).
- A 58 ERPM gli hall cambiano **5.8 volte/s (ogni 172 ms)**. `correct_hall` interpola a velocità costante
  `rad_per_sec = (π/3)/m_hall_dt_diff_last`, aggiornata solo a ogni transizione → la "velocità" del VESC è un
  segnale campionato a 5.8 Hz. Da fermo (stick) continua a interpolare alla velocità VECCHIA finché
  `max(dt_now, dt_last)` non supera la soglia di `foc_hall_interp_erpm` (con 20 ERPM: **0.5 s**) o finché l'errore
  supera 30° el. → lo speed PID non vede lo stacco/l'incollamento per centinaia di ms → limit cycle peggiore di oggi.
- Guadagni: `run_pid_control_speed` (r.3722) fa `iq = (err·kp/20 + ...)·l_current_max`. Con kp 0.004 un errore di
  58 ERPM dà **0.35 A**, ki 0.004 integra 0.35 A/s: per arrivare ai 10-12 A di stacco servono ~30 s.
- **Scoperta collaterale:** `s_pid_min_erpm = 900` (default `MCCONF_S_PID_MIN_RPM 900.0`). Sotto 900 ERPM il VESC
  azzera l'integratore (r.3742) e **forza duty 0 = frena** (r.2369). È per questo che
  `vesc_return_to_center_rpm.py` (TARGET_ERPM 150) non muoveva niente su asmile2: non mancavano i guadagni, il
  setpoint era sotto `s_pid_min_erpm`. 900 ERPM = ~155 deg/s al piantone di #001.

### (b) Position PID interno (COMM_SET_POS) — NO senza encoder sul VESC
- r.2737-2762: senza encoder configurato `angle_now = fase ELETTRICA` (0-360°) → la posizione si avvolge ogni giro
  elettrico = **10.4° di piantone**, risoluzione hall 60° el. = 1.7° piantone. `p_pid_ang_div` divide ma non dà
  posizione assoluta. Inutilizzabile.

### (c) AMT22 come sensore del VESC — NO con questo AMT22, SÌ come upgrade futuro con un altro encoder
- fw 5.02 legge AS5047 via SPI bit-bang a 20 kHz (`encoder.c` r.31, `encoder_tim_isr` r.609) e scarta i campioni con
  **parità pari su 16 bit** (`spi_check_parity`, r.598). L'AMT22 ha 2 bit di check dispari separati (K1 dispari/K0
  pari) e vuole ≥2.5-3 µs fra i byte: il frame non è AS5047, ~metà dei campioni verrebbero scartati e il timing non
  è garantito. In più: oggi l'AMT22 lo legge il Pi (serve alle sicurezze), è 12 bit reali (i log cambiano a passi di
  4 count = 0.088°), sta DOPO il riduttore (gioco × 35 in gradi elettrici).
- Il rapporto giusto NON sarebbe 1.4: `phase = enc_deg · foc_encoder_ratio` (r.2323) → 1 giro piantone =
  5 giri motore × 7 coppie = **foc_encoder_ratio 35**.
- Interessante per dopo: se un encoder è configurato, `angle_now = enc_ang` (r.2740) anche con `foc_sensor_mode`
  HALL → SET_POS lavorerebbe in gradi dell'encoder, e `COMM_GET_VALUES` restituisce `pid_pos_now` (commands.c r.369).
  Upgrade pulito: AS5047P/MT6816 magnetico sull'albero MOTORE (ratio 7) → VESC con speed/pos PID fino a ~0 rpm.
  Sul VESC6/FSESC6.x i pin hall (PC6-8) servono anche all'ABI, SPI su PA4-7 (hw_60.h r.225-258): verificare il
  connettore prima di comprare.

### (d) Loop sul Pi con SET_CURRENT — SÌ, ma fatto bene (RACCOMANDATO)
Cosa non andava nei log di oggi (`agents/prove/sterzo_001/sterzo_vel_20261109_163726.csv`):
- loop reale **40 Hz** (dt mediano 25 ms, non 100 Hz): GET_VALUES completo ~75 byte = ~6.5 ms di UART + attesa;
- velocità da finestra 50 ms → lo stacco si vede con 25-50 ms di ritardo, la spinta di stacco resta troppo a lungo;
- molla morbida (0.03 A/count = 1.4 A/deg) con anticipo fino a 3°: per vincere lo stacco (11 A vs 6.5 A in moto)
  la molla si carica di ~3°, poi scatta → **stick-slip a ~2 Hz di ampiezza ~3°**. Ampiezza scatto ≈ (I_stacco −
  I_moto)/KP (Armstrong-Hélouvry, "A survey of models, analysis tools and compensation methods for the control of
  machines with friction", Automatica 1994): si riduce solo con molla più rigida + smorzamento + loop più veloce.
Il nuovo script:
- 200 Hz; SET_CURRENT ogni ciclo (10 byte, 0.9 ms); corrente letta con **COMM_GET_VALUES_SELECTIVE (id 50) maschera
  bit 2** (corrente motore media) = 14 byte, 1 ciclo su 5; il VESC limita comunque a l_current ±30 A;
- velocità con filtro alfa-beta sui campioni encoder datati con l'mtime del file (~20 ms di ritardo);
- riferimento a trapezio (40 deg/s²), **KP 3 A/deg** (scatto residuo ≤ ~1.5° e frequente), KD 0.25 A/(deg/s),
  integrale ±3 A, **feedforward coulombiano I_COUL** (parte 6.5 A, appreso in moto), **dither ±1.5 A a 100 Hz solo
  quando dovrebbe muoversi ed è fermo** (rompe l'attrito statico senza farsi sentire);
- `tieni`: molla 6 A/deg (30 A a 5° di spostamento), soft-start 1 s, si sgancia oltre 10°, caldo >8 s sopra 20 A.

### (e) HFI / observer a bassa velocità — NO
HFI in 5.02 è per avviare motori sensorless (`foc_sl_erpm_hfi`, r.2479), con L = 18 µH la salienza è minima; non dà
risoluzione migliore degli hall a 58 ERPM e aggiunge rumore udibile. Con hall + AMT22 non serve.

## Parametri
**Via raccomandata: nessuna scrittura sul VESC.** Restano: l_current ±30, foc_hall_interp_erpm 20 (ok: sopra 20 ERPM
interpola → meno ripple di coppia a 58 ERPM).

Offset mcconf fw 5.02 (calcolati da `confgenerator_serialize_mcconf`, controllo: tornano 198/207/215/219/269 già
provati), per eventuale prova A/B della via (a) o per il futuro:

| campo | offset | tipo | oggi | solo per prova A/B SET_RPM |
|---|---|---|---|---|
| s_pid_kp | 329 | float32_auto | 0.004 | 0.05 (58 ERPM err → 4.4 A) |
| s_pid_ki | 333 | float32_auto | 0.004 | 0.5 (→ ~43 A/s) |
| s_pid_kd | 337 | float32_auto | 0.0001 | 0 |
| s_pid_kd_filter | 341 | float32_auto | 0.2 | 0.2 |
| s_pid_min_erpm | 345 | float32_auto | 900 | 20 |
| s_pid_allow_braking | 349 | u8 | 1 | 1 |
| s_pid_ramp_erpms_s | 350 | float32_auto | -1 | 200 |
| p_pid_kp / ki / kd / kd_filter / ang_div | 354/358/362/366/370 | float32_auto | — | non usare |
| foc_encoder_inverted / offset / ratio | 169/174(ratio) | u8 / float32_auto | — | 35 se encoder sul piantone, 7 sul motore |
| foc_sensor_mode | 198 | u8 | 2 (HALL) | invariato |
| foc_pll_kp / ki | 199 / 203 | float32_auto | 2000/30000 | invariati |
| m_sensor_port_mode | 406 | u8 | — | AS5047 solo con encoder compatibile |

Blob totale 457 byte dopo la firma inclusa. Se si fa la prova A/B: estendere `vesc_mcconf_limiti_001.py` con questi
offset, stessa procedura (backup, diff, vai a mano, rilettura) e poi **ripristinare il backup**.

## Piano di prova (3 passi, bici sul cavalletto, ruota anteriore a terra come oggi)
1. `python3 pi/steering/sterzo_fluido_001.py vai --target <centro-20°> --vel 5 --imax 20 --dry-run`, poi senza
   `--dry-run`. Guardare nel CSV: `v_est` deve stare 3-7 deg/s senza tornare a 0 ogni 0.5 s; frequenza cicli ≥180 Hz
   (stampata a fine). Se vibra/ronza: `--kp 2 --dither 0.8`.
2. Stesso a `--vel 10` e `--vel 20` andata e ritorno al centro (`vai` senza target). Se c'è ancora scatto: `--kp 4`.
3. `tieni --imax 15 --durata 15`: Daniele spinge il manubrio a mano piano; poi `--imax 30`. Nel CSV: `i_cmd` vs
   `lag_deg` deve dare ~6 A/deg; si sgancia da solo oltre 10°.
Opzionale dopo: A/B SET_RPM con la tabella sopra, solo per confermare sul banco che con gli hall è peggio.
