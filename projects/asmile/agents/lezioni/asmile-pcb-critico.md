# Lezioni di asmile-pcb-critico

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Confronto pad-per-pad col PDF ufficiale del modulo e col footprint: trova la collisione GPIO leggendo il firmware, non il riassunto
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Non ho potuto rifare ERC/DRC (kicad-cli assente) ne leggere il manuale Inno-Maker del trigger: restano non verificati; piedinatura TP4056/LSM6DS3 da memoria, non da pdf riletto
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Ho rifatto ERC/DRC/netlist con kicad-cli e rigenerato PIN_HW4.md: i tre punti del VETO 1 chiusi con prove mie
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Trovato il difetto del partitore leggendo la sequenza temporale del firmware e simulandola, non fidandomi del rapporto 0,248
- 2026-11-18 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Letto lo schema Waveshare a 400 dpi: R46 su GPIO36 chiude il dubbio sul Joint Download
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Non ho provato fisicamente nulla (nessun banco): power-path allo stacco USB e hot-plug restano calcoli, non misure
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Lo script pin guarda solo main/ e sdkconfig: components/ controllato a grep, non dimostrato
- 2026-11-18 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Il montaggio JLC resta senza preventivo vero: non l'ho potuto verificare
- 2026-11-19 GIUSTO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Pin-map AW32901 riletto sul datasheet Awinic V1.0 e orientamento del footprint (A1 in alto a sinistra, righe A-C) contro la vista dall'alto; R36 verificato sulla tabella jumper UniOhm; ERC/DRC/BOM/stock rifatti da me (24 Extended veri)
- 2026-11-19 SBAGLIATO (`projects/asmile/hw/pcb/logger_hw4/DESIGN.md`): Assemblabilita JLC del CSP 0,4 mm non verificata (fonti in conflitto, nessun preventivo con i file); non ho letto il datasheet MDD dell'SS14 per le curve Vf a basso corrente (Vgs di Q3 stimato, non misurato); non ho provato nulla su banco
