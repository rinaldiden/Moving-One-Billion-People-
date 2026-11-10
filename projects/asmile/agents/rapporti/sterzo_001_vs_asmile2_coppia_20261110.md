# Sterzo #001 vs asmile2: perché a pari ampere #001 ha poca coppia (2026-11-10)

Prova 10/11 con foc_hall_interp_erpm 500 (come asmile2), 30 A: Daniele "niente da fare". Iq 30.0 A reali, Id ~0, ERPM senza salti
(log in agents/prove/sterzo_001/hall500/). Quindi né l'interpolazione né la lettura UART.

## Differenze trovate
| | asmile2 (config/vesc_steering_config_asmile2.md, config/vesc_foc_ok.xml) | #001 (fleet/001/vesc_backup, detection 26/10 + misura 9/11) |
|---|---|---|
| motore | Flipsky 6354 **140 KV** | KV da flux ~600 (da verificare etichetta) |
| R / L | 46.8 mOhm / 55.9 uH | 29.8 (29.3) mOhm / 18.3 (20.3) uH |
| flux | 5.037 mWb (-> ~156 KV) | 1.318 mWb (-> ~600 KV) |
| giri elettrici per giro di piantone | 0.105 tach/step x 4096 / 6 = **~72** (7 pp -> ~1:10) | misurato oggi tach/encoder 0.0128 = 6/468 -> **35** (7 pp -> 1:5) |
| coppia al piantone per A (1.5 x flux x giri el.) | **~0.54 Nm/A** | **~0.07 Nm/A** |
| hall interp | 500 | 500 (da oggi) |
| limite corrente | 43.46 A (uso reale 8-18 A) | 45 A |
| comando UART | COMM_SET_CURRENT in mA, 50 Hz, 8-18 A (vesc_return_to_center.py, power_steering.py max 15 A) | COMM_SET_CURRENT in mA, 400 Hz (stesso comando, stessa scala) |

Rapporto ~7.8x: 30 A su #001 ~ 4 A su asmile2; 45 A ~ 6 A. asmile2 usava 8-18 A = 60-140 A equivalenti su #001.
Il modo di pilotare via UART è lo stesso (stesso comando, stessa scala, solo più frequente): non spiega la differenza.

## Da confermare (Daniele)
1. Etichetta KV del motore di #001 (e di asmile2): R, L e flux diversi dicono avvolgimento diverso.
2. Rapporto di riduzione di asmile2 (il valore 0.105 tach/step dice ~1:10; #001 misurato 1:5).
Se confermato: o motore 140 KV su #001, o riduzione maggiore, o (non consigliato) correnti molto più alte del FSESC.

## Correzione 2026-11-10 (Daniele)
Riduzione asmile2 = **1:5 identica** a #001 (il valore 0.105 tach/step non dava il rapporto: scartato). Motore montato su #001 dichiarato
6354 140 KV come asmile2. Allora la sola differenza misurata è il flux (1.32 vs 5.04 mWb) con R/L diversi:
asmile2 ~0.26 Nm/A, #001 ~0.07 Nm/A (3.8x). 30 A su #001 ~ 8 A asmile2; 45 A ~ 12 A.
Prova decisiva: Daniele collega il 6354 140 KV di scorta al VESC di #001 al posto del motore montato -> measure_res / measure_ind via UART
(motore fermo). Se R/L del ricambio ~47 mOhm / ~56 uH e il montato resta 29 / 20 -> il montato non è un 140 KV: si cambia.
