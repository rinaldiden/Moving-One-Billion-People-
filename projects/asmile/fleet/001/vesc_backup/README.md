# VESC sterzo asmile #001 — configurazione (mcconf fw 5.02, 457 B)
Letta via UART con pi/steering/vesc_mcconf_limiti_001.py (offset da vedderb/bldc tag 5.02 confgenerator.c,
layout provato: R 29.82 mOhm, L 18.28 uH, flux 1.318 mWb, sensori HALL = detection 2026-10-26).

| file | quando | l_current max/min | l_in_current max/min | abs max | foc_hall_interp_erpm |
|---|---|---|---|---|---|
| vesc_mcconf_backup_20261109_160801.bin | 2026-11-09 16:08 (originale) | 44.85 / -44.85 | 99 / -60 | 150 | 500 |
| vesc_mcconf_backup_20261109_163009.bin | 2026-11-09 16:30 (dopo tentativo di scrittura NON applicato) | 44.85 / -44.85 | 99 / -60 | 150 | 500 |
| vesc_mcconf_backup_20261109_163432.bin | 2026-11-09 16:34 **NUOVA, scritta e verificata** (rilettura byte per byte) | **30 / -30** | 99 / -60 | 150 | **20** |

Modifica proposta e autorizzata da Daniele (2026-11-09): l_current ±30 A, foc_hall_interp_erpm 500 -> 20 (scatti a bassa velocità).
Stato: APPLICATA 2026-11-09 16:34 via UART (vai di Daniele). Ritorno all'originale: `vesc_mcconf_limiti_001.py ripristina vesc_mcconf_backup_20261109_160801.bin --apply`. Ogni nuova scrittura aggiunge una riga qui.
| vesc_mcconf_backup_20261109_174816.bin | 2026-11-09 17:48 **NUOVA** (vai Daniele: 45 A a fase) | **45 / -45** | 99 / -60 | 150 | 20 |
| vesc_mcconf_backup_20261109_181307.bin | 2026-11-09 18:15 prova VESC in velocità: s_pid_min_erpm 900->10, ramp 400, kp/ki 0.004->0.02 (0.05 instabile) | 45 / -45 | 99 / -60 | 150 | 20 |
| vesc_mcconf_backup_20261109_184850.bin | 2026-11-09 18:45 dopo foc_sensors_detect_apply 25: tabella hall [22,91,57,158,190,123] (prima [23,93,59,159,191,125], uguale entro 2-4° el.) | 45 / -45 | 99 / -60 | 150 | 20 |

Verifica 2026-11-09 18:40 (manubrio collegato, solo movimenti lenti agganciati, encoder registrato):
- measure_res 10 -> 29.34 mOhm; measure_ind 0.1 -> 20.26 uH (ld-lq 6.05 uH): confermano la detection del 26/10 (29.82 / 18.28).
- hall_analyze 25 -> 6 stati, scarti 57-65° el., deviazione max 4°: "good alignment".
- foc_sensors_detect_apply 25 -> tabella praticamente identica: la tabella hall NON era sfasata.
- asmile2 (maggio): R 46.8 mOhm, L 55.9 uH, flux 5.04 mWb -> motore diverso (KV ~150-190) da #001 (flux 1.32 mWb ~ KV ~600): coppia per ampere ~3.8 volte più bassa su #001. Da verificare l'etichetta KV dei due motori.
