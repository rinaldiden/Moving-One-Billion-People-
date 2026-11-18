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
