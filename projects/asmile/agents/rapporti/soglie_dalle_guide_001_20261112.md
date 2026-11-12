# Soglie dalle guide di #001 - 2026-11-12 (event-miner)

Script: training/eventi/soglie_dalle_guide.py (estrazione) + soglie_report.py (tabelle, proposta). Eventi: training/eventi/out_guide_20261112_c0.3477/ e _c0.3374/ (frenate.csv, sterzate.csv, velocita_1hz.csv, segmenti.json). Percezione solo letta da training/depth/out_20261112_v9 (tracks_20261109_094146.pkl).
Ruota: numeri con 0.3477 m/giro enc (proposta, L0.encoder_ruota_20261112) e tra parentesi con 0.3374 (in uso). Differenza: velocita e decel -3% con 0.3374.

## 0. Cosa sono davvero le "guide": LIMITE GROSSO sui dati
- Dei 17 CSV sensori 08-11/11 solo 2 hanno la bici in moto con encoder valido: 20261108_160150 e 20261109_085334. Tutti gli altri: ruota ferma (cavalletto/banco) o GPS/encoder incoerenti (11/11: sterzo -1 o 0..16380). Scartati.
- Tratti in moto (|v|>0.5 m/s, >5 s): 13; usati 8 (encoder/GPS entro 0.7-1.3). Scartati: 6356 s (spinta calibrazione 10 giri, gps assente), 5617 s (rapporto GPS 1.5), 3 tratti 08/11 senza GPS (fermi / limiter a bici quasi ferma).
- Distanza usata: 1540 m, di cui 1343 m col speed_limiter attivo (servo freno, target 10 km/h, cap 12): in quei tratti velocita e parte delle frenate sono del LIMITER, non di Daniele. Solo 197 m sono senza limiter (08/11 pomeriggio e 09/11 09:23-09:25), in cui non e dimostrato chi guidava (nessun video di quei tratti).
- Percezione: solo il giro 094146 (t 6639-6730 s, 233 m, 90 s a 15 fps). Verifica di Daniele su v9: primo ostacolo con 28 falsi vs 11 veri (regress_v9.json): le distanze Z sotto sono "depth:coarse" e possono essere falsi primo.
- Controlli: v e acc da Savitzky-Golay ord. 2 su cumulativo (v 0.5 s, acc 1.5 s come L0). IMU non usata per la decel: a riposo ay=+0.074 g (offset 0.7 m/s2) e non compensata per il pitch (IMU da -1.6 a -1.8 contro -0.9..-1.2 encoder).

## 1. FRENATE (31 eventi decel >=0.3 m/s2 per >=1 s, dv>=0.5 m/s)
Classi: stop_umano=15 (v finale <2 km/h: il limiter rilascia sotto 8 km/h e non puo fermare), umano=7 (servo <5 gradi: rallentamenti dolci), limiter=9 (servo >=5 gradi e non stop: freno automatico, escluso).

### 1a. Stop completi di Daniele per fascia di velocita iniziale (0.3477; [0.3374])
| fascia km/h | n (0.3477/0.3374) | v0 p50 | decel media p25/p50/p75 m/s2 | decel picco p25/p50/p75 | durata s p50 | spazio di frenata p25/p50/p75 m | note |
|---|---|---|---|---|---|---|---|
| 5 | 5/5 | 5.1 | 0.28/0.42/0.61 [0.41] | 0.77/0.97/1.13 | 3.0 | 2.26/2.68/3.06 [2.6] |  |
| 8 | 2/2 | 7.8 | 0.50/0.54/0.57 [0.52] | 0.79/0.94/1.08 | 3.2 | 4.45/4.50/4.55 [4.4] | pochi dati: resta segnaposto |
| 10 | 4/4 | 10.2 | 0.71/0.75/0.91 [0.73] | 1.20/1.37/1.70 | 3.2 | 4.21/5.51/6.68 [5.3] | pochi dati: resta segnaposto |
| 12 | 4/4 | 11.9 | 0.97/1.09/1.23 [1.06] | 2.01/2.42/2.63 | 3.1 | 4.60/5.26/6.14 [5.1] | pochi dati: resta segnaposto |
| 15 | 0/0 | - | -/-/- [-] | -/-/- | - | -/-/- [-] | nessun evento: resta segnaposto |
| pooled | 15/15 | - | 0.54/0.68/0.95 [0.66] | 0.96/1.23/1.85 | 3.1 | 3.3/4.4/5.3 [4.2] | - |

Lettura: sono frenate di ROUTINE (picco massimo smussato 2.8 m/s2 a ~12 km/h), non di emergenza. La decel cresce con la velocita (0.4 a 5 km/h, ~1.1 a 12), quindi un solo valore costante e sbagliato. Il massimo del freno idraulico NON e misurato. La decel di 1.5 del segnaposto e sopra la mediana di Daniele (0.68) e il segnaposto frena_entro e PIU CORTO dello spazio che Daniele usa da solo per fermarsi (a 5 km/h: segnaposto 1.84 m totale contro 2.7 m p50 di sola frenata; a 10 km/h 4.46 contro 5.5).
Fit pooled spazio di frenata: sp = 1.58*v +0.55 m (v in m/s, n=15; residui p75 +0.67 m) [0.3374: 1.59*v +0.50, +0.65].

