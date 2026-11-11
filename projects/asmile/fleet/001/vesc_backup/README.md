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
| vesc_mcconf_backup_20261110_180449.bin | 2026-11-10 (prima della scrittura) | 45 / -45 | 99 / -60 | 150 | 20 |
| vesc_mcconf_backup_20261110_180450.bin | 2026-11-10 **NUOVA, scritta e verificata** (Daniele: "ripristina 500"): solo byte 269-270 | 45 / -45 | 99 / -60 | 150 | **500** |

2026-11-10: foc_hall_interp_erpm 20 -> 500 (valore originale/asmile2). Motivo: con 20 il fw 5.02 interpola gia' a velocita' quasi nulla e con
cambi di verso "puo' restare 60° fuori" (commento mcpwm_foc.c) -> Iq letto 45 A ma coppia vera ridotta. Tutte le prove di resistenza del 9/11
erano con 20. Ora la prova di resistenza va rifatta. Nota: su #001 la root e' overlay, gli script in ~/wip spariscono al riavvio (copiati in /tmp/steering).
| (backup vesc_mcconf_backup_20261110_181426.bin rimasto sul Pi in ~/wip, overlay: forse perso; diff = solo l_current) | 2026-11-10 18:14 Pi **NUOVA, scritta e verificata** (Daniele: "prova a dare 100A a fase") | **100 / -100** | 99 / -60 | 150 | 500 |

ATTENZIONE: il VESC di #001 resta a 100 A in flash finché non si riabbassa (prova di resistenza/tenuta in sospeso). Per tornare a 45 A:
`vesc_mcconf_limiti_001.py scrivi --apply --l-current-max 45 --l-current-min -45 --l-in-current-max 99 --l-in-current-min -60`
(oppure `ripristina vesc_mcconf_backup_20261110_180450.bin`). Dopo la prima sterzata a 100 A (ok, fet 22 C, motore 14 C) il Pi è sparito dalla rete.
| vesc_mcconf_backup_20261111_145701.bin | 2026-11-11 14:57 prima del ripristino (70 A, interp 100, spid prove) -> **RIPRISTINATO 20261109_163432 (approvato 09/11: 30 A, interp 20, spid originali, tabella hall originale)**, scritto e verificato (vai Daniele) | 30 / -30 | 99 / -60 | 150 | **20** |
| vesc_mcconf_backup_20261111_18xxxx.bin | 2026-11-11 18:3x **MOTORE NUOVO** (gemello del banco) detection a motore libero: R 29.5 mOhm, L 19.5 uH, flux 4.918 mWb (undriven; driven 5.45), current kp 0.0195 ki 29.5, observer 4.13e7, hall table [23,93,59,158,192,124] (foc_sensors_detect_apply 10), hall_analyze: settori 50-69 deg. l_current ±80 A (Daniele: max 80 A per 5 s, il limite di tempo sta negli script) | 80 / -80 | 99 / -60 | 150 | 20 |
