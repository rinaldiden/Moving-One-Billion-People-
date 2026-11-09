# asmile-logger001 — velocità ruota BLE (CooSpo BK467) — 2026-11-09 — STATO: PRONTO, NON DEPLOYATO (manca ALLOW asmile-sicurezza)

Unità: asmile-logger001 (hostname asmile-logger, 100.83.200.55). Non vale per #001/asmile2 (nessun file toccato lì).

## Fatto sul Mac (provato)
- `pi/sensors/bike_speed_ble.py` (nuovo; `bike_speed_reader.py` di asmile2 intatto): bleak, CSC 0x2A5B, scrive
  `/tmp/bike_speed.json` atomico: t_ms = istante di ricezione con `time.monotonic_ns()//1e6` (identico a `hub_client.now_ms`
  = orologio frame/sensor_hub), `wheel_rev` e `wheel_evt` GREZZI, speed_ms, circ_m, circ_placeholder, mac.
  Riconnessione infinita; MAC in `/data/bike_speed_mac` (persistente), rescan per prefisso "BK6LS" dopo 3 fallimenti.
  Velocità a 0 dopo 3 s senza giri nuovi.
- Circonferenza: 1.576 m, fonte Daniele (messaggio capo 2026-11-09): stessa ruota di #001, metro 10 giri = 15.760 m.
  Va in `asmile_id.conf` (`BIKE_SPEED_CIRC_M=1.576` + commento con fonte). Senza chiave il reader usa 1.50 con `circ_placeholder=true`.
  I grezzi sono sempre loggati: si ricalcola offline.
- `sensor_hub.py`: 4 colonne IN CODA (dopo `evento`): `ble_t_ms, ble_wheel_rev, ble_wheel_evt, ble_speed_ms`; vuote se il file
  manca, è rotto o più vecchio di 3 s. Consumatori trovati (encoder_taratura_metro.py ecc.) leggono per NOME colonna: non si rompe.
  Schema resta asmile_sensors_v1 (colonne solo aggiunte). Diff: `agents/rapporti/logger001_ble_speed_sensor_hub.diff` (+20 righe).
- `config/bike_speed_logger.service`: root, After=bluetooth.target, Restart=always, enabled.
- `deploy/deploy_bike_speed.sh` (dry-run provato OK; `--rollback` incluso), chiude con registra_deploy.sh.
- Test: `python3 pi/sensors/test_bike_speed_ble.py` → OK (parse, wrap uint16 evt e uint32 rev, notifica ripetuta, stop a 0,
  file BLE assente/vecchio/rotto/fresco, header 52 colonne senza duplicati).

## Letture sul logger (sola lettura, online)
- bluetooth: active+enabled, hci0 UP RUNNING. Overlay attivo. bleak NON installato (python 3.13, aarch64).
- Plan: bleak 3.1.0 + dbus-fast 5.2.0 (wheel aarch64 cp313, provati in /tmp del Pi: import OK) in `~/logger/vendor`,
  copiati in live E /media/root-ro (niente apt sotto overlay, che si perderebbe al riavvio). Modifica persistente da dichiarare.
- ATTENZIONE: il logger STA REGISTRANDO (recorder.sh + rpicam-vid segmenti 30 s). Il deploy riavvia solo sensor_hub:
  nuovo CSV sensors_*, buco di ~3 s nei dati IMU. Recorder e /data/recordings non toccati (il capo sta scaricando).

## NON VERIFICATO / mancante
- Connessione reale al BK467 e righe CSV con ble_* piene: serve ruota che gira, dopo il deploy.
- ALLOW asmile-sicurezza: non ho lo strumento per interpellarlo da qui. Da chiedere col diff sopra + deploy_bike_speed.sh.
- Rollback provato: da fare una volta dopo il deploy (`deploy_bike_speed.sh --rollback`), poi ri-deploy.