### 1b. Frenate con percezione (finestra v9, 094146, depth:coarse)
| t (s) | classe | v0 km/h | decel media | Z primo ostacolo nell arco (m) | Z dritto | TTC s | note |
|---|---|---|---|---|---|---|---|
| 6650 | stop_umano | 12.2 | 1.19 | 5.9 | 5.9 | 1.7 |  |
| 6658 | stop_umano | 11.6 | 1.33 | 1.7 | 1.7 | 0.5 | possibile falso primo |
| 6672 | stop_umano | 12.8 | 0.91 | 17.1 | 19.6 | 4.8 |  |
| 6699 | limiter | 12.4 | 0.37 | 4.2 | 4.2 | 1.2 |  |
| 6718 | umano | 12.5 | 0.42 | 7.1 | 7.1 | 2.0 |  |
| 6725 | umano | 10.5 | 0.64 | 9.1 | 9.1 | 3.1 |  |
| 6729 | stop_umano | 5.1 | 0.61 | 2.0 | 2.0 | 1.4 | possibile falso primo |

Stop con percezione: n=4, Z a inizio frenata 1.9/3.9/8.7 m (range molto largo), TTC 1.2/1.6/2.5 s: **pochi dati (n<5): la distanza di inizio frenata resta segnaposto**. Non e dimostrato che Daniele frenasse PER quell ostacolo (nessun caso dubbio aperto): l etichetta intento resta "intent:unknown" salvo conferma.

## 2. STERZATE (curve con |gz|>22 dps per >=0.5 s a v>1 m/s: n=11, di cui n=7 a v>8 km/h)
| indicatore | p25 / p50 / p75 | note |
|---|---|---|
| velocita angolare manubrio picco (deg/s) | 23/25/33 | |
| ampiezza manubrio nella curva (deg dal punto di partenza) | 13/23/26 | |
| curvatura gz/v (1/m) | 0.15/0.20/0.25 | raggio ~5.0 m al p50 |
| gz picco (deg/s) | 30/33/35 | |
| anticipo: manubrio parte prima di gz>22 (s) | 0.29/0.78/0.89 | |

Curvatura contro velocita (n piccolo): v=4 km/h k=0.38 rate=49 deg/s; v=6 km/h k=0.33 rate=35 deg/s; v=7 km/h k=0.24 rate=17 deg/s; v=7 km/h k=0.27 rate=27 deg/s; v=8 km/h k=0.23 rate=110 deg/s; v=9 km/h k=0.20 rate=25 deg/s; v=10 km/h k=0.16 rate=23 deg/s; v=11 km/h k=0.15 rate=21 deg/s; v=12 km/h k=0.14 rate=31 deg/s; v=12 km/h k=0.15 rate=24 deg/s; v=14 km/h k=0.14 rate=23 deg/s.
Lettura: curvatura scende con la velocita (0.38 a 4 km/h, 0.14 a 12): a 12-13 km/h Daniele non supera ~0.15 1/m (raggio ~7 m) e ~24-31 deg/s. La velocita angolare del manubrio piu alta (110 deg/s) e a 8 km/h in un evento a bassa velocita.
Velocita del manubrio su tutto il moto (campioni 1 Hz, |steer_rate|, deg/s) p50/p90 e |angolo| p50/p90 per fascia:
| fascia km/h | n | rate p50/p90 | angolo p50/p90 |
|---|---|---|---|
| 5 | 143 | 4.6/21.6 | 2.9/20.5 |
| 8 | 90 | 9.1/30.0 | 4.4/13.1 |
| 10 | 75 | 5.2/21.7 | 3.4/14.2 |
| 12 | 118 | 3.2/10.8 | 1.5/6.1 |
| 15 | 130 | 4.3/12.7 | 1.0/5.8 |

Anticipo rispetto a curva/ostacolo: il manubrio parte ~0.8 s (p50) prima che gz superi 22 dps. Con percezione solo 3 curve (Z a inizio sterzata 3.1/4.5/5.5 m): **pochi dati**, l anticipo "quanto prima dell ostacolo" non e stimabile.
Nota: centro sterzo 6606 e finecorsa del 09/11 16:05 (dopo la guida di 09:46): ripetibilita centro +-1.27 gradi; valgono fino al rimontaggio del 12/11.

