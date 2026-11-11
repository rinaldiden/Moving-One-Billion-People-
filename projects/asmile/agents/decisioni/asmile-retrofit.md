# Decisioni di asmile-retrofit

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-09 18:54 [retro] **comprare o fare il modulo stereo** → fare: barra rigida con 2 OV9281 e lenti M12 bloccate con colla UV. Perché: OAK-D Pro W (75 mm) ~5% a 5 m contro ~0.7% della nostra baseline 200 mm; fornitore unico; prezzi a volume non pubblici. Scartato: OAK-D Pro W / OAK-D LR / ZED. Evidenza: `agents/rapporti/calib15000_hardware.md`.
- 2026-11-11 17:58 **motore sterzo #001 sostitutivo** → raccomandare attuatore CubeMars AK80-8 KV60 (CAN, doppio encoder) sulla conica 1:5; scartare 63xx a KV basso. Perché: 63xx hall dà ~2-3 Nm continui (Kt 0.043-0.059 Nm/A x 45 A): un KV più basso non basta; AK80-8 10/25 Nm, 575 g, encoder 14+15 bit, stesso peso del 6354. Scartato: 63xx low KV (+36% Kt solo), gearmotor OMC 24V 4.2kg, RS PRO (scheda incoerente), Steadywin/MyActuator (dati non verificabili). Evidenza: `agents/rapporti/motore_sterzo_ricerca_20261111.md`.
