# Ricerca: separare MURI/FACCIATE da OSTACOLI nello strato "senza nome" di #001 (2026-11-10, asmile-ricercatore)

Solo ricerca e lettura. Nessun codice toccato, nessun calcolo pesante. Unita': SOLO #001 (2 OV9281 1280x800, baseline 200 mm). Niente di qui vale per il logger (Camarray).

## Problema (da `L1.ostacoli_ombra_20261110.md`, sezione v3)
v3 su set C trova 11/15 (73%) degli ostacoli veri nel corridoio e nessun falso su asfalto vuoto, ma 26 falsi su 27 sono muri/facciate/basi di edificio a X 0.5-1.7 m, Z 3-12 m (FONTE: decisione di asmile-occhio 2026-11-10T12:59:36 e nota del suo VERDETTO VETO 3/3 delle 12:59:44 in `agents/palla/registro.jsonl`, righe 114 e 117: 27 falsi = 0.47/frame su 57 frame, tipo (ii) muri/facciate = 26. Il conteggio per-frame dei falsi NON e' in `training/depth/out_20261110/verita_occhio_C.json` (sha256 df1f23c5...b1e28): quel file contiene solo i veri e gli ambigui; i falsi nascono dall'abbinamento con `ostacoli_det_v3_C.json` fatto da occhio. Occhio avverte che le Z di quel file hanno incertezza 15-40%); una persona vicina al muro si fonde col muro. v3 stessa ammette: "pilastri e spigoli ... non li distinguo con la sola geometria ... limite di classificazione".
Vincolo: non perdere furgoni, auto, persone vicine.

