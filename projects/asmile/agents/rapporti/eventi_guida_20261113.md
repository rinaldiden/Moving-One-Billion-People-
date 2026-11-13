# Eventi di guida #001 del 13/11/2026 — impuntate, frenate, sterzate (event-miner)

Dati: `sensors_20261113_145727.csv` (14:57-15:36, 116 400 campioni a 50 Hz), giri video `session_20261113_150337` e `_151400`. Moto reale 11.9 min, 1969 m in 4 tratti (15:03:45-15:20:45), GPS/encoder coerenti (rapporto 0.99-1.03). Ruota 0.3374 m/giro encoder, centro sterzo 4112 (calib 13/11).

## IMPUNTATE — per Daniele, in parole semplici

1. **Le due impuntate sono confermate** (15:03:51 e 15:08:52): decelerazione IMU 4.5 e 4.1 m/s², muso giù +4.2° e +4.3°, az scende a 0.47 e 0.31 g (e sale a 1.5 g). Il video lo conferma da solo: la scena sale nell'immagine di ~36 e ~26 px (il muso si abbassa) negli stessi istanti.
2. **Il segno è sicuro: gx positivo = muso GIÙ (posteriore su).** Tre prove: (a) video, lo spostamento verticale dell'immagine segue gx con correlazione −0.77 a ritardo zero, su entrambi i giri (e la sterzata gz segue lo spostamento orizzontale con 0.96-0.97, quindi tempo e assi sono allineati); (b) fisica, regola della mano destra con X=sinistra, Y=indietro, Z=su; (c) l'az scende quando il posteriore si alleggerisce.
3. **Non ne ho trovate altre uguali.** Solo queste due hanno insieme decelerazione sopra 4 m/s² e muso giù ≥3° in 0.3 s (nessun'altra frenata supera 3.5 m/s² con il muso giù). C'è però **un caso strano**: 15:18:32, a 3.6 km/h, muso giù **+6.3°** in 0.7 s (confermato dal video, −34 px) con decelerazione debole (IMU 2.5, ruota 0.5 m/s²): non è una frenata forte; non so dire se sia la leva, un peso spostato o un dosso. **Da guardare con te.**
4. **Il problema grosso: il segnale di beccheggio arriva troppo tardi.** Il muso scende solo negli ultimi 0.2-0.25 s della frenata, quando la bici è già a 1-5 km/h. Con qualunque soglia sul beccheggio il rilascio parte 0.2-0.26 s prima del picco. L'attuatore ha circa 0.3 s di ritardo: rilasciare "quando si vede il muso scendere" non basta. Il segnale **precoce** è la decelerazione: sopra 3.0 m/s² (IMU) si è 0.4 s prima del picco (a 7 e 3.5 km/h). Perciò propongo due livelli: tetto sulla decelerazione (precoce) + rilascio sul beccheggio (ultima rete).
5. **Il servo non c'entra, in questi due casi.** Nell'ultimo secondo il servo era a ≤1.1° (massimo 3.7° nei 1.5 s): a frenare forte è stata la leva di Daniele (o un freno non registrato). Una regola che rilascia il *servo* non avrebbe cambiato niente. Per la regola ferrea va deciso chi la fa rispettare quando frena la mano.
6. **Soglie attuali (15 °/s, 2°, ripresa 70%) nei dati**: rilascio 0.22-0.26 s prima del picco, ma scattano su 7 frenate su 34 (solo 2 sono vere) e 31 volte in 11.9 min di moto (2.6 al minuto: pavé, buche, pedalate). Inoltre la velocità di beccheggio in avanti della 2ª impuntata arriva solo a 14.3 °/s (<15): i 26 °/s erano il rimbalzo all'indietro. In quel caso ha scattato il solo "2°", e a 1.7 km/h.
7. **Proposta** (file a parte, non ho toccato quello in uso): `config/soglie_attuazione_001.PROPOSTA_anti_impuntata.json`. Rilascio: decel IMU ≥2.0 m/s² **e** variazione di beccheggio ≥1.5° in 0.3 s → scatta nelle 2 impuntate, **0 falsi nelle 34 frenate**, 6 episodi in 11.9 min di moto (0.5/min: bici maneggiata alla partenza, 2 buche a 11-12 km/h, il caso 15:18:32). Tetto: decel ≥3.0 m/s² → non aumentare e scendi al 70%. **n=2 impuntate: sono valori di partenza da provare a banco/ombra, non soglie.**

## 1. Estrazione e registro

- Script: `training/eventi/estrai_guide_20261113.py` (riusa `soglie_dalle_guide.py` con centro 4112, circ 0.3374). Uscita: `training/eventi/out_guide_20261113/` (frenate.csv, sterzate.csv, segmenti.json).
- **Frenate 34**: stop_umano 4, umano 11, stop_limiter 5, limiter 14. **Pulite** (servo <1° e lim_zone attiva <0.2): 7 (4 stop con v finale <2 km/h, 3 rallentamenti). **Sterzate 17** (|gz|>22 °/s ≥0.5 s, v>1 m/s, manubrio ≥5°): 17.
- Importate nel registro (`registro_guide.py aggiungi --unita asmile-001 --fonte-v encoder_ruota --qualita alta`): sessione `20261113_145727`, 51 eventi, 1969 m. Registro ora: 84 frenate (usabili per soglie 30, tutte #001), 46 sterzate. Le righe del 08-09/11 sono state calcolate con 0.3477 m/giro, quelle del 13/11 con 0.3374 (−3% su v, decel e spazi): nel registro non sono riscalate.
- **Encoder ruota, filtro**: nella colonna `enc_wheel_cum` non ho trovato i salti a 83 km/h: incrementi massimi 7039 conteggi/campione = 26 km/h istantanei, v lisciata (Savitzky-Golay) max 17.2 km/h, nessun >30; -518 conteggi di jitter all'indietro. Il campo si aggiorna solo sul 52% dei campioni (≈25 Hz, il resto è ripetuto), per questo gli incrementi sembrano a gradini. I 83 km/h visti da Daniele devono venire da un'altra colonna (`enc_wheel_raw` o `lim_speed_ms`), non dal cumulativo: **non verificato**. Controllo di coerenza: rapporto encoder/GPS 0.99-1.03 su tutti e 4 i tratti.

## 2. Impuntate: dati per frenata

Tabella completa per le 34 frenate: `training/eventi/out_guide_20261113/impuntate_per_frenata.csv` (decel IMU picco, decel ruota, beccheggio picco, variazione in 0.3 s, velocità di beccheggio, az min/max, v al picco, servo max, quali regole scattano). Script: `training/eventi/impuntate_20261113.py` (carica + beccheggio) e `impuntate_analisi_20261113.py` (regole, falsi allarmi).

| | 15:03:51 | 15:08:52 | 15:18:32 (anomalia) |
|---|---|---|---|
| v all'inizio frenata | 9.6 km/h | 13.5 km/h (a 6 km/h nel picco di decel) | 9.2 km/h |
| decel IMU picco / decel ruota picco | 4.5 / 2.3 m/s² | 4.1 / 2.2 m/s² | 2.5 / 0.5 m/s² |
| muso giù (passa-alto 4 s) | +4.2° (picco a 3.6 km/h) | +4.3° (picco a 0.1 km/h) | +6.3° (picco a 3.5 km/h) |
| variazione in 0.3 s | 5.0° | 3.1° | 2.7° |
| velocità beccheggio in avanti | 21.6 °/s | 14.3 °/s | 10.5 °/s |
| az min / max | 0.47 / 1.49 g | 0.31 / 1.51 g | 0.55 / 1.22 g |
| servo max (1.5 s prima del picco) | 3.7° | 1.1° | 0 |
| video: scena su (px a 320 largh.) | −36 | −26 | −34 |

Note:
- La velocità di 15:08:52 dice "~6 km/h" nel resoconto di Daniele: è la velocità a metà del picco di decelerazione; la frenata partiva da 13.5 km/h col limiter (RELEASE/OVER) e Daniele ha continuato a mano.
- Il muso scende solo alla fine: picco di beccheggio quando v≈0.1-3.6 km/h, dopo il picco c'è il rimbalzo all'indietro (−2° e −1°, fino a −33 °/s). Il decelerazione dell'IMU (4.1-4.5) è circa il doppio di quella ricavata dalla ruota (2.2): ipotesi non verificata (ruota che rallenta meno della bici?), non usata per le soglie.
- az non discrimina: in frenate normali az va da −0.6 a 2.0 g (buche). Non lo uso nella regola.
- Il passa-alto con tau 4 s usato dalla regola attuale deriva: dà +6° dopo frenate lente senza muso giù (15:07:07, 15:09:31) per colpa del gx medio non nullo mentre si pedala. La regola proposta usa la variazione in 0.3 s (nessuna deriva).
- Altri picchi di decelerazione IMU ≥3.0 m/s²: 13 episodi in moto, tutti senza muso giù tranne le due impuntate (alcuni sono buche: IMU ay a picchi isolati). 15:03:29 (bici a 1.9 km/h appena mossa, muso +6°) è la bici maneggiata alla partenza: non è guida.

### Soglie: cosa succede (tutti i segnali causali, 50 Hz)

| regola | anticipo sul picco (2 impuntate) | frenate su 34 che scattano | episodi in moto (11.9 min) |
|---|---|---|---|
| attuale: rate>15 °/s o beccheggio HP>2° | 0.22 s e 0.26 s | 7 (5 non impuntate, una è l'anomalia 15:18:27) | 31 (2.6/min) |
| **P1 proposta: dec≥2.0 e Δ0.3s≥1.5°** | 0.24 s e 0.22 s | 2 (0 falsi) | 6 (0.5/min) |
| P2: dec≥2.5 e Δ0.3s≥1.5° | 0.24 s e 0.22 s | 2 | 3 (0.25/min) |
| P3: dec≥2.0 e Δ0.3s≥2.0° | 0.22 s e 0.18 s | 2 | 5 |
| P4: Δ0.3s≥3.0° (senza decel) | 0.18 s e 0.06 s | 2 | 6 |
| tetto dec≥3.0 | 0.40 s e 0.42 s | 5 (3 falsi) | 14 (1.2/min) |
| tetto dec≥3.5 | 0.38 s e 0.36 s | 2 | 7 (0.6/min) |

Rumore in moto (v>1 km/h): velocità beccheggio EMA p99 8.7 °/s, p99.9 14.8 °/s; Δ0.3s p99 1.7°, p99.9 3.7°; decel IMU p99 2.1 m/s². Sotto 15 °/s e 2° la regola attuale è dentro il rumore (p99.9 = 14.8 °/s).
P2 ha meno episodi di P1 ma con n=2 non si distingue da P1 sulle impuntate vere; scelgo P1 (soglia di decel più bassa = più margine). Ripresa (in piano, 70%): non misurabile, la bici si ferma sempre prima.

**Limiti**: 2 impuntate in 11.9 min di moto, 1 sola unità, 1 solo giorno, bilanciamento bici che Daniele sta correggendo (dato non rappresentativo dopo la correzione). Nessuna soglia è validata. Il tempo di risposta reale dell'attuatore (0.3 s) è stimato, non misurato qui. Non so dire se P1 scatterebbe in frenate di emergenza a velocità più alta (non ce ne sono).

## 3. Proposta soglie dalle guide (v4)

`config/soglie_attuazione_001.PROPOSTA_guide.json`, generata da `training/eventi/soglie_report_20261113.py`. Regole di qualità invariate (riga = max di fit pulito p75, fit solo stop verificati GPS, p75 osservato in banda con n≥2, + v·0.5 s + 0.5 m; mai sotto il segnaposto; crescente; ≥10 km/h segnaposto; qualità per n: solida ≥10, media 5-9, debole 2-4, segnaposto 0-1).
- Nuovi stop puliti 13/11: **4** (6.1, 9.2, 5.8, 8.0 km/h; spazio 4.26, 6.37, 2.87, 3.59 m). Totale 16 (12 dello scettico riscalati a 0.3374 + 4), verificati GPS 12 (8 + 4).
- Fit: sp = 2.53·v − 1.12 (v in m/s, offset p75 +0.62 m), prima 2.34·v − 0.95 a 0.3477. Verificati GPS: 2.11·v − 0.28.
- Tabella (frena entro / rallenta entro, m): 3 km/h 2.99/4.48 (n 3, debole); 5 km/h **4.45**/6.67 (n 8, media); 8 km/h 6.73/10.09 (n 3, debole); 10 km/h 8.42/12.63 (segnaposto); 12: 10.09/15.13; 15: 12.63/18.95; 20: 16.84/25.27; 25: 21.03/31.54 (tutte segnaposto). Rispetto a v3: 5 km/h 4.56→4.45 (ora la ruota è 0.3374 invece di 0.3477, e in banda ci sono 8 stop e non 6), 8 km/h 6.39→6.73, 10 km/h 7.98→8.42.
- **Nessuno stop pulito sopra 9.3 km/h** (anche il 13/11: limiter in zona OVER/RELEASE/HYST per 1669 m su 1968, cioe 85%): le righe da 10 km/h restano segnaposto. Per migliorarle serve un giro con limiter spento.
- Sterzo (indicativo, non soglie): 27 curve (17 del 13/11): velocità manubrio picco 24-32-39 °/s (p25-p50-p75), ampiezza 17-24-33°, curvatura 0.16-0.22-0.25 1/m, anticipo 0.4-0.8-1.0 s. Le sterzate del 13/11 sono più rapide delle precedenti (rate p50 36 °/s), ma n piccolo.

## 4. Intento e limiti

- Intento (`intent`) non assegnato a nessuna frenata del 13/11: **intent:unknown** (nessuna percezione girata su questi giri; non ho accoppiato oggetti alla scena). Le frenate sono segnalate solo dai sensori.
- Il video è stato usato solo per il segno del beccheggio (spostamento verticale globale della metà alta dell'immagine, phase correlation 320x200, `training/eventi/video_shift_20261113.py`, CSV in out_guide_20261113/shift_*.csv). Convenzione verificata con uno shift sintetico (dy>0 = contenuto verso il basso). Fotogrammi: `agents/rapporti/img/eventi_guida_20261113_beccheggio_video.jpg`. 5791 e 6181 fotogrammi decodificati su 5804 e 6182 del CSV (alcuni macroblocchi corrotti): l'indice-fotogramma può slittare di 1-2 dopo gli errori; il tempo viene da `t_ms` della riga, quindi l'errore resta ≤0.1 s.
- Soglie IMU/guide: nessuna toccata in `config/soglie_attuazione_001.json`.
