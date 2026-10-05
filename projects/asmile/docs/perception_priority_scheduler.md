# Perception Priority Scheduler — percezione CPU-only per Asmile

> Casa PROGETTO → KNOWLEDGE. Nasce dalla voce di Daniele (2026-10-05) + dal post LinkedIn di
> **Affan Khan** su un sistema di percezione **CPU-only** su filmati di guida reale.
> Scopo: portare lo schema di Affan su Asmile (Raspberry Pi 5, no GPU) **senza sovraccaricare il
> Pi**, con stima di profondità (depth) sui segmenti che contano durante la guida.
> **DA FIRMARE** — proposta + scaffold, niente va in campo senza firma in `DECISION_LOG.md`.

## 1. Cosa fa Affan (lo schema da rubare)
Un sistema di percezione costruito a strati, girato **su CPU** su video di guida vera. Risponde a:
*cosa c'è intorno, dov'è la strada guidabile, come si muovono gli oggetti, a cosa vale la pena
prestare attenzione.* Moduli: object detection + tracking stabile, human pose, moto nello spazio
immagine (direzione), drivable-area, e una **Perception Priority Map** (priorità relativa della
scena, non attention umana né collision prediction).

**Il numero che conta per noi** — stessa CPU limitata, moduli a **rate diversi**:
- detection **~4 Hz** (lento, pesante)
- road/drivable perception **~1 Hz** (lentissimo)
- **display ~22 FPS**, **0% stale tracking** (il tracker riempie i buchi fra una detection e l'altra)

La lezione non è "quale modello": è l'**architettura**. Non fai girare tutto a 15–30 FPS. Fai
girare il pesante di rado, e un tracker leggero tiene aggiornate le posizioni ad alto rate. La
Priority Map decide *dove spendere* il poco compute che resta.

## 2. Perché calza perfetto su Asmile
Oggi su Asmile la percezione è spaccata in due estremi:
- `pi/autonomous/vision_safety.py` → CV leggerissima (motion, blob, bordi strada), **niente YOLO
  sul Pi**, gira a basso Hz. Robusta ma cieca al *cosa*.
- `pi/autonomous/object_depth.py` → YOLOv8m-seg + depth da bbox, ma **YOLO sul Pi è troppo pesante
  a frame rate pieno**. Oggi si usa offline / sul Mac.
- `follow_me/disparity.py` → **StereoSGBM** (OpenCV) per depth densa, pesante: oggi acceso solo in
  follow-me, su tutta l'immagine.

Lo schema di Affan **unisce i due estremi**: YOLO (pesante) a 2–4 Hz, un **tracker leggero** che
propaga i box a 15 FPS, e la **depth densa (SGBM) calcolata SOLO dentro le ROI che la Priority Map
marca come importanti** — non su tutto il frame. Così il Pi non frulla mai l'intera immagine col
modello pesante, e la depth stereo (costosa) si paga solo dove serve davvero.

## 3. Architettura proposta — scheduler multi-rate
```
            ┌──────────── camera (stereo 2560x800 @15fps, GREY) ────────────┐
            │                                                               │
  [15 FPS]  frame LEFT ──► TRACKER leggero (CSRT/KCF OpenCV o IOU+flow)      │
            │                 ▲  propaga i box fra detection, stima moto     │
            │                 │                                              │
  [2-4 Hz]  └─► DETECTOR (YOLOv8n-seg o MobileNet-SSD INT8) ─► box+classi ───┘
                              │ (ogni N frame, ridimensionato a 320/416)
                              ▼
  [~1 Hz]   DRIVABLE-AREA (CV: bordi strada + ground plane) ─► corridoio libero
                              │
                              ▼
            ┌──── PERCEPTION PRIORITY MAP ────┐  score per oggetto da:
            │  classe · posizione · moto ·    │  (persona>auto>statico),
            │  dentro-corridoio · confidenza  │  (centro>bordo), (verso di noi),
            └──────────────┬──────────────────┘  (dentro drivable), (conf)
                           ▼
  [on-demand]  DEPTH SOLO sulle top-K ROI prioritarie:
                 • bbox-depth (object_depth.py) sempre, ~0 costo
                 • StereoSGBM (disparity.py) SOLO dentro le ROI top-K  ◄── chiave anti-carico
                           ▼
            intento di guida (frena / rallenta / scansa) ──► speed_limiter v2 (owner GPIO)
```

Regole di rate (configurabili, punto di partenza):
- **Tracker**: ogni frame (~15 FPS). È OpenCV puro, leggero.
- **Detector**: 1 ogni 4–8 frame (2–4 Hz). Frame ridotto (320–416 px lato lungo), INT8.
- **Drivable-area**: ~1 Hz. CV classica, nessun modello.
- **Depth SGBM**: on-demand, solo top-K ROI (K=2–3), mai full-frame in marcia.
- **0% stale**: se una detection scade e il tracker perde il lock → l'oggetto si marca `stale` e
  cade dalla Priority Map, non resta a mentire (esattamente il "0% stale tracking" di Affan).

## 4. Depth dei segmenti che contano (la parte che Daniele ha chiesto)
Due livelli, dal gratis al costoso — si sale solo quando serve:
1. **bbox-depth** (già in `object_depth.py`): distanza da altezza/larghezza nota dell'oggetto +
   ground-plane per l'ignoto. Costo ~0, gira su ogni box tracciato. Prima stima sempre disponibile.
2. **StereoSGBM ritagliata** (da `follow_me/disparity.py`): disparità densa **solo nel ritaglio
   della ROI prioritaria**. Dà depth vera (non assume la taglia dell'oggetto), utile per ostacoli
   sconosciuti e per il muro/corridoio. Costo proporzionale all'area → ritagliando le top-K ROI il
   costo crolla rispetto al full-frame.
3. **Cross-check**: se bbox-depth e SGBM divergono troppo su un oggetto prioritario → flag di
   bassa confidenza (non ci fidiamo di una sola fonte sull'oggetto che conta).

Questo è il "depth dove conta": non una depth-map densa buttata via, ma profondità pagata **solo
sui segmenti che la Priority Map ha già detto essere importanti** per la guida ora.

## 5. OpenCV ci basta? — sì, per quasi tutto
- **Tracker**: `cv2.legacy.TrackerCSRT`/`KCF`, oppure `cv2.calcOpticalFlowPyrLK` + IOU. OpenCV puro.
- **Drivable-area / bordi**: Canny + Hough + ground-plane, già lo stile di `vision_safety.py`.
- **Depth**: `cv2.StereoSGBM` (già usato in follow-me) + rettifica da `stereo_calibration.yaml`.
- **Moto nello spazio immagine**: optical flow (OpenCV) o delta-centroide del tracker.
- **Detection**: qui OpenCV da solo non basta per le *classi*. Opzioni, in ordine di leggerezza:
  - **YOLOv8n** (nano) export **ONNX** → `cv2.dnn` o `onnxruntime` CPU, input 320. Molto più
    leggero del `yolov8m-seg` attuale.
  - **MobileNet-SSD INT8** via `cv2.dnn` — il più leggero, meno preciso.
  - **NCNN / tflite** se vogliamo spremere il Pi. Da misurare.
  - **Human pose** (opzionale, come Affan): MoveNet-lightning tflite, solo se avanza budget.

## 6. Gira agile sul Pi? — ipotesi da misurare (gate prima di costruire tutto)
Target su Pi 5 (4 core A76), tutto a 1280→ridotto:
- Tracker CSRT su 2–4 box a 320px: atteso **<30% di un core** → ~15 FPS ok.
- YOLOv8n-ONNX 320 INT8, 1 inferenza: atteso **120–300 ms** → **3–8 Hz** plausibile (da misurare).
- SGBM su ROI 200x200: pochi ms; su full-frame 1280 è 100+ ms (per questo si ritaglia).
- Drivable CV a 1 Hz: trascurabile.

**Gate G0 (benchmark) prima di tutto**: `perception_scheduler.py --benchmark` su un video di
logging stampa Hz reali e %CPU per stadio. Se YOLOv8n-ONNX non supera ~2 Hz sul Pi, si scende a
MobileNet-SSD o si alza l'intervallo detection. **Non si costruisce il resto finché G0 non passa.**

## 7. Pipeline di lavoro (step che poi facciamo insieme)
1. **G0 — Benchmark** su Pi: misurare Hz/CPU di tracker, YOLOv8n-ONNX@320, SGBM-ROI, drivable.
   → `perception_scheduler.py --benchmark --video <sessione>`. *(scaffold pronto)*
2. **Export YOLOv8n→ONNX INT8** (sul Mac) e drop sul Pi. Verificare caricamento con `cv2.dnn`/ORT.
3. **Tracker leggero**: wrappare CSRT/flow, test 0% stale su un video (lock/lost/re-acquire).
4. **Priority Map**: formalizzare lo score (pesi classe/posizione/moto/corridoio/conf) e tararlo
   sui pattern P1–P9 già scritti (`docs/.../driving_patterns`).
5. **Depth on-demand**: collegare `object_depth` (sempre) + SGBM-ROI (top-K) con cross-check.
6. **Shadow mode**: girare lo scheduler in parallelo alla guida, **solo log**, confronto con
   `shadow_mode.py`. Nessun attuatore finché non firmato.
7. **Integrazione soft** con `speed_limiter v2` via flag/socket (owner unico GPIO), mai GPIO diretto.

## 8. Cosa NON è / linee rosse ereditate
- Non pilota il GPIO: parla a **speed_limiter v2** (`/tmp/emergency_brake`), owner unico.
- Non va in strada senza firma Daniele in `DECISION_LOG.md`. Prima: shadow + benchmark.
- Non è un rewrite: **riusa** `object_depth.py`, `disparity.py`, `vision_safety.py`. Ci mette
  sopra solo lo *scheduler multi-rate* + *tracker* + *priority map*.
- Freno idraulico MAI oltre 60°, limiti autonomi < umani (vedi `CONTEXT.md`).

## Riferimenti
- Post di Affan Khan — sistema di percezione CPU-only su filmati di guida reale (object
  detection+tracking, human pose, image-space motion, drivable-area, Perception Priority Map).
- `pi/autonomous/object_depth.py`, `follow_me/disparity.py`, `pi/autonomous/vision_safety.py`,
  `pi/autonomous/shadow_mode.py`.
- Scaffold: `pi/autonomous/perception_scheduler.py`.
