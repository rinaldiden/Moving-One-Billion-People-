# File di produzione — logger HW4 (generati da `../kicad/esporta_produzione.py`, 19/11/2026)

**NON ordinato.** L'ordine lo decide Daniele.

| File | Cosa |
|---|---|
| `gerber_logger_hw4.zip` | gerber 4 strati (F.Cu, In1.Cu, In2.Cu, B.Cu), maschere, paste, serigrafie, contorno, foratura Excellon PTH/NPTH, mappe fori, job file |
| `BOM_JLC.csv` | Comment, Designator, Footprint, LCSC — 52 righe, 125 pezzi montati (i DNP sono esclusi) |
| `CPL_JLC.csv` | Designator, Mid X, Mid Y, Layer, Rotation — 125 pezzi, tutti sul top |
| `FORNITI_DA_NOI.csv` | i 2 moduli Waveshare ESP32-P4-Module (IPEX): non sono nella libreria JLC → conto lavoro o saldatura a mano |

## Opzioni da scegliere nel preventivo
- 4 strati, 250 × 50 mm, 1,6 mm, FR-4, **stack-up JLC04161H-3313** (prepreg 0,1 mm: piste MIPI 0,15 mm ≈ 50 Ω;
  verificare col calcolatore di impedenza), rame 1 oz esterno / 0,5 oz interno, **ENIG** (pad CSP da 0,23 mm: JLC chiede
  ENIG sotto 0,25 mm), traccia/spazio minimo 0,1 mm (4 mil), via minima 0,6/0,3 mm, maschera verde.
- Assemblaggio un lato (top), 125 pezzi, 23 codici Extended montati.

## Rotazioni del CPL (controllate)
Tutte 0°. I footprint dei pezzi LCSC vengono da easyeda2kicad (stesso disegno della libreria JLC). Pezzi polarizzati
controllati a mano: LED D2 (C2286: catodo = pad 2 a −x), D3/D4 (C12624/C2288: catodo = pad 1 a −x) = footprint KiCad
(catodo a −x) → 0°. D5 usa il land pattern di SS14 (C2480, piazzole ±1,96 mm) col codice SS34 C8678 (piazzole JLC
±2,20 mm): stesso package DO-214AC, stessa polarità (catodo pad 1 a −x) → 0°. **Da ricontrollare comunque nel
visualizzatore DFM del fornitore** prima di confermare (U*, Q*, D*, J1, J2, J3, J60, J70, BZ1).

## Coordinate
Origine assoluta di KiCad (l'origine di foratura non è impostata): gerber, fori e CPL usano le stesse coordinate.
