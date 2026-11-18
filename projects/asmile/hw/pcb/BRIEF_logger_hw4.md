# Brief asmile-hw-pcb — scheda dedicata logger HW4 (dal capo, 18/11/2026)

Lavori in un'istanza dedicata. Il capo (sessione principale) rilegge OGNI riga che committi: lavora pulito, un commit
per passo, messaggi chiari. Scrivi in italiano semplice. Repo: `~/progetti/Moving-One-Billion-People-`.

## Il compito (parole di Daniele)
- «Fai un giro su KiCad o simile per fare una schedina dedicata partendo dal BOM di HW3 del logger. Semplifica,
  unifica, e lato compute stai più largo per poterci mettere mano se serve. Voglio arrivare a 25 € cad di schedina +
  cam. Anche le cam le sceglierei giuste per quello che ci interessa: tutto quello che si fa in sw lo facciamo in sw,
  meno hw c'è meglio è.»
- «Guarda la struttura hw che c'è di base da rifare e tutto lo stack che gira sopra — e che ci potrà girare — per
  creare una base hw che supporti sviluppi futuri rispetto alla direzione del progetto e prodotto.»
- «Sa leggere tutti i datasheet e incrociare funzionalità e funzionamenti. Cerca su forum, dev, git per migliorarsi;
  autoapprende da quello che è ok e da quello che sbaglia, da tutti i registri sw e hw.»
- «Alla fine si logga in PCBWay per fare il preventivo.»

"25 € cad di schedina + cam" è ambiguo: dai il costo in entrambe le letture (25 € tutto / 25 € scheda + camere a parte).

## Cosa c'è oggi (HW3 = logger02)
2 × Waveshare ESP32-P4-Module-DEV-KIT (A master, B slave), ciascuna con 1 × Inno-Maker OV9281 (global shutter mono,
MIPI, 1280×720 RAW8 @16,67 fps, baseline 200 mm, TRIG/FSIN hardware da GPIO3 della A), wifi via C6 (ESP-Hosted SDIO),
microSD, H.264 hw su SD a pezzi da 60 s + CSV frame; MPU6050 sulla A (I2C GPIO7/8, INT GPIO4 sveglia dal deep sleep),
partitore batteria su ADC; sync A↔B con fili GPIO SYNC/WAKE + UART; saluto vocale ES8311 + altoparlante;
2 × 18650 2P, MH-CD42 solo caricatore, MT3608 step-up 5,1 V, USB-C, LED RGB KY-016, interruttore.
Firmware ESP-IDF 5.5.6 con OTA, Tailscale (MicroLink), download dal Mac via wifi.
Leggi: `projects/asmile/logger02/README.md`, `projects/asmile/logger/hw3/PIN_logger002.md`,
`projects/asmile/logger/hw3/PROVA_20261117.md`, `projects/asmile/logger02/firmware/main/*.c`.
logger001 (Pi 5 + Camarray): `projects/asmile/logger/hw_v2/`. #001 (Pi 5 + 2 OV9281 + encoder + VESC + servofreno) è
un'altra unità. Direzione: `projects/asmile/.collegio/CONTEXT.md` + memoria
`~/.claude/projects/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/memory/` (MEMORY.md,
project_obiettivo_guida_leggera, feedback_logger_vs_001_*): modello leggero a bordo seg + depth ostacoli → freno/sterzo.

## Punti di partenza del capo (DA VERIFICARE, non verità) → `projects/asmile/hw/pcb/CONOSCENZA.md`
P4 regge MIPI + DVP insieme; OV9281 ha anche DVP ma esp_cam_sensor ha solo il driver MIPI; H.264 hw a 2 flussi;
chip OV9281 stock 0 su LCSC (forse obsoleto), OV9782 = versione a colori, SC035HGS = VGA GS MIPI+DVP;
P4NRW32 EOL → P4NRW32X. Idea: un solo P4, sensori saldati alle estremità di una scheda lunga ~220 mm (baseline rigida,
portalente M12 su scheda, niente moduli/flat), FSIN e XCLK comuni, C6 come modulo MINI con antenna, IMU moderna su
scheda, caricatore 1S + buck duty 100%, buzzer al posto di codec+altoparlante, USB-C per carica e flash.
Stima grezza: scheda senza sensori ~13-15 € @100; con 2 × OV9281 + lenti ~30-35 €; con sensori VGA/rolling ~20-25 €.
Smonta o conferma con i datasheet (DCDC core P4, alimentazioni sensori, PCLK DVP max, strapping, pin-compat).

## Consegne
1. `projects/asmile/hw/pcb/STACK_HW.md` — inventario hw flotta + stack sw che gira e girerà; per funzione: sw o hw?
2. `projects/asmile/hw/pcb/logger_hw4/DESIGN.md` — architettura, 2-3 alternative camera, raccomandata e perché,
   datasheet citati (pagina/sezione), rischi e la prova da fare PRIMA di ordinare (es. carico 2 encoder su una P4).
3. `projects/asmile/hw/pcb/logger_hw4/BOM.csv` — parte, LCSC#, Basic/Extended, stock, prezzo 10/100/1000,
   alternativa pin-compatibile; costo per scenario con PCB 4 strati + assemblaggio.
4. Progetto KiCad (`brew install --cask kicad`; se chiede la password del Mac fermati e scrivilo: la lancia Daniele)
   partendo dai reference design open (Espressif ESP32-P4 Function EV Board, progetti P4 open su GitHub).
   ERC/DRC con kicad-cli; gerber, BOM e CPL quando lo schema e il layout reggono.
5. `CONOSCENZA.md` aggiornata: dove si risparmia, dove si spende, lezioni dai registri (`projects/asmile/agents/
   lezioni|decisioni|prove/`, `logger02/DEPLOY_LOG.md`, `feedback_*` in memoria) e da forum/repo, con fonti.
6. **Preventivo PCBWay** (alla fine, coi gerber/BOM/CPL veri): accedi a pcbway.com — se serve un account crealo con
   `~/.asmile_depth_venv/bin/python ~/.claude/skills/compra-miglior-prezzo/account.py nuovo pcbway.com` (password
   generata e salvata nel Portachiavi, email daniele@movingonebillionpeople.org; codice di verifica dalla Gmail o
   chiedi a Daniele con `~/progetti/doppio/telegram-brain/scrivi_a_daniele.py`), browser Playwright Chrome come nella
   skill compra-miglior-prezzo. Carica i file, preventivo PCB + assemblaggio per 10 e 100 pezzi, screenshot e
   numeri in `logger_hw4/PREVENTIVO_PCBWAY.md` (confronta con JLCPCB). **NON ordinare, NON pagare, NON inserire carte**:
   l'ordine è di Daniele.

## Regole
- Non toccare logger02 né il suo firmware; niente OTA/flash/reboot di nessun Pi.
- Segreti mai in chiaro (solo Portachiavi). Email ai fornitori solo come bozza.
- Commit + push solo dei tuoi file in `projects/asmile/hw/pcb/`, chiusi da `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Fine: `python3 projects/asmile/agents/palla.py passa --verticale veicolo --da asmile-hw-pcb --a asmile-pcb-critico
  --artefatto projects/asmile/hw/pcb/logger_hw4/DESIGN.md` + `palla.py bilancio --da asmile-hw-pcb ...`.
- Report finale in ≤40 righe in `logger_hw4/REPORT_CAPO.md`: scelta, costo per scenario, verificato/non verificato,
  2-3 decisioni per Daniele.
