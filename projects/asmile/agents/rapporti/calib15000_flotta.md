# Calibrazione a 15.000 unita: angolo FLOTTA / PROCESSO

Autore: asmile-flotta, 2026-11-09. Solo progetto, nessun Pi toccato. NON VERIFICATO sul campo: e' un disegno.

## Idea in una frase
La calibrazione diventa un DATO legato al modulo camere: si fa UNA volta in fabbrica su un banco fisso, vive scritta DENTRO il modulo (e in copia centrale), e a ogni accensione il Pi controlla da solo che la calib sia di quelle camere. L'operatore RSA vede solo un semaforo.

## Punto di partenza (cosa c'e' oggi)
- Un file per unita: `logger/depth/calib_asmile-001.json`, `calib_asmile-logger.json` (+ varianti `_metro`, `provvisoria-scena`). Il nome file e' l'unico legame unita-calib: nessun seriale camere, nessuna versione, nessun controllo.
- `drift_monitor.py` (usage riga 14: `--video clip.h264 --calib calib_logger.json --thresh 0.5`) misura gia' la deriva da un clip: e' la base del controllo di salute. `Calib.load` in `stereo_common.py:45`.
- `deploy/registra_deploy.sh` fotografa config + commit + push: gia' il meccanismo di registro per i deploy.
- Lezioni: calib vale solo per unita + set camere (`feedback_calib_per_unit`); 001 e logger hanno hardware diverso (2 OV9281 separate vs Camarray SBS). Il veto del 2026-11-09 su `calib_asmile-001.json` (`agents/lezioni/asmile-calib.md`) mostra che una calib va anche VERIFICATA su punti non usati nel fit: il registro deve contenere l'esito della verifica, non solo il file.

## Principio: il modulo camere e' l'unita di calibrazione
Calibrare "la bici" e' sbagliato: cio' che conta e' la coppia di camere + il supporto rigido. Quindi:
- si assegna un **ID modulo** (es. `MOD-000123`) stampato su targhetta + QR sul supporto delle camere;
- la calib appartiene al modulo, non al Pi, non alla bici;
- Pi e bici sono sostituibili; il modulo calibrato viaggia con la sua calib.

Due varianti hardware diverse = due "tipi modulo" con codice diverso (`TIPO-A` = 2 camere separate, `TIPO-B` = Camarray SBS). Il tipo e' dentro l'ID e dentro il file: un file di tipo A non si carica mai su un modulo di tipo B (rifiuto, non fallback).

