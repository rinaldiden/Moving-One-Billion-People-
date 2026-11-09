# Calib #001: verifica vicino e bordi (video 153251) - 2026-11-09

Unità: asmile #001 (2 OV9281, cam0 = destra, baseline 200 mm). SOLA VERIFICA con `calib_asmile-001.json` (nessun fit, nessun candidato scritto).
Video: `asmile-loggers/asmile-001/session_20261109_153251/` (locale, mai su git). Bici ferma, Daniele con la scacchiera (7x10, quadretti ~29.7 mm).
Miniature: `agents/rapporti/img/calib001_vicino_*.png` (panoramica: `calib001_vicino_panoramica.png`; sinistra = cam sinistra rettificata, destra = cam destra alla disparità trovata, riga bianca = stessa riga).
Dati: `logger/depth/banco_fisso_asmile-001_vicino_bordi.json`. Script: `logger/depth/calib_001_20261109/vicino_153251/`.

## Metodo
- Soste trovate con la differenza dal fondo (persona ferma >=1 s). Ordine osservato: 1 m C,dx; 2 m dx,C,sx; 3 m sx,C,dx; 4 m dx,C,sx; 5 m sx,C,dx (a serpentina); poi seconda passata a 2 m dx,C,sx.
- Z = f_rett*B/d con la rettifica di `Calib.rectify`. d = ZNCC del bersaglio (nucleo della scacchiera) sx->dx con sub-pixel, mediana di 12 frame. Sui centri controllato con i corner ChArUco-style (findChessboardCornersSB): stessi valori (±0.3%).
- "pos" = posizione nell'immagine rettificata: sx x≈90-230, centro x≈720-860, dx x≈1190-1300.
- Controllo indipendente dalla disparità: Z da scala = Z del centro × (quadretto centro / quadretto bordo) nella stessa passata.

## Tabella errore % (Z stereo rispetto al metro)
| dist. | sinistra | centro | destra |
|---|---|---|---|
| 1 m | fuori campo comune | Z 1.035: **+3.5%** | fuori campo comune |
| 2 m | 2.63: **+31.7%** (scala: 2.40) | 2.046 +2.3 / 1.979 -1.0 / 2.064 +3.2 | 2.28 **+14.0%** / 2.29 **+14.6%** (scala 2.25 / 2.30) |
| 3 m | 3.69: **+23.1%** (scala 3.44) | 3.123: **+4.1%** | fuori campo comune |
| 4 m | 4.93: **+23.2%** (scala 4.80) | 4.117: **+2.9%** | 4.65: **+16.2%** (scala 4.60) |
| 5 m | 6.14: **+22.8%** (scala 5.84) | 5.15: **+3.0%** | 5.48: **+9.6%** (scala 5.35) |

"Fuori campo comune": il bersaglio al bordo con la distanza < 3 m esce dal campo dell'altra camera (disparità 80-250 px): non misurabile in stereo. "Basso a 2-3 m" e avvicinamento finale: non trovati / non misurabili (scacchiera troppo vicina, <1.5 m o a cavallo del bordo).
dy residuo sul bersaglio (px, dopo rettifica): centro +2.6...+4.3 (cresce con la disparità), destra -1.0...-1.9, sinistra -3.3...-6.3. Sfondo SIFT: centro +2, bordo sinistro -3 (stessa forma, anche con i dati di stamattina: bordi -2/-3, centro +0.3/+0.5).

## Cosa dice
1. **Centro**: errore +2.3...+4.1% (media +2.6%) a tutte le distanze 1-5 m; stamattina era 0.5-1%. Criterio ≤2% NON raggiunto. Segno sempre positivo: sembra un offset comune (cam spostate dopo il pranzo o scala metro diversa), non rumore. Variazione fra visite allo stesso metro (2 m: -1.0...+3.2) = posizionamento a mano ±2%: è il limite del banco.
2. **Bordi**: errori +10...+32% col metro, segno uguale a sx e dx (Z troppo lontana), sinistra peggio della destra. MA il controllo dalla scala dei quadretti dà Z del bordo molto vicina alla stereo (destra: -0.2...+2.4%; sinistra: +2.7...+9.8%). Quindi la maggior parte dello "scarto" è Daniele che al bordo era più lontano del nominale (plausibile: spostamento laterale non a Z costante), non solo calibrazione. Resta un residuo sistematico a SINISTRA di +3...+10% (stereo più lontana della scala, segno coerente, ma la scala ha ±5% per scacchiera inclinata) = probabile distorsione/rettifica al bordo sinistro. Destra: nessun residuo dimostrabile.
3. **dy**: NON <1 px: centro +3, bordo sx -5, bordo dx -1.5. Forma a "parabola" in x (picco al centro, negativo ai bordi, più forte a sinistra) = k1/k2 o punto principale verticale; dcy destra del fit era 15.0 = sul limite imposto (il modello è al bordo). Già noto come L1.rettifica aperto.
4. Ipotesi spostamento camere: il dy centrale è passato da ~0.4 (mattina, stessa calib) a ~2-3 px nel pomeriggio -> la rettifica non vale più com'era. NON VERIFICATO (servirebbe una foto stessa scena stamattina/ora con camere ferme).

