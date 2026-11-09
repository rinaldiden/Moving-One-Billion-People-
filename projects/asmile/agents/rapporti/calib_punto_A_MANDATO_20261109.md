# Punto A — mandato firmato all'istanza calib (2026-11-09 sera)

**Per:** asmile-calib (produttore) → asmile-calib-critico (contro-agente). Lo stesso giro di
`HANDOFF_calib_camere_20261109.md` e `calib_consigli_daniele_REVISIONE_20261109.md`.
**Firme:** D012 FIRMATO con aggiustamenti, Q11 chiusa → D013 (`.collegio/DECISION_LOG.md`).
**Perimetro:** SOLO codice sul Mac. Nessun Pi toccato, nessun messaggio a Daniele, nessuna calib sostituita.

---

## 1. Cosa ha firmato Daniele (sua voce, sintesi fedele)

> D012 – Gate proposti: FIRMATO con leggeri aggiustamenti. Accetto le soglie come obiettivo operativo.
> - RMS mono < 0.5 px (viste tenute fuori): OK. RMS stereo < 1 px (held-out): OK.
> - dy p95 < 1 px in tutte le 9 zone: OK e prioritario. Il –4 px a sinistra è il segnale più importante da eliminare.
> - Baseline 200 mm ± 3% (misurata, non forzata): OK. Se è fuori di oltre ±1%, misura col calibro e annotazione.
> - Depth centro ≤ 2% a 5 m, ≤ 3% a 10 m: OK. Depth bordi ≤ 3% a 2-5 m: OK come target, gate più critico della sessione B.
> - Sync p95 Δt < 1 ms: OK e molto importante. Scarta automaticamente le coppie oltre soglia.
> - Aggiunta non bloccante: dopo il fit, riportare anche l'errore di depth ai bordi a 1 m e a 10 m.
> - Il test sintetico con sensore inclinato: tienilo come regressione automatica ogni volta che tocchi il codice di calibrazione.
>
> Q11: "Jig fisso" = dima del fornitore + nostro script di collaudo a campione. Non riaprire una stazione nostra per i 15.000.
>
> A – Codice sul Mac. B – Sessione tabellone rigido su #001. Fit → CANDIDATO → gate D012. Solo dopo che PASSA: depth/seg
> sulle rettificate, poi logger001 + smonta/rimonta ×3. **Il punto A fallo preparare agli agenti dell'istanza di prima.**

## 2. Il lavoro (A1-A8), file: `logger/depth/calib_charuco_dual.py`, `test_calib_charuco_dual_synth.py`, `depth.py`

| # | Cosa | Criterio di fatto |
|---|---|---|
| A1 | Le 7 correzioni del critico: T[0]≥0 → ROSSO; zona con scala o dy vuota → ROSSO; \|T\| fuori 200 mm ±3% → ROSSO (fra ±1% e ±3% → ARANCIO "calibro + annotazione"); caso file scambiati nel sintetico → deve dare ROSSO; p95 \|dy\| < 1 px nel gate; hold-out a **blocchi di tempo contigui**; **niente riscalatura di T** | ogni regola ha un caso nel test |
| A2 | RMS mono (<0.5 px per camera) e stereo (<1 px) calcolati **sulle viste tenute fuori**, nel gate | report + gate |
| A3 | 3° modello candidato `rational+prism+tilted` (`CALIB_TILTED_MODEL`); fisheye solo con FOV misurato >100° (non #001) | scelta sulle viste tenute fuori |
| A4 | Export `calib_<unità>.CANDIDATO.yaml` (OpenCV FileStorage: K1,D1,K2,D2,R,T,R1,R2,P1,P2,Q, modello, RMS, data, hash video) + mappe `initUndistortRectifyMap` in `.npz`. Il JSON resta la fonte | file scritti solo con "CANDIDATO" nel nome |
| A5 | Δt per coppia nel report (p50/p95/max), **scarto automatico** delle coppie >1 ms, gate p95 < 1 ms | numero di coppie scartate nel report |
| A6 | Sintetico con **sensore inclinato** (~0.3° su una camera): il tilted lo ritrova, gli altri due no. **Regressione automatica**: un solo comando che gira tutti i casi (9 zone VERDE, solo-centro ROSSO, file scambiati ROSSO, inclinato) e fallisce con exit≠0 | `esito.json` aggiornato |
| A7 | `depth.py`: filtro confidenza WLS opzionale (`getConfidenceMap`), **default invariato** | default bit-identico |
| A8 | (aggiunta di Daniele) Report depth **ai bordi anche a 1 m e a 10 m**, solo informativo, non nel gate | colonna nel report |

Gate D012 che lo script deve applicare (tabella firmata):

| Gate | Soglia |
|---|---|
| RMS mono | < 0.5 px per camera, viste tenute fuori |
| RMS stereo | < 1 px, viste tenute fuori |
| dy rettificato | p50 < 0.5 px, **p95 < 1 px in tutte le 9 zone** (prioritario) |
| Baseline | \|T\| = 200 mm ±3%, mai forzata; >±1% → calibro + annotazione |
| Depth centro | ≤2% fino a 5 m, ≤3% a 10 m (griglia col metro, sessione B) |
| Depth bordi | ≤3% a 2-5 m (sessione B, gate più critico); 1 m e 10 m solo riportati |
| Sync | p95 Δt < 1 ms, coppie oltre scartate |

## 3. Chiusura
Produttore → `palla.py passa --verticale percezione --da asmile-calib --a asmile-calib-critico --artefatto logger/depth/calib_charuco_dual.py`.
Critico: rilancia la regressione, cerca falsi verdi nuovi, verdetto con `palla.py verdetto`. Nessun gate della lavagna si
chiude con A: L1.rettifica resta aperto finché la sessione B non porta dati veri.

## 4. Esito
(compilato in fondo dagli agenti)
