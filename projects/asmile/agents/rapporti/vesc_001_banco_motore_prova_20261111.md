# VESC di #001 al banco col motore di prova (6354 identico) — 2026-11-11
VESC sul Mac via USB (/dev/cu.usbmodem3041): fw 5.2, HW 60, nessun fault. Config letta = quella di #001 (diff solo motore/limiti/PID,
backup `fleet/001/vesc_backup/vesc_mcconf_backup_20261111_075839_banco_motore_prova.bin`). Nessuna scrittura in flash.

## Misure sul motore di prova (motore libero)
| | motore prova (oggi) | #001 montato (9/11, in config) | asmile2 (maggio, VESC Tool) |
|---|---|---|---|
| R (measure_res 10) | 27.9 mOhm | 29.3 / 29.8 | 46.8 |
| L (measure_ind 0.1) | 20.65 uH (ld-lq 6.26) | 20.3 / 18.3 | 55.9 |
| flux (measure_linkage_openloop 10 0.3 1500) | **5.43 mWb** (non pilotato 4.86) | **1.318** (detection 26/10) | 5.04 |
| R efficace a rotore fermo 30 A (handbrake) | 50 mOhm (|V| 1.35 V / 26.9 A) | 47 mOhm (log res30 10/11: duty 0.058, 42.5 V, Iq 30) | — |

## Cosa dice
1. **Il flux di #001 in config è sbagliato di 4 volte** (1.32 vs 5.4 mWb): la detection del 26/10 è stata fatta col motore sotto carico
   (piantone 1:5, "usare ≥20 A"), l'openloop non segue → flux basso. Ne segue observer gain 5.75e8 invece di ~3.4e7.
   Il confronto "0.07 vs 0.26 Nm/A" del 10/11 usava questo flux: **è sbagliato**. Motore uguale → Kt uguale ≈ 1.5·7·5.4e-3 = **0.057 Nm/A**
   (140 KV → 9.55/140 = 0.068): 30 A ≈ 1.7 Nm al motore ≈ 8.5 Nm al piantone con 1:5 (prima delle perdite).
2. **Tabella hall di #001 coerente** (scala fw 200 = 360°): coincide con quella del motore di prova e di asmile2 a meno di cablaggio
   (fasi specchiate + fili hall permutati), scarto rms 3-5° el. La detection hall del fw 5.02 media avanti+indietro: il carico simmetrico si annulla.
3. **A rotore fermo #001 sulla bici si comporta come il motore al banco** (R efficace 47 vs 50 mOhm a 30 A): corrente e tensione coerenti,
   niente di elettricamente strano a velocità zero.
4. Altre differenze di config #001 vs asmile2: foc_cc_decoupling 2 (BEMF, usa il flux sbagliato → in movimento Vq sotto-compensato, Iq cala)
   vs 0; m_hall_extra_samples 1 vs 3 (hall più sensibili ai disturbi ad alta corrente → lettura invalida → angolo = observer col flux sbagliato);
   foc_d_gain_scale_max_mod 0.2 vs 0.9; foc_observer_type 0 vs 3.

## Ipotesi aperta: il rapporto di asmile2
Il dato 0.105 tach/step (Briter 12 bit) dice 4096·0.105/42 = **1:10** su asmile2; Daniele dice 1:5. Se asmile2 è 1:10, a pari ampere ha il
doppio di coppia al manubrio (e 15 A asmile2 ≈ 30 A #001). Va contato a mano: giri del motore per un giro di piantone su asmile2.

## Proposta (serve il vai di Daniele per scrivere in flash)
A. Correggere su #001: flux 5.43e-3, observer gain 1e3/λ² = 3.39e7, hall_extra_samples 3, cc_decoupling 0 (come asmile2). Non cambia la coppia
   a motore fermo, la sistema in movimento e quando un hall legge male.
B. Prova decisiva della coppia vera: dinamometro/bilancia pesa-valigie al manubrio a raggio noto, sterzo bloccato, 10/20/30 A →
   Nm misurati vs attesi 0.057·5·I. Stessa prova sul motore di prova con una leva (Kt del VESC). Se al banco torna e sulla bici no → meccanica
   (slittamento cinghia/ingranaggio, attrito). Se torna su entrambi → serve più riduzione o più corrente (o asmile2 è davvero 1:10).
