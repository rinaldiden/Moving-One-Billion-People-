# Metodo unico di registrazione: camere e sensori sullo stesso ms (flotta + logger)

Deciso da Daniele il 2026-11-07. Vale per asmile #001, asmile2 e asmile-logger: stessi segnali,
stesso passo, stesso formato.

## Regole
1. **Un solo orologio**: `t_ms` = CLOCK_MONOTONIC del Pi in millisecondi. È quello dei frame
   camera (SensorTimestamp di libcamera), dei campioni encoder (bridge Arduino) e del sensor_hub.
   `wall` (ora reale) serve solo a leggerla.
2. **Un solo CSV sensori** per unità, scritto da `pi/sensors/sensor_hub.py`: **una riga ogni
   20 ms** a scadenza fissa (50 Hz, senza deriva).
3. **GPS a 10 Hz**: i campi `gps_*` sono pieni solo nella riga in cui arriva un fix nuovo, cioè
   ogni ~5 righe. `gps_t_ms` = arrivo del fix, `gps_utc` = istante del fix secondo il GPS.
4. **Stesse colonne ovunque** (`asmile_sensors_v1`): un sensore assente lascia la colonna vuota.
5. **Frame**: `frames_<cam>.csv` (`frame,t_ms,sensor_ts_ns,…`) accanto a ogni video. Unione
   frame↔sensori: la riga del hub con `t_ms` più vicino è entro 10 ms.

## Chi scrive cosa
| processo | prima | con `SENSOR_HUB=1` |
|---|---|---|
| sensor_hub (nuovo, systemd) | — | CSV unico 50 Hz in `/data/logging/sensors/` (+ `.json` con orologi, dispositivi, firmware encoder), stato live `/dev/shm/asmile_hub.json` |
| speed_limiter | CSV proprio 10 Hz, GPS da UART3 | stato freno a 50 Hz in `/dev/shm/asmile_limiter.json` → colonne `lim_*`/`brake_*`; GPS dal hub (ripiega su UART3 se il hub è fermo > 3 s) |
| servofreno_server (#001) | CSV training ~9,3 Hz, GPS da UART3 | solo pulsante freno; GPS dal hub; evento `FRENATA_TELEFONO_ON/OFF` nel CSV |
| training_recorder (asmile2) | CSV 10 Hz + VESC | solo video + `frames.csv`; VESC nel hub (`HUB_VESC=1`) |
| dual_cam_recorder (#001) | pts relativi | + `frames_left.csv` / `frames_right.csv` |
| recorder.sh (logger) | solo clip | + `clip_<STAMP>_frames.csv` (numerazione continua fra i segmenti) |
| bridge encoder | ora di arrivo USB | `micros()` dell'Arduino portato sull'orologio del Pi (sketch v2, vedi `firmware/steering/FLASH_LOG.md`) |

Senza `SENSOR_HUB=1` in `~/asmile_id.conf` tutto resta come prima: si attiva unità per unità.
Se `rpicam-vid` non ha `--metadata`, i recorder registrano come prima, senza frames csv.

## Uscite: cosa viene deciso e cosa parte verso freno e sterzo
Ogni comando a un attuatore viene timbrato nell'istante in cui parte verso l'hardware
(`pi/sensors/actuator_log.py`, chiamato subito dopo la scrittura):
| chi | cosa | riga |
|---|---|---|
| speed_limiter | PWM al servo freno (angolo, duty), stop PWM + pin libero | `brake,pwm,<deg>` / `brake,free,<deg>` |
| master_switch | pulse di rilascio all'ON, pulse 60° all'OFF | `brake,pwm/free,…,master_switch …` |
| servofreno_server | richiesta frenata dal telefono | `brake,phone_flag,1/0` |
| route_replay | richiesta freno (ora max 60°, prima 95°) | `brake,request,<deg>` |
| steering_controller / power_steering / route_replay | corrente VESC su UART0 (200 Hz) | `steer,set_current,<A>` |

Il hub le scrive **tutte** in `actuators_<sessione>.csv` (stesso nome e stesso `t_ms` del CSV
unico; provato: 565/565 comandi sterzo a 200 Hz e 8/8 freno, anche con rotazione del file).
Nel CSV unico: `brake_out_*` = ultimo comando freno con il suo istante, `steer_out_*` = ultimo
comando sterzo, numero e media dei comandi nei 20 ms, `evento` = tutti i comandi freno della riga.
Decisione del limiter: `lim_*`, `brake_target_deg`, `brake_cmd_deg` con `lim_t_ms` del suo tick.
INA219 (corrente servo freno) letta subito dopo l'IMU nella stessa riga: entro ~1 ms da `t_ms`.
VESC: un solo padrone della UART0. Con lo sterzo acceso la telemetria la pubblica lui
(`/dev/shm/asmile_vesc.json`, `vesc_t_ms`); prima su asmile2 il recorder interrogava il VESC
in contemporanea allo sterzo, sulla stessa seriale. Telemetria (rpm, duty, correnti, tensione,
fault = cosa ESEGUE) a **50 Hz**, una per riga da 20 ms: la richiesta parte ogni 4 tick del
loop a 200 Hz e la risposta si raccoglie nei tick dopo, senza fermare il loop (prima: 10 Hz e
15 ms di attesa bloccante a lettura). Pacchetti accettati solo con CRC giusto.

## Colonne `asmile_sensors_v1`
`t_ms, wall, imu_ax_g, imu_ay_g, imu_az_g, imu_gx_dps, imu_gy_dps, imu_gz_dps,
enc_t_ms, enc_wheel_cum, enc_wheel_raw, enc_steer_raw, servo_v, servo_ma,
lim_t_ms, lim_source, lim_zone, lim_speed_ms, lim_accel_ms2, lim_error_ms, brake_target_deg, brake_cmd_deg,
brake_out_t_ms, brake_out_cmd, brake_out_deg, steer_out_t_ms, steer_out_a, steer_out_n, steer_out_mean_a,
vesc_t_ms, vesc_rpm, vesc_duty, vesc_i_motor, vesc_i_in, vesc_v_in, vesc_tach, vesc_fault,
gps_t_ms, gps_utc, gps_fix, gps_lat, gps_lon, gps_speed_ms, gps_heading, gps_sats, gps_hdop, gps_alt_m, evento`

`enc_t_ms` e `lim_t_ms` sono gli istanti VERI di quei campioni (possono precedere `t_ms` di
qualche ms). IMU con filtro passa-basso a ~21 Hz (anti-aliasing per i 50 Hz, ritardo ~8,5 ms).

## Deploy
`bash deploy/deploy_sensor_hub.sh 001|asmile2|logger [--dry-run]`, a interruttore **OFF**:
backup `.bak-<data>`, copia in root viva + root vera sotto overlay, unità systemd, `SENSOR_HUB=1`.

## Verifiche da fare sul Pi al primo avvio
- passo delle righe: mediana 20 ms, `late_ticks` ~0;
- GPS: `gps_config` = ACK e righe GPS ogni ~5 (se il NEO-M10 non regge 10 Hz con 4 costellazioni,
  si riducono le costellazioni);
- camere: `first_rx_minus_sensor_ms` positivo e piccolo (10–80 ms) → SensorTimestamp è davvero
  CLOCK_MONOTONIC; `boottime_minus_monotonic_s` ~0;
- encoder: `encoder_fw` = v2 dopo il flash; `t_ms - enc_t_ms` di pochi ms.