## Verdetto
Criterio (≤2% sotto 5 m, centro E bordi): **NON raggiunto** (centro +2.6% medio; bordi non misurabili col metro finché non si conoscono Z reali; dy 3-6 px). Gate L0.calib_001 resta aperto (PASSA parziale).

## Correzione proposta (non applicata; nessun CANDIDATO scritto)
- Aspettare gli spostamenti laterali in cm di Daniele: se Z al bordo non è quella nominale, ricalcolare i nominali (Z reale = valore da lui) e rifare la tabella: serve a dire se il bordo sbaglia davvero.
- Poi rifit joint (`calib_tape_joint.py`/`fit_verify.py`) con: centri di questo video (1-5 m) + bordi con Z reale come FIT, dy=0 su SIFT di tutta l'immagine (anche di questo video, sfondo fermo), k1,k2 per camera liberi con dcy non al limite, e come VERIFICA le soste 4-6-8-12 m di stamattina e un nuovo set 6-15 m (importante: il centro a 7-15 m oggi non è verificato dopo il possibile spostamento). Candidato in `calib_asmile-001.CANDIDATO.json`, scartato se peggiora un solo punto del banco fisso.
- Prima domanda a Daniele: stamattina e ora le camere sono state toccate/smontate? (dy centrale cambiato).

---
# Aggiornamento pomeriggio: PnP al posto dei cm laterali, camere NON toccate (Daniele), rifit joint

Script in `logger/depth/calib_001_20261109/vicino_153251/`: `detect_corners_pm.py` (angoli scacchiera 6x9 per camera sulle soste), `prep_boards_pm.py` / `prep_boards_am.py` (angoli grezzi pomeriggio / mattina), `ratio_scala_mattina_pomeriggio.py`, `zdy_zone_mattina_pomeriggio.py`, `fit_joint_pm.py` (fit), `eval_joint_pm.py` (tabelle). Interprete con scipy: `~/.asmile_depth_venv/bin/python`.

## 1. Perche' il centro e il dy sono cambiati se le camere non si sono mosse (misurato)
- **Scala, indipendente da focale e da metro**: Zstereo / tz(PnP, in quadretti) con la calib attuale. Mattina 2-5 m: 0.02899, 0.02899, 0.02896, 0.02884 (7 m: 0.02869). Pomeriggio centro 1-5 m: 0.02930, 0.02918, 0.02937, 0.02923, 0.02926. Differenza **+1.0%** (0.7-1.4). Quindi lato camera/focale cambia ~1%, non il 2.6-3.5%.
- Il resto e' il bersaglio: a parita' di "segno metro" la scacchiera del pomeriggio e' piu' lontana (tz PnP): 2 m +2.4%, 3 m +2.1%, 4 m +1.5%, 5 m +1.0% rispetto alla mattina = offset ADDITIVO ~4-5 cm (decresce con la distanza), piu' scatto fra visite allo stesso segno (2 m: 67.7 / 70.5 / 70.8 quadretti = -1.7...+0.3%). Il metro del pomeriggio ha quindi ±4 cm di posizionamento: fittare la focale su di esso scambia un artefatto per focale (il fit solo-pomeriggio porta fL 1153->1123 e fa leggere la mattina -3.5...-7.8%: SCARTATO).
- **dy**: stesso sfondo lontano, stessa zona (x 600-900 rett.): mattina +0.2/+0.6, pomeriggio +1.9/+2.2; (x 300-600) +0.36/-0.02 -> +1.56/+1.17. Offset quasi uniforme **+1.3...+1.6 px** al centro, +2.5 sul bordo destro. Sulla scacchiera dy = a + 0.0093*d in entrambe le sessioni (mattina a~0.6, pomeriggio a~2.0): la pendenza (Ty ~1.9 mm, geometria reale) e' stabile, cambia solo l'offset di 1.4 px (0.06 gradi: gioco/temperatura, non uno spostamento). Con UNA calib il dy mediano al centro resta ~0.7 px per sessione: <1 px mediana ma non p95.
- Dubbio sul metodo "scala dai quadretti" del rapporto: ignora l'inclinazione della scacchiera (tilt ~27 gradi a X=1.1 m, Z=2 m -> quadretto x0.89 = 12% di errore di Z). Il PnP lo corregge: con PnP i bordi destro/sinistro NON sono "scala-coerenti".

