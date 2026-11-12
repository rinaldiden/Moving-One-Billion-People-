# Soglie dalle guide di #001 - 2026-11-12 (event-miner, giro 2 dopo scettico)

> ## Per Daniele (5 righe, da validare)
> Frenata di routine di Daniele misurata su 12 stop completi PULITI (servo <1 gr e limiter non attivo), tutti a v0 <= 9.5 km/h (scartato lo stop a 5617 s: encoder all indietro, v finale negativa). Sopra 10 km/h non c e nessuno stop senza limiter: quelle righe sono segnaposto.
>
> | km/h | frena entro (m) | rallenta entro (m) | n stop puliti | qualita |
> |---|---|---|---|---|
> | 5 | 4.56 | 6.83 | 6 | **media** |
> | 8 | 6.39 | 9.58 | 2 | **debole** |
> | 10 | 7.98 | 11.96 | 1 | **segnaposto** |
> | 12 | 9.54 | 14.30 | 0 | **segnaposto** |
> | 15 | 11.92 | 17.88 | 0 | **segnaposto** |
>
> Metodo: ogni riga = MASSIMO fra (a) fit sui stop puliti (p75 residui), (b) lo stesso fit coi soli stop verificati col GPS, (c) p75 osservato nella banda (se n>=2), tutti + latenza 0.5 s + cuscinetto 0.5 m (segnaposto, non dalle guide); mai sotto il segnaposto, tabella crescente. Qualita dal numero di stop puliti nella banda: solida n>=10, media 5-9, debole 2-4, segnaposto 0-1 (e ogni riga >=10 km/h, dove non ci sono dati puliti).
> **Per completarla serve un giro con il limiter SPENTO**: frenate normali e qualche frenata decisa a 10, 15 e 20 km/h (fino a fermarsi), sempre in sicurezza, su tratto libero e solo col tuo vai. Servono almeno 5 stop per fascia; i dati di curva e bordi restano a parte (sterzo = solo indicativo, bordi in arrivo da v10).

Script: training/eventi/soglie_dalle_guide.py (estrazione) + soglie_report.py (tabelle, proposta). Eventi: training/eventi/out_guide_20261112_c0.3477/ e _c0.3374/ (frenate.csv, sterzate.csv, velocita_1hz.csv, segmenti.json). Percezione solo letta da training/depth/out_20261112_v9 (tracks_20261109_094146.pkl).
Ruota: numeri con 0.3477 m/giro enc (proposta, L0.encoder_ruota_20261112) e tra parentesi con 0.3374 (in uso). Differenza: velocita e decel -3% con 0.3374.

## 0. Cosa sono davvero le "guide": LIMITE GROSSO sui dati
- Dei 17 CSV sensori 08-11/11 solo 2 hanno la bici in moto con encoder valido: 20261108_160150 e 20261109_085334. Tutti gli altri: ruota ferma (cavalletto/banco) o GPS/encoder incoerenti (11/11: sterzo -1 o 0..16380). Scartati.
- Tratti in moto (|v|>0.5 m/s, >5 s): 13; usati 8 (encoder/GPS entro 0.7-1.3). Scartati: 6356 s (spinta calibrazione 10 giri, gps assente), 5617 s (rapporto GPS 1.5), 3 tratti 08/11 senza GPS (fermi / limiter a bici quasi ferma).
- Distanza usata: 1540 m, di cui 1343 m col speed_limiter attivo (servo freno, target 10 km/h, cap 12): in quei tratti velocita e parte delle frenate sono del LIMITER, non di Daniele. Solo 197 m sono senza limiter (08/11 pomeriggio e 09/11 09:23-09:25), in cui non e dimostrato chi guidava (nessun video di quei tratti).
- Percezione: solo il giro 094146 (t 6639-6730 s, 233 m, 90 s a 15 fps). Verifica di Daniele su v9: primo ostacolo con 28 falsi vs 11 veri (regress_v9.json): le distanze Z sotto sono "depth:coarse" e possono essere falsi primo.
- Controlli: v e acc da Savitzky-Golay ord. 2 su cumulativo (v 0.5 s, acc 1.5 s come L0). IMU non usata per la decel: a riposo ay=+0.074 g (offset 0.7 m/s2) e non compensata per il pitch (IMU da -1.6 a -1.8 contro -0.9..-1.2 encoder).

