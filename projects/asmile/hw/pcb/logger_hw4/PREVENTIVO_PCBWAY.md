# Preventivo PCBWay (e confronto JLCPCB) — logger HW4, 18/11/2026

**NON ordinato, NON pagato, nessuna carta inserita, nessun account creato** (il preventivo PCB istantaneo di PCBWay non
chiede il login). L'ordine è di Daniele.

## Cosa ho caricato e cosa no (onesto)
- **Gerber/BOM/CPL veri NON caricati**: il layout non è sbrogliato (364 collegamenti aperti, `kicad/DRC.rpt`), quindi
  niente file di produzione. Il preventivo PCB è **per parametri**, che è esattamente quello che PCBWay usa per il prezzo
  della scheda nuda; cambierà solo se lo sbroglio richiede vie più piccole o più strati.
- **Assemblaggio PCBWay: prezzo NON ottenuto.** Il loro preventivo PCBA si chiude solo dopo la revisione dei file
  ("exact quotation will be updated after all the files you uploaded pass review"); il form automatico non l'ho
  compilato fino in fondo (campi dinamici). Va rifatto coi file veri, da loggati → account da creare in quel momento
  (`account.py nuovo pcbway.com`). Sotto c'è la stima con le tariffe JLCPCB pubblicate.

## Parametri usati (screenshot in `preventivo/`)
250 × 50 mm · 4 strati FR-4 TG150 · 1,6 mm · rame 1 oz · **traccia/spazio 4/4 mil** (USB-C) · foro min 0,3 mm ·
**ENIG 1 µ"** (planarità per il modulo a castello, l'IMU LGA e l'USB-C) · maschera verde · pezzi singoli (non pannello).

| Quantità | PCB (PCBWay, 4-5 / 6-7 gg) | per scheda | Spedizione DHL* | Totale |
|---|---|---|---|---|
| 10 | **130,89 $** | 13,09 $ | 40,28 $ | 171,17 $ |
| 100 | **350,89 $** | 3,51 $ | 77,25 $ | 428,14 $ |
| 10, HASL invece di ENIG, 6/6 mil (riferimento) | 101,03 $ | 10,10 $ | 40,28 $ | 141,31 $ |

\* La pagina propone gli USA come destinazione e lo script non è riuscito a cambiare paese: la spedizione in Italia è
**DA VERIFICARE** (di solito simile per DHL). Dazi e IVA esclusi.

Screenshot: `preventivo/pcbway_10_ENIG_4L.jpg`, `preventivo/pcbway_100_ENIG_4L.jpg`.

## Assemblaggio — stima con le tariffe JLCPCB (standard PCBA, pagina "PCB assembly price", 09/2026)
Dati dal PCB generato: **116 pezzi montati, 44 codici diversi (17 Extended), 518 pad SMD (176 sono dei due moduli),
4 fori (gusci USB-C)**.
| Voce | Tariffa | a 10 | a 100 |
|---|---|---|---|
| setup (standard, 1 lato) | 25,56 $ a ordine | 2,56 $ | 0,26 $ |
| stencil | ~15,72 $ a ordine | 1,57 $ | 0,16 $ |
| Extended | 3,07 $ × 17 a ordine | 5,22 $ | 0,52 $ |
| giunti | 0,0016 $ × 518 | 0,83 $ | 0,83 $ |
| 2 moduli Waveshare forniti da noi (consegna + posa/saldatura) | stima | 3,00 $ | 1,00 $ |
| **totale montaggio per scheda** | | **13,18 $** | **2,77 $** |
Fonte tariffe: jlcpcb.com/help/article/pcb-assembly-price e jlcpcb.com/solutions/pcb-prototype-assembly (letti 18/11,
le cifre differiscono un po' fra pagine: fa fede il carrello). **NON VERIFICATO col preventivo vero.**

## JLCPCB per la scheda nuda
Non ho ottenuto il prezzo istantaneo JLC da script (il loro preventivo è un'app JS). Da rifare a mano o coi gerber veri.

## Costo per scheda e per scenario → `DESIGN.md §7`
