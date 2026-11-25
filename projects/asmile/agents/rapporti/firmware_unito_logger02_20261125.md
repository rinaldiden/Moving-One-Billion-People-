# logger02 — firmware unito "unito-25nov-2" (25/11/2026) — PRONTO, NON CARICATO

Il logger NON è stato toccato (nessuna connessione, regola di Daniele). Lavoro solo sul Mac e su git.

## Commit
| commit | cosa |
|---|---|
| `72cd868d` (tag `logger02-rete-25nov-1`) | sorgente ESATTO del firmware che gira su A e B (fix wifi, base ac6d8974). Verificato con `diff -r` identico ai sorgenti del build `~/esp/l02_rete/fw` (.bin sha256 `49cd6a318e93eda4ebbd387720fdbd22a7368b6eb2f74b87bd25f1d10ad09002`) |
| `c2efedaa` | merge su main: fix wifi + scarico affidabile e sveglia B (5793e906) + protezione 3 V (2f8cad2e). Unico conflitto in `logger02_imu.c` (dormi spezzato su main): blocco "riavvio pulito già in corso" messo in `logger02_dormi` e in `logger02_dormi_def` |
| commit DEPLOY_LOG | A 25/11 11:35/11:40 e B 25/11 11:49 su rete-25nov-1 |
| `ca91081e` | firmware unito (unito-25nov-1, superato): + task batteria 1 Hz separato dall'IMU, 3 bip a batteria scarica, conferma OTA prima del sonno per batteria, mutex del CSV IMU anche nel riavvio pulito e in `/dormi` |
| `e9ef5b83` | **taratura batteria definitiva** (Daniele 25/11): V = 1,025 × lettura + 0,01 al posto di 0,936 → versione **unito-25nov-2** |

## Il .bin
- versione `unito-25nov-2`, compilato da `git archive e9ef5b83` in `~/esp/l02_unito/fw` (cartella separata, ESP-IDF 5.5.6 `~/esp/esp-idf-556`; sorgenti verificati identici al commit)
- `logger02/rilasci/logger02_unito-25nov-2.bin` (rilasci/ è gitignored, verificato), 1 879 216 byte
- **sha256 `9eb7f80a845f09fea00340cfc07b9d30ab310b75b377fd4dd939c0f6651387b5`**
- `controlla_segreti.sh`: nessun segreto
- (superato: `unito-25nov-1`, sha256 7bc2819f…, con la taratura vecchia 0,936: NON usarlo)

## Test host (sul Mac)
`test_batt_logic` 35 ok (anche soglie in letture grezze con la taratura nuova), `test_rete_logic` 21 ok, `test_sleep_logic` 11 ok, `test_wake_logic` 10 ok, `check_batt_indipendente.sh` ok. Nessun fallimento.
Build: nessun avviso nuovo nei file toccati.

NON verificato: niente è stato provato sull'hardware (unione fix wifi + scarico + batteria mai girata su una scheda).

## Taratura batteria — DECISA (chiusa)
Daniele 25/11: **V_vera = 1,025 × lettura + 0,01** (`L02_BATT_PENDENZA`, `L02_BATT_OFFSET`, unico posto
`main/logger02_batt_logic.h`). Fonte: tester 3,24↔3,33 e 4,05↔4,16 V (TODO_capo 25/11 08:45) + confronto delle 14:03
(tester 4,0 V, logger 3,87 V). Spegnimento 3,0 V veri = lettura grezza ~2,917; avvio 3,1 V veri = grezza ~3,015.
Il punto 2,03↔1,90 (cella sovrascarica) è fuori retta e non entra. Resta non verificato sull'hardware.

## Procedura proposta quando dirai "carica"
1. Controllare lo sha256 del .bin (`9eb7f80a…`).
2. Solo la **A**: `SOLO=A BIN=logger02/rilasci/logger02_unito-25nov-2.bin bash logger02/ota.sh` (rollback automatico se la rete non torna).
3. Rollback pronto: `bash logger02/ota.sh rollback` (torna a rete-25nov-1 sull'altra partizione).
4. Confermare SOLO con rete funzionante (verifica a 4 min, `/api/stato` con la versione nuova); se la rete non torna, rollback.
5. La **B** solo dopo la tua prova della A, una scheda alla volta.
6. Registrare in DEPLOY_LOG.md e committare.
