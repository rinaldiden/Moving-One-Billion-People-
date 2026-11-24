# Scarico affidabile logger02 + sonno B del giro 24/11 (asmile-deploy, 24/11)

Stato: codice scritto e compilato, NON caricato sulla scheda, NON provato in hardware. Test a secco Python verde.

## 1. Analisi RAM / errori (CSV salute e errori 20-24/11, ~85.000 righe)
- RAM interna libera normale ~200 KB (A) / ~300 KB (B). `ram_int_min` e' il minimo dall'avvio.
- A, 24/11 sessione 160413: ram_int_min 184 KB (16:04:18) -> 176 KB (16:04:30) -> **57 KB (16:08:18)** durante lo scarico dei clip. Altrove nel giorno il minimo e' >= 80 KB; il 23/11 >= 126 KB. Il 57 KB e' il valore piu' basso mai registrato.
- Crash (contatore): 0 (20/11) -> 1 (21/11) -> 3 (24/11). Reset A alle 16:04:03 (B lo vede: "la A ha abbassato WAKE").
- Errori ricorrenti in giornata: `httpd_uri: uri handler execution failed` x140 (invio al Mac fallito), `HTTP_CLIENT Connection failed / esp-tls select() timeout` x69 (proxy verso B), `H_SDIO_DRV rx buffers dynamically allocated: allocation attempt may fail` x92 (il C6 non riporta i buffer: i 23 KB si allocano a richiesta = il meccanismo del crash 18/11), Tailscale (ml_coord/ml_derp/STUN) in retry continuo senza rete esterna = altri allocatori in RAM interna.
- Lettura: ogni trasferimento lungo (malloc/free 32 KB + 16 KB per richiesta, proxy con buffer http client da 8 KB) frammenta la RAM interna; il C6 ha bisogno di blocchi contigui. Il minimo 57 KB conferma la pressione. NON VERIFICATO: dimensione del blocco contiguo piu' grande (il CSV ha solo la somma libera). Proposta: aggiungere `heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)` al CSV salute (non fatto: tocca il formato).
- I timeout dei clip A/B non sono solo RAM: `.part` ripartiva da 0 a ogni giro (2 MB, poi timeout, ripartenza) -> non finiva mai un file da 8-10 MB.

## 2. Ripresa (fatto)
- `loggers/pull_from_loggers.py`: `scarica_con_ripresa()` con `Range: bytes=N-`, verifica `Content-Range` iniziale, server senza Range -> riparte da 0, `.part` piu' lungo -> da capo, 416 -> da capo, 503 -> attesa, stop dopo 3 tentativi senza progresso, stop del giro dopo 2 file di fila falliti, 1 s di pausa fra file. Size finale uguale a `/api/files` prima di `/del` (invariato). Hash: NON aggiunto (sha256 lato logger = seconda lettura della SD per file; la dimensione + chiusura del pezzo bastano finche' i pezzi sono immutabili). Il job launchd sta gia' usando il codice nuovo (compatibile con il firmware vecchio: ripartenza da 0).
- `loggers/test_ripresa.py`: server finto con cadute a 700 KB, `.part` preesistente, server senza Range, `.part` troppo lungo, 503 temporaneo/permanente: tutto OK.
- Firmware `logger02/firmware/main/logger02_web.c`: `/dl` con Range (206, `Content-Range`, 416), proxy `/b` che inoltra `Range` e riporta 206/416/503/404 e `Content-Range`; se la B cade a meta' il proxy NON manda il chunk finale (il Mac vede il troncamento e riprende).

## 3. Robustezza A (fatto nel sorgente, compilato)
- Buffer preallocati all'avvio (PSRAM, 8 KB file + 8 KB api), niente malloc per richiesta (prima 32 KB in /dl, 16 KB nel proxy; solo lo streaming :82 alloca ancora).
- Blocchi 8 KB (erano 32 KB / 16 KB), 1 tick di pausa per blocco, buffer http client 4 KB (era 8).
- Un solo trasferimento di FILE alla volta (A o via proxy B): il secondo riceve 503 + Retry-After, il Mac riprova. Proxy non-file: 1 alla volta con attesa 5 s.
- Contropressione: se la RAM interna libera < 70 KB si aspetta fino a 1 s prima del blocco successivo.
- Non toccati: registrazione, sync camere, sonno. Rischio: il throughput scende (blocchi piccoli + tick); a 8-10 MB/min (170 KB/s) basta ampiamente, DA MISURARE al primo scarico dopo l'OTA.
- Da fare dopo la prova: rollback-guardian e prova OTA solo A con `SOLO=A`, osservare `ram_int_min` durante uno scarico lungo.

