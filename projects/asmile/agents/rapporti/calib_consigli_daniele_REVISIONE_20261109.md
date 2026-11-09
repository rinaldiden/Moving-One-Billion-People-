# Calibrazione camere: i consigli di Daniele passati agli agenti calib + strategia rivista (2026-11-09 sera)

**Per:** asmile-calib, asmile-calib-critico, asmile-depth, asmile-capo (istanza che porta avanti
`HANDOFF_calib_camere_20261109.md`). **Stato:** PROPOSTA. Cambia l'ordine e i gate della calib, ma non firma niente:
le firme stanno in D012 (DECISION_LOG, DA FIRMARE).
**Da leggere prima:** `HANDOFF_calib_camere_20261109.md`, `calib_SOLUZIONE_DEFINITIVA_20261109.md`,
`calib_001_vicino_bordi_20261109.md`, `../lezioni/asmile-calib.md`.

---

## 0. Prima di applicarli: a quale unità si riferiscono i consigli

I consigli di Daniele partono da un caso preciso: "RMS 1.27, errore depth 7.8%, Camarray 2560x800, FOV ~118°". Quei
numeri sono della linea **Camarray** (asmile2 e oggi **asmile-logger001**), **non di #001**. Regola: mai confondere le unità.

| | **asmile #001** | **asmile-logger001** |
|---|---|---|
| Camere | 2 OV9281 Inno-Maker **separate**, 2 CSI, rpicam --sync | Camarray SBS 2560x800, 1 CSI |
| FOV misurato | f ≈ 1150 px su 1280 → **HFOV ≈ 58°** (da `calib_asmile-001.json`) | da misurare (lente diversa) |
| Stato oggi | centro 0.5-1% fino a 15 m (mattina); **bordi +4…+17%**, dy −4 px a x<430, offset dy +1.4 px nel pomeriggio | mai calibrata col metro; il video del 9/11 è andato perso |
| "RMS 1.27 / 7.8%" | **non è suo** | è il punto di partenza del consiglio |

Conseguenza pratica: su #001 il problema non è "il centro al 7.8%". Il centro è già buono. Il problema sono **i bordi e
la stabilità del dy**. I consigli servono soprattutto lì, e sul logger servono tutti.

---

## 1. Consiglio per consiglio: cosa c'è già, cosa cambia, cosa resta aperto

