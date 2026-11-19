# Pattern — cosa funziona (estratto da REGISTRO.md)

Ogni pattern: regola · prova (righe del registro) · quando si applica.

- **P1 — Il codice che gira prima del brief.** I pin e le funzioni vere si leggono nel firmware (`logger02.h`, `*_rec.c`),
  non nella descrizione: SYNC GPIO3 = impulso 1 Hz (non trigger), sync stereo software via VTS, SD alimentata da GPIO45.
  Prova: registro 14:46 e 15:04. Quando: ogni scheda che sostituisce hardware esistente.
- **P2 — Netlist unica + verifica incrociata.** La netlist in Python genera schema e PCB; dopo l'ERC si esporta la netlist
  da KiCad e si confronta pin per pin (494 pin, 0 differenze). Prova: 15:36. Quando: ogni schema generato o modificato.
- **P3 — Footprint dal codice LCSC (easyeda2kicad).** Stesso disegno con cui JLC monta quel pezzo; poi pulizia (tipi pin,
  NPTH, modelli 3D). Prova: 15:07, 15:30, 15:53. Quando: ogni pezzo che monta JLC/PCBWay.
- **P4 — Stessi GPIO = firmware gratis.** Tenere la mappa pin della versione precedente fa girare il firmware congelato
  sulla scheda nuova (HW4 ← hw3-def), salvo i pezzi cambiati (driver IMU). Prova: 15:04, 15:38. Quando: ogni revisione.
- **P5 — Supply prima del prezzo.** Controllare stock e MOQ (API JLC, DigiKey, produttore) PRIMA di innamorarsi di un
  chip: il P4 nudo e tutti i sensori nudi erano a stock 0. Prova: 14:58, 15:22. Quando: ogni pezzo critico.
- **P6 — Revisione elettrica propria prima del critico**, pin per pin contro il firmware: ha trovato CAM_EN senza pull-up e
  l'IMU non compatibile col driver. Prova: 15:38. Quando: prima di ogni `palla.py passa`.
- **P7 — Preventivo PCB senza account**: il preventivo istantaneo PCBWay si compila da script (Playwright headless,
  selettori `a.clsPlatingType[data=…]`, `a.clsLineWeight[data=…]`); l'account serve solo per l'assemblaggio. Prova: 16:10.
- **P8 — Modello numerico dei transitori nel repo.** Partitore con la sequenza del firmware e stacco USB con le capacità vere
  (`kicad/modello_partitore.py`, `modello_power_path.py`): il critico e il capo rifanno il conto con un comando, e il
  modello ha mostrato che la correzione proposta (R35 10k) da sola non bastava. Prova: registro 23:02-23:08.
- **P9 — Catena di sbroglio a passi separati con metrica scritta.** genera → fanout → coppie critiche col router nostro →
  Freerouting → completa → pulizia guidata dal DRC → riempimenti → allarga; ogni passo un processo, DRC di KiCad come
  giudice, misure (MIPI, SW, larghezze) in un file. Prova: registro 00:40-01:55 (DRC 0 / 0 aperti riproducibile).
- **P10 — Preventivo coi file prima di chiedere il login.** JLC e PCBWay leggono i gerber e danno il prezzo PCB senza
  account: si verifica subito che i file siano accettati (strati, misure). Prova: registro 02:10-02:15.
