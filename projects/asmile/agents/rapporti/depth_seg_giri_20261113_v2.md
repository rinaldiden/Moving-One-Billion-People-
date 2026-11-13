# Depth + segmentazione giri 13/11 di #001 — giro 2 (dopo VETO 1/3 di asmile-occhio)

Unita': asmile #001. Codice: `training/depth/video_fluido_001.py` (modo `v13`, default), stadio A invariato (`out_20261113_giri/A_*`). Uscite locali (mai su git): `training/depth/out_20261113_giri_v2/` (5 video `video_fluido_*.mp4` + `tracks_*.pkl` con stato, azione, orario). Fotogrammi guardati: `agents/rapporti/img/giri2_video_fluido_*_f*.jpg`. Il rapporto precedente resta `depth_seg_giri_20261113.md`.

## Perche' la Z del banner non era quella dell'oggetto (causa misurata)
Guardando le tracce dei fotogrammi del critico (pkl v10):
1. **La Z scritta era lo stato del filtro (Kalman), non la misura della maschera.** f4440 palo: Z scritta 0.97, misura della maschera 6.5. f4470 persona: scritta 0.84, ultima misura 46. f4530 veicolo: 0.85 vs 23. Il filtro si era agganciato a misure vicine sbagliate e le misure vere venivano scartate come outlier (servono 4 outlier di fila per riagganciare).
2. **La Z misurata sulla maschera era essa stessa impossibile per l'oggetto** (il filtro veniva da li'): f4722 bidone alto 113 px scritto a 2.1 m = 0.17 m reali; f4722 'car' largo 98 px a 1.9 m = 0.13 m; f4470 persona alta 139 px a 1.5 m = 0.15 m. Causa: nel campo vicino la depth sulla maschera (picco con il 11-29% dei pixel validi, `frac_picco`) prende cluster sbagliati. Non e' un bug di associazione traccia-Z: la traccia e' giusta, la Z lo e' no.
3. **Tracce in coast (maschera non vista fino a 4 fotogrammi) restavano "primo ostacolo"** con la Z predetta e nessuna maschera disegnata (f4470, f4530, f4580 erano coast). R1 era applicata (la lista `declassato` c'e' nel ramo 15 fps), ma il banner usava la traccia anche quando le ultime osservazioni erano declassate.
4. v10 non aveva il controllo maschera-sagoma ne' la coerenza Z (erano in v11/v12, che la v10 dei giri non usava): FRENA scattava per qualunque candidato dentro il corridoio largo.

