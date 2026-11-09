# Calibrazione ai bordi e "tunnel virtuale" - 2026-11-09 (asmile-ricercatore)

Due unità, MAI mischiate: **#001** (2 OV9281 Inno-Maker separate, M12, 1280x800, rpicam --sync) e **logger001** (Camarray SBS 2560x800, 1 CSI). Stesso METODO, calibrazioni separate (`calib_asmile-001.json`, `calib_asmile-logger001.json`).

## Diagnosi dai nostri dati (rapporto calib_001_vicino_bordi_20261109.md)
- dy residuo a parabola in x (centro +3, sx -5, dx -1.5 px) e dcy al limite (15 px) = il modello a 12 parametri NON ha la capacità: o manca la distorsione di ordine alto (k3+, rational), o il punto principale/rotazione relativa non è identificato perché i dati di fit stanno quasi tutti al centro. Non è un problema di "più video col metro": è un problema di COPERTURA dei bordi nei dati di fit.
- A 5 m d≈46 px: 2% = 0.9 px di disparità. Il requisito vero è bias di disparità <1 px ai bordi + dy<0.5 px.
- Il metro a mano ha ±2% (visite ripetute) e al bordo laterale Z non è nota: il metro non può essere il giudice dei bordi. Il giudice dei bordi è la geometria (dy=0 e scala quadretti), la scala assoluta viene dal centro + baseline 200 mm.

## Cosa può voler dire "tunnel virtuale" (valutazione)
| opzione | lavoro | serve da Daniele | atteso ai bordi | verdetto |
|---|---|---|---|---|
| (a) ChArUco/scacchiera su MONITOR/TV, 40-60 viste che coprono angoli, distanza 0.5-1.5 m, inclinazioni | basso: `calib_charuco.py --make-board` esiste; ChArUco accetta viste parziali (OpenCV `aruco`/`CharucoDetector`), quindi la scacchiera può uscire dal bordo = punti proprio negli angoli | 10 min per unità: mostrare il pattern, muovere la camera (o il monitor) | corner reproj <0.3 px su tutto il campo se il modello è ricco; dy<0.5 px | **SCELTA** |
| (a2) pattern attivi a strisce/fase sul monitor (densità punti, tipo Zhang/Bell; Schöps usa target a griglia fitta per il modello generico) | medio-alto: codice nuovo di decodifica fase, sincronia schermo-camera | uguale a (a) | migliore densità, ma serve solo se (a)+rational non basta | riserva, NON ora |
| (b) modello lente più ricco: OpenCV `CALIB_RATIONAL_MODEL` (k1-k6), `CALIB_THIN_PRISM_MODEL`, `CALIB_TILTED_MODEL`; Kannala-Brandt (`cv2.fisheye`) solo se il campo >~100° (il nostro f≈1150 px ⇒ HFOV≈58°: pinhole+rational basta); modello generico a griglia/spline (Schöps et al., CVPR 2020) | basso per rational (flag in `stereoCalibrate`); alto per generico | niente: è software, ma vale SOLO con dati ai bordi da (a) | rational: tipico <0.2-0.3 px RMS su M12 | **va insieme ad (a)** |
| (c) self-calibration dai video di guida (BA su feature, SfM, baseline nota): `calib_colmap.py`, autorectify | medio; NON provata su dati reali (memoria) | niente | buono per dy e scala-residua, debole per distorsione ai bordi (poche feature stabili, scena dinamica) | rifinitura/controllo, non base |
| (d) target SINTETICO renderizzato | basso | niente | NON calibra la lente vera (non contiene la distorsione reale) | **solo test del fitter**: genero viste sintetiche con distorsione nota e verifico che il fit recuperi dcy/k senza saturare |

Quindi il "tunnel virtuale" utile = (a)+(b), con (d) come test software di mezz'ora e (c) come verifica sui video di guida. Un vero "digital twin" della camera da simulare non sostituisce la misura: i parametri vengono dalla fisica della lente reale.

## Raccomandazione unica (più rapida che chiude ≤2% ai bordi < 5 m)
**ChArUco a monitor + stereoCalibrate con modello rational, intrinseci liberi, viste che coprono tutto il campo comune, baseline vincolata a 200 mm in post (riscalo |T|), + mappa residuale dy(x,y) se serve.**

