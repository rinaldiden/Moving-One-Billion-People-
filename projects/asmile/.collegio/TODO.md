# TODO — pipeline / tooling Asmile

> Cose da fare, concrete e azionabili. Append-only. Quando una voce diventa decisione presa migra in DECISION_LOG.md; quando è una tensione irrisolta vive in QUESTIONI_APERTE.md.

## Sync log raspi → Mac

<!-- 2026-10-05 — evoluzione di sync_can_logs.sh / D005 (BOZZA in DECISION_LOG): oggi tira i CAN di OGGI finché il Pi è acceso; qui si chiede trigger all'accensione + scarico di IERI + notifica -->
- [ ] Logga il raspi appena si accende. Così scarichi sul Mac tutto quello che è successo ieri. Avvisami quando hai scaricato.

## Perception Priority Scheduler (percezione CPU-only, post Affan Khan) — DA FIRMARE

<!-- 2026-10-05 — voce di Daniele: studiare lo schema CPU-only di Affan Khan e portarlo su Asmile
     senza sovraccaricare il Pi, con depth sui segmenti che contano. Proposta + scaffold.
     Doc: docs/perception_priority_scheduler.md — Scaffold: pi/autonomous/perception_scheduler.py -->
- [ ] **G0 BENCHMARK (gate, prima di tutto)**: `perception_scheduler.py --benchmark --video <sessione>` sul Pi 5. Misura Hz/CPU di tracker, detector (YOLOv8n-ONNX@320), SGBM-ROI, drivable. Detector deve reggere ≥2 Hz, altrimenti si scende a MobileNet-SSD o si alza detect-every.
- [ ] Export YOLOv8n → ONNX INT8 sul Mac, drop sul Pi, verifica carico con cv2.dnn/onnxruntime.
- [ ] Tracker leggero (CSRT/flow) → test 0% stale su un video (lock/lost/re-acquire).
- [ ] Priority Map: tarare pesi su pattern P1–P9.
- [ ] Depth on-demand: object_depth (sempre) + StereoSGBM ritagliata sulle top-K ROI + cross-check.
- [ ] Shadow mode: scheduler in parallelo alla guida, SOLO log, confronto con shadow_mode.py. Nessun attuatore finché non firmato in DECISION_LOG.
