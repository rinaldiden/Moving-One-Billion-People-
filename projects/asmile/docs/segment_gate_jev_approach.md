# Asmile — Gate di selezione segmenti (approccio "Jev / System-1")

> Stato: **BOZZA DA FIRMARE** (Daniele). Design doc. Nessun codice a terra ancora. Niente strada senza firma.
> Data: 2026-10-06. Si innesta su `perception_scheduler.py` + `docs/perception_priority_scheduler.md`.

## 0. Il punto di partenza (onesto)

**Jev** (TypeSafe AI, 15 set 2026) è un modello **"System-1" non-autoregressivo**: in un forward restituisce una **decisione tipizzata + probabilità calibrate** (non testo). Pensato per loop real-time (robot/giochi/sim), 100-400× più economico di un LLM su classificazione/routing/safety-filter.

**Perché NON lo usiamo direttamente:** è (a) **proprietario + cloud API-only**, (b) **solo testo** (non fa visione). Quindi non gira sul Pi e non segmenta. **Non esiste un clone open ufficiale.**

**Cosa prendiamo di Jev:** il *pattern*, non il prodotto → un **gate di decisione velocissimo, CALIBRATO e tipizzato** che per ogni ROI dice `{keep/discard, priorità, confidence}`. L'equivalente open, collaudato e sub-millisecondo su Pi: **GBDT/MLP piccolo calibrato offline + conformal prediction**. È la versione *appresa e calibrata* del `priority_score()` scritto a mano oggi.

## 1. Architettura a stadi (tutto on-Pi, CPU-only)

```
          ┌─────────────── ogni frame (cheap) ───────────────┐
camera →  │ 1. PRE-GATE: MOG2/frame-diff (+opt. flow DIS)     │  decide DOVE/QUANDO
 stereo   │    → regioni con movimento/novità                 │  vale la rete pesante
          └───────────────────────────────────────────────────┘
                              │ (solo se serve)
          ┌──────── gated, non ogni frame (detect_every) ─────┐
          │ 2. ROI/SEG: YOLO11n-seg / YOLO26n (NCNN INT8)     │  classi + box + mask
          │    (EdgeSAM on-demand per mask class-agnostic)     │
          └───────────────────────────────────────────────────┘
                              │ feature per ROI
          ┌──────── ogni ROI, microsecondi (il "Jev-gate") ───┐
          │ 3. GATE System-1: LightGBM/logreg CALIBRATO        │  {keep/discard,
          │    (m2cgen→C) + soglia CONFORMAL (MAPIE)           │   priorità, confidence}
          │ 4. OOD override: Energy-score → "novel? NON scartare"│
          └───────────────────────────────────────────────────┘
                              │ solo i "keep" (top-K)
          ┌───────────────────────────────────────────────────┐
          │ 5. DEPTH (StereoSGBM ritagliata) → distanza + TTC  │
          │    → decisione freno/sterzo NEI LIMITI (≤60°, slew) │
          └───────────────────────────────────────────────────┘
```

Mappa sul codice esistente: lo stadio 3-4 **sostituisce/affianca** `priority_score()` in `perception_scheduler.py`; `topk_depth=3` e `detect_every=6` restano i knob. Il detector va **off-thread** (blocco noto, vedi `mock_pi5_e_test_realtime.md`).

## 2. Il GATE (stadio 3) — cuore "System-1"