Piano in 5 passi (per unità, #001 prima, poi logger001 con lo stesso metodo):
1. **Test sintetico (Mac, 30 min, nessun hardware)**: render di viste ChArUco con distorsione rational nota + dcy offset; verificare che `calib_charuco.py` (con flag rational, vincoli larghi su cy, nessun clamp a 15 px) la recuperi. Se il fit satura anche qui, il bug è nel fitter, non nella lente. NON VERIFICATO: non so se in calib_charuco.py ci sia già il clamp dcy; da controllare.
2. **Acquisizione (Daniele, 10 min/unità)**: monitor alla massima luminosità, pattern ChArUco grande (quadretti ~30-40 mm sul monitor, misurati col righello su schermo = scala), schermo fermo, camera spostata a 0.6-1.5 m. 40-60 coppie: 1/3 con il pattern nel terzo SINISTRO, 1/3 destro, 1/3 centro, tutte con inclinazione 20-40° e angoli alto/basso. #001: video a camere ferme sul supporto in bici (stessa posa montata, perché la calib vale montata), muovendo il monitor. Logger001: stesso, split SBS 2560x800.
3. **Fit**: `stereoCalibrate` con `CALIB_RATIONAL_MODEL` (provare anche +THIN_PRISM), intrinseci liberi, 2 camere insieme; tenere 20% delle viste fuori come test. Criterio: RMS<0.3 px, dy dopo rettifica <0.5 px su griglia 3x3 di zone. Poi |T| riscalato a 200 mm (baseline nota, vedi D010).
4. **Verifica indipendente**: (i) i video col metro già in mano per #001 (centro 1-15 m ≤2%); (ii) bordi: scala dei quadretti (metodo già usato nel rapporto) e dy SIFT di sfondo = 0 su tutta l'immagine; (iii) valori candidati scartati se peggiora un punto del banco fisso. Candidato in `calib_<unità>.CANDIDATO.json`, mai sovrascrivere.
5. **Se i bordi restano >1 px**: aggiungere una mappa residuale (polinomio 2D/griglia sparse di dy e dx in coordinate rettificate, fit sui corner del passo 2): è la versione "poveri" di Schöps (modello generico) e corregge ogni residuo sistematico senza parametrizzare la lente. Solo dopo, valutare fasi/strisce (a2).

## Rischi / cose da controllare (onestà)
- Monitor: moiré e sfarfallio PWM con otturatore globale a esposizione corta (OV9281): usare luminosità massima, esposizione >=1/60 s oppure PWM-free; pannello piano (OLED/IPS), nessun vetro lucido con riflessi. Geometria del pixel del monitor nota esattamente (vantaggio rispetto alla stampa). NON VERIFICATO sul nostro monitor.
- Il bordo laterale a <3 m è fuori dal campo comune (disparità 80-250 px): ai bordi sotto 3 m non esiste stereo; il requisito "≤2% ai bordi <5 m" è valido solo dove i due campi si sovrappongono. Va scritto nel gate.
- Camere #001 forse spostate fra mattina e pomeriggio (dy centrale 0.4 → 2-3 px): la calibrazione va fatta con la camera montata e poi BLOCCATA (viti/colla), altrimenti nessun modello regge. Chiedere a Daniele se le camere sono state toccate.
- La lente M12 grandangolare "vera" potrebbe superare il pinhole+rational: se i corner ai bordi estremi hanno reproj >0.5 px con rational, passare a `cv2.fisheye` o alla mappa residuale (passo 5).

## Fonti
- Schöps, Larsson, Pollefeys, Sattler, "Why Having 10,000 Parameters in Your Camera Model Is Better Than Twelve", CVPR 2020 (arXiv 1912.02908): modelli generici/griglia battono i parametrici a 12 parametri quando la lente non è ben descritta. Citata dalla conoscenza, non riletta oggi.
- OpenCV docs, `calibrateCamera`/`stereoCalibrate` flags `CALIB_RATIONAL_MODEL`, `CALIB_THIN_PRISM_MODEL`, `CALIB_TILTED_MODEL`; `cv::aruco::CharucoDetector` accetta viste parziali della board. Citate dalla conoscenza, non riaperte oggi.
- Kannala & Brandt, "A generic camera model and calibration method for conventional, wide-angle, and fish-eye lenses", IEEE TPAMI 2006 (base di `cv2.fisheye`).
- Interni: rapporto calib_001_vicino_bordi_20261109.md; logger/depth/calib_charuco.py, calib_colmap.py.
- NON fatta ricerca web oggi (limite 25 min, urgenza): le fonti sopra vanno controllate dallo scettico.