## 3. VELOCITA tenute (campioni a 1 Hz in moto, km/h; p25/p50/p75)
| contesto | n | senza limiter (FREE/off) | n | limiter attivo (HYST/RELEASE/OVER) |
|---|---|---|---|---|
| rettilineo | 142 | 4.6/5.8/7.0 | 252 | 11.5/13.2/14.7 |
| curva | 9 | 5.5/6.5/7.4 | 14 | 10.0/11.1/12.8 |
| altro | 68 | 3.9/5.4/7.8 | 71 | 9.6/11.8/13.7 |
| vicino a ostacolo (Z arco <10 m, v9) | 0 | - | 56 | 9.0/11.3/12.7 |
| lontano (Z arco >=10 m, v9) | 0 | - | 21 | 8.2/10.4/13.1 |

Lettura: le velocita "con limiter" (mediana ~13.5 km/h in rettilineo) sono il cap del limiter, non scelta di Daniele; le velocita libere (mediana ~5-6 km/h) sono il comportamento di Daniele sotto 8 km/h, dove il limiter non interviene. Nel giro 094146 (limiter attivo) i campioni vicino/lontano non mostrano differenza leggibile perche il cap domina: contesto "vicino a persone" non separabile (n troppo basso e limiter confondente).

## 4. MARGINI LATERALI
Nel v9 (tracks pkl) non ci sono distanze dai bordi (solo X laterale degli oggetti e flag in_arc/in_str): **in arrivo da v10**. bordo_margine resta segnaposto.

## 5. Tabella: segnaposto vs proposta dalle guide
Fuori 5-12 km/h il valore e max(segnaposto, estrapolazione del fit) per non rompere la monotonia (3 km/h resta segnaposto). Colonne come config. frena_entro = spazio frenata Daniele p75 (fit) + v*0.5 s + 0.5 m (latenza e cuscinetto segnaposto: non vengono dalle guide). rallenta = max(1.5*frena, v*3 s) (formula, non guide).
| km/h | frena_entro segnaposto | frena_entro PROPOSTA | rallenta segnaposto | rallenta PROPOSTA | bordo_margine | origine |
|---|---|---|---|---|---|---|
| 3 | 1.15 | 3.45 | 2.50 | 5.17 | 0.34 (segnaposto, v10) | pochi dati: fuori 5-12 km/h, max(segnaposto, estrapolazione fit) per restare monotona |
| 5 | 1.84 | 4.62 | 4.17 | 6.92 | 0.37 (segnaposto, v10) | dalle guide (n banda=5, fit pooled n=15) |
| 8 | 3.26 | 6.34 | 6.67 | 9.52 | 0.41 (segnaposto, v10) | dalle guide (n banda=2, fit pooled n=15) DEBOLE |
| 10 | 4.46 | 7.51 | 8.33 | 11.27 | 0.44 (segnaposto, v10) | dalle guide (n banda=4, fit pooled n=15) DEBOLE |
| 12 | 5.87 | 8.66 | 10.00 | 12.98 | 0.47 (segnaposto, v10) | dalle guide (n banda=4, fit pooled n=15) DEBOLE |
| 15 | 8.37 | 10.40 | 12.56 | 15.61 | 0.51 (segnaposto, v10) | pochi dati: fuori 5-12 km/h, max(segnaposto, estrapolazione fit) per restare monotona |
| 20 | 13.57 | 13.57 | 20.35 | 20.36 | 0.58 (segnaposto, v10) | pochi dati: fuori 5-12 km/h, max(segnaposto, estrapolazione fit) per restare monotona |
| 25 | 20.05 | 20.05 | 30.07 | 30.08 | 0.65 (segnaposto, v10) | pochi dati: fuori 5-12 km/h, max(segnaposto, estrapolazione fit) per restare monotona |

Decel / sterzo proposti (non in tabella per velocita): decel_frenata_ms2 segnaposto 1.5 (resta nel JSON); decel dalle guide p25 0.54 m/s2 (campo decel_guide_p25_ms2, solo riferimento); velocita manubrio picco in curva p50 25 deg/s (p25-p75 23-33), curvatura max osservata a 12 km/h ~0.15 1/m: **pochi dati (n=11), non adottati come soglia**.

## 6. Casi dove i dati non bastano
- fascia 15 km/h e oltre: nessuno stop (solo frenate parziali del limiter): segnaposto. 3 km/h, 20, 25: segnaposto.
- fasce 8, 10, 12: n=2/4/4 (<5): proposta da fit pooled, DEBOLE.
- Frenate di emergenza e decel massima: non presenti (picco smussato 2.8 m/s2); il segnaposto non puo essere confermato ne smentito per l emergenza.
- Distanza ostacolo a inizio frenata / TTC / anticipo sterzata: n<5 con percezione, falsi primo noti.
- Guide "pure" di Daniele senza limiter: ~197 m soli. Servono altre uscite con il limiter spento (o velocita sopra 10 km/h) per le fasce 12-15 e per gli stop da 15.
- Logica: nessun evento ha intento verificato; Z accoppiata solo per coincidenza temporale (intent:unknown).
