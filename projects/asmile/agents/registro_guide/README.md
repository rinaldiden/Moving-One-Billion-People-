# Registro guide — come guida il pilota, per unità e sessione

Daniele 2026-11-13: i dati delle guide aumentano a ogni uscita; teniamo UN registro cumulativo per tutte le unità
(asmile #001 insegnante, asmile-logger001, altre Asmile) per confrontare come si è comportato il pilota anche in
situazioni che #001 non ha incontrato. Da qui si ricavano (e si rivalidano) le soglie di config/soglie_attuazione_<unità>.json.

- `frenate.csv`, `sterzate.csv`: un evento per riga, colonne `unita, sess, …, classe, fonte_v, qualita, origine`.
  `classe`: stop_umano / umano (pilota) · stop_limiter / limiter (servo o limiter attivo: NON è il pilota).
- `sessioni.csv`: una riga per sessione importata (metri, fonte della velocità, qualità, nota).
- Importare: `python3 training/eventi/registro_guide.py aggiungi --unita <u> --dir <out con frenate.csv/sterzate.csv> --fonte-v <encoder_ruota|ruota_ble|imu_video|gps> --qualita <alta|media|bassa>`;
  riepilogo: `python3 training/eventi/registro_guide.py riepilogo`. Rimportare una sessione la sostituisce.
- Per unità: #001 = encoder ruota + sterzo + IMU + freno (qualità alta). Logger = IMU + video (o ruota BLE), niente sterzo né freno:
  frenate da IMU/video (qualità media/bassa), sterzate solo da gz. Mai mischiare segni IMU fra unità (logger: frenata = ax positivo).
- Ogni importazione passa dal contro-agente asmile-event-scettico.