## 2. Bordi con PnP (calib ATTUALE, SQ=0.0288 m dalle soste mattina, stereo vs PnP)
dx 2 m +10.0% e +9.2%; dx 4 m +7.4%; dx 5 m +4.5%; sx 3 m +10.9%; sx 2 m +17.3%. dy bersaglio: dx -0.8...-1.6, sx -4.4...-5.7. Il bordo e' davvero sbagliato (non solo "Daniele piu' lontano"). Ordine di grandezza dipende da SQ (±1%) e dal modello di distorsione usato dal PnP: NON verita' assoluta.

## 3. Rifit joint
Split deciso PRIMA: FIT pomeriggio centro 1-2(348)-3-5 m, bordi dx 2 m(243), sx 3 m(523), dx 4 m(852); mattina fit 1-2-3-5-7-10-15 m. TENUTI FUORI: pomeriggio centro 4 m, 2 m(1818), 2 m(2152), dx 2 m(2064), dx 5 m, sx 2 m(2197); mattina 4-6-8-12 m. Parametri: R, f per camera, k1,k2(,k3) per camera, dcx/dcy, Ty,Tz, pp sinistra, offset additivo metro per sessione (z0), offset dy pomeriggio; dy=0 su SIFT mattina (moto) e pomeriggio (sfondo lontano) e sugli angoli.
Esito: **nessuna soluzione accettabile**. Tutte le varianti saturano i limiti (dcy 40-80 px, tz, dly) e, quando abbassano il dy a sinistra (-4 -> -1.3), peggiorano la mattina di 1-3 punti %: 1 m -3.8%, 2 m -2.2%, 4 m -1.25% (prima -1.2, -0.05, +0.54), e i bordi tenuti fuori restano +3...+11% (sx 2 m +11%). Un modello radiale k1,k2,k3 + pp non spiega il dy sinistro (-4 px a x<430, y 270-530, identico in entrambe le sessioni: forma non radiale -> serve tangenziale/altro modello o una misura di bordo sinistro con piu' punti). Dati sul bordo sinistro scarsi (SIFT <300 punti, 2 soste di scacchiera, nessuna a 4-5 m: angoli non rilevati).

## Tabella prima/dopo sui punti TENUTI FUORI (migliore tentativo joint "fb2" vs calib attuale; err% vs metro, bordi vs PnP)
| punto | attuale | fb2 (scartato) |
|---|---|---|
| mattina 4 m | +0.54 | -1.25 |
| mattina 6 m | +0.84 | -0.60 |
| mattina 8 m | +0.45 | -0.66 |
| mattina 12 m | -1.14 | -1.54 |
| pom. centro 4 m | +2.96 | +1.12 |
| pom. centro 2 m (1818 / 2152) | -1.09 / +3.46 | -3.05 / +1.34 |
| pom. dx 2 m / dx 5 m (PnP) | +9.2 / +4.5 | +5.0 / +3.2 |
| pom. sx 2 m (PnP) | +17.3 | +11.4 |
| dy mediana/p95 mattina moto | 0.68-1.01 / 2.8-5.2 | 0.66-0.83 / 2.6-3.2 |
| dy mediana pomeriggio | 1.74 | 1.50 |

Il centro pomeriggio migliora solo perche' il fit assorbe l'offset del metro: peggiora la mattina (che vale 0.5-1% fino a 15 m): scartato per regola. **Nessun `calib_asmile-001.CANDIDATO.json` scritto. `calib_asmile-001.json` invariato.**

## Cosa serve (decisioni)
1. La calib attuale e' gia' buona al centro (mattina 0.5-1% fino a 15 m): NON ricalibrarla sul metro del pomeriggio. Il centro +3% del pomeriggio = ~1% scala + ~2% posizione scacchiera.
2. dy: aggiungere una correzione verticale a runtime (drift_monitor: offset dy ~1.4 px per sessione) invece di cercare una calib che copra entrambi gli stati.
3. Bordi: serve un set dedicato (scacchiera a 3-6 m fissa ai bordi con tilt ~0, 2 per lato, almeno 4 e 5 m a sinistra, ripresa con camere ferme) e un modello con tangenziali; oppure dichiarare il campo utile = centro (+-15 gradi) finche' il bordo non e' risolto.