**Input (feature per ROI, già prodotte dallo scheduler):** classe (one-hot/weight), dimensione/vicinanza (h/frame_h), posizione orizzontale (|cx-0.5|), dentro-corridoio (0/1), velocità di avvicinamento (vy, |vx|), **TTC = distanza/vel_chiusura** (quando c'è depth), confidenza detector.

**Modello:** `LightGBM` (o `LogisticRegression` per massima semplicità) addestrato **offline sui log**. Output = probabilità calibrata "questo segmento è rilevante per una correzione freno/sterzo".

**Calibrazione (il valore vero di Jev):** `sklearn.CalibratedClassifierCV` — *sigmoid/Platt* con pochi dati, *isotonic* se ne hai migliaia. Poi **soglia conformale** con `MAPIE`: invece di una soglia tarata a mano, una soglia con garanzia statistica di copertura.

**Deploy on-Pi:** esporta con **`m2cgen` → C puro** (zero dipendenze, µs/sample) oppure **`lleaves`**/ONNX Runtime. Online = un forward + confronto soglia → **sub-millisecondo**.

### 2.1 Architettura di riferimento — dai repo open "System-One" (ecosistema 2026)

Esiste un ecosistema open nato sulla scia di Jev. Architettura COMUNE a tutti:
```
stato + opzioni (renderizzati) → ENCODER bidirezionale (UN forward, NON autoregressivo)
  → TESTE TIPIZZATE:  Choice (1 di K, prob. su tutte) · Noul (P(vero), binario) · Score (scala ordinale)
  → LAYER DI CALIBRAZIONE → decisione tipizzata + confidence   (protocollo /v1/systemone)
```
Repo di riferimento:
- **Von** — ModernBERT 395M, drop-in Jev, protocollo `/v1/systemone`, CPU/OpenVINO, `von calibrate` CLI, p50 96ms (Xeon 4-vCPU). github.com/wfzyx/von
- **Laya** — ModernBERT in UN grafo ONNX (no PyTorch runtime). github.com/receptron/laya
- **sys1-fast-encoder-v2** — MiniLM 22M + testa 1-neurone, ~35ms CPU. huggingface.co/ashurath/sys1-fast-encoder-v2
- **sys1** (ashutosh-rath02/sys1), **open_system_one** (Readyaddy). Liste: github.com/yanng981/awesome-system-one, github.com/hiroki-abe-58/awesome-open-system-one
- Kev/Decider/Clef = Qwen fine-tuned, pesanti → NO Pi.

**Cosa adattiamo (il nostro gate = stessa architettura SENZA l'encoder di testo):** quei modelli sono encoder di TESTO (ModernBERT/MiniLM); noi abbiamo già il ROI come **vettore di feature** → l'encoder non serve (costerebbe 300-800ms su Pi). Teniamo **teste tipizzate + calibrazione + contratto**:
- input: feature ROI tabellari → modellino LightGBM/MLP (l'"encoder" leggero, µs)
- teste stile Jev: **Noul** = P(ROI rilevante → KEEP) · **Score** = urgenza/priorità ordinale (ordina i top-K) · **Choice** = bucket azione {ignora|osserva|depth|freno-candidato}
- **calibrazione** (Platt/isotonic) + **conformal** (MAPIE) = la confidence vera
- output nel **contratto `/v1/systemone`** (Choice/Noul/Score) come interfaccia pulita gate↔scheduler + Energy-OOD override.

Bonus futuro: **Von** (ModernBERT, CPU) per decisioni a livello di scena/linguaggio *fuori dal loop per-frame* (occasionali), se mai servisse.

## 3. La rete di sicurezza anti-"scarto del pericolo nuovo" (stadio 4)

Regola tua: nel dubbio **non scartare, tieni** (umiltà sul caso raro). Due canali, entrambi quasi gratis (operano su logit/feature già calcolati):
- **Energy-OOD** (logsumexp dei logit, <0.1 ms): se lo score è anomalo (mai visto) → override "keep".
- **Conformal set vuoto/troppo grande** (MAPIE) → "astieniti dallo scarto" → keep + depth.
- Toolkit unico se vuoi provarne vari offline: **PyTorch-OOD** (Energy, Mahalanobis, ReAct…).

## 4. Data-engine — come etichettare "interessante" dai log (senza annotare a mano)

Il gate si addestra sui **tuoi log già registrati**:
- **Ostacoli-ingombro** (persone/auto/cordoli/marciapiedi/alberi/animali): label "rilevante" = ROI dentro corridoio con TTC basso o che ha preceduto una sterzata/scostamento.
- **Stop-decel** (freno mancato, stop, semafori, precedenze): le **frenate delle prime ore di log** sono gold — l'event-miner estrae gli eventi decel-vs-stop; la ROI/scena che precede la frenata = "rilevante". Poi il freno va rilasciato (label temporale).
- Ogni sessione nuova → nuove etichette → **riaddestri il gate** (spirale: fai → capisci → automatizzi).

⚠️ **Gap da chiudere:** `categories.yaml` oggi **non ha** `traffic_light`/`stop_sign`/`give_way` → per semafori/precedenze vanno aggiunte quelle classi (o un classificatore dedicato), altrimenti la parte stop-decel vede solo "oggetto fermo davanti".

## 5. Strumenti open (tutti aarch64) — con fattibilità Pi 5 CPU

| Stadio | Strumento | Pi5 CPU | Link |
|---|---|---|---|
| 1 pre-gate | OpenCV **MOG2** / frame-diff | ~30 FPS **MEASURED** | opencv.org |
| 1 flow | **DIS optical flow** (OpenCV) | ~15-30 FPS *estimate* | opencv.org |
| 2 seg | **YOLO11n-seg / YOLOv8n-seg** (NCNN/ONNX INT8) | ~5 FPS @640, 10-25 FPS @240-320 *est.* (YOLO11n detect 157ms **MEASURED**) | github.com/ultralytics/ultralytics |
| 2 det | **YOLO26n** (NCNN) | **~15 FPS @640 MEASURED** su Pi5 | docs.ultralytics.com/guides/raspberry-pi |
| 2 seg on-demand | **EdgeSAM** (encoder CNN) | ~3-10 FPS *est.* (unico SAM-lite CPU-friendly) | github.com/chongzhou96/EdgeSAM |
| — evitare | EfficientViT-SAM (GPU-only), DINOv2 (~2 FPS), YOLO-World (~0.5-3 FPS) | solo on-demand/no | — |
| 3 gate | **LightGBM** + **CalibratedClassifierCV** | µs *est.* | microsoft/LightGBM · scikit-learn calibration |
| 3 deploy | **m2cgen** (→C) / **lleaves** / ONNX Runtime | sub-µs/µs | github.com/BayesWitnesses/m2cgen · github.com/siboehm/lleaves |
| 3 conformal | **MAPIE** (il più maturo) / crepes | sub-ms *est.* | github.com/scikit-learn-contrib/MAPIE |
| 4 OOD | **Energy-OOD** / **PyTorch-OOD** | <0.1 ms *est.* | github.com/weitliu/energy_ood · github.com/kkirchheim/pytorch-ood |

**Onestà sui numeri:** sul Pi 5 reale sono MEASURED solo YOLO11n/YOLO26n e MOG2. Tutto il resto è *estimate* (A76 ≈ 5-10× più lento di CPU desktop). **Primo passo tecnico = timing one-shot sul Pi** del backbone scelto + gate+OOD, per trasformare le stime in misure.

## 6. Stack minimo consigliato (semplicità > complessità)

> **MOG2/frame-diff → YOLO11n-seg (NCNN INT8) off-thread → LightGBM calibrato (m2cgen→C) + soglia conformale MAPIE, con Energy-OOD come override "flag novel" → depth solo sui keep → freno/sterzo nei limiti.**

Tutto open, tutto aarch64, gate online sub-ms, e la parte "calibrata e tipizzata" (il vero valore di Jev) senza cloud né modello proprietario.

## 7. Ordine di costruzione (proposto)

1. **Detector off-thread** nello scheduler (sblocca il real-time — è il collo di bottiglia noto). G0 timing sul Pi.
2. **Pre-gate MOG2** + salvataggio feature-per-ROI nei log (per avere il dataset del gate).
3. **Dataset del gate** dai log esistenti (label da frenate/TTC/corridoio) + classi `traffic_light`/`stop_sign` nel training seg.
4. **Train gate** LightGBM + calibrazione + conformal (offline, Mac) → export m2cgen C.
5. **Wire del gate** al posto/accanto di `priority_score()` + **Energy-OOD override**.
6. **Shadow mode** sul mock (`test_perception_scheduler.py`) poi G0 sul Pi con video reale. Firma D00x prima di qualsiasi attuazione su strada.

## 8. Linee rosse (invariate)

- Freno ≤ **60°** (idraulico MTB inchioda a 65°). Slew rate. `speed_limiter` v2 padrone del GPIO12.
- Il gate può **solo restringere** (scartare ROI irrilevanti) — **mai** sopprimere una frenata di sicurezza: l'override OOD e il freno d'emergenza (`/tmp/emergency_brake`) hanno sempre la precedenza.
- Niente strada senza firma (DECISION_LOG D002).
