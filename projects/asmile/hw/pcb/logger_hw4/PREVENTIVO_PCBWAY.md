# Preventivo PCBWay e JLCPCB — logger HW4, 18/11/2026

**NON ordinato, NON pagato, nessuna carta inserita, nessun account creato.** L'ordine è di Daniele.

## 19/11/2026 — preventivo CON I FILE VERI (`produzione/gerber_logger_hw4.zip`)
Entrambi i fornitori hanno letto i gerber senza errori: JLCPCB «Detected 4 layer board of 50×250mm», PCBWay «Detected 4
layers board of 250 x 50mm». Parametri: 4 strati, 1,6 mm, ENIG 1 µ", 1 oz, maschera verde (PCBWay anche 4/4 mil).
| | 10 pz | 100 pz | spedizione | screenshot |
|---|---|---|---|---|
| **JLCPCB** PCB nudo coi gerber | **60,00 $** (3-4 gg) | **279,05 $** (5-6 gg; 388,15 $ a 3-4 gg) | UPS DDP 31,07 / 81,30 $ | `preventivo/jlcpcb_file_10_*.jpg`, `jlcpcb_file_100_*.jpg` |
| **PCBWay** PCB nudo coi gerber | **130,89 $** | **350,89 $** | DHL 40,28 / 77,25 $ | `preventivo/pcbway_file_10.jpg`, `pcbway_file_100.jpg` |
Voci JLC a 100 pz: progettazione 25,00 · ENIG 57,10 · test elettrico 14,50 · pellicole 6,40 · scheda 175,00 · conferma
file 1,05 $. → **JLC resta il fornitore più economico** (279 contro 351 $ a 100 pz).

**Assemblaggio coi file (BOM + CPL): BLOCCATO.** Su JLCPCB la sezione PCBA si apre (Economic/Standard, lato top, 10/100
pz) ma «NEXT», dove si caricano BOM e CPL e compare il prezzo dei componenti e del montaggio, porta al login. Per l'account:
password generata e salvata nel Portachiavi (`claude-jlcpcb.com`, utente daniele@movingonebillionpeople.org), modulo
compilato (Personal, Italia, solo i termini, niente newsletter), poi **"Security Verification" con reCAPTCHA «I'm not a
robot»** → mi sono fermato (non si aggira un captcha). PCBWay: la registrazione ha **due iframe captcha** → non tentata.
Serve Daniele per 2 minuti: risolvere il captcha (o accedere con Google) su jlcpcb.com con quella email; poi carico io BOM e
CPL e leggo il prezzo di montaggio e il DFM. Fino ad allora il montaggio resta la stima con le tariffe pubblicate
(`kicad/costi.py`: 15,04 $ a scheda a 10 pz, 4,64 $ a 100 pz, moduli saldati a mano compresi).

**CSP AW32901 passo 0,4 mm:** accettabile secondo le capacità pubblicate JLC (pad BGA minimo 0,2 mm, con ENIG fra 0,20 e
0,25 mm: i nostri sono 0,23 NSMD su ENIG; pagina jlcpcb.com/capabilities/pcb-capabilities, 19/11). Il ponte di maschera
fra i pad (0,07 mm) è sotto il minimo di 0,10 mm: JLC lo toglierà fra i pad del CSP. **Conferma DFM vera: solo dopo il
login** (stesso blocco di sopra).


## Cosa ho caricato e cosa no (onesto)
- **Gerber/BOM/CPL veri NON caricati**: il layout non è sbrogliato (375 collegamenti aperti, `kicad/DRC.rpt`), quindi
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

## Assemblaggio — stima del 1° giro (SUPERATA dopo il VETO 1: conto aggiornato in `kicad/costi.py` e sotto)
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

## JLCPCB per la scheda nuda (ottenuto dopo il VETO 1, 18/11 sera) — stesso fornitore del montaggio
cart.jlcpcb.com/quote da script (senza login): 4 strati, 250 × 50 mm, FR-4 TG135, 1,6 mm, ENIG 1 µ", rame 1 oz / 0,5 oz
interno, pezzi singoli. Screenshot: `preventivo/jlcpcb_10_ENIG_4L.jpg`, `preventivo/jlcpcb_100_ENIG_4L.jpg`.
| Quantità | PCB JLCPCB (prezzo web) | per scheda | Spedizione UPS Express Saver **DDP** | Totale |
|---|---|---|---|---|
| 10 | **60,00 $** | 6,00 $ | 31,07 $ | 91,07 $ |
| 100 | **297,00 $** (con consegna 3-4 gg, +86,50 $ inclusi; con 4-5 gg costa meno se si ordina anche il PCBA) | 2,97 $ | 60,92 $ | 357,92 $ |
JLC costa meno di PCBWay (60 vs 131 $ a 10 pz, 297 vs 351 $ a 100) e monta anche: **scelgo JLC come fornitore unico** per
il conto (DESIGN §7, `kicad/costi.py`). Il paese della spedizione resta quello proposto dalla pagina (DDP = dazi
inclusi): DA VERIFICARE verso l'Italia nel carrello.

## Assemblaggio dallo stesso fornitore: perché manca ancora il numero vero
JLC e PCBWay danno il prezzo di montaggio solo caricando gerber + BOM + CPL; i gerber veri arrivano dopo lo sbroglio.
Fino ad allora vale la stima con le tariffe JLC pubblicate, comprese **la saldatura a mano dei 2 moduli castellati
forniti da noi** (176 giunti × 0,0164 $ = 2,89 $ a scheda, più 3,58 $ a ordine) e 23 Extended × 3,07 $.

## Costo per scheda e per scenario → `DESIGN.md §7`
