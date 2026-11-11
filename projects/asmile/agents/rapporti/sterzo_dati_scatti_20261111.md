# Sterzo #001 — dati per togliere gli scatti (2026-11-11)

Script: `pi/steering/sterzo_vel_daniele_001.py` (COMM_SET_RPM ogni 10 ms). VESC fw 5.2, HW60, sensori HALL.

## Log CSV (corse tipiche, 20 deg/s, bici ferma)
`agents/prove/sterzo_001/vel_daniele_20261111/`: colonne `t,pos,v_enc,v_set,erpm,i_mot,i_batt,v_batt,t_fet,t_mot`

| file | corsa | v media | oscillazione | I media/max |
|---|---|---|---|---|
| sterzo_vel_20261111_151836_daniele.csv | 5192→6600 DX | 13.3 deg/s | 44% | 2.9 / 6.7 A |
| sterzo_vel_20261111_151840_daniele.csv | 6600→5300 SX | 13.8 | 35% | 1.8 / 4.8 |
| sterzo_vel_20261111_151844_daniele.csv | 5300→7800 DX | 14.2 | 50% | 3.1 / 7.4 |
| sterzo_vel_20261111_151849_daniele.csv | 7800→6600 SX | 15.0 | 33% | 2.0 / 4.9 |

Corsa a 6-10 deg/s: da registrare (serve il vai di Daniele).

## Encoder sterzo (AMT22 sul piantone)
- 16384 count/giro → `sf.DEG` = 360/16384 = **0.02197 deg/count** (risoluzione reale: a 20 deg/s cambia ogni ~2 cicli da 2.6 ms; letto via Arduino USB → `/tmp/encoder_steer`).
- Riduzione motore→piantone **1:5**, motore 7 coppie polari → **35 giri elettrici per giro di manubrio = 468 count per giro elettrico**; 1 tach (passo hall, 60 deg el.) ≈ 78 count ≈ 1.7 deg di manubrio.
- 20 deg/s al manubrio = **117 ERPM**: a questa velocità arriva un fronte hall ogni ~85 ms.
- **Gioco meccanico**: misurato oggi col campo a fase fissa, al cambio di verso il piantone resta fermo per ~20-40 count (0.4-0.9 deg di manubrio, ~15-30 deg el.) prima di muoversi. Elastici: nessuno noto.
- Limiti software 4500/8700, finecorsa veri 4304/8884, centro 6606. Encoder SCENDE verso SX.

## Comportamento osservato (dai log a 20 deg/s)
- **Partenza**: il manubrio resta indietro di 9-10 deg/s rispetto al comando nei primi 0.4 s (rampa).
- **A regime**: non arriva a 20: resta 5-7 deg/s sotto e oscilla di ±5-7 deg/s a **~2.5-3 Hz**. A 14 deg/s il motore fa 1.36 giri elettrici al secondo → 2.7 Hz = **2 oscillazioni per giro elettrico**: legate alla posizione elettrica (hall), non alla meccanica.
- **Avvicinamento**: oscillazione uguale o maggiore (sd 5-10 deg/s), arriva comunque entro 0.2-0.35 deg.
- **Inversione**: ogni corsa parte da ferma; nessun cambio di verso dentro una corsa.
- Con il controllo in corrente (sterzo_fluido) stessa firma: verso DX 10-15%, verso SX 27-46% con 2 picchi per giro elettrico.

## Parametri VESC attuali (mcconf letta oggi 15:18)
| | valore |
|---|---|
| foc_current_kp / ki | 0.01828 / 29.82 |
| foc_observer_gain | 5.75e8 (observer_type 0) |
| foc_pll_kp / ki | 2000 / 30000 |
| foc_sensor_mode | 2 = HALL, foc_hall_interp_erpm 20, m_hall_extra_samples 1 |
| foc_hall_table | 23, 93, 59, 159, 191, 125 (scala 200 = 360) |
| foc_motor_r / l | 29.8 mOhm / 18.3 uH (misurati: 29.0 / 19.5) |
| foc_motor_flux_linkage | **1.318 mWb (sbagliato: misurato 5.43 mWb)** |
| foc_f_sw | 25 kHz, foc_cc_decoupling 2 |
| s_pid_kp / ki / kd | 0.02 / 0.02 / 0.0001, kd_filter 0.2 |
| s_pid_min_erpm / ramp | 10 / 400 ERPM/s, allow_braking 1 |
| l_current_max/min | ±30 A |
