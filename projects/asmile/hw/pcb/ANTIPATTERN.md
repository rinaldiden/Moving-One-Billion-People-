# Antipattern — errori fatti e regola che li evita (estratto da REGISTRO.md)

- **A1 — generatore che sovrascrive modifiche a mano.** Rigenerare file "GENERATO" cancella quello che qualcuno ha
  aggiunto a mano dopo. Regola: dopo ogni rigenerazione `git diff` riga per riga; le regole nuove si scrivono nel
  generatore, mai solo nel file generato. (Registro 2026-11-18 14:40) — vale anche per `logger_hw4/kicad/*.kicad_sch`:
  si cambia `netlist_hw4.py`, mai lo schema.
- **A2 — togliere una riga da un'espressione S multilinea.** Ho tolto solo `(model "…"` dai footprint easyeda e le parentesi
  si sono sbilanciate (KiCad: "Unable to load library"). Regola: nei file KiCad si tolgono/sostituiscono **blocchi
  bilanciati** (funzione `blocco()`), mai righe con regex. (Registro 15:32)
- **A3 — impacchettatore senza ostacoli.** Blocchi diversi con la stessa zona e cursori separati → pezzi uno sopra l'altro
  (784 violazioni DRC); courtyard easyeda più stretti dei pad → corti. Regola: piazzamento con elenco degli occupati
  (fissi prima) e ingombro = courtyard ∪ pad. (Registro 15:52)
- **A4 — indovinare URL della documentazione.** 404 sulla checklist P4: prima l'indice della guida, poi la pagina. (14:48)
- **A5 — "firmware invariato" detto troppo presto.** Cambiando l'IMU (MPU6050 → LSM6DS3TR-C) il driver va riscritto: ogni
  pezzo cambiato va incrociato col codice che lo usa prima di promettere zero software. (Registro 15:38)
- **A6 — "stessi GPIO = firmware invariato" senza cercare chi usa quei pin.** HW3 usa GPIO9/10/12/13 per l'I2S del codec
  (`logger02_saluto.c:36`) e il saluto apre il canale prima di provare il codec: in HW4 quei pin sono LED e CAM_EN.
  Regola: per ogni GPIO riassegnato `grep` del numero in TUTTO il firmware (anche I2S/SPI/LEDC con numeri sparsi) e
  tabella pin hw↔fw firmata prima dello sbroglio. (Critico, 18/11)
- **A7 — percorso di programmazione non disegnato.** Un modulo senza USB né header montato non si flasha in produzione;
  ricordare che il ROM del P4 scarica solo da UART0 (GPIO37/38) e USB-Serial/JTAG. Regola: per ogni MCU della scheda
  scrivere "come si flasha la prima volta e in serie" prima dello sbroglio. (Critico, 18/11)
- **A8 — fidarsi della numerazione dei pin di easyeda2kicad.** Le linguette meccaniche hanno tutte il numero "0" (pin
  duplicati → ERC) e il formato vecchio scrive `(pad 0 …)` senza virgolette. Regola: dopo l'import contare i numeri
  duplicati in simbolo E footprint e rinumerarli insieme. (Registro 17:32)
- **A9 — "il pezzo fa da solo" su un pin che il firmware vecchio pilota (buzzer sul PA).** Mettere un pezzo nuovo su un pin
  che il firmware vecchio usa per altro, contando su un effetto collaterale, è un comportamento non provato. Regola: pin
  usati dal firmware vecchio per funzioni che non esistono più → pad libero. (Registro 17:16)
- **A10 — costi con fornitori misti e voci mancanti.** PCB da PCBWay + montaggio a tariffa JLC, senza saldatura dei moduli
  forniti da noi né IVA/dazio: numero più basso del vero. Regola: un fornitore per PCB+montaggio nel conto, ogni pezzo
  fornito da noi ha la sua voce di posa, e una riga "caso peggiore" con dazio + IVA. (Critico 17:05)
- **A11 — "stesso rapporto, quindi stesso firmware" sul partitore ADC.** Il firmware ha una sequenza temporale (pull-down
  interno 2 ms + attesa 2 ms) tarata sull'impedenza di HW3; un condensatore da 100 nF su 248 kΩ la rende troppo lenta e la
  lettura sbaglia del 31 %. Regola: ogni modifica a un nodo che il firmware legge o forza va simulata con la sua sequenza
  (RC con i tempi del codice), non solo con il rapporto. (Critico, 18/11)
- **A12 — power-path: guardare solo il caso "USB presente" e "USB assente a regime".** La transizione (stacco del cavo)
  dipende dalla costante di scarica del gate del P-MOS e dal diodo di body. Regola: per ogni OR di alimentazione scrivere i
  tre casi (collegare, regime, scollegare) con tensione di VSYS e tempo; il gate si scarica con ≤ 10 kΩ. (Critico, 18/11)
- **A13 — TVS "da 5 V" accanto a pezzi con massimo 6-6,5 V.** SMF5.0A limita a 9,2 V a 21,7 A e conduce da 6,4 V: non basta
  a proteggere TP4056 (6,5 V) e TLV62569 (6 V) su un hot-plug. Regola: confrontare VC del TVS con il VIN massimo di ogni
  pezzo sulla linea; se supera, prevedere un elemento serie (perla/0 Ω) e la prova con sonda. (Critico, 18/11)
- **A14 — correggere il valore che il critico indica senza rifare il conto.** "R35 → 10k" riduceva il buco allo stacco USB
  da 130 a 60-80 ms, non lo toglieva: il problema era la capacità di VBUS sul gate, non la resistenza. Regola: per ogni
  correzione di valore rifare il modello e scrivere il risultato numerico; se non basta, dirlo e cambiare la topologia
  (qui: gate via diodo). (Registro 23:06)
- **A15 — `git stash` + `git stash pop` "per sicurezza".** Se non ci sono modifiche locali lo stash non viene creato e il
  pop ripesca il primo stash della lista, di qualcun altro (successo 19/11: vecchio stash su pi/braking). Regola: solo
  `git pull --rebase --autostash`; mai `stash pop` senza aver visto `git stash list` subito prima. (Registro 00:20)
- **A16 — togliere rame con un criterio mio quando il DRC sa già cos'è pendente.** Ho tolto 12 vie "pendenti" e ne servivano
  3. Regola: si tolgono solo gli oggetti che il DRC di KiCad segnala (coordinate dal JSON). (Registro 01:40)
- **A17 — un solo processo Python di KiCad per tutta la catena.** In 10.0.8 dopo un Remove o un ImportSpecctraSES gli
  oggetti SWIG non si iterano più. Regola: un passo = un processo, il file .kicad_pcb fa da passaggio. (Registro 00:55)
- **A18 — piazzamento "vicino a chi ti collega" senza gruppi.** Nodo SW dei buck a 48 mm: l'induttore finiva dove c'era
  posto. Regola: alimentatori a commutazione e loro L/C in un gruppo con un'area dedicata, prima di tutto il resto. (01:05)
- **A19 — router fatto in casa senza aggiornare gli ostacoli.** Le piste appena messe devono diventare subito ostacoli, e il
  foro-foro vale anche fra vie della stessa net. (Registro 01:20)
