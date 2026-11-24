# calib logger02 24/11 - col case fissato la calib viene ottima?
Prova: `agents/prove/asmile-calib_logger02_20261124/` (PREREG.md scritto prima di misurare, sync.py, extract.py, analyze.py, v4.py, json e log). Solo lettura, niente sul logger. Video 1280x800; base = v3 con cy+40 su entrambe le camere e size 1280x800 (nota del capo).

## Risposta breve
- **Verdetto pre-registrato (R fissa fittata sul blocco iniziale 0-70 s del giro 14:32): "SI MUOVE ANCORA".** Ma per un motivo preciso: nei primi ~75 s la sessione e' un transitorio (dy v3 -8.5 px a 18 s, -17.7 a 24 s con gyro 49 dps, -22 px da 36 a 60 s, -13 a 66 s, -4/-7 da 73 s): lo scarto verticale e' cambiato a scatti due volte mentre il logger era maneggiato. Il blocco di fit era dentro quel transitorio, quindi R fissa su di lui dava dy 13 px dopo.
- **Dopo il transitorio il montaggio e' FERMO**: da 90 s a 870 s (13 minuti, officina + strada + fermo) dy con segno fra -0.32 e +0.25 px, salto massimo fra finestre di 30 s 0.39 px, Rx per blocco di 60 s (t>=60) da -0.329 a -0.361 gradi (variazione 0.03 gradi < 0.05). **Questa e' una lettura ESPLORATIVA (post-hoc: scelta dopo aver visto i dati)**, dichiarata tale; il verdetto formale resta quello sopra. Il protocollo e' stato rifatto con pari/dispari (v4) su t>=120 s.
- Il **problema ieri era il case, in buona parte**: nessun salto/deriva a riposo e in uso per 13 min. NON dimostrato in bici su strada lunga: la strada nel giro e' ~4-5 min (clip 4-7, IMU in moto 270-510 s), nessun urto/buca vera. Il transitorio dei primi 75 s dice che maneggiando il logger le camere si spostano ancora: da capire cosa e' successo li (Daniele stava chiudendo/fissando?).
- **v3 non vale piu'**: con v3 (cy+40) dy mediano **-7.3 px** su tutto il giro (stabile). Rotazione cambiata di Rx **-0.335 gradi** (Rz +0.059) rispetto a v3; ieri v3 era -0.435 rispetto a v2. Mattina 10:37 con v3: -7.85 px: il montaggio del mattino e' praticamente quello del pomeriggio (con R v4 la mattina da -7.85 a -0.44 px, mediana 0.76).

## Numeri (tutti dy rettificato, px)
| prova | n punti | mediana | p95 | segno |
|---|---|---|---|---|
| v3 (cy+40) tutto S2 t>=120, dispari | 93 941 | 7.30 | 10.21 | -7.29 |
| R pre-registrata (fit 0-70 s) su tutto il resto di S2 | 108 404 (in moto) | **13.10** | 16.08 | +13 |
| v4 fit pari, **test dispari** | 93 844 | **0.51** | 4.08 | +0.04 |
| v4 scambio (fit dispari, test pari) | 102 176 | 0.49 | 3.92 | +0.06 |
| test dispari IN MOTO (IMU) | 59 604 | 0.63 | 4.57 | +0.01 |
| test dispari FERMO | 34 240 | 0.38 | 3.07 | +0.06 |
| mattina 10:37 (2 clip, RIFERIMENTO DEBOLE) con v4 | 8 336 | 0.76 | 4.97 | -0.44 |
| **verifica indipendente cv2.remap + SIFT**, 60 coppie dispari: v3_800 | 8 393 | 7.24 | 10.17 | +7.2 |
| idem v4 | 8 744 | **0.50** | 4.09 | -0.06 |

