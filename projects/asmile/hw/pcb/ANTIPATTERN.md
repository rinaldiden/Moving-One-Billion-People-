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
