# Lezioni di asmile-hw-pcb

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): letto il firmware prima del brief: pin veri di HW3 (SYNC=1 Hz non trigger, SD su GPIO45) → stessa mappa = firmware riusato
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): supply prima del prezzo: scoperto che chip P4 nudo e tutti i sensori nudi sono a stock 0, cambiata architettura
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): netlist unica in Python + verifica pin per pin della netlist esportata da KiCad (494 pin, 0 differenze), non solo ERC 0
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): revisione elettrica mia prima del critico: trovato CAM_EN senza pull-up e IMU non compatibile col driver
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): KiCad dal DMG in sola lettura invece di forzare la password; preventivo PCBWay vero senza account
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): tolta una sola riga del blocco (model …) nei footprint easyeda: parentesi sbilanciate (A2)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): primo impacchettatore senza ostacoli: 784 violazioni DRC (A3)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): avevo scritto 'firmware invariato' prima di incrociare l'IMU nuova col driver (A5)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): preventivo assemblaggio PCBWay non ottenuto e paese di spedizione non cambiato: restano stime
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): sbroglio non fatto: niente gerber di produzione
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): tabella pin hw/fw generata da script su TUTTO il firmware (macro, numeri a mano, sdkconfig) con eccezioni di ruolo provate da riga di codice: 0 conflitti
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): KiCad installato in /Applications senza password e senza riempire il disco (niente 3dmodels); ERC/DRC/netlist rifatti e datati
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): PCB e montaggio dallo stesso fornitore (preventivo JLC vero da script, parametri verificati sullo screenshot), voci mancanti aggiunte (moduli, IVA, dazio)
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): TLV62569 riletto sul datasheet vero SLVSDG1C con pagina: soglia di cella corretta
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): 1° giro: 'stessi GPIO = firmware invariato' senza cercare i numeri scritti a mano (I2S del saluto su 9/10/12/13): LED e CAM_EN in collisione (A6)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): 1° giro: nessun percorso di flash per la B e COLLAUDO che diceva UART 22/23 (A7)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): 1° giro: TEMP del TP4056 a GND, niente TVS, J2 e J3 uguali, niente power-path; citato SLVSDB6 invece di SLVSDG1C
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): linguette easyeda numerate 0 (A8); costi con fornitori misti e senza saldatura moduli/IVA (A10)