Finestre di 30 s (R pari fissa, S2 t>=90, tutte; "moto" da IMU): mediana |dy| 0.54-0.90 px in moto/maneggio (270-510 s: 0.69-0.90), 0.37-0.42 da fermo (510-870 s); segno -0.32..+0.25, nessuna finestra con salto >0.4 px. Tabella completa: `v4_analisi.json` (finestre).
Zone 3x3 (test dispari, R pari; n / mediana / p95): alto-sx 4163/0.97/4.7, alto-c 20317/0.35/2.1, alto-dx 4023/0.76/7.5, centro-sx 4411/0.83/7.1, centro 17539/0.42/4.9, centro-dx 17444/0.55/3.9, basso-sx 1970/0.90/4.9, basso-c 10707/0.69/4.3, basso-dx 13270/0.57/3.6. Nessuna zona con mediana >1 px; **p95 resta 2-7.5 px (gate p95<1 NON raggiunto)**: con SIFT H.264 e officina ripetitiva e' in parte il pavimento del metodo (come il 2.7 di ieri), non dimostrato che sia solo quello. Disparita' dei punti: 5%/50%/95% = 7.9/41/226 px (profondita' varia: epipolare ben condizionato, non degenere).

## Sync A/B (fw nuovo)
Firmware: nei file salute/errori NON c'e' l'hash: **NON VERIFICATO con hash**; prove indirette: tutte le sessioni sono del 24/11 (OTA 941d249d il 23/11 19:47) e lo scarto e' 0.02 ms (prima del fix 0-30 ms).
- giro 14:32 (14 768 fotogrammi A): scarto |dt| mediano **0.023 ms**, p95 0.076 ms; coppie con |dt|>5 ms 0.97% (sono i buchi fra clip, scarto fino a secondi); numero frame sfasato rispetto alla corrente 0.35%; banco 14:03: 0.021 / 0.065 ms, 0.27%; mattina 10:37: 0.024 / 0.22 ms, 1.4% (2 clip, dominato dal bordo). Offset di numero frame = 0 per tutto il giro.
- Il dy e' misurato SOLO su coppie con |dt|<=1 ms e offset frame modale.

## Dati: cosa sono davvero
- 14:03 (140339/140323, banco, portatile <1 m): NON giro, scena vicina quasi piana: dopo la rettifica restano ~33 punti validi (disparita' >500 px scartata) -> **degenere**, non usata per il dy; usata per sync.
- 10:37: 2 clip, banco: riferimento debole.
- 14:32 (143247/143252): giro di Daniele. IMU in moto 9-540 s (officina, strada ~4-5 min, officina), fermo dopo. Per i punti: step 15 coppie, max 300 punti/coppia.

## Candidato v4 (PROVVISORIO, non promuovibile)
`logger/depth/calib_logger02.CANDIDATO_v4_20261124.json` (1280x800, base v3+cy40, R = Rx -0.3353 gradi, Rz +0.0593 gradi rispetto a v3, Ry e d0 invariati; stato scritto nel JSON). v1-v3 non toccati. Perche' provvisorio: (1) fit esplorativo su t>=120 s scelto dopo aver visto il transitorio; (2) giro corto, strada ~4-5 min senza urti; (3) **scala NON verificata** (arrivera' il metro: Z = f*B/(d-d0), d0 e f da v2/v3 non rimisurati; Ry non fittabile e sposta d0 ~3.9 px per 0.2 gradi); (4) p95 >1 px.

## Prossimo passo
1. Giro vero in bici (>=15 min di strada, con buche/urti) col case chiuso: stesso test (R fissa dal primo blocco STABILE, pre-registrato, scartando i primi 2 minuti dopo il maneggio).
2. Foto ferma col metro di Daniele -> scala/d0.
3. Capire il transitorio dei primi 75 s (maneggio durante il fissaggio?): se camere si spostano maneggiando il logger, serve il test dy dopo ogni apertura del case.

---
# Controllo col metro (Daniele, 24/11 pomeriggio) — vedi agents/prove/foto_metro_logger02_20261124/METRO.md
v4 provvisorio: 1.22/1.23 (-0.7%), 1.86/1.82 (+2.2%), 1.84/1.79 (+3.0%); v3: punto 2 -21% per il dy di 7.5 px. Prima verità metrica per logger02: v4 regge a ~±3% fra 1.2 e 1.9 m; servono punti a 3-10 m.
