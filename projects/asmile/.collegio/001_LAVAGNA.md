# Lavagna asmile #001 — 2026-11-09 10:00

**Livello raggiunto:** nessuno  ·  **Stiamo lavorando per:** L0 (registra)

## Cosa serve da te (parte fisica)
- video col metro col logger: soste 1-2-3-4-5-6-7-8-10-12-15 m + tabellone  ← per: Calibrazione stereo del logger col metro (±2% da fermi)
- video col metro con #001: soste a 1-2-3-5-7-10-15 m  ← per: Calibrazione stereo di #001 col metro (±2% da fermi, 1-15 m)

## Gate

| | gate | cosa | chi → contro-agente | prova |
|---|---|---|---|---|
| ✅ | L0.sync_001 | Camere di #001 sincronizzate anche nei video in movimento | asmile-pi-001 → asmile-pi-001-verifica | agents/rapporti/L0.encoder_sync_001_20261109.md (visto asmile-pi-001-verifica, 2026-11-09) |
| ✅ | L0.sensori_001 | sensor_hub a 50 Hz attivo su #001 (camere+sensori stesso ms) | asmile-pi-001 → asmile-pi-001-verifica | agents/rapporti/L0.sensori_sync_001_20261109.md (visto asmile-pi-001-verifica, 2026-11-09) |
| ⬜ | L0.encoder_ruota | Encoder ruota tarato (velocità e accelerazione giuste) | asmile-pi-001 → asmile-pi-001-verifica |  |
| 🟡 | L0.calib_logger | Calibrazione stereo del logger col metro (±2% da fermi) | asmile-calib → asmile-calib-critico | calib_asmile-logger_metro.json: residui del fit ≤2.1%, mancano soste di verifica fuori fit (4-6-8-12 m) |
| 🟡 | L0.calib_001 | Calibrazione stereo di #001 col metro (±2% da fermi, 1-15 m) | asmile-calib → asmile-calib-critico | calib_asmile-001.json ha soste col metro: serve il visto di asmile-calib-critico |
| ✅ | L0.dati | Video nuovi scaricati, controllati e indicizzati | asmile-logger-ingest → asmile-ingest-critico | agents/rapporti/L0.dati_indice_20261109.json (visto asmile-ingest-critico, 2026-11-09) |
| ⬜ | L1.banco_fisso | Banco di misura fisso: punti col metro MAI usati nel fit (4-6-8-12 m) + oggetti reali | asmile-calib → asmile-calib-critico |  |
| ⬜ | L1.rettifica | Rettifica vera: scarto verticale L-R < 1 px su tutta l'immagine, anche in movimento | asmile-calib → asmile-calib-critico |  |
| ⬜ | L1.depth_moto | Depth in movimento: ±2% <5 m, ±5% 5-10 m, ±10% 10-20 m sul banco fisso | asmile-depth → asmile-occhio |  |
| ⬜ | L1.ostacoli | Ostacoli SENZA nome nel corridoio davanti (depth densa / occupazione) | asmile-depth → asmile-occhio |  |
| ⬜ | L1.ttc | Tracking + filtro: distanza, velocità di avvicinamento e tempo-al-contatto stabili | asmile-depth → asmile-occhio |  |
| ⬜ | L1.classi | SAM 3 vede cancelli, griglie, catene, dossi (test: rientro logger frame ~1500) | asmile-seg-segmenter → asmile-seg-verifier |  |
| ⬜ | L1.ombra_5 | 5 sessioni in OMBRA su #001: percezione+decisione calcolate, non agite, confrontate con Daniele | asmile-sim-validator → asmile-regressione |  |
| ⬜ | L2.freno_bam | Modello del freno (BAM): gradini ≤60° a 10-15 km/h, decelerazione da encoder | asmile-actuator-modeler → asmile-attuatori-avversario |  |
| ⬜ | L2.freno_limite | Freno mai oltre 60° garantito nel codice (speed_limiter unico padrone GPIO12) | asmile-sicurezza → asmile-sicurezza-redteam |  |
| ⬜ | L2.watchdog | Watchdog indipendente + disco in sola lettura su #001 (ferma e torna al noto-buono) | asmile-deploy → asmile-rollback-guardian |  |
| ⬜ | L2.redteam | Red team di sicurezza superato sul freno automatico | asmile-sicurezza → asmile-sicurezza-redteam |  |
| ⬜ | L3.sterzo_limiti | Centro e finecorsa sterzo di #001 misurati | asmile-banco-hw → asmile-banco-critico |  |
| ⬜ | L3.sterzo_bam | Modello dello sterzo (BAM) VESC + Speed PID configurato | asmile-actuator-modeler → asmile-attuatori-avversario |  |
| ⬜ | L3.ombra_sterzo | 5 sessioni in ombra dello sterzo | asmile-sim-validator → asmile-regressione |  |
| ⬜ | L4.sim2real | Policy validata in sim + banco virtuale senza regressioni | asmile-sim-validator → asmile-regressione |  |

**Video da lavorare:** 15  ·  **Decisioni da firmare:** 10  ·  **Pi online:** nessuno

_Generata da projects/asmile/agents/stato.py — non modificarla a mano._