## Cosa dicono le fonti (primarie dove indicato)
- **Stixel World** (Badino, Franke, Pfeiffer, DAGM 2009): free space + bastoncini verticali (distanza, altezza), con programmazione dinamica per colonna; ~128 stixel per immagine VGA. [paper](https://www.cvlibs.net/projects/autonomous_vision_survey/literature/Badino2009DAGM.pdf)
- **Multi-layer stixel** (Pfeiffer, Franke, BMVC 2011): piu' stixel per colonna, serve proprio al caso "pedone davanti a un edificio". [paper](https://bmva-archive.org.uk/bmvc/2011/proceedings/paper51/paper51.pdf)
- **Dynamic stixels** (Pfeiffer, Franke, IV 2010): aggiunge moto. [paper](https://www.cvlibs.net/projects/autonomous_vision_survey/literature/Pfeiffer2010IV.pdf)
- **Object-level priors for stixels** (Cordts et al., GCPR 2014): classi freespace/obstacle/sky/vehicle/guard rail con detector come priori. [paper](https://www.cvlibs.net/projects/autonomous_vision_survey/literature/Cordts2014GCPR.pdf)
- **Semantic Stixels** (Schneider et al., IV 2016): due canali (profondita' + semantica) come termini dati dello stesso modello: "la profondita' non basta". [preprint](https://download.visinf.tu-darmstadt.de/papers/2016-iv-schneider-semantic_stixels-preprint.pdf)
- **v-disparity / u-disparity** (Labayrade, Aubert, Tarel; u-disparity: Hu & Uchimura): strada = retta in v-disparity, oggetto verticale frontale = retta verticale; u-disparity accumula la disparita' per colonna e dice dove stanno gli ostacoli. Limite noto: superfici NON frontali (muri obliqui) si spalmano su molte disparita'. [Labayrade et al. (copia secondaria, equazioni non ricontrollate sull'originale)](https://typeset.io/pdf/road-scene-analysis-by-stereovision-a-robust-and-quasi-dense-47py5kdwa0.pdf), [ICVS Bielefeld](https://biecoll.ub.uni-bielefeld.de/index.php/icvs/article/download/215/308/305), [rassegna single-frame](https://users.utcluj.ro/~igiosan/Resources/Papers/Obstacle%20Detection%20Based%20on%20Single%20Frame%20Stereo%20Vision.pdf)
- **Carrozzine autonome** con stereo: disparita' -> mappa 3D -> mappa 2D di evitamento ([UTS](https://opus.lib.uts.edu.au/handle/10453/2886)); terreno/cordoli = punti ben sopra/sotto il piano ([Smith-Kettlewell CVHI 2007](https://www.ski.org/wp-content/uploads/2025/02/curbscvhi07.pdf)); i bordi marciapiede da stereo hanno falsi e mancati noti ([UCL](https://discovery-pp.ucl.ac.uk/10074210/1/79.04_06.pdf)). Non ho trovato fonti che trattino proprio "muro a bordo percorso a bassa velocita'": su questo punto le fonti NON rispondono, la scelta e' nostra e va misurata.
- **Segmentazione leggera a bordo**: PIDNet-S 93 FPS a 2048x1024 su RTX 3090 ([paper](https://arxiv.org/pdf/2206.02066)); per Pi 5 NON ho trovato numeri (ricerca fatta: solo GPU desktop e Pi 4 senza risultati leggibili). **Fps su Pi 5 = NON VERIFICATO**.

## Intuizione geometrica chiave (DERIVAZIONE MIA, non da fonte: da verificare su sintetico)
Immagine rettificata, f focale, B=0.2 m, cx punto principale. Per un piano verticale X = X0 parallelo alla direzione di marcia: Z = f X0/(u-cx), quindi **d = fB/Z = B (u-cx)/X0**.
- La disparita' del muro e' una **retta in u, indipendente dalla riga v** (il piano contiene l'asse Y). Pendenza B/X0: 0.13 px/colonna a X0=1.5, 0.12 a X0=1.7.
- Un piano verticale con yaw qualsiasi: ancora d = a u + b. Il pitch 7.4 deg di #001 introduce una lieve dipendenza da v solo per muri NON paralleli (ny = nz sin(theta): ~13% della pendenza per un muro frontale, nulla per muro parallelo). Rotazione/roll non considerati.
- Una persona a X=1.0 davanti a un muro a X0=1.6 ha disparita' maggiore del muro nella stessa colonna di un fattore 1.6 (+60%): salto enorme (diversi px a 5 m), molto oltre il rumore SGBM (~0.5 px). Un furgone/auto idem (superficie frontale a d costante, orizzontale in u-disparity, non obliqua). Questo e' il motivo per cui il "pezzo di muro + persona fusi" si puo' separare: il muro e' un modello a 1-2 parametri, la persona e' residuo.
- Perche' v3 fallisce oggi: la finestra Z [z, 1.3z] taglia il muro in fette oblique che sembrano blob compatti (area, altezza e riempimento passano). La finestra in Z e' la forma sbagliata per un piano che attraversa tutte le Z.

## STATO (giro 2, dopo VETO 1/3)
Questo documento non e' piu' una sola ricerca: e' un **PROTOCOLLO PRONTO per asmile-depth**, da usare solo se Daniele sceglie l'opzione A (gli ostacoli sono fermi in attesa di Daniele dopo il 3 VETO). Il set D NON lo creo io. Nessun codice toccato, nessun lavoro pesante (solo numpy a mano). Solo #001. Tutto con calib PROVVISORIA (`calib_asmile-001.json`: f_rect 1312.49 px, B 0.2 m, cx 640).

## 1. Set D: PREREQUISITO (se meno, il risultato e' dichiarato NON DIMOSTRATIVO)
- >= 40 frame NUOVI di `session_20261109_094146`, con **>= 30 ostacoli veri nel corridoio** (Z 2-12 m, |X|<=4.5; stesso criterio di `L1.ostacoli_ombra` sez. v3-4, invariato). Se i veri sono < 30 il verdetto e' "non dimostrativo" qualunque sia il numero.
- Nessun frame entro +-30 frame da quelli in `frames_dev.json` (10), `frames_ostacoli.json` (A, 30), `frames_ostacoli_B.json` (30), `frames_ostacoli_C.json` (57). Controllo mio: le finestre +-30 attorno ai 127 frame usati coprono **5298 dei 10066 frame** della sessione; ne restano ~4770 (liberi, non verificati uno per uno come "tenuto/in moto"). Limite da dichiarare: D e' nella STESSA corsa, scene che si ripetono: meno indipendente di una sessione nuova.
- Arricchimento AUTOMATICO: SAM 3 persona/auto (come per C, `objects_giro.csv`) con criterio scritto: maschera person/car/bicycle/truck a <= 150 px laterali da una maschera building/wall, oppure con |X|<=2.5. Il criterio e il seed si congelano prima di guardare le uscite di v3.
- Lista + sha256 **committata prima** di far girare SGBM; verita' alla cieca di asmile-occhio (D aperto UNA volta, stesso protocollo anti-taratura di v3).
- Perche' >= 30: Clopper-Pearson una coda 95% con 0 persi su n veri: n=25 -> limite inferiore 88.7%; n=29 -> 90.2%; **n=30 -> 90.5%**; n=40 -> 92.8% (calcolati). Sotto 30 non si puo' dimostrare richiamo >= 90%.

## 2. Soglie FISSE e confronto accoppiato
- **Falsi <= 0.2/frame** (su 40 frame: <= 8). v3 su C ne fa 0.47/frame: il filtro deve togliere almeno il ~58% dei falsi-muro solo per entrare. Limite dichiarato: con 8 falsi su 40 frame il limite superiore 95% (Poisson esatto) e' **0.36/frame**; per DIMOSTRARE <= 0.2 al 95% servono <= 3 falsi su 40 (limite 0.19). Verdetto: "<= 8" = soddisfatto in punto, "<= 3" = dimostrato.
- **Richiamo >= 90%** sui veri del corridoio, riportato per v3 e per v3+filtro, **ACCOPPIATI frame per frame** (stessi frame, stessi veri, stessa verita' cieca).
- **"Persi 0"** = nessun vero che v3 trova viene perso da v3+filtro. Si elenca ogni vero con (v3 trova? si/no, v3+filtro trova? si/no). Il richiamo assoluto di v3 (73% su C) NON e' da recuperare col filtro: il filtro non puo' aggiungere veri, solo togliere falsi.
- **Limite al 95% (Clopper-Pearson)** dichiarato per il numero di veri effettivi (tabella sopra), sia per "persi 0" sia per il richiamo.
- Sottoinsieme a parte e riportato: veri "persona/auto a <= 0.5 m da un muro" (il caso a rischio), con il suo n e il suo limite.
- Ripetibile: sui veri di C gia' noti (furgone f05996, auto f05315, persone f05574/f03008/f07242, f06558 fusa col muro) la regola va provata a parte come **controllo di sviluppo** (C e' bruciato per il richiamo ma non per il test "il filtro perde questi?").

## 3. Proposta 1: UNA regola in px assoluti, congelata
File congelato: `agents/rapporti/regola_muro_px_FREEZE_20261110.json`, **sha256 `2300fd9be62216b436b0ba44c28dfb26087139b662c15311738f5f607bb6c6c7`** (non committato da me: lo committa il capo/asmile-depth PRIMA di D).
- Piano per lato `d = a*u + b*v + c` (3 parametri, RANSAC, fino a 3 piani sequenziali per lato per gradini/nicchie).
- **Un solo numero: tau = 1.5 px.** Pixel **assorbito come muro** se `d - d_piano <= +1.5 px`; **sporge = oggetto** se `d - d_piano > +1.5 px`. Nessuna banda morta, nessuna tolleranza in percento di d (la vecchia 0.15*d e' ELIMINATA: valeva 3 px a d=20 e contraddiceva la sporgenza 1.5 px).
- Pixel PIU' LONTANI del piano (residuo < -1.5 px) non vengono assorbiti e non contano come sporgenza (nicchie): non sono ostacoli per costruzione.
- Piano valido solo se: supporto >= 150 colonne, delta-d >= 6 px sul supporto, pendenza |a| in [0.05, 0.5] px/colonna col segno giusto per il lato (destra +, sinistra -), supporto che arriva sopra 2.2 m (cosi' il fianco di un furgone, che finisce a ~2 m, non e' "muro"). Questi vincoli escludono per costruzione una persona (131 colonne a 5 m, 66 a 10 m, delta-d ~ 0) e un veicolo frontale (pendenza ~0).
- **Motivazione di tau, col rumore SGBM:** sigma assunto 0.5 px (block 7, sub-pixel 1/16): tau = 3 sigma. **sigma NON misurato** (nelle fonti di questo lavoro non c'e'): va misurato sui residui dei muri nei frame DEV (gia' visti) PRIMA di D. Se 3 sigma > 1.5 px, STOP: non si ritocca tau in silenzio, si fa una regola nuova con nuovo sha256 e si dichiara.
- Perche' piano a 3 parametri e termine libero: (a) un errore di d0 (+-2 px) e' una costante, assorbita dal termine c (un piano vincolato al punto di fuga lo subirebbe); (b) errore di cx +-2 px sposta d del muro di B*2/X0 = 0.16-0.4 px (X0 2.5-1.0 m), sotto tau; (c) pitch 7.4 gradi + yaw bici introducono una dipendenza da v: coefficiente 0.2*sin(psi)*sin(7.4 gradi)/X0 = 0.0014-0.0042 px/riga per psi 5-15 gradi -> **su 400 righe 0.56 / 1.12 / 1.67 px (X0 1.6 m)**: un piano solo-u (come nella versione del giro 1) sbaglierebbe di quasi tau con yaw 10 gradi. Con termine in v questo sparisce. (Pitch puro su muro parallelo: nessun effetto, la normale e' sull'asse X.)

## 4. Test sintetico da fare PRIMA di D + tabella ANALITICA
### Specifica del sintetico (CPU, secondi, nessun dato reale)
Generare disparita' ideale (+ rumore gaussiano sigma 0.5 px, + quantizzazione 1/16) per: piano verticale per lato + persona (cilindro/rettangolo 0.5 x 1.7 m, d costante) + furgone/auto frontale + palo (0.15 m). Griglia di casi:
- persona con bordo a **gap 0 / 0.2 / 0.3 / 0.5 m** dal muro; **Z = 5 e 10 m** (e 12 come limite del gate);
- **yaw bici** 0, +-5, +-10 gradi (muro divergente/convergente); **pitch 7.4 gradi** sempre; roll 0;
- errori **cx +-2 px** e **d0 +-2 px** (applicati alla disparita' in ingresso);
- muro **a gradini** (aggetto di 0.1/0.2/0.3 m con piano di rientro) e **a nicchie** (rientro 0.5 m), **piu' piani per lato**, X0 in {1.0, 1.6, 2.5} m;
- persona DENTRO la nicchia (secondo piano) e davanti a un gradino.
Cosa si misura per ogni caso: (1) minimo gap persona-muro per cui il blob sopravvissuto supera ancora i gate di v3 (dimensione/area/altezza); (2) larghezza/area della fetta di persona assorbita; (3) falsi-muro residui (gradino/pilastro: restano oggetti, non vanno peggio di v3); (4) il piano viene stimato giusto (errore di pendenza). **Il sintetico passa solo se nessuna persona con gap >= 0.2 m a Z <= 10 m viene persa in nessuna combinazione di errori**; il gap minimo assorbito va dichiarato nel verdetto. Se fallisce, la proposta 1 cade prima di toccare D.

### Tabella analitica (solo calcolo, numpy a mano)
Formula (derivata mia, vedi sezione geometria): **stacco_px = (f*B/Z) * gap / X0**, con f*B = 1312.49*0.2 = 262.5 px*m, gap = distanza laterale tra il bordo della persona piu' vicino al muro e il muro, X0 = intercetta laterale del piano a Z=0 (per muro parallelo alla marcia = distanza laterale). Una persona ha d = fB/Z; il muro nella stessa colonna ha d piu' basso di quel fattore.

Muro parallelo (yaw 0). Stacco in px (da confrontare con tau = 1.5) e gap minimo assorbito (= tau*X0*Z/fB):
| X0 (m) | Z (m) | gap 0.2 | gap 0.3 | gap 0.5 | gap minimo assorbito |
|---|---|---|---|---|---|
| 1.0 | 5 | 10.5 | 15.7 | 26.2 | 0.03 m |
| 1.0 | 10 | 5.2 | 7.9 | 13.1 | 0.06 m |
| 1.0 | 12 | 4.4 | 6.6 | 10.9 | 0.07 m |
| 1.6 | 5 | 6.6 | 9.8 | 16.4 | 0.05 m |
| 1.6 | 10 | 3.3 | 4.9 | 8.2 | 0.09 m |
| 1.6 | 12 | 2.7 | 4.1 | 6.8 | 0.11 m |
| 2.5 | 5 | 4.2 | 6.3 | 10.5 | 0.07 m |
| 2.5 | 10 | 2.1 | 3.1 | 5.2 | 0.14 m |
| 2.5 | 12 | 1.7 | 2.6 | 4.4 | 0.17 m |

Con yaw della bici (muro a 1.6 m dalla bici alla Z della persona; X0 = 1.6 +- Z*tan(psi), + = muro che si allontana):
| yaw | Z | X0 | gap 0.2 | gap 0.3 | gap 0.5 |
|---|---|---|---|---|---|
| 5 gradi, divergente | 5 | 2.04 | 5.2 | 7.7 | 12.9 |
| 5 gradi, divergente | 10 | 2.47 | 2.1 | 3.2 | 5.3 |
| 10 gradi, divergente | 5 | 2.48 | 4.2 | 6.3 | 10.6 |
| **10 gradi, divergente** | **10** | **3.36** | **1.6** | **2.3** | **3.9** |
| 5 gradi, convergente | 10 | 0.73 | 7.2 | 10.9 | 18.1 |
| 10 gradi, convergente | 10 | <=0 | il muro taglia la traiettoria: caso non ammesso |  |  |

Errori di calibrazione: d0 +-2 px e' costante su muro e persona -> **stacco invariato** (con termine c libero); cx +-2 px -> variazione di d del muro 0.16-0.4 px -> stacco ridotto al piu' di 0.4 px.

### DOVE LA REGOLA RISCHIA DI ASSORBIRE UNA PERSONA (dichiarato)
1. **Persona adiacente al muro (gap ~0) a Z 10-12 m:** e' fisicamente inseparabile con la sola geometria. Lo stacco cresce lungo il corpo (al centro, gap+0.25 m): a Z=10, X0=1.6 le colonne a <= 0.09 m dal muro (circa 18% di 0.5 m) vengono assorbite, **l'82% sopravvive**; con X0 2.5 o muro divergente 10 gradi (X0 3.36) si assorbe fino a 0.14-0.19 m, cioe' **28-38% del corpo**, a Z=12 fino a 0.23 m (46%). Il blob sopravvive ma piu' stretto: **NON SO se supera i gate di dimensione di v3** (da misurare nel sintetico: e' il punto 1 della specifica).
2. **Caso peggiore tabellato:** yaw 10 gradi divergente, Z=10, gap 0.2: stacco **1.6 px = a tau**; persona a 0.2 m dal muro in quel caso e' al limite. Con piano mal stimato (errore +-0.5 px dal rumore) stare a meno di 2 px di stacco = rischio vero: **soglia di prudenza dichiarata: sotto 2.0 px di stacco la persona e' considerata a rischio.** Nei casi con X0 >= 2.5 e Z >= 10 con gap 0.2 siamo li' (2.1 e 1.6 px).
3. **Oggetti sottili/bassi** (bollard 0.15-0.2 m, palo, paletto) a ridosso di un muro oltre 10 m: stacco = come persona ma l'oggetto e' largo 0.15 m, quindi se il gap < gap minimo e' ASSORBITO INTERO (non resta nessuna fetta). I frame f09435 paletti e f07584 persone sono comunque >12 m (fuori gate).
4. **Gradino/pilastro/aggetto di 0.1-0.3 m** NON viene assorbito se sporge: stacco (aggetto 0.1/0.2/0.3 m, X0 1.6) = 3.5/7.5/12.1 px a Z=5 e 1.7/3.7/6.1 px a Z=10. Quindi il filtro NON rimuove i falsi di tipo "pilastro/spigolo" (stessa classe che v3 dichiara non risolvibile): restano falsi; l'aggetto sotto 0.1 m a Z=10 e' al limite.
5. **Furgone/auto paralleli a bordo:** il fianco e' un piano laterale; protetto solo dalla regola "supporto sopra 2.2 m" (il fianco finisce a ~1.5-2 m). **NON VERIFICATO** con dati; facciata tagliata dal campo visivo (cima non visibile) resta rischio: quel muro non e' assorbito (conservativo), cioe' si resta con i falsi di v3.
6. **Persona in piedi al centro di una nicchia/su secondo piano**: vale la stessa formula con il X0 del secondo piano; piano fantasma fra persona e muro non e' possibile per i vincoli (150 colonne, delta-d>=6).
7. Calib PROVVISORIA: tutta la tabella usa f=1312.49 e B=0.2; se la scala cambia, gli stacchi scalano linearmente con f.

## 5. Proposta 2: veto SAM solo ASIMMETRICO (con conteggio PRIMA)
- Veto = scartare un blob v3 solo se >= 80% dei pixel e' building/wall/fence **e** il blob (maschera dilatata 10 px) NON interseca nessuna maschera person/car/bicycle/truck. Puo' solo togliere falsi mai proteggere male: la classe semantica non puo' mai cancellare un oggetto protetto.
- **Conteggio prima di attivare** (sui frame dev+A+B+C, tutti gia' con person/car in `objects_giro.csv`): (a) quante istanze person/car hanno >= 20% di pixel dentro/adiacenti (10 px) a una maschera building/wall; (b) **recall di SAM person/car sui veri noti** di `verita_occhio*.json`; (c) quanti dei 26 falsi-muro di C verrebbero tolti. Attivabile solo se (b) = 100% sui veri noti e (c) significativo; altrimenti non si attiva e si riporta il numero.
- Richiede un run SAM 3 con prompt building/wall: **non fattibile adesso (Mac occupato)**, quindi nessun numero oggi: **NON VERIFICATO**.
- Rischio da misurare: persona vicino al muro etichettata "building" da SAM (corpo contenuto nella maschera building). Mitigazione gia' dentro la regola: se SAM non da' la maschera person il veto scatta -> e' questo il caso che il conteggio (b) deve escludere.

## 6. Ordine e piano per asmile-depth (se opzione A)
1. (CPU, minuti) sintetico della sezione 4. Se persone con gap >= 0.2 m a Z <= 10 vengono perse in qualche combinazione -> stop, rapporto.
2. (CPU) misura sigma SGBM dei residui su muro sui frame DEV gia' visti: se 3 sigma > 1.5 px -> stop e nuovo freeze.
3. Prop. 1 su dev+A+B+C come controllo di sviluppo (regola gia' congelata, nessuna modifica): quanti dei 26 falsi tolti, quali veri persi.
4. Capo/asmile-depth crea D (sezione 1), commit lista+sha256, regola gia' committata con sha256 sopra.
5. Un giro unico su D, confronto accoppiato, tabella veri/falsi con i limiti 95% dichiarati.
6. Solo dopo, quando il Mac e' libero: prop. 2 con conteggio.
Prop. 3 (BEV) e stixel completo: non consigliati ora (vedi giro 1), invariato.

## Geometria (DERIVAZIONE MIA, da verificare su sintetico)
Immagine rettificata, f, B=0.2, cx. Piano verticale X = X0 + Z*tan(psi): d = (B/X0)*(u - cx - f*tan(psi)) -> lineare in u, pendenza B/X0, indipendente dalla riga v per un muro parallelo; con psi e pitch theta compare un termine in v di coefficiente B*sin(psi)*sin(theta)/c. Persona a distanza gap dal muro alla stessa Z: stacco = (fB/Z)*gap/X0. Non ricontrollato su dati reali.

## Limiti di questa ricerca
- Equazioni di Labayrade da copia secondaria; stixel da PDF su cvlibs.net.
- Fps segmentazione su Pi 5 NON VERIFICATO.
- sigma SGBM = 0.5 px e' un'ASSUNZIONE (3 sigma = tau); nessuna misura fatta qui.
- La tabella e' analitica: non prova che v3 non scarti la fetta di persona sopravvissuta.
- Set D non esiste: nessun risultato di richiamo/falsi in questo documento, solo protocollo.
- Tutti i numeri di #001 con calib PROVVISORIA (punto A in corso); #001 solo, non il logger.