## 1. FRENATE (31 eventi decel >=0.3 m/s2 per >=1 s, dv>=0.5 m/s)
Classi (pipeline, soglie_dalle_guide.py): stop_umano=8 (v finale <2 km/h E servo <1 gr E frazione lim_zone attiva <0.2), stop_limiter=7 (stop con servo/limiter attivo: contaminati, ESCLUSI dal fit), umano=7 (rallentamenti dolci, servo <5 gr), limiter=9 (freno automatico, escluso).
NOTA SET DEL FIT: la pipeline (con la condizione di coerenza encoder/GPS sui tratti) trova solo 8 stop puliti; il fit usa i 12 stop puliti trovati dall estrazione indipendente dello scettico (agents/prove/eventi_scettico_20261112/ev.csv: stessi criteri, ma include anche stop in tratti brevi/senza GPS ma il filtro v1<0 elimina lo stop del tratto 5617 s (encoder all indietro, enc/GPS 1.51)). (giro 3: quello stop e ora SCARTATO col filtro v finale < -1 km/h, contatore encoder che scende; piccoli negativi da overshoot dello smoothing a bici ferma restano).

### 1a. Stop PULITI di Daniele per fascia di velocita iniziale (0.3477; [0.3374])
| fascia km/h | n (0.3477/0.3374) | v0 p50 | decel media p25/p50/p75 m/s2 | (decel picco: n/d nel set puliti) | durata s p50 | spazio di frenata p25/p50/p75 m | note |
|---|---|---|---|---|---|---|---|
| 3 | 3/3 | 3.5 | 0.46/0.48/0.50 [0.46] | - | 2.0 | 0.79/1.00/1.07 [1.0] | debole (n<5) |
| 5 | 6/6 | 5.2 | 0.36/0.48/0.57 [0.47] | - | 3.2 | 1.95/2.62/3.04 [2.5] | solida |
| 8 | 2/2 | 8.0 | 0.51/0.54/0.57 [0.52] | - | 4.3 | 4.69/4.71/4.72 [4.6] | debole (n<5) |
| 10 | 1/1 | 9.5 | 0.72/0.72/0.72 [0.70] | - | 3.7 | 4.56/4.56/4.56 [4.4] | segnaposto: stop singolo al limite del campo |
| 12 | 0/0 | - | -/-/- [-] | - | - | -/-/- [-] | segnaposto: nessuno stop pulito |
| 15 | 0/0 | - | -/-/- [-] | - | - | -/-/- [-] | segnaposto: nessuno stop pulito |
| pooled | 12/12 | - | 0.45/0.50/0.59 [0.48] | - | 3.2 | 1.4/2.6/4.1 [2.5] | - |

Lettura: sono frenate di ROUTINE (decel media mediana 0.50 m/s2), non di emergenza. La decel cresce con la velocita, quindi un solo valore costante e sbagliato. Il massimo del freno idraulico NON e misurato. Il segnaposto frena_entro e PIU CORTO dello spazio che Daniele usa da solo per fermarsi gia a 5 km/h (segnaposto 1.84 m totale contro 2.6 m p50 di sola frenata). Nessuno stop pulito sopra 9.5 km/h: oltre quella velocita il fit e estrapolazione.
Fit pooled spazio di frenata: sp = 2.34*v -0.95 m (v in m/s, n=12; residui p75 +0.54 m) [0.3374: 2.34*v -0.93, +0.53].
Sensibilita del fit pulito (frena_entro in m a 5 / 8 / 10 km/h = fit + latenza + cuscinetto; n):
- tutti i puliti (scelto): n=12, sp=2.34*v-0.95, p75 +0.54; frena_entro 4.03 / 6.39 / 7.97
- senza stop <4.5 km/h: n=9, sp=1.91*v-0.09, p75 +0.74; frena_entro 4.50 / 6.51 / 7.85
- 8 stop verificati col GPS dalla pipeline: n=8, sp=1.67*v+0.48, p75 +0.56; frena_entro 4.55 / 6.36 / 7.56

### 1b. Frenate con percezione (finestra v9, 094146, depth:coarse)
| t (s) | classe | v0 km/h | decel media | Z primo ostacolo nell arco (m) | Z dritto | TTC s | note |
|---|---|---|---|---|---|---|---|
| 6650 | stop_limiter | 12.2 | 1.19 | 5.9 | 5.9 | 1.7 |  |
| 6658 | stop_limiter | 11.6 | 1.33 | 1.7 | 1.7 | 0.5 | possibile falso primo |
| 6672 | stop_limiter | 12.8 | 0.91 | 17.1 | 19.6 | 4.8 |  |
| 6699 | limiter | 12.4 | 0.37 | 4.2 | 4.2 | 1.2 |  |
| 6718 | umano | 12.5 | 0.42 | 7.1 | 7.1 | 2.0 |  |
| 6725 | umano | 10.5 | 0.64 | 9.1 | 9.1 | 3.1 |  |
| 6729 | stop_umano | 5.1 | 0.61 | 2.0 | 2.0 | 1.4 | possibile falso primo |

Stop con percezione (solo stop_umano della pipeline): n=1, Z a inizio frenata 2.0/2.0/2.0 m (range molto largo), TTC 1.4/1.4/1.4 s: **pochi dati (n<5): la distanza di inizio frenata resta segnaposto**. Non e dimostrato che Daniele frenasse PER quell ostacolo (nessun caso dubbio aperto): l etichetta intento resta "intent:unknown" salvo conferma.