## Correzioni (regole fissate prima di rigirare, decisione registrata)
1. **Z = Z della maschera**, validata con le dimensioni fisiche per classe (`SIZE_M`: estensione max(larghezza, altezza) alla Z deve stare in [min, max*1.3]; box tagliato dal bordo: niente controllo del minimo). Se impossibile: Z da dimensione tipica (+-50%, scritta con `~`, es. `~13.5 m`). Picco solo se contiene >=30% dei pixel validi, altrimenti mediana. Se il filtro si allontana dalla misura >max(0.5 m, 15%) vince la misura. In coast: ultima Z della maschera meno la strada percorsa dall'encoder; **il coast non puo' essere primo ostacolo ne' FRENA**.
2. **FRENA solo con maschera sulla sagoma**: gate v11/v12 (sagoma 0-2 m della maschera alla sua Z interseca la sagoma bici, oppure tocca terra nel corridoio+margine), sotto 2 m Z coerente su 3 fotogrammi con encoder, altrimenti RALLENTA.
3. **Maschere dentro un veicolo** (>=70% dentro la maschera veicolo, Z non piu' vicina di 1 m): non candidate e non disegnate (f4626 persona nel finestrino: risolto).
4. **Superficie**: 'altro' con >=50% dei pixel in strada/marciapiede (stuff) o largo >60% e alto <0.5 m = fondo strada, non ostacolo (f1022 'bed' 3.7 m).
5. **NON MISURATO** (grigio, mai verde): pixel saturi >25% nel corridoio -> sempre; depth valida sulla strada del corridoio (fino a rallenta_entro, min 8 m) <0.15 -> solo se nessuna maschera misurata nel corridoio. Il verde "nessun ostacolo misurato" resta solo con misura buona.
6. **Orari**: `frames_*.csv t_ms` = stesso orologio dei `sensors_*.csv t_ms` (il `wall` dei sensori, interpolato). Il rapporto precedente aveva gli orari sbagliati: frenata 1 e' 15:03:46-15:04:01 (non 15:03:41), f4588 = 15:08:52.0. Orari ora anche nella barra del video e nel pkl.

## Risultati (1155 fotogrammi, 5 tratti, bici in moto)
| azione | v10 (prima) | v13 (dopo) |
|---|---|---|
| FRENA | 174 (5+64+75+26+4) | **28** (0+1+26+1+0) |
| FRENA con Z<1 m | 45 | **0** |
| RALLENTA | 85 | 70 |
| STERZA | 50 | 65 |
| NON MISURATO | - | 446 (di cui saturo 261; poca depth senza maschere 185) |
Casi richiesti: FRENA Z<1 m = 0 su f4440, 4470, 4530, 4722, 1124, 2482 (anche f4512, 4524, 4580: nessun FRENA). Oggetti con Z da dimensione marcati `~`.
**Monovolume**: RALLENTA da f4569 (15:08:50.7) a 8.9 m, poi 7.5 m a 15:08:51.5 e 5.9 m f4588 (15:08:52.0); a 4.8 m da fermo (v=0, nessuna azione). Con gli orari giusti il RALLENTA parte ~0.7 s DOPO l'inizio della decelerazione umana (v 3.9 -> 3.4 m/s tra 15:08:49.5 e 15:08:50.1), perche' la soglia rallenta_entro (11.7 m a 3.9 m/s) viene superata solo a 11.7 m; la formulazione "prima della frenata umana" del rapporto precedente era un effetto degli orari sfasati. Encoder: 5.85 m percorsi e 1.01 m coerenti con Z (rapporto 1) invariato.

**I 28 FRENA rimasti, guardati:** 26 = paletto (bollard) vero a 6.7 -> 1.5 m sul percorso nel vicolo (f1124-1157; f1137 visto: il paletto alto 0.9 m a 3.3 m e' nel corridoio, altezza coerente con la Z; un fotogramma, f1145, Z 1.5 poi 4.2 = salto); 1 = veicolo a 7.3 m (f4542, frena_entro 7.5 m a 14 km/h); 1 = palo a 6.9 m (f2380, il palo sta a ~0.1 m dal bordo del corridoio: caso di bordo da giudicare).

**Ostacoli veri <5 m persi?** Guardati ~25 fotogrammi (28, 60, 188, 1039, 1044, 1055, 1060, 1107, 2465, 2472, 2478, 3013, 4509, 4540, 4583, 4625, 1022, 2386, 4512...). Dei fotogrammi in cui v10 aveva il primo ostacolo a 2-5 m e ora no o piu' lontano (65): 37 sono ora NON MISURATO (alleys bianchi saturi/vicolo scuro), 20 sono persone in coast con Z del filtro (6.8 m scritto 2.9; 16.8 scritto 3.2, ecc.), il resto blob su pareti. Nessun ostacolo vero in corridoio entro 5 m trovato perso nei fotogrammi guardati; NON dimostrato su tutti.

## Limiti dichiarati (NON VERIFICATO)
- **Nessuna distanza a terra col metro**: la correzione e' di coerenza fisica (dimensioni, encoder), non di errore %. Z da dimensione e' +-50%.
- Le soglie `SIZE_M` (per classe), 0.30/0.7/1.0/0.15/0.25 sono scelte prima ma non validate su altre sessioni. Un'auto parzialmente nascosta con estensione visibile <1.0 m a distanza vicina verrebbe spostata lontano (f4540: auto stimata 8.2 m con estensione 1.0 m, probabile ~15-18 m, RALLENTA al limite).
- Residui: f1022 blob a 7.0 m sul muro in alto -> RALLENTA (non FRENA); f2380 palo al bordo; 446 NON MISURATO su 1155 e' molto (valid<0.15 e' comune su asfalto/pietra liscia: nel tratto monovolume la mediana e' 0.14), la soglia 0.15 e' quella fissata ma probabilmente troppo alta per la strada.
- Non girato: regressione `regress_v12_casi` sulle sessioni del 12/11 (il codice di v10-v12 e' invariato nei rami non-v13, `VFMODE=v12` lo riproduce). Non girate le regole su tutto il giro (solo i 5 tratti).

## Per asmile-occhio (cosa guardare)
(a) i 28 FRENA: tutti veri/giusti? soprattutto f2380 (palo a bordo) e f4542. (b) `~` Z da dimensione: plausibile su f4470 (persona 13.5 m) e f4530? (c) NON MISURATO in controsole (f3100, 3140, 3150 grigio) e nei 90 del tratto monovolume: troppo severo? (d) manca un ostacolo vero <5 m?
