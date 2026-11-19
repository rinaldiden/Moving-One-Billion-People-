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
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): modelli numerici nel repo (partitore con la sequenza del firmware, stacco USB con le capacità vere): riprodotto il -31,9 % del critico e dimostrato 0,000 % con 100k/33k
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): il modello ha mostrato che R35 10k da solo non bastava (60-80 ms sul diodo di body): gate via diodo, tau 7 us
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): OVP AW32901 scelta dal datasheet (soglia 5,83-6,07 V sotto i 6/6,5 V dei pezzi) invece di un TVS che limita a 9,2 V
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): nel giro precedente avevo cambiato il partitore guardando solo il rapporto, non la sequenza temporale del firmware (A11)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): power-path progettato solo a regime, senza il transitorio di stacco (A12); TVS 5 V accanto a pezzi da 6 V (A13)
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): R36 messo 0805 invece del 0603 richiesto: scelta motivata (2 A) ma da far confermare al critico
- 2026-11-19 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): sbroglio 4 strati con DRC 0 errori e 0 aperti, ERC 0, schema e PCB = netlist (526 pin/pad), catena riproducibile con un comando
- 2026-11-19 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): coppie MIPI instradate a coppie dal router nostro prima di Freerouting: differenza P/N da 7-24 mm a <= 1,6 mm
- 2026-11-19 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): nodo SW dei buck da 48 mm a 6,7 mm con gruppi vincolati nel piazzamento
- 2026-11-19 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): preventivo con i gerber veri su JLC e PCBWay (file letti senza errori); fermo davanti al reCAPTCHA invece di aggirarlo
- 2026-11-19 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): git stash pop senza modifiche locali ha ripescato uno stash di altri: ripristinato subito, nessun file altrui committato (A15)
- 2026-11-19 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): criterio mio per le vie pendenti ha rotto 3 collegamenti (A16); router A* prima versione senza aggiornare gli ostacoli: 16 corti (A19)
- 2026-11-19 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): piazzamento senza gruppi: nodo SW a 48 mm (A18); VBUS resta a 0,3 mm per 39 mm
- 2026-11-19 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): montaggio e DFM del CSP non verificati coi file (bloccato dal captcha)
