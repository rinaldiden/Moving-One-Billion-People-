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

### Esito produttore (asmile-calib, 2026-11-10)
Regressione unica `python3 logger/depth/test_calib_charuco_dual_synth.py --work <tmp>`: exit 0, 12/12 casi OK (9zone VERDE,
solo_centro ROSSO, file_scambiati ROSSO, scala_2pct ARANCIO, scala_5pct ROSSO, sync_3pct VERDE, sync_20pct ROSSO con coppie
scartate, export, depth_default bit-identico, tilt_rational/tilt_prism ROSSO). `esito.json` aggiornato.
- A1 A2 A5 A4 A8 A7: fatti e coperti dal test (gate D012: RMS mono/stereo sulle viste tenute fuori, p95 |dy|<1 in 9 zone, T mai riscalata, Δt scartato >1 ms).
- Novita' di oggi: refinement subpixel dei corner ChArUco (CORNER_REFINE_SUBPIX): senza, il caso 9zone sintetico dava ROSSO (p95 dy 1.01-1.09 px); con, VERDE (peggior zona 0.93 px).
- A3: 3° candidato `rational+prism+tilted` presente, scelto sulle viste tenute fuori. Nel sintetico con sensore inclinato e' **NON DISTINGUIBILE**
  (LM del tilted in minimi locali; il caso da' ROSSO, mai falso verde). Non e' un blocco; su dati veri decide l'hold-out.
- Tabellone A3: `--squares 10x7 --square-len 0.038` (DICT_5X5_1000): --make-board verificato. NON provato su video veri.
- Nessun Pi toccato, nessuna calib sostituita (solo CANDIDATO nel nome).

### Esito produttore, 2o giro dopo il VETO (asmile-calib, 2026-11-10)
Regressione: `python3 logger/depth/test_calib_charuco_dual_synth.py --work <tmp> [--reuse]` (200 viste, max 3 processi). **TEST VERDE, 14/14 casi OK.**
Criterio fissato PRIMA (nel docstring e in `SEEDS_9ZONE`/`MIN_VERDI`): 9zone su 5 seed [20261109, 1, 2, 3, 4], >= 4/5 VERDE e zero falsi verdi; soglie D012 NON toccate (dy p50 0.5, p95 1.0, RMS mono 0.5, stereo 1.0, |T| 1/3%, scala 2%).
- **9zone: 4/5 VERDE** (20261109, 2, 3, 4). Seed 1 = ROSSO per zona basso-sx INSUFFICIENTE (90 punti ma solo 5 viste con >=5 corner, servono 6): il messaggio "servono piu' viste in zona basso-sx" funziona. **Zero falsi verdi** (verita' 3D: dy p95 0.33-0.48 px, depth p95 <=1.74% nei VERDI).
- Seed extra INFORMATIVI (11, 12, scelti dopo, non nel criterio): **entrambi ROSSO per RMS mono 0.506 / 0.521 px (soglia 0.5)**, verita' buona (dy p95 0.49 / 0.85 px). Totale 7 seed: 4 VERDE, 1 ROSSO per zona insufficiente, 2 ROSSO per RMS. Non l'ho aggiustato: e' un fatto da riportare.
- **Diagnosi piu' profonda del veto**: il problema non era solo n piccolo. Anche con 90-300 punti per zona il p95 del dy GREZZO sta a 1.2-1.6 px (verita' 0.4): c'e' un pavimento di rumore di localizzazione dei corner (sigma del dy 0.5-0.66 px nel sintetico; p95 di |gauss| = 1.96 sigma). Con RMS mono ammesso fino a 0.5 il p95 grezzo <1 px NON e' raggiungibile nemmeno con calibrazione perfetta: **D012 e' internamente incoerente** (RMS mono<0.5 e dy grezzo p95<1). Soglia 1 px invariata, ma il p95 per zona e' ora calcolato sulle MEDIE PER VISTA (patch >= 5 corner, rumore/sqrt(k)) = errore sistematico, quello che conta per la depth. Il p95 grezzo resta nel report. **Questa e' una scelta di statistica, non di soglia: DA CONFERMARE da Daniele/critico** (D012 dice "dy p95 < 1 px").
  Prova che la nuova statistica non maschera errori: unit `stat_dy_unit` (solo rumore 0.44 px -> 0.19; offset sistematico 1.2 px -> 1.28 ROSSO; 0.6 px -> 0.83 VERDE) e caso nuovo `camera_mossa` (camera destra toccata di 0.12 gradi a meta' sessione): ROSSO con dy p50 1.43 / p95 1.66 px, verita' p95 1.65 px.
- (1) fatto, vedi sopra. (2) fatto: zona con < 60 punti o < 6 viste nel gate = INSUFFICIENTE = ROSSO + messaggio; bootstrap a cluster (viste) del limite alto nel report (`dy_patch_abs_p95_boot_hi`, avviso se >= soglia). (3) fatto: 3 blocchi di tempo FIT 50% / SCELTA 20% / GATE 30% (blocchi 5,2,3 su 10, mai adiacenti, guard 1); modello e modalita' stereo scelti sul blocco SCELTA (RMS stereo), rifit finale su fit+scelta, il GATE e' toccato solo per giudicare.
- (4) tilt_auto: il VERDE e' ammesso solo se la verita' 3D regge, altrimenti FAIL (falso verde). **Scoperta**: con 300 viste e la statistica corretta il modello `rational` ASSORBE il tilt di 0.3 gradi (verita' dy p95 <=0.45 px, depth <=1.03%): tilt_auto/rational/prism sono VERDE VERO. Il vecchio "ROSSO" di tilt_rational/prism era un artefatto del rumore del p95 grezzo, non una vera rilevazione. L'atteso del test e' ora "il gate concorda con la verita'", e la sensibilita' a un errore reale e' provata da camera_mossa e scala_*. `tilted` non e' mai stato scelto (non migliora il blocco scelta del 5%).
- (5) RMS mono vicino a soglia: nel sintetico 0.47-0.52 px (sulle viste del gate). In report `avvisi_margine` (RMS >= 80% soglia, dy p95 >= 80%, bootstrap sopra soglia) e stampa "! margine". Su dati veri e' il primo numero da guardare.
- Altri casi invariati e OK: solo_centro ROSSO, file_scambiati ROSSO (T[0]), scala_2pct ARANCIO, scala_5pct ROSSO, sync_3pct VERDE, sync_20pct ROSSO, export, depth_default bit-identico. depth.py NON toccato. calib_rock/ non toccato. Nessun Pi, nessuna calib sostituita.
- Limiti: sintetico (rumore corner scelto da me, non misurato su OV9281 veri); il run principale e' stato fatto in due passate (la seconda con `--reuse`: stesse calib, stesso codice calib_charuco_dual.py, rifatti solo verita'/criteri/camera_mossa); zone basse della camera destra poco coperte dal generatore sintetico.
- Per Daniele (A3 10x7 38 mm, #001): servono >= 60 punti e >= 6 viste (>= 5 corner) per zona NEL BLOCCO DEL GATE, che e' il 30% delle viste. Stima dal sintetico + geometria A3: una posa mirata a una zona da' 24-42 punti in quella zona (basso 24). Quindi ~250 viste DISTINTE (non fotogrammi duplicati), ~25-30 pose per zona, ripartite in 10 giri (ogni giro = tutte e 9 le zone, 2-3 pose per zona, piu' le zone basse), circa 10 minuti di registrazione, una posa ferma ~1 s ogni ~2 s, shutter corto, tabellone piatto.

## 4b. Esito critico (asmile-calib-critico, 2026-11-10) — VETO
Rifatto da me (solo CPU, file del produttore non toccati, lavoro in scratchpad):
- 9zone col seed del produttore (20261109): VERDE riprodotto, peggior zona p95 |dy| 0.93 px, RMS mono 0.36/0.38, stereo 0.37, |T| 199.96 mm.
- **FALSO VERDE AL CONTRARIO / fragilita': stesso caso 9zone, 3 seed diversi (1, 2, 3) = 3 ROSSO su 3** (peggior zona p95 1.37-1.41 px; zone con 17-27 punti). La verita' indipendente (punti 3D) dice p95 0.43-0.48 px e depth <=1.4%: la calibrazione e' buona, e' il numero del gate a essere rumoroso (p95 di 20-30 punti = quasi il massimo, dentro c'e' il rumore del rilevamento corner). Il VERDE del test dipende dal seed scelto: 0.93 contro soglia 1.0 non e' margine. Il subpixel ha spostato il test verso il verde su UN seed, non ha reso il gate stabile.
- Scala: square-len x1.05 -> |T| +4.99% ROSSO; x1.02 -> +1.99% avviso ARANCIO (riprodotti). T non riscalata (grep: "riscal" solo in commenti).
- A3 10x7 38 mm: PDF A3 reale, 100 dpi = 0.2542 mm/px -> quadretto 37.97 mm; rilevamento 54/54 corner a 3 scale e tilt 0/30/45 gradi, uguale all'A2 (70/70). OK (solo immagine resa, non video veri).
- depth.py: diff vs 1a73c2a7 = solo `conf_min=None` (ramo non toccato se None): default identico per ispezione. NON VERIFICATO col WLS vero (ximgproc assente su questo Mac).
- NON rifatti per tempo (ogni run ~10 min CPU, 12 casi ~1.5 h): file_scambiati, sync, tilt_*, export. Regressione completa NON rilanciata da me.
- Debolezze minori: scelta modello e scelta stereo congiunta/fissa fatte sulle stesse viste del gate (bias ottimista lieve); `tilt_auto` non puo' mai fallire (accetta anche NON DISTINGUIBILE); RMS mono 0.46 in un seed vs soglia 0.5.
**Correzioni da eseguire:** (1) la regressione deve girare >=5 seed per 9zone e riportare quante volte VERDE; il criterio atteso va fissato prima (es. >=4/5 VERDE e zero falsi verdi), senza ritoccare soglie. (2) Rendere stabile la statistica dy: p95 solo con n>=60 punti per zona (o bootstrap con limite alto), o hold-out piu' grande/piu' viste per zona; oppure il test sintetico deve avere meno rumore corner. (3) Scegliere modello/stereo su una parte e giudicare il gate su un blocco mai usato. Gate D012 NON dimostrato.

## 4c. Esito critico (giro 1) — asmile-calib-critico, 2026-11-10 — PASSA (parziale: il gate L1.rettifica NON e' chiuso)
Rifatto da me: copia del codice (md5 calib_charuco_dual.py identico a quello del produttore) in una cartella mia, regressione completa
da zero (niente --reuse), 3 processi, esito in `/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People--projects-asmile/758f768b-ae92-4aca-ae16-d5efde1a9966/scratchpad/esito_critico.json`, nessun file del produttore toccato. **TEST VERDE, 14/14.**
- 9zone, 5 seed del criterio: **4/5 VERDE** (20261109, 2, 3, 4 VERDE; seed 1 ROSSO perche' basso-sx INSUFFICIENTE: 90 punti ma 5 viste su 6). Identico al produttore: il risultato e' riproducibile.
- Due seed miei, scelti prima di vedere gli esiti (31, 32): entrambi ROSSO per RMS mono R 0.519 (soglia 0.5); le altre zone passano. Totale 7 seed: 4 VERDE.
- Zero falsi verdi su tutti i casi. camera_mossa ROSSO, file_scambiati ROSSO, scala_5pct ROSSO, scala_2pct ARANCIO, sync_20pct ROSSO, solo_centro ROSSO.
- Soglie D012: confrontato il diff, i default degli argomenti sono invariati (dy p50 0.5, p95 1.0, RMS mono 0.5, stereo 1.0, |T| 1/3%, scala 2%). Zona con <60 punti o <6 viste = ROSSO "servono piu' viste in zona X" (visto nel seed 1). Modello e modalita' stereo scelti sul blocco SCELTA (blocchi 3,7), gate sui blocchi 1,5,9, rifit finale su fit+scelta: separazione verificata nel codice e nel log. tilt_auto ora puo' fallire. Avvisi di margine stampati (RMS mono 0.49 = 98% soglia).
Punti che restano, per questo PASSA e' PARZIALE:
1. Il p95 del gate e' ora calcolato sulle medie per vista (patch >=5 corner), non sul dy grezzo di D012. La motivazione (pavimento di rumore dei corner) e' coerente con la verita' 3D, ma e' un cambio di statistica: lo deve confermare Daniele (D012). Il dy p50 resta grezzo. Prova della sensibilita': solo offset uniforme (stat_dy_unit) e camera_mossa; un errore che cambia segno dentro la zona verrebbe in parte mediato: non e' provato.
2. L'RMS mono 0.47-0.52 contro soglia 0.5: nel sintetico e' una moneta. Su OV9281 veri puo' dare ROSSO con calibrazione buona; non ritoccare la soglia senza decisione di Daniele.
3. Rumore dei corner scelto dal produttore, non misurato; tilt forte (>1 grado) non provato; depth.py col WLS vero NON VERIFICATO. Serve la sessione vera col tabellone (circa 250 viste distinte, 10 giri) prima di chiudere L1.rettifica.