## 4. B servita direttamente sulla rete (solo valutazione)
- Oggi la B ha wifi solo interno (rete A<->B?) e si raggiunge dal proxy della A: ogni byte della B passa 2 volte nel wifi della A e nella RAM interna della A, e blocca /dl della A.
- Costi: la B apre un secondo ruolo di rete (IP raggiungibile, Tailscale o IP di casa); piu' RAM interna sulla B (a oggi 300 KB liberi, ne ha molta di piu' della A); codice gia' presente (stesso `/dl`). Rischi: la B ha gli stessi crash SDIO se mai facesse trasferimenti lunghi in parallelo alla registrazione; piu' consumo di batteria (wifi B sempre acceso) e un secondo ospite sulla rete di Daniele. Non e' una modifica da fare ora: prima misurare quanto migliora il proxy con Range/lock. NON IMPLEMENTATO.

## 5. Giro 24/11: "B in deep sleep alle 16:12" e "A ferma alle 16:21"
Cosa dicono i dati (sensors_*, salute_*, errori_*, clip_*_frames.csv di logger02):
- **La B NON e' andata in sleep alle 16:12.** Il clip B 160420_00012 inizia a t=744 s dall'avvio della B (16:16:44) e il 00013 esiste (.part). Mancano solo i clip 7-11: non sono stati scaricati (timeout, vedi /tmp/asmile-loggers-ingest.log, 160420_B_00009-11 "timed out") e restano sulla scheda B. Il "finisce dopo 8 clip" e' un artefatto dello scarico.
- **La A alle 16:21:02 si e' addormentata giustamente**: nei sensors_160413 i clip 15 e 16 (ultimi 2,5 min) hanno gyro p95 1.1 deg/s e dacc max 0.012 g (bici ferma, soglia 3 deg/s e 30 mg), il 13 uguale: errore "bici ferma da 2 minuti". Non e' una "ferma falsa in moto": l'IMU 4 min prima mostrava moto vero (clip 9-10 gyro p95 70 deg/s).
- La A **non ha smesso**: si e' svegliata col movimento alle 16:24:59 (sessione A 162459, 14 clip, fino al sonno delle 16:38:35 per fermo vero), poi 16:39:34 (A 163934, 22 clip, fino a ~17:01), poi 17:02/17:04/17:09. Quindi la nota "nessuna sessione A fino alle 17:02" non regge (sensors_ e clip_ A 162459/163934 ci sono).
- **Il guasto vero: la B non si e' svegliata alle 16:39:34.** B 162506 (14 clip) si chiude con "deep sleep: comando dalla A" alle 16:38:35.611; la A si risveglia dopo 59 s ma non esiste nessuna sessione B 163934, ne' B alle 17:02/17:04/17:09; la B ricompare solo alle 17:14 (171410, dopo l'OTA). Per ~35 min la A ha registrato da sola (22+ clip senza il lato destro). Prima volta che succede: il 16:21->16:25 la B si era svegliata (162506, 7 s dopo la A).
- Causa: **NON VERIFICATA** (la B dormiva/era bloccata e non ha scritto nulla dopo le 16:38:35). Ipotesi dal codice, in ordine di sospetto:
  1. `logger02_dormi()` della B (chiamata da rx_task su "Z") si blocca prima di `esp_deep_sleep_start()` (rec_stop/standby/chiusura salute con SD e C6 gia' spenti dai pin hold): B senza wifi, senza registrazione, ma non in sleep; `wake_task` non la salva perche' il filo WAKE torna alto quando la A si sveglia. Spiega "B morta ma mai riavviata" fino all'OTA. Il sonno breve (59 s) rende la finestra stretta fra "A sveglia, WAKE alto" e "B ancora nel suo dormi".
  2. B armata (ext1 ANY_HIGH) dopo che WAKE era gia' tornato alto: con livello gia' alto dovrebbe svegliarsi subito, ma se il livello e' salito PRIMA di `rtc_gpio_pulldown_en/ext1` e la B non lo rivede come evento, dorme per sempre (la A alza WAKE una volta sola in `logger02_link_init`).
  3. B sveglia ma non parte la registrazione (nessun file ne' log: improbabile, non c'e' salute B dopo 16:38:35).
- **Il firmware di stasera (ac6d8974, "sveglio mentre scarica") NON lo corregge**: tocca la decisione di sonno della A (contatore trasferimenti, attesa wifi, niente tetto) e non il percorso wake/sleep della B (`logger02_link.c`, `dormi` lato B).
- Correzione proposta (NON implementata, tocca il sonno: serve ok di Daniele + guardian):
  a. **A ri-sveglia la B**: dopo l'avvio, se dopo 25 s la B non ha mandato la sua riga UART ("S"/stato), la A porta WAKE a 0 per 200 ms e poi a 1 (due volte, a 25 s e 60 s). Costa niente e copre i casi 1-2 quando B e' in sleep.
  b. **Watchdog su B dentro dormi**: arma un timer (esp_timer/task wdt, 15 s) all'ingresso di `logger02_dormi()` sulla B; se non e' entrata in deep sleep, `esp_restart()` (e la rilettura di WAKE decide). Cosi' una B bloccata si riavvia da sola.
  c. **B: timer wake di sicurezza** `esp_sleep_enable_timer_wakeup(90 s)` e al risveglio, se WAKE e' ancora basso, si riaddormenta subito (costo: ~1 s di boot ogni 90 s con la A ferma; se la B e' lenta a ripartire va misurato prima di accettarlo).
  d. **Diagnostica**: salvare in NVS l'ultimo passo di `dormi` (inizio, rec_stop fatto, deep_sleep_start) e l'`ultimo_riavvio` + il passo precedente nel CSV salute, cosi' la prossima volta la causa e' nei dati. Piu' `largest_free_block` nel CSV.
  e. La A segnala a log/`/api/stato` "B non vista da N s" cosi' il Mac (e Daniele) vedono subito che registra mezza coppia.

## 6. Correzioni dopo VETO del guardian (24/11 sera)
- Proxy /b: il Content-Range della B ora si cattura in `HTTP_EVENT_ON_HEADER` (`ev_b`, IDF 5.5: `esp_http_client_get_header` legge la richiesta) e si inoltra. Mac tollerante: 206 senza Content-Range accettato SOLO se i byte ricevuti sono esattamente size-offset (messi in `.r`, accodati dopo la verifica); lunghezza diversa = rifiutato, `.part` intatto. Test in `loggers/test_ripresa.py` (server finto 206 senza CR, giusto e corto): TUTTI OK; la logica precedente lanciava "Content-Range inatteso" su questi casi.
- B che non si risveglia (punti 5a/5b): implementati. (a) la A, se la B non ha mandato nessuna riga UART da quando e' accesa, fa un impulso su WAKE (basso 200 ms, poi alto) a 25 s e a 60 s, poi basta (`logger02_wake_logic.h`, test `host_test/test_wake_logic.c` 10/10 OK; la B non si addormenta per un impulso: servono 6 letture da 500 ms consecutive basse). (b) in `logger02_dormi()` sulla B timer da 30 s: se non e' entrata in deep sleep, `esp_restart()` (la A sveglia = la B riparte; la A addormentata = wake_task la rimette a dormire). NON provati in hardware. La diagnostica NVS e il timer wake della B (5c-d) NON fatti.
- Build in copia separata: sha256 13f4aaac1a00c680153ec15cfbeea749bad6bd15ab9c88607cb0ce0f7224be29 (`scratchpad/fw_head/projects/asmile/logger02/firmware/build/logger02.bin`).
