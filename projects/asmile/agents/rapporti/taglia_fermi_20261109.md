# taglia_fermi 20261109 (asmile-logger-ingest)

Strumento: `loggers/taglia_fermi.py`, agganciato in `loggers/on_new_videos.sh` PRIMA della percezione (la percezione usa i video "solo movimento" se esistono, altrimenti il grezzo; errore del taglio = grezzo). Uscita in `asmile-loggers/_solo_movimento/<unita>/<sessione>/` (index.json, frames CSV ritagliati con colonna `orig_frame`, video, metrics.npz). Grezzi MAI toccati. Idempotente (firma ingressi; seconda corsa 0.2 s).

Regola: fermo = (velocita' encoder #001 / BLE logger < 0.3 m/s) E IMU quieta (std 1 s: acc somma 3 assi < 0.03 g, gyro < 1.5 dps) E scena immobile (< 3 blocchi 10x10 su 160 con diff > 12/255 vs frame -0.2 s, finestra 1 s) per >= 5 s; margine 1 s attorno al movimento. Scena che si muove con bici ferma = TENUTO. Sensori assenti = solo diff frame (dichiarato nell'indice). Sensori scelti per file con wall coerente con l'inizio sessione (t_ms e' monotonic dal boot: boot diversi si sovrappongono).
Calibrazione: nome calib/metro, file `NON_TAGLIARE`, `loggers/non_tagliare.txt`, o pattern soste regolari -> non si taglia e si scrive nel log.

| sessione | durata | tagliato | tenuto | note |
|---|---|---|---|---|
| #001 session_20261109_093216 (metro) | 301.5 s | 0.0% | tutto | NON TAGLIATA (marcatore + non_tagliare.txt) |
| #001 session_20261109_093909 | 27.1 s | 0.0% | tutto | nessun fermo >= 5 s; 406 frame decodificati vs 408 righe csv (ultimi 2 non decodificabili, errore h264 nel grezzo) |
| #001 session_20261109_094146 | 671.1 s | 3.6% (24.3 s, 4 tratti) | 5 tratti | in gran parte in moto (vel_max 5.3 m/s, 58% frame sopra 0.3 m/s) |
| logger001 clip_20261109_085836 | 1349.3 s | 85.0% (1147.5 s) | 201.6 s (0-202 s) | dopo 202 s IMU quieta e scena immobile fino a fine; solo IMU (niente BLE/enc in questo file) |

Verifiche: video tagliato = righe del csv ritagliato (#001 sx=dx=9702 frame; logger 3025); sx/dx tagliati con gli stessi intervalli t_ms.
Limiti dichiarati: (1) logger: 20460 frame decodificati vs 20239 righe csv (csv scaricato prima della fine, ultima riga parziale scartata) -> ultimi ~221 frame fuori dalla sessione elaborata, allineamento per indice assumendo nessun frame perso nei chunk; (2) tenuti 202 s sul logger, non ~60 s: 0-60 s mano, 60-200 s attivita' IMU/scena intermittente, tenuti per prudenza; (3) soglie tarate a occhio su queste 4 sessioni, da riverificare con altre; (4) il re-encode x264 crf 18 dei video tagliati e' una ricompressione (i grezzi restano per chi vuole il bit-exact); (5) sessioni intera ferme -> nessun video, percezione le salta.
