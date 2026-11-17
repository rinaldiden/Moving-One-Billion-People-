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