| # | Consiglio di Daniele | Stato nel repo | Cosa cambia (proposta) |
|---|---|---|---|
| 1 | **ChArUco**, niente scacchiera pura | ✅ `calib_charuco_dual.py`, tabelloni A3 10x7 38 mm e A2 11x8 50 mm, PNG per monitor | Nessuna modifica. L'ultima ripresa di #001 (153251) era ancora una **scacchiera 7x10 a mano** → la prossima solo ChArUco |
| 2 | **Board piatta e rigida** (fa la differenza fra 1.3 e <0.5) | ⚠️ Il foglio A3 stampato è montato a mano: non è rigido | **Gate fisico prima di riprendere:** A2/A3 incollato su MDF/forex/vetro ≥5 mm, opaco. Lato di 10 quadretti misurato col metro → `--square-len`. Planarità: righello sulle due diagonali, luce sotto <0.5 mm |
| 3 | **Modello per il wide FOV** (rational o fisheye) | ✅ rational e rational+prism, scelti sulle viste tenute fuori | **Fisheye NON serve su #001** (58°, non 118°): il modello equidistante per lenti ≤60° di solito peggiora. Da aggiungere come 3° candidato **solo `rational+prism+tilted`** (`CALIB_TILTED_MODEL`): il dy −4 px a sinistra NON è radiale (lezione calib), e potrebbe essere il sensore inclinato sulla M12. Sul logger: misurare prima il FOV, poi decidere (se >100° provare anche `cv2.fisheye` nel confronto sulle viste tenute fuori) |
| 4 | **RMS stereo < 0.5-1 px** | ⚠️ Lo script stampa l'RMS ma **il gate non lo usa** | Aggiungere al gate: RMS mono < 0.5 px per camera **e** RMS stereo < 1 px (obiettivo 0.5), **calcolati sulle viste tenute fuori**. L'RMS sulle viste del fit è un residuo, non una prova: da solo non chiude nessun gate |
| 5 | **Baseline risultante ~200 mm** | ❌ Oggi lo script **riscala T a 200 mm** (tautologico: correzione 7 del critico) | **Inversione:** non riscalare più T. |T| viene dal tabellone (lato misurato) ed è un **controllo**. ROSSO se fuori 200 mm ±3% (correzione 3 del critico). Se è dentro ma ≠200 di più dell'1%, la baseline va **misurata col calibro sui centri delle lenti**, non forzata |
| 6 | **Mappe di rettifica + intrinseci/estrinseci in YAML/JSON** | ✅ JSON `calib_<unità>.json`, `Calib.rectify` in `stereo_common.py` | Aggiungere (solo export, il JSON resta la fonte): `calib_<unità>.CANDIDATO.yaml` in formato OpenCV FileStorage (K1,D1,K2,D2,R,T,R1,R2,P1,P2,Q, modello, RMS, data, hash video) e mappe `initUndistortRectifyMap` salvate come `.npz` per il Pi (niente ricalcolo a ogni avvio) |
| 7 | **Validazione depth 1-2-5-10 m al centro e ai lati** | ✅ banco fisso centro 1-15 m; ⚠️ bordi solo col PnP, mai col metro | Griglia fissa **4 distanze × 3 posizioni = 12 punti** (1, 2, 5, 10 m × sx / centro / dx), con la posizione laterale misurata in **cm col metro dal centro** (ieri lo scarto ai bordi era quasi tutto Daniele più lontano del nominale). A 1 m i lati escono dal campo comune: lì "fuori campo" è un esito valido, non un buco |
| 8 | **SGBM o WLS, subpixel, filtra bassa confidenza** | ✅ `depth.py`: SGBM /16 subpixel, WLS, left-right consistency, uniqueness 12, speckle | Manca il **filtro sulla confidenza WLS** (`getConfidenceMap()`): pixel sotto soglia → invalido, invece di "riempito". Per la verità a terra misurare sul **bersaglio**, mai sul riempimento WLS |
| 9 | **Se l'errore laterale resta alto → ricattura con più bordi** | ✅ copertura 3x3 per camera, minimo 150 corner a zona | Già regola. In più: gli angoli vanno coperti in **ENTRAMBE** le camere (lezione dal sintetico: le due sono ruotate di ~5°) |
| 10 | **Global shutter: esposizione corta + buona luce** | ⚠️ `dual_cam_recorder.py` non fissa lo shutter (auto) | Per la sola clip di calibrazione: `--shutter 2000-4000 µs`, gain fisso, `--awb`/`--ev` fissi, luce diffusa (all'aperto ombra, no sole diretto sul foglio). È un parametro di registrazione e **non tocca il codice del Pi**: va proposto a Daniele come comando della sessione, non deployato |
| 11 | **Sync timestamp left/right** | ✅ #001: rpicam --sync ≤0.045 ms (07/11); lo script accoppia coi sensor_ts dei frames_*.csv | Aggiungere al report: Δt per coppia (p50/p95/max) e **scarto delle coppie con Δt > 1 ms**. Sul logger (SBS) il sync è di scheda: basta registrarlo |
| 12 | **Librerie semplificate (calibrating di DIYer22, tool tipo Luxonis)** | — | **Come seconda opinione, non come sostituto.** `calibrating` (pip, ChArUco, viste di rettifica e depth nel browser) e il flusso Luxonis girano sugli **stessi video**: se danno R/T/dy diversi dai nostri oltre la soglia, è un campanello. Non sostituiscono il nostro script perché non hanno hold-out per posa, dy per zona né il gate per unità. Kalibr resta l'opzione pesante solo se il bordo sinistro non si chiude con OpenCV |

---

## 2. Dove i consigli **cambiano la strategia**

1. **La baseline smette di essere un'ipotesi e diventa una prova.** Fino a oggi ogni calib di #001 aveva `baseline_mm 200.0`
   imposto. Il consiglio "controlla che risulti ~200 mm" ribalta la cosa: è il primo controllo indipendente della scala che
   abbiamo **senza metro**. Se il tabellone dice 196 o 204, la scala delle depth di oggi è sbagliata di 2%, e questo
   pesa più di qualsiasi rifinitura dei bordi.

2. **Il collo di bottiglia del bordo è il bersaglio, non il software.** Lo script, il sintetico e il critico ci sono già.
   Mancano un **tabellone rigido** e una ripresa delle **9 zone di entrambe le camere**, con esposizione corta. Prima
   di toccare altro codice serve **una ripresa fatta bene**.

3. **Il fisheye esce dal tavolo per #001, entra il modello "tilted".** Il consiglio "fisheye se necessario" applicato ai
   numeri veri dice: non necessario a 58°. Il dy non radiale a sinistra punta invece a sensore/lente inclinati → modello tilted.

4. **Scala 15.000: un punto da firmare, non un conflitto.** Il consiglio "calibrazione di fabbrica ripetibile (dima +
   tabellone grande + script)" sembra la **stazione nostra che Daniele ha SCARTATO** (calib15000_METODO). Letto con la
   SOLUZIONE_DEFINITIVA si compone così:
   - **la dima la fa il fornitore** (modulo monoblocco 200 mm calibrato per seriale, bozza e-con NON inviata);
   - **il nostro script automatico** (`calib_charuco_dual.py` + gate) diventa il **collaudo a campione** per lotto e lo
     strumento con cui verifichiamo il file del fornitore;
   - **montaggio ripetibile** = tolleranze nella richiesta d'offerta (baseline, angolo relativo fra sensori, centratura
     lente) + prova smonta/rimonta x3 sul logger;
   - **self-calibration online** = autoregistrazione già in SOLUZIONE (dy/rotazione dalle immagini, scala e d0 dal moto
     con encoder ruota), monitor deriva 0.5 px;
   - **stile Tesla** = allievo allenato con piccoli errori di calibrazione simulati (già in SOLUZIONE).
   La domanda aperta va a Daniele (Q11): con "jig fisso" intendevi la **dima del fornitore** (compatibile) o vuoi
   **riaprire la stazione nostra**? Gli agenti non decidono.

