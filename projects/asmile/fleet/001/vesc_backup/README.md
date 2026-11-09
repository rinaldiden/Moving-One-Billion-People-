# VESC sterzo asmile #001 — configurazione (mcconf fw 5.02, 457 B)
Letta via UART con pi/steering/vesc_mcconf_limiti_001.py (offset da vedderb/bldc tag 5.02 confgenerator.c,
layout provato: R 29.82 mOhm, L 18.28 uH, flux 1.318 mWb, sensori HALL = detection 2026-10-26).

| file | quando | l_current max/min | l_in_current max/min | abs max | foc_hall_interp_erpm |
|---|---|---|---|---|---|
| vesc_mcconf_backup_20261109_160801.bin | 2026-11-09 16:08 (originale) | 44.85 / -44.85 | 99 / -60 | 150 | 500 |
| vesc_mcconf_backup_20261109_163009.bin | 2026-11-09 16:30 (dopo tentativo di scrittura NON applicato) | 44.85 / -44.85 | 99 / -60 | 150 | 500 |

Modifica proposta e autorizzata da Daniele (2026-11-09): l_current ±30 A, foc_hall_interp_erpm 500 -> 20 (scatti a bassa velocità).
Stato: NON ancora applicata (la scrittura via UART non è andata a buon fine, da ripetere). Ogni nuova scrittura aggiunge una riga qui.
