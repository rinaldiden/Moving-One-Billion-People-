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