## Dove vive la calib (3 copie, 1 verita)
1. **Sul modulo** (verita operativa): una piccola EEPROM I2C (tipo 24C32, pochi euro) sul modulo camere, oppure se non c'e' spazio una micro-SD/flash piccola. Contiene: ID modulo, tipo, seriali camere, versione, calib compressa, hash. Cosi' il modulo di ricambio arriva "gia' calibrato" e il Pi lo legge appena collegato. Alternativa piu' semplice se EEPROM non si puo': file sul Pi in `/data` + QR sul modulo che porta all'ID (vedi sotto, meno robusto).
2. **Sul Pi** (cache): copia in `/data/calib/calib_<ID modulo>.json` (la partizione scrivibile, il resto e' overlay read-only). Serve per partire anche se la EEPROM e' lenta.
3. **Copia centrale** (backup + registro): repo/cartella centrale privata dei file `calib_<ID modulo>.json`. Mai su git pubblico con video; i JSON di calib sono piccoli e senza dati personali, quindi ok.
Regola di conflitto: vince quella con versione piu' alta E hash valido; se EEPROM e cache differiscono si usa la EEPROM e si riscrive la cache.

NOTA: la EEPROM e' una proposta mia, NON verificata (bus I2C libero, cablaggio sul tipo B con 1 CSI). Va provata prima su 1 modulo.

## Registro (una tabella sola)
CSV/SQLite centrale `registro_moduli`, una riga per evento:

| campo | esempio |
|---|---|
| id_modulo | MOD-000123 |
| tipo | A (2xOV9281 separate) / B (Camarray SBS) |
| seriale_cam_sx, seriale_cam_dx | numeri sensore letti da libcamera |
| id_bici (oggi) | ASM-0457 |
| id_struttura (RSA/centro) | RSA-xxxx |
| versione_calib | v3 |
| hash_calib | sha256 corto |
| data_calib, banco_id | |
| esito_verifica | depth err% a 2-5 m, dy max nelle 9 zone |
| stato | in_uso / ricambio / scartato |

Ogni scambio di modulo = nuova riga; la tabella "chi e' dove" si ricostruisce dall'ultima riga per id_modulo. Riuso: stessa filosofia di `registro_deploy`/`palla.py registro.jsonl` (append-only).

## Controllo automatico all'accensione ("la calib e' di queste camere?")
Il Pi, prima di far partire percezione (e prima di qualunque uso della depth per freno/sterzo), fa 4 controlli veloci (secondi, nessun video):
1. **Seriali**: legge i seriali dei sensori camera (libcamera li espone; DA VERIFICARE per OV9281 Inno-Maker e per Camarray) e li confronta con quelli scritti nella calib. Diversi = ROSSO "camere non corrispondono".
2. **Tipo**: tipo hardware rilevato (2 camere separate o 1 CSI SBS) = tipo nella calib, altrimenti ROSSO.
3. **Hash/versione**: il file non e' corrotto e la versione e' quella attesa dal software (formato). Altrimenti ROSSO.
4. **Risoluzione/modo camera**: 1280x800 (A) o 2560x800 (B) come da calib.
Se tutti ok: VERDE-calib. Se uno fallisce: la depth NON parte (mai fallback su altra calib), il sistema resta in modalita' sicura (solo logging, niente decisioni da depth). Questa e' la regola "mai fallback" resa automatica.

## Controllo di salute "dolce" (deriva)
I seriali non vedono un urto che sposta una camera. Serve un controllo geometrico leggero, senza metro e senza laptop:
- **Cartello fisso da inquadrare** (idea di Daniele): un pannello con ChArUco/AprilTag stampato, fissato a muro nella stanza di ricovero o sul punto di ricarica, a distanza fissa. La bici, quando e' parcheggiata/in carica, lo inquadra per 5-10 secondi. Il Pi misura: (a) dy tra sx e dx sui corner (deve essere < 1 px), (b) distanza stimata dal cartello vs distanza nota (entro 2%). Costo zero per l'operatore: succede da solo alla ricarica.
- Senza cartello: `drift_monitor.py` su un breve clip di scena normale (scarto dy mediano > soglia 0.5 px = giallo). Meno affidabile; solo come ripiego.
- Il cartello si usa anche come **verifica finale dopo sostituzione**: il modulo nuovo e' ok solo se passa il cartello.
Limite: il cartello fisso controlla a UNA distanza; non sostituisce la verifica 1-15 m in fabbrica. Per questo la fabbrica resta il luogo della calibrazione, RSA solo del controllo.

## Semaforo per l'operatore RSA
Un LED/schermo/avviso sulla bici (o il buzzer gia' presente) con 3 stati, e basta:
- **VERDE**: calib di queste camere e deriva ok. Si usa.
- **GIALLO**: deriva sopra soglia o cartello non visto da piu' di N giorni. Si puo' usare ma si chiede "inquadra il cartello" (30 s).
- **ROSSO**: camere non corrispondenti, calib corrotta o deriva forte. Bici in modalita' sicura (non guida autonoma). Azione unica: "chiama assistenza / sostituisci il modulo con quello di ricambio".
Il rosso scrive anche un evento (id bici, id modulo, motivo) che arriva alla centrale appena c'e' rete. Nessun codice, nessun numero da leggere per l'operatore.

## Sostituzione camera o modulo in RSA ("scambio a caldo")
Regola semplice: **non si cambia mai una camera sola, si cambia il MODULO intero**. Una camera singola sostituita invalida la calib (focale, distorsione, relativa) e la lezione dice che servirebbe ricalibrare.
Passi per l'operatore (tutti a bici SPENTA, spegnimento fatto da Daniele/personale autorizzato, mai da agente):
1. Prendi il modulo di ricambio dalla scatola (arriva gia' calibrato, con ID e QR).
2. Stacca il vecchio (connettori camera + fissaggio), monta il nuovo nello stesso supporto, stessa orientazione (il supporto ha chiavi meccaniche: un solo verso possibile).
3. Accendi. Il Pi legge la EEPROM del nuovo modulo, confronta seriali/tipo/hash.
4. Inquadra il cartello fisso 10 s. Semaforo VERDE = fatto.
5. Scansiona il QR del modulo e della bici (app/telefono): la centrale scrive la riga di scambio nel registro. Il vecchio modulo va nella scatola "da rispedire" col suo QR.
Se il semaforo e' ROSSO dopo lo scambio: ricambio difettoso o montato male; si prova un altro ricambio.
Il modulo rientrato in fabbrica viene testato: se la calib regge ancora (verifica banco) torna "ricambio", altrimenti ricalibrato con nuova versione.
Pro: nessuna calibrazione in RSA. Contro: serve un magazzino di moduli di ricambio (stima scorta: da dimensionare sul tasso di guasto, NON noto oggi).

## Come non confondere le unita (lezione logger vs #001)
1. **Tipo modulo dentro l'ID e dentro il file**, rifiuto automatico se non coincide col rilevato.
2. **Mai fallback**: se manca la calib giusta la depth non parte (oggi basta un nome file sbagliato per usare quella dell'altra unita).
3. **Il nome del file e' l'ID modulo**, non il nome della bici: `calib_MOD-000123.json`. Le bici cambiano moduli, i moduli no.
4. **Un solo registro**, niente altre tabelle "chi ha cosa".
5. **Test CI sul repo**: un test che fallisce se un file calib manca di campo `tipo`, `seriali`, `versione`, `hash`, o se il tipo non e' tra quelli noti.
6. **Targhetta + QR su ogni modulo**, tipo scritto in chiaro (A/B) e colore diverso per i due tipi.
7. I numeri di validazione (errore depth, dy) stanno NEL file calib: "validato" non si trasferisce a un'altra unita perche' e' legato all'ID.

## Processo in passi numerati (ciclo di vita)
Fabbrica (una volta per modulo, tecnici):
1. Assembla modulo (camere + supporto rigido + EEPROM), assegna ID, stampa targhetta/QR.
2. Metti sul banco fisso (cartello grande + distanze note, vedi gli angoli della ricerca sul banco): acquisisce, calcola calib, verifica su punti NON usati nel fit (regola del veto), controllo dy sulle 9 zone.
3. Se passa (depth <= 2% sotto 5 m, dy < 1 px in tutte le zone) scrive calib in EEPROM + copia centrale + riga di registro. Se non passa: scarto o ricalibra, mai spedisci.
4. Il modulo va in scatola ricambi o montato su una bici.
Installazione in RSA (non tecnici):
5. Monta il modulo (chiavi meccaniche), accendi, semaforo.
6. Inquadra il cartello fisso; verde = ok.
7. Scansiona QR bici+modulo.
Vita normale:
8. Ad ogni accensione: controllo seriali/tipo/hash (secondi).
9. Ad ogni ricarica: controllo cartello (dy, distanza).
10. Giallo/rosso: azione unica (inquadra / sostituisci modulo).
Centrale:
11. Cruscotto: bici in rosso/giallo, moduli per versione, ricambi disponibili. Un rosso su molti moduli della stessa versione = problema di processo, non di singole bici.

## Cosa NON risolve questo angolo
- Come calibrare bene in fabbrica ai bordi (angolo altri agenti: banco, modello distorsione, tunnel virtuale).
- La precisione di per se: dipende dal banco; qui si gestisce solo il dato.
- Urti e deriva lenta: il cartello li rileva ma solo a una distanza e con soglia da tarare su dati reali (NON VERIFICATO).
- Se i seriali dei sensori sono leggibili sulle camere reali: da controllare (lettura in sola lettura, nessun intervento sul Pi).
- Il rischio normativo/sicurezza del rosso in strada: serve firma di Daniele in `DECISION_LOG.md` prima di legare qualunque decisione di guida al semaforo.

## Rischi
- EEPROM non fattibile sul tipo B (1 CSI) -> ripiego: calib sul Pi + QR, con piu' rischio di scambio.
- Falsi rossi che fermano bici in RSA: soglie da tarare, il rosso deve essere raro.
- Scorta ricambi costosa a 15.000 unita se i guasti sono alti.
- Cartello fisso spostato/sporco = falsi gialli: va fissato con tacche e un controllo "cartello visto bene".
- Singolo punto di errore nel registro: backup e append-only.
- Modulo ricambio rimasto in magazzino per mesi: la calib e' invecchiata? Prevedere ricontrollo cartello prima della spedizione.

## Stima costi e tempi (ordine di grandezza, NON misurati)
- EEPROM + etichetta/QR: pochi euro per modulo.
- Cartello fisso stampato rigido: pochi euro per struttura.
- Tempo operatore per scambio: 10-15 min stimati; controllo cartello 10 s.
- Software (controllo all'accensione, registro, semaforo): alcuni giorni di lavoro, riuso `drift_monitor.py` e `registra_deploy.sh`.

## Fonti
- Codice e lezioni interni: `logger/depth/drift_monitor.py:14`, `logger/depth/stereo_common.py:45`, `deploy/registra_deploy.sh`, `agents/lezioni/asmile-calib.md`, memoria `feedback_calib_per_unit`, `project_fleet_timestamp_method`, `project_standalone_video_logger`.
- Nessuna fonte esterna consultata (nessun fatto esterno asserito; EEPROM I2C e lettura seriali sensore libcamera sono ipotesi tecniche da verificare).