## 2. STERZATE (curve con |gz|>22 dps per >=0.5 s a v>1 m/s E ampiezza manubrio >=5 gr: n=10, di cui n=7 a v>8 km/h) - INDICATIVE, NON SOGLIE
| indicatore | p25 / p50 / p75 | note |
|---|---|---|
| velocita angolare manubrio picco (deg/s) | 23/26/34 | |
| ampiezza manubrio nella curva (deg dal punto di partenza) | 18/24/26 | |
| curvatura gz/v (1/m) | 0.15/0.18/0.26 | raggio ~5.6 m al p50 |
| gz picco (deg/s) | 32/33/35 | |
| anticipo: manubrio parte prima di gz>22 (s) | 0.41/0.81/0.91 | |

Curvatura contro velocita (n piccolo): v=4 km/h k=0.38 rate=49 deg/s; v=6 km/h k=0.33 rate=35 deg/s; v=7 km/h k=0.27 rate=27 deg/s; v=8 km/h k=0.23 rate=110 deg/s; v=9 km/h k=0.20 rate=25 deg/s; v=10 km/h k=0.16 rate=23 deg/s; v=11 km/h k=0.15 rate=21 deg/s; v=12 km/h k=0.14 rate=31 deg/s; v=12 km/h k=0.15 rate=24 deg/s; v=14 km/h k=0.14 rate=23 deg/s.
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
Regole: nessuna riga piu corta del segnaposto, tabella crescente. Righe con dati puliti (v0 <= 9.5 km/h, righe <10): max(segnaposto, fit pulito p75 + v*0.5 s + 0.5 m). Righe >=10 km/h: max(segnaposto, proposta v2 del giro 1, fit pulito) e marcate segnaposto. Latenza e cuscinetto segnaposto non vengono dalle guide. rallenta = max(1.5*frena, v*3 s, segnaposto).
| km/h | frena_entro segnaposto | frena_entro PROPOSTA | rallenta segnaposto | rallenta PROPOSTA | bordo_margine | origine |
|---|---|---|---|---|---|---|
| 3 | 1.15 | 3.34 | 2.50 | 5.01 | 0.34 (segnaposto, v10) | dalle guide: debole (n stop puliti in banda=3; max di fit 2.44, verificati-GPS 3.34, p75-banda 1.98) |
| 5 | 1.84 | 4.56 | 4.17 | 6.83 | 0.37 (segnaposto, v10) | dalle guide: media (n stop puliti in banda=6; max di fit 4.03, verificati-GPS 4.56, p75-banda 4.23) |
| 8 | 3.26 | 6.39 | 6.67 | 9.58 | 0.41 (segnaposto, v10) | dalle guide: debole (n stop puliti in banda=2; max di fit 6.39, verificati-GPS 6.36, p75-banda 6.33) |
| 10 | 4.46 | 7.98 | 8.33 | 11.96 | 0.44 (segnaposto, v10) | segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito) |
| 12 | 5.87 | 9.54 | 10.00 | 14.30 | 0.47 (segnaposto, v10) | segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito) |
| 15 | 8.37 | 11.92 | 12.56 | 17.88 | 0.51 (segnaposto, v10) | segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito) |
| 20 | 13.57 | 15.86 | 20.35 | 23.79 | 0.58 (segnaposto, v10) | segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito) |
| 25 | 20.05 | 20.05 | 30.07 | 30.08 | 0.65 (segnaposto, v10) | segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito) |

Decel / sterzo proposti (non in tabella per velocita): decel_frenata_ms2 segnaposto 1.5 (resta nel JSON); decel dalle guide p25 0.45 m/s2 (campo decel_guide_p25_ms2, solo riferimento); velocita manubrio picco in curva p50 26 deg/s (p25-p75 23-34), curvatura max osservata a 12 km/h ~0.15 1/m: **pochi dati (n=10), non adottati come soglia**.

## 6. Casi dove i dati non bastano
- Dai 10 km/h in su nessuno stop pulito (solo stop con servo/limiter attivo, esclusi): righe 10, 12, 15, 20, 25 = segnaposto. Fascia 8 km/h: n<5 (debole), 3 km/h: n<5 (debole).
- Frenate di emergenza e decel massima: non presenti; il segnaposto non puo essere confermato ne smentito per l emergenza.
- Distanza ostacolo a inizio frenata / TTC / anticipo sterzata: n<5 con percezione, falsi primo noti.
- Guide "pure" di Daniele senza limiter: ~197 m soli. Servono altre uscite con il limiter spento (o velocita sopra 10 km/h) per gli stop a 10, 15 e 20 km/h (almeno 5 per fascia).
- Logica: nessun evento ha intento verificato; Z accoppiata solo per coincidenza temporale (intent:unknown).
