# Piano del giro asmile-capo — 2026-11-10 (v2 dopo VETO 1/3 di asmile-capo-critico)

## Livello e ECCEZIONE dichiarata
- `stato.py`: **livello L-1 → lavoro per L0**. Aperti `L0.encoder_ruota` (Pi + altra sessione Claude) e `L0.calib_logger` (serve video col metro di Daniele).
- Daniele (2026-11-10) ha vincolato questo giro a **solo Mac** (niente Pi, niente sterzo/freno, niente calibrazione). Nessuno dei due gate L0 aperti è lavorabile così.
- **Eccezione:** lavoro L1 IN ANTICIPO, in ombra. **Nessun gate L1 si chiude in questo giro**: i PASSA del critico, se arrivano, sono `--parziale` (rapporto ok, gate aperto) finché L0 non è chiuso e la calib (punto A) non è definitiva.

## Stato di partenza (misurato)
- `L1.depth_moto`: 2 VETO di asmile-occhio; mancano dati fisici (<5 m, bordi col metro) e dipende da `L1.rettifica` (istanza calib). → FERMO, niente 3° giro.
- `training/depth/test_ostacolo_4600.py` rilanciato: PASSA (botte 63%, vasi 40%, Z 6.9 m).
- session_20261109_094146 (#001): 10066 frame; da `asmile-loggers/_solo_movimento/asmile-001/session_20261109_094146/index.json` solo 57.7% dei frame ha velocità encoder sopra soglia.
- Rientro logger 160535 c67-71: `_seg_sam3/` ha 775 campioni su indice 0-2301 (~1 ogni 3) → tratto 1500-1554 ≈ 18 campioni; SAM 3 di allora: pole×2, person×1, 0 gate/fence. gate/fence sono già in THINGS dal 2026-11-09.
- Mac condiviso: 1 test calib su CPU. Regola: **un solo job GPU alla volta** (prima `ps` per maestro depth/calib), SGBM con `nice`.

## Lavori (a ritroso: freno su visione ← TTC ← ostacoli visti + classi giuste)
1. **L1.ostacoli** — asmile-depth → asmile-occhio. Solo SGBM CPU (`nice -n 10`, ≤4 processi), niente SAM 3.
   - Lista FISSA di ~30 frame scelta SOLO fra quelli con v_encoder > 0.3 m/s (index.json), passo regolare, scritta in `training/depth/out_20261110/frames_ostacoli.json` PRIMA di eseguire.
   - Immagini rettificate SENZA sovrapposizioni per l'annotazione alla cieca; la verità la annota **asmile-occhio** a occhio prima di guardare i risultati.
   - Misura: richiamo ≥ 90% e falsi ≤ 0.2/frame, contati come **presenza + lato (sx/centro/dx) + fascia Z (<5 m, 5-12 m)**, NON in metri. Valido solo se gli ostacoli veri annotati sono **≥ 20** (altrimenti "non misurabile").
   - Test fissi verdi: `test_ostacolo_4600.py`, `test_pali_sottili.py`. Ogni numero marcato **"calib PROVVISORIA, punto A in corso"**.
2. **L1.classi** — asmile-seg-segmenter → asmile-seg-verifier. Unico job GPU.
   - Prerequisito: un fotogramma del tratto 1500-1554 guardato a occhio per confermare che il cancello c'è (se no: trovare il tratto giusto e dirlo).
   - "Passata" = un campione SAM 3. Rigirare SAM 3 (THINGS attuali) su tutti i frame del tratto (non 1 su 3): cancello visto come gate/fence (non solo pole) in ≥ 80% delle passate.
   - Set di controllo FISSO ≥ 100 frame senza cancelli, **#001 e logger riportati separati, mai fusi**: gate/fence falsi in ≤ 2% dei frame; classi vecchie ±5% vs THINGS senza gate/fence, stesso set e stesse soglie conf.
   - Griglie a terra / catene / dossi: se nei video non ci sono esempi → NON VERIFICATO + richiesta clip a Daniele (non si aggiungono classi alla cieca).
3. **Triage dati** — asmile-log-harvester → asmile-dati-auditor. Leggero, niente GPU.
   - Per le 15 sessioni #001 non lavorate: durata, frame L/R, sync, luma, metri da encoder ruota (se c'è), tratti fermi; elenco "in moto e buone".

## Non faccio oggi
- L1.ttc (dipende da ostacoli + L0.encoder_ruota), L1.banco_fisso/rettifica (istanza calib + metro), L1.ombra_5 (#001 acceso).
- Niente Pi, pi/steering, pi/braking, speed_limiter, calib_charuco_dual.py, calib_rock/.

Rischio fisico: nessuno. Costo: 1 job GPU + 1 CPU moderato + 1 leggero.