5. **"Prima 2, poi poche, poi automatizza".** Ordine confermato: **#001 → asmile-logger001 → 3-5 monoblocchi**. Niente
   lavoro su 15.000 finché #001 non ha il PASSA ai bordi.

---

## 3. Piano rivisto (in ordine, ognuno col suo contro-agente)

**A. Codice, solo sul Mac** (asmile-calib → asmile-calib-critico). Ai 7 punti del critico già aperti nell'HANDOFF si aggiungono:
- A1 = critico 1-7 (T[0]≥0 ROSSO, zona vuota ROSSO, |T| 200±3% ROSSO, file scambiati nel sintetico, p95 dy<1 px, hold-out a
  blocchi di tempo, **niente riscalatura di T**);
- A2 = RMS mono/stereo **sulle viste tenute fuori** nel gate (consiglio 4);
- A3 = 3° modello candidato `rational+prism+tilted`; fisheye solo se il FOV misurato è >100° (consiglio 3);
- A4 = export YAML OpenCV + mappe `.npz` (consiglio 6);
- A5 = Δt coppie nel report, scarto >1 ms (consiglio 11);
- A6 = sintetico rifatto con sensore inclinato di 0.3° su una camera: il tilted lo ritrova? Gli altri due modelli no?
- A7 = `depth.py`: filtro confidenza WLS opzionale (consiglio 8), **solo aggiunta, default invariato**.

