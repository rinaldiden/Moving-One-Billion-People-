# Storico flash: Arduino Uno ponte encoder (sterzo + ruota)

Regola: ogni modifica allo sketch → nuova `FW_VERSION` nello sketch, hex compilato in `hex/`,
riga qui sotto. Il flash si fa dal Pi con `pi/steering/flash_encoder_arduino.sh <hex>`, che
scrive anche lo storico locale `/data/firmware/flash_history.csv` e stampa la riga da incollare.
Compilazione sul Mac: `arduino-cli compile --fqbn arduino:avr:uno --output-dir <dir> amt22_dual_uno`.

## Versioni dello sketch
| versione | data | sketch / commit | formato riga USB | note |
|---|---|---|---|---|
| v1 | 2026-10-27 | `amt22_dual_uno.ino` @ 5a9c4822 | `sterzo,ruota` | bit-bang 2 encoder, ~880 Hz, nessun banner di versione |
| v2 | 2026-11-07 | `amt22_dual_uno.ino` + `hex/amt22_dual_uno_v2_20261107.hex` (sha256 416e048f5482c109…) | `sterzo,ruota,t_us` | `micros()` della misura → il bridge lo porta sull'orologio del Pi (stesso di camere e sensor_hub); banner `# amt22_dual_uno v2 2026-11-07 t_us` all'avvio |

## Flash eseguiti
| data e ora | unità | hex | sha256 (16) | commit | esito | versione letta |
|---|---|---|---|---|---|---|
| 2026-10-27 (circa) | asmile-tirano (#001) | v1, caricato da IDE | — | 5a9c4822 | OK (bridge 882 Hz) | — (v1 senza banner) |
| 2026-11-08 16:01:27 | asmile-tirano (#001) | amt22_dual_uno_v2_20261107.hex | 416e048f5482c109 | 0fb52d87 (repo Mac; sul Pi 1967cbf) | OK, verificato da avrdude | amt22_dual_uno v2 2026-11-07 t_us |
