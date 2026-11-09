# Passaggio di consegne — calibrazione camere ai bordi (asmile #001 + asmile-logger001)
2026-11-09 sera. Da leggere per primo in una nuova sessione.

## Obiettivo
Depth stereo ≤2% sotto 5 m **anche ai bordi** (dove i due campi si sovrappongono) e dy < 1 px in tutte e 9 le zone
dell'immagine, su due unità DIVERSE (mai confonderle, calib separate):
- **#001**: 2 OV9281 Inno-Maker separate (M12), 1280x800, baseline 200 mm, rpicam --sync; cam0=video_left=fisicamente DESTRA, order RL.
  Calib in uso: `logger/depth/calib_asmile-001.json` (centro ottimo 0.5-1% fino 15 m; bordo sx +4…+17%, dy −4 px a x<430).
- **logger001**: Arducam Camarray SBS 2560x800, 1 CSI, baseline 200 mm. Mai calibrata col metro (video del 9/11 perso:
  logger-cleanup ha cancellato le clip con orologio non sincronizzato → fix da proporre, vedi lezioni asmile-deploy).

## Cosa sappiamo
- Rapporto: `agents/rapporti/calib_001_vicino_bordi_20261109.md` (tabelle prima/dopo, PnP, dy per zona).
- Rifit joint col metro del pomeriggio: SCARTATO (peggiora la mattina, parametri contro i limiti).
- Ricerca: `agents/ricerche/calib_bordi_tunnel_virtuale_20261109.md` → **ChArUco a monitor + modello rational/thin-prism,
  viste in tutte le 9 zone**; scettico PASSA parziale con condizioni:
  1. `logger/depth/calib_charuco.py` legge solo SBS: serve variante per 2 file separati sincronizzati (#001);
  2. aggiungere griglia 3x3 con minimo corner per zona + viste tenute fuori + dy per zona;
  3. prima di chiamare Daniele: test sintetico sul Mac (render della scacchiera con distorsione nota → il fit la ritrova?);
  4. verificare a fuoco/moiré del monitor con le OV9281 (M12 a fuoco ~infinito: a 0.6-1.5 m i corner possono essere molli →
     monitor grande e più lontano, o stampa A2/A1 rigida).
- Lezioni: `agents/lezioni/asmile-calib.md`, `agents/lezioni/daniele.md`.

## Piano (in ordine)
1. Variante `calib_charuco.py` per #001 (due file) + copertura 3x3 + hold-out + report dy per zona. Test sintetico verde.
2. Messaggio a Daniele: UNA sessione da 10 minuti per bici (prima #001, poi logger001 a Wi-Fi già collegato da minuti):
   scacchiera (monitor o stampa rigida) in tutte le 9 zone, inclinata 20-40°, 40-60 viste, + 3 soste col metro al centro come controllo.
3. Fit → `calib_<unità>.CANDIDATO.json` → asmile-calib-critico (bordi con PnP, metro solo al centro) → solo col PASSA sostituisce la calib.
4. Ripassare L1.depth_moto (veto 2/3: non bruciare il 3° senza dati nuovi).

## Comando per partire
In una nuova sessione Claude Code in `projects/asmile`:
`/asmile-capo` e poi: "leggi agents/rapporti/HANDOFF_calib_camere_20261109.md e porta a termine il piano"

## Stato al passaggio (2026-11-09 ~16:45, istanza calib)
Fatto (punto 1 del piano, solo Mac, nessun Pi toccato, nessun messaggio a Daniele):
- `logger/depth/calib_charuco_dual.py`: profili per unità fissi (#001 = 2 file, video_left=camera DESTRA, order RL,
  accoppiamento controllato coi sensor_ts dei frames_*.csv; logger001 = SBS, order/flip da confermare). Copertura 3x3
  per camera (minimo 150 corner a zona), 1 vista ogni 5 tenuta fuori dal fit (scelta fissa), modello rational e
  rational+prism scelto sulle viste tenute fuori, stereo con intrinseci fissi e poi rifinito tutto insieme, T riscalata
  a 200 mm (in metri come calib_asmile-001.json), dy ed errore di scala (lato triangolato vs metro) per zona sulle viste
  tenute fuori, gate VERDE/ROSSO. Scrive solo file con "CANDIDATO" nel nome.
- `logger/depth/test_calib_charuco_dual_synth.py` (esito in `test_calib_charuco_dual_synth.esito.json` + `.log`): render
  con distorsione nota (rational+thin-prism, simile a #001), 2 h264 a 500 kbps con la convenzione file di #001, punti
  3D di verità indipendenti a 1-5 m. **TEST VERDE**: 9 zone → caso peggiore dy |p95| 0.77 px (basso-sx), depth |p95|
  1.12% (basso-dx), centro 0.17%, |T| 200.0 mm. Controllo negativo solo-centro → gate ROSSO (bordi depth p95 8-12%, dy
  3-4 px: lo stesso difetto di oggi su #001). Soglia interna più severa (0.5 px / 1%): la mancano basso-sx e basso-dx.
  Lezione: la prima prova è venuta ROSSA perché era coperta solo la camera sinistra → **vanno coperti gli angoli di
  ENTRAMBE le camere**: le due sono ruotate di ~5° fra loro (va detto a Daniele).
- Tabelloni: `logger/depth/board_charuco_A2_11x8_50mm.pdf` (stampa al 100%, quadretto 50 mm, poi misurare 10 quadretti
  col metro → --square-len) e `board_charuco_monitor_12x7_1920x1080.png` (variante a monitor, il lato va misurato).
- Palla passata ad asmile-calib-critico (artefatto calib_charuco_dual.py, nessun gate): **verdetto IN CORSO** al
  passaggio, controllare con `python3 agents/palla.py stato`.

Resta: verdetto del critico; punto 2 (sessione scacchiera con Daniele: 40-60 viste inclinate 20-40°, tutte le 9 zone
di ENTRAMBE le camere, 3 soste col metro al centro; prima #001, poi logger001); NON VERIFICATO col sintetico: fuoco M12
a 0.6-1.5 m, moiré del monitor, sync reale; poi punti 3-4 del piano.
