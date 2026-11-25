# logger02 — firmware unito "unito-25nov-1" (25/11/2026) — PRONTO, NON CARICATO

Il logger NON è stato toccato (nessuna connessione, regola di Daniele). Lavoro solo sul Mac e su git.

## Commit
| commit | cosa |
|---|---|
| `72cd868d` (tag `logger02-rete-25nov-1`) | sorgente ESATTO del firmware che gira su A e B (fix wifi, base ac6d8974). Verificato con `diff -r` identico ai sorgenti del build `~/esp/l02_rete/fw` (.bin sha256 `49cd6a318e93eda4ebbd387720fdbd22a7368b6eb2f74b87bd25f1d10ad09002`) |
| `c2efedaa` | merge su main: fix wifi + scarico affidabile e sveglia B (5793e906) + protezione 3 V (2f8cad2e). Unico conflitto in `logger02_imu.c` (dormi spezzato su main): blocco "riavvio pulito già in corso" messo in `logger02_dormi` e in `logger02_dormi_def` |
| commit DEPLOY_LOG | A 25/11 11:35/11:40 e B 25/11 11:49 su rete-25nov-1 |
| `ca91081e` | firmware unito: + task batteria 1 Hz separato dall'IMU, 3 bip a batteria scarica, conferma OTA prima del sonno per batteria, mutex del CSV IMU anche nel riavvio pulito e in `/dormi` |

## Il .bin
- versione `unito-25nov-1`, compilato da `git archive ca91081e` in `~/esp/l02_unito/fw` (cartella separata, ESP-IDF 5.5.6 `~/esp/esp-idf-556`)
- `logger02/rilasci/logger02_unito-25nov-1.bin` (rilasci/ è gitignored, verificato), 1 879 200 byte
- **sha256 `7bc2819fa715c69bbd18411ef5bee113315e717acb40aa7101743b7be4a02a3d`**
- `controlla_segreti.sh`: nessun segreto

## Test host (sul Mac)
`test_batt_logic` 26 ok, `test_rete_logic` 21 ok, `test_sleep_logic` 11 ok, `test_wake_logic` 10 ok, `check_batt_indipendente.sh` ok. Nessun fallimento.
Build: nessun avviso nuovo nei file toccati.

NON verificato: niente è stato provato sull'hardware (unione fix wifi + scarico + batteria mai girata su una scheda).

## DECISIONE PER DANIELE (blocca il caricamento)
`L02_BATT_SCALA = 0.936` (in `main/logger02_batt_logic.h`) è lasciato com'è, ma in TODO_capo (25/11 08:45) è segnato
**SBAGLIATO**: con i tuoi 3 punti col tester, fra 3,2 e 4,2 V la lettura è quasi 1:1 (V ≈ 1,025 × lettura + 0,01).
Con 0,936 questo firmware **spegnerebbe a circa 3,2 V veri e rifiuterebbe l'avvio sotto circa 3,3 V**.
Va scelta la taratura (es. guadagno + offset dai 2 punti alti) prima di caricarlo. Non l'ho decisa io.

## Procedura proposta quando dirai "carica"
1. Prima sistemare la taratura batteria (sopra), ricompilare, rifare test host e sha256.
2. Solo la **A**: `SOLO=A BIN=logger02/rilasci/logger02_unito-25nov-1.bin bash logger02/ota.sh` (rollback automatico se la rete non torna).
3. Rollback pronto: `bash logger02/ota.sh rollback` (torna a rete-25nov-1 sull'altra partizione).
4. Confermare SOLO con rete funzionante (verifica a 4 min, `/api/stato` con la versione nuova); se la rete non torna, rollback.
5. La **B** solo dopo la tua prova della A, una scheda alla volta.
6. Registrare in DEPLOY_LOG.md e committare.