**B. Ripresa con Daniele** (UNA sessione da ~15 min, prima #001; messaggio semplice tramite asmile-capo, quando A1-A2 passano):
1. tabellone A2 su pannello rigido, lato misurato col metro;
2. comando di registrazione con shutter corto e gain fisso (lo prepara asmile-calib; nessuna modifica al Pi);
3. 40-60 viste **ferme**, inclinate 20-40° (mai >45°), che coprono le 9 zone di **entrambe** le camere, a 0.8-2.5 m (attenzione al fuoco M12 vicino: se i corner sono molli, più lontano e più grande);
4. subito dopo, sulla stessa clip o su quella dopo: **griglia 12 punti** 1-2-5-10 m × sx/centro/dx, con la posizione laterale misurata in cm.

**C. Fit e giudizio** → `calib_asmile-001.CANDIDATO.json/.yaml` → asmile-calib-critico (bordi sulla griglia col metro + PnP,
dy p95 su tutta l'immagine in moto) → sostituisce la calib **solo** col PASSA e se non peggiora nessun punto del banco fisso
(4-6-8-12 m). Seconda opinione con `calibrating` sugli stessi video, solo come confronto.

**D. asmile-logger001** con lo stesso metodo, poi smonta/rimonta x3 (misura di tolleranza per la richiesta d'offerta).

**E. Depth + segmentazione** (asmile-depth): solo dopo C, il maestro sul Mac (stereo moderno + monoculare ancorato) usa
le immagini rettificate con la calib PASSATA. La depth fa da prior e da feature; finché la calib non passa ai bordi,
**la depth laterale non comanda niente**.

---

## 4. Gate proposti (da firmare in D012)

| Gate | Soglia proposta | Dove si misura |
|---|---|---|
| RMS mono | < 0.5 px per camera | viste tenute fuori |
| RMS stereo | < 1 px (obiettivo 0.5) | viste tenute fuori |
| dy rettificato | p50 < 0.5 px, **p95 < 1 px** in tutte le 9 zone | viste tenute fuori + SIFT in moto |
| Baseline | \|T\| dal tabellone = 200 mm ±3% (fra ±1% e ±3%: misurare col calibro) | fit senza riscalatura |
| Depth centro | ≤ 2% a 1-2-5 m, ≤ 3% a 10 m | griglia col metro, punti mai nel fit |
| Depth bordi | ≤ 3% a 2-5 m (oggi +4…+17%), a 10 m solo misurato | griglia col metro + PnP |
| Sync | Δt coppia p95 < 1 ms, scarto oltre | report fit |

Nota onesta: "sotto il 2-3% nelle distanze utili" è l'obiettivo di Daniele. Che lo raggiungiamo ai bordi di #001 **NON è
verificato**: oggi il sintetico lo dà (p95 1.1%), i dati veri no.

---

## 5. NON VERIFICATO
- Che il dy sinistro di #001 sia un sensore inclinato (ipotesi dalla forma non radiale).
- FOV reale delle lenti del logger (il "118°" della nota è un valore tipico, non misurato da noi).
- Che un pannello rigido porti #001 da bordi +4…+17% a ≤3% (il consiglio "1.3 → <0.5" vale per l'RMS, non per la depth ai bordi).
- `calibrating` (DIYer22): letto solo README/PyPI (ChArUco, viste di rettifica, ~43 stelle, poco attivo), mai provato sui nostri video.
- Fuoco M12 a 0.8-1.5 m con il tabellone A2.

Fonti esterne: [github.com/DIYer22/calibrating](https://github.com/diyer22/calibrating), [PyPI calibrating](https://pypi.python.org/project/calibrating/0.5.24/).
