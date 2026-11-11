# Calibrazione per 15.000 Asmile — angolo FABBRICA (2026-11-09)

Autore: asmile-calib. Solo analisi/progetto sul Mac. Nessun Pi toccato, nessuno script modificato.
Stato: PROGETTO. Niente di questo e' stato provato su una stazione vera: dove manca la prova scrivo NON VERIFICATO.

## 1. L'idea in due righe
La calibrazione stereo (lenti + posizione relativa delle 2 camere) dipende solo dal MODULO, non dalla bici.
Quindi si fa UNA volta a fine linea, su un modulo stereo rigido (2 camere in un'unica piastra), con una stazione fissa. Sulla bici
resta da stimare solo "come e' appoggiato il modulo" (altezza, inclinazione), e lo fa il software da solo, senza operatore.

## 2. Perche' funziona (e cosa la rompe oggi)
- Oggi #001 ha 2 camere SEPARATE: ogni montaggio cambia la rotazione L-R, per questo la calib e' manuale e instabile
  (bordo sx +4..+17% depth, dy -4 px: agents/lezioni/asmile-calib.md, sezione "bordi #001").
- Con una piastra rigida (alluminio, camere avvitate + spinotti, obiettivi M12 bloccati con frenafiletti) R e T non cambiano piu' da un montaggio all'altro.
- ATTENZIONE: #001 NON e' un modulo rigido, quindi questa stazione vale per le unita' NUOVE. #001 e asmile-logger001 restano con la loro calib per unita'.
  asmile-logger001 (Camarray) e' gia' un blocco unico: e' il candidato naturale per provare la stazione per primo (NON VERIFICATO: non ho misurato quanto sia rigida la sua scheda).
- Regola non negoziabile: obiettivo avvitato, messo a fuoco e BLOCCATO (colla/frenafiletti, indurita) PRIMA di calibrare. Se il fuoco cambia, cambia la focale e la calib e' da buttare.

## 3. La stazione (tutta fissa, nessun metro, nessun esperto)

### 3.1 Cosa c'e'
1. Parete di bersagli ChArUco fissa, a 1,5-2 m dal modulo (spazio: una stanza di ~3 m). Pannelli stampati su dibond/alluminio o vetro
   (piani, non cartone), certificati dal fornitore sul lato del quadretto (tolleranza dichiarata, es. +-0,1 mm). Il lato lo misuriamo UNA volta sul pannello campione, non su ogni modulo.
   Sono 3 pannelli A1 inclinati a 0, +25, -25 gradi (cosi' ci sono viste "inclinate 20-40 gradi" che calib_charuco_dual.py:gate richiede, riga 325-327).
2. Supporto del modulo su testa pan/tilt motorizzata (2 servi o 2 stepper) con staffa a spinotti: il modulo si infila in un solo verso.
   Si muove il modulo, NON il bersaglio: 12-16 pose fisse programmate (pan +-25, tilt +-15, roll +-10 gradi, 2 distanze con una slitta o 2 posizioni).
   Le pose sono scelte perche' ogni angolo delle 9 zone dell'immagine veda corner (copertura 3x3: calib_charuco_dual.py:131-152, soglia 150 corner a zona).
3. Illuminazione diffusa fissa (LED a luce costante, niente sole): OV9281 e' mono e soffre la luce scarsa.
4. Un mini-PC (o Pi 5) sulla stazione, uno schermo con 3 stati: VERDE / ROSSO / RIPROVA. Un solo pulsante "Start". Lo scanner QR e' nel supporto.
5. Cavo di alimentazione + CSI/USB verso il modulo: il modulo e' attaccato a un Pi "banco" che registra i frame. Il Pi banco e' della stazione, non e' quello della bici.

### 3.2 Cosa fa l'operatore (non tecnico)
1. Infila il modulo nella staffa (1 verso solo), 2. scansiona il QR/seriale inciso sulla piastra, 3. preme Start, 4. legge VERDE/ROSSO.
ROSSO = il modulo va nel cestino "da rivedere" (lo guarda il tecnico a fine giornata, non l'operatore). Zero decisioni.

### 3.3 Tempo per modulo (STIMA, NON MISURATA)
- Carico + QR: ~30 s. Pose + cattura sincrona: 14 pose x ~1,5 s di assestamento + ~5 frame per posa = ~25-30 s.
- Calcolo: lo script sul Mac e' fatto per video h264 interi e prende 1 frame su 3 (--step 3); su pose gia' separate il carico e' minore, ma
  il tempo di cv2.stereoCalibrate col modello rational su ~90 viste NON l'ho misurato: da cronometrare. Si fa in parallelo al carico del modulo successivo.
- Verifica + scrittura + scarico: ~30 s.
- Ciclo realistico con parallelismo: ~2 min/modulo, 30/h, ~240 per turno di 8 h per stazione.
  15.000 moduli = ~63 giorni lavorativi con 1 stazione, ~32 con 2, ~16 con 4. Le stazioni costano poco (vedi 8): il collo di bottiglia e' il montaggio, non la calib.

## 4. Cosa si riusa di calib_charuco_dual.py (e cosa NO)

Riuso diretto (le funzioni sono gia' nel file, da IMPORTARE, non da modificare):
- make_board / detect (righe 70-85): stesso tabellone e rilevamento.
- coverage / zone_of (131-152): copertura 3x3 = gate "ogni zona ha corner".
- calib_mono (205), stereo_fit (247), holdout_stereo (266): intrinseci per camera, stereo, errore su viste tenute fuori.
- gate (308-330): VERDE/ROSSO su dy per zona e scala per zona; lo stesso gate di oggi, stessi limiti (dy<1 px, scala <2%).
- Formato di uscita Calib (stereo_common.py:29, save riga 70) + JSON con "valid_for": cosi' il resto della pipeline (depth) non cambia.

Cosa NON va bene cosi' com'e' per la fabbrica (da scrivere in un file NUOVO, es. calib_fabbrica.py, che importa il resto):
1. Scala: la riga 414 riscala T a 200 mm nominali (`sq_scale = BASELINE_M / |T|`). Va bene per un singolo #001 senza metro, ma in fabbrica
   e' sbagliato: nasconderebbe un modulo costruito male. Qui la scala viene dal pannello certificato; |T| e' un RISULTATO.
   Gate nuovo: |T| = 200 +- 1 mm (1 mm = 0,5% di errore sulla depth), se fuori -> ROSSO (piastra storta/sbagliata), non riscalare.
2. Hold-out: split_holdout (176-181) tiene fuori "1 vista ogni 5" di un video. Viste vicine nel tempo sono quasi uguali = hold-out debole.
   In stazione l'hold-out deve essere per POSA: 3-4 pose su 14, scelte apposta una per ogni fascia (basso-sx, alto-dx ecc.), mai usate nel fit. Pose diverse = verifica vera.
3. Input: oggi legge h264 + csv (collect, 154). In stazione servono frame gia' ritagliati per posa; il Pi banco li salva per posa e il calcolo li legge.
4. Aggiungere al JSON: seriale modulo, versione stazione, data, hash dei frame, numero pannello, e il report del gate.
5. Le 2 camere "UNITS" (righe 50-57) sono profili per unita' esistenti. Serve un profilo "modulo-rigido-vN", mai mescolato con #001.

## 5. Verifica con punti mai usati nel fit (3 livelli)

Livello A — su ogni modulo, in stazione (obbligatorio, ~10 s):
- 3-4 pose di hold-out, scelte per coprire tutte le 9 zone. Si misura dy e scala per zona. VERDE solo se ogni zona: |dy mediana| < 1 px e scala < 2% (limiti gia' in calib_charuco_dual.py:308-330).
  Aggiungo: p95 di dy <1 px (la lezione sul gate: la sola mediana nasconde i bordi).
- Zona con pochi punti = "non verificata" = ROSSO (stessa regola del gate di oggi).

Livello B — distanza lunga, per CAMPIONE (1 modulo su 20, e ogni lotto nuovo di piastre/obiettivi):
- La stazione sta a 1,5-2 m, ma il gate del progetto e' a 5-15 m. Calibrare da vicino e verificare solo da vicino NON prova la depth a 5 m.
- Quindi un secondo bersaglio a ~5-6 m (un corridoio di fabbrica) con 3-4 oggetti a distanza misurata col metro/laser UNA volta: errore % vero a 3, 5 m (il gate dice +-2% <5 m).
- A 10-15 m la verifica in fabbrica non e' possibile (spazio): si fa 1 volta su un prototipo di lotto, all'aperto (gate +-5% 5-10 m, +-10% 10-20 m). NON VERIFICATO oggi.
- Perche' conta: a 5 m con focale rettificata ~1300 px e B 0,2 m la disparita' e' ~52 px; 2% sono ~1 px. Un errore di 1 mm su T e' 0,5%, un errore di 0,3% di focale e' 0,3%: stanno nei margini, ma solo se il fuoco e' bloccato.

Livello C — sul campo, ogni accensione e in marcia (rete di sicurezza, vedi 7): drift_monitor.py misura il dy su feature naturali;
oltre soglia segnala "ricalibra / da rivedere".

Regola di apprendimento (dal mestiere): ogni nuova versione della stazione si confronta col banco fisso del prototipo: se peggiora un punto, si scarta.

## 6. Salvare la calib e legarla al seriale del modulo

Problema: le camere OV9281 da sole non hanno un seriale che io sappia leggere via libcamera (NON VERIFICATO: da controllare su un modulo vero). Quindi il seriale lo creiamo noi.

Scelta semplice (a prova di errore):
1. Il modulo ha un seriale inciso (laser) + DataMatrix/QR sulla piastra. Il seriale = identita' del modulo.
2. In stazione, il JSON "calib_<seriale>.json" viene scritto in 3 posti:
   a. sul server della fabbrica (archivio, mai su git: sono dati nostri, ma niente video);
   b. sulla SD del Pi che finira' nella stessa scatola (il Pi e il modulo viaggiano in kit);
   c. in una piccola EEPROM I2C (24C32, ~0,5 euro) sul modulo stesso, con seriale + CRC + parametri compressi (K, D, R, T stanno in ~1-2 KB).
3. All'avvio il Pi controlla: seriale EEPROM == seriale nel JSON sulla SD, e CRC ok. Se no: NON usa la calib (mai fallback su altra unita': linea rossa del progetto) e accende un avviso.
   Vantaggio della EEPROM: se si cambia Pi o SD, la calib resta col modulo; se si cambia modulo, la calib non e' sbagliata silenziosamente.
4. Se la EEPROM non e' possibile (costo/progetto), basta la SD+JSON con il seriale letto dal QR; resta il rischio "SD di un altro kit": si mitiga col controllo (7a).

## 7. Cosa resta da calibrare quando il modulo e' sulla bici (e come, senza operatore)

Cosa NON cambia mai in bici: lenti, R e T tra le due camere (se la piastra e' rigida). La depth stereo NON dipende da altezza e pitch.
Cosa cambia: la posa modulo -> bici (altezza dal suolo, pitch, roll). Serve per la traiettoria proiettata, il piano del suolo, l'ingombro.

1. Progettare la staffa con un riferimento meccanico (battuta + vite unica) che fissi pitch e altezza nominali (oggi #001: pitch 7,4 gradi misurato).
   La tolleranza meccanica la assorbe il software (punto 2).
2. Auto-stima al primo avvio, bici ferma su terreno piano (o nei primi minuti di marcia):
   - piano del suolo dai punti vicini della mappa di disparita' (RANSAC su 2-8 m): da qui altezza, pitch, roll del modulo;
   - controllo incrociato con la gravita' dell'IMU (la bici ha l'IMU; ricordare che il segno degli assi e' per unita', es. logger001 asse avanti = -ax);
   - mediana mobile su N minuti, e limiti di plausibilita' (valori fuori range -> "montaggio da rivedere", non si usa).
   Il risultato va in un file SEPARATO "mount_<seriale>.json": la calib stereo di fabbrica non si tocca mai.
3. Piccola correzione di rotazione: se drift_monitor.py (righe 3-11 spiegano il principio) vede dy sopra soglia, si puo' lanciare un
   ritocco tipo selfcalib_essential.py (matcha feature L-R, riga 25-63) MA solo come trim piccolo (es. <0,3 gradi di rotazione), con il gate dy; se serve di piu' -> modulo da rivedere. Mai riscrivere la calib di fabbrica in automatico: scrive un file "trim", il PASSA resta di asmile-calib-critico.
4. Nessun metro in RSA. L'unico dato esterno e' "bici ferma su pavimento piano" che e' gia' vero a ogni ricarica nel posto di parcheggio.

Limiti onesti: l'auto-stima del piano e' NON VERIFICATA su queste unita' (non l'ho mai provata sui video di #001/logger). In un corridoio RSA con riflessi sul pavimento lucido la depth sul suolo e' peggiore: si valida in un RSA pilota.

## 8. Costo per unita' (stima, NON preventivo)
- Stazione (parete pannelli certificati, testa pan/tilt, luci, mini-PC, schermo): ordine di 3-8 mila euro una tantum, ripartiti su 15.000 = pochi centesimi/modulo. NON VERIFICATO (nessun preventivo).
- Per modulo: EEPROM + etichetta laser/QR ~1 euro; lavoro ~2 min di operatore.
- Piastra rigida + viti + colla: costo costruttivo del modulo (fuori da questo rapporto).

## 9. Rischi
1. Rigidita': la piastra puo' muoversi con urto/caldo/trasporto. Mitigo con alluminio, spinotti, test di caduta, e il monitor in campo (livello C). NON VERIFICATO finche' non c'e' un prototipo.
2. Calibro vicino, uso lontano: estrapolazione 1,5 m -> 15 m. Serve il livello B (campione a 5 m) e un pilota a 10-15 m prima di produrre in serie.
3. Dipendenza dalla precisione del pannello: 1% di errore sul lato = 1% di scala. Pannelli certificati + controllo periodico (1 pannello campione al mese col metro, o 2 pannelli incrociati).
4. Fuoco che si sposta nel tempo (M12 non bloccate bene): focale cambia. Frenafiletti + controllo a campione dopo 1 mese.
5. Temperatura: OV9281 e lenti cambiano focale con il caldo; effetto non misurato qui. NON VERIFICATO.
6. Mono OV9281 in poca luce: se la stazione ha luce variabile i corner vengono male -> luce costante.
7. Sincronia camere: gia' risolta nel software con rpicam --sync (<=0.045 ms) su #001; sul modulo rigido va ripetuta la prova.
8. Il test sintetico di calib_charuco_dual.py e' VERDE ma NON e' dati reali (handoff HANDOFF_calib_camere_20261109.md): la stessa pipeline sui video veri di #001 non ha ancora il PASSA di asmile-calib-critico per i bordi. Prima si dimostra li', poi si costruisce la stazione.

## 10. Cosa NON risolve
- Le unita' gia' esistenti (#001 camere separate, logger001): restano col metodo per unita'.
- Non risolve la qualita' della depth oltre 10 m (limite fisico: lente 2,7 mm, 1-2% fino ~7 m).
- Non risolve il montaggio bici (inclinazione, altezza): solo li stima.
- Non risolve il pulire/sporcare le lenti in RSA ne' i danni durante l'uso: serve il monitor (drift_monitor) e un'assistenza.
- Non risolve i dati di guida (sterzo, freno, VESC): e' solo percezione.

## 11. Passi per partire (ordine)
1. Prima dimostrare calib_charuco_dual.py su dati reali di #001 con PASSA (gate L0.calib_001 / L1.rettifica). Senza questo la stazione ripete lo stesso errore.
2. Prototipo di piastra rigida col Camarray (logger001 e' gia' monoblocco) e provare: calibra, sposta, rimonta, ricalibra -> quanto cambiano R e T (misura la rigidita').
3. Scrivere calib_fabbrica.py nuovo (import delle funzioni sopra), con gate |T| e hold-out per posa; test sintetico prima, poi sul prototipo.
4. Costruire una stazione di prova (pannello + testa a mano, poi motorizzata) e cronometrare il vero tempo di ciclo.
5. Banco fisso a 5 m (livello B) e pilota a 10-15 m: tabella errore per distanza.
6. EEPROM + controllo all'avvio; auto-stima piano/mount; RSA pilota.

## 12. Fonti
- File del repo: logger/depth/calib_charuco_dual.py (righe citate), stereo_common.py:29-80, drift_monitor.py:1-25, selfcalib_essential.py:25-63,
  agents/lezioni/asmile-calib.md, agents/lezioni/daniele.md, agents/rapporti/HANDOFF_calib_camere_20261109.md.
- Fatti esterni (non verificati qui con URL): le cifre di tempo/costi sono mie stime, non fonti. Nessun URL citato perche' non ho fatto ricerche web in questo giro.
