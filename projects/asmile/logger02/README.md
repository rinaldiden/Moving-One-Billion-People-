# logger02 (HW3) — 2 × Waveshare ESP32-P4-Module-DEV-KIT + 2 × OV9281 Inno-Maker

Porta del logger001 (Pi 5) su due ESP32-P4. Stesso firmware su A e B: il ruolo lo dà il MAC (`main/logger02_ruolo.c`).
Pin: `../logger/hw3/PIN_logger002.md`. Prove: `../logger/hw3/PROVA_20261117.md`.

| | A (master) | B (slave) |
|---|---|---|
| hostname | logger02a | logger02b |
| IP fisso EOLO | 192.168.1.122 | 192.168.1.124 |
| camera | sinistra | destra |

## Fatto (17/11/2026, verificato su A)
- Saluto "Narmade Har!" all'accensione (ES8311 sul bus I2C della camera, PA GPIO53)
- OV9281 riconosciuta (PID 0x9281), 1280×720 RAW8
- Wifi EOLO via C6 (ESP-Hosted SDIO), IP fisso; streaming web su http://<ip>/ (solo banco, non nei logger)

## Da fare (parità col logger001)
registrazione H.264 su SD a segmenti + CSV frame · trigger camere + misura latenza sync A↔B · IMU 50 Hz ·
batteria ADC + avviso Telegram · deep sleep + risveglio da INT IMU + autospegnimento 5 min · download dal Mac
(pull_from_loggers) · OTA via wifi · Tailscale (MicroLink) · BLE CooSpo · LED di stato

## FIRMWARE DEFINITIVO HW3 (Daniele 18/11/2026: «quello che abbiamo finito stamattina consideralo def per hw3»)
- È il firmware che gira su logger02 A e B dalle 08:19 del 18/11: `87dd0423-dirty Nov 18 2026 08:06:46`, codice = commit
  `fa457fc0` (tag git **`hw3-def-20261118`**): buffer wifi in PSRAM (crash risolto), guardia OTA 3 min + DNS, AE A→B,
  pipeline ISP Espressif spenta, deep sleep + risveglio IMU (provato da Daniele), batteria "non collegata".
- Set di flash congelato in `rilasci/HW3_DEF_20261118/` (bootloader, partizioni, ota_data, app + flash_args; SOLO sul Mac,
  dentro c'è la password del wifi), impronte in `HW3_DEF_20261118.sha256` (su git).
- `flasha_nuovo.sh` flasha QUESTO set (controlla le impronte); `REBUILD=1` ricompila solo per un firmware nuovo, che va
  prima provato sul logger di prova (regola ferrea, sotto).

## Flotta HW3: logger nuovo e aggiornamenti (18/11/2026, regola di Daniele)
- **Logger nuovo** (A e B attaccate al Mac col cavo, prima di montare): `bash logger02/flasha_nuovo.sh`
  → nome automatico (logger03, 04...), IP fisso crescente della sola A (la B prende il DHCP e lo dice alla A),
  identità scritta nella NVS "ident" (stesso firmware per tutti), MAC in `flotta.csv`, riga in `DEPLOY_LOG.md`.
  Attacca prima la A (quella con IMU e partitore), poi la B quando lo chiede. Poi: test (stato, voce, camere) e si monta.
- **Chiave Tailscale** del logger nuovo: generala dal pannello (monouso), `security add-generic-password -U -s
  claude-tailscale-loggerNN -a loggerNN -w`, prima del flash (entra nella NVS) o dopo con `chiave_tailscale.sh loggerNN`.
  Poi scrivi l'IP Tailscale nella colonna `tailscale` di `flotta.csv`.
- **REGOLA FERREA (Daniele 18/11, fino a nuovo ordine):** ogni modifica → commit + push → OTA **solo sul logger di
  prova di Daniele** (oggi logger02): `bash logger02/ota.sh`. Il resto della flotta **mai di mia iniziativa**: solo
  quando Daniele, dopo averlo provato e visto funzionare, lo ordina → `OK_DANIELE="..." bash logger02/ota_flotta.sh`
  (rifiuta se il logger di prova non gira già quel .bin). Firmware che tocca avvio/rete/sonno: prima UNA scheda col cavo.
- logger02 (montato prima della NVS "ident") resta riconosciuto dal MAC: niente da riflashare.

## Compilare
```
. ~/esp/esp-idf-556/export.sh        # ESP-IDF v5.5.6 (serve per P4 rev v3.x)
cd firmware
# password wifi dal Portachiavi, file NON su git:
PW=$(security find-generic-password -D 'AirPort network password' -a EOLO_378899 -w)
printf 'CONFIG_EXAMPLE_WIFI_SSID="EOLO_378899"\nCONFIG_EXAMPLE_WIFI_PASSWORD="%s"\n' "$PW" > sdkconfig.defaults.local
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.esp32p4;sdkconfig.defaults.local" set-target esp32p4
idf.py build && idf.py -p /dev/cu.usbmodemXXXX flash
```

## Segreti: mai nel firmware (17/11/2026, avviso GitHub secret scanning)
Un `CONFIG_...` di `sdkconfig` finisce in chiaro nel `.bin`. La chiave Tailscale era un CONFIG ed è finita su GitHub
dentro `rilasci/logger02_38fd492f-dirty.bin` (commit 02e5b2a3; chiave monouso già consumata → morta). Da allora:
- **chiave Tailscale nella NVS della A**, non nel firmware: `bash chiave_tailscale.sh` (legge il Portachiavi
  `claude-tailscale-logger02`, fa POST `/tskey`). Serve solo per registrare da capo la scheda: già registrata si
  ricollega con le chiavi macchina di MicroLink (NVS "microlink"), anche a chiave vuota.
- **`rilasci/` fuori da git** (`.gitignore`): i .bin restano sul Mac; il rollback vero è l'altra partizione OTA.
- **`ota.sh` controlla il .bin** con `controlla_segreti.sh` (chiavi `tskey-…` e valori di `sdkconfig.defaults.local`
  tranne il wifi) e si ferma se trova qualcosa.
- Pulizia della storia su GitHub: `purga_storia_bin.sh` (prova a secco di default; force push solo con `FIRMA=D015`).
