# BLM GROUP — taglio laser tubo, incastri automatici e carpenteria metallica (stato a nov. 2026)

> Note di ricerca (Italiano). Fonti in gran parte BLM stesse (marketing): dove un dato è solo dichiarato dal produttore lo segnalo. Ricerca fatta con ~22 chiamate web; diversi PDF/pagine BLM non leggibili (404 o PDF binari) → vedi Gaps.

## 1. Gruppo, software e macchine: cosa offre BLM oggi

### Takeaway
BLM GROUP = BLM SpA (Cantù, curvatubi/celle 3D) + ADIGE SpA e ADIGE-SYS SpA (Levico Terme, Lasertube e grandi profili). La suite software si chiama oggi "BLMelements": ArTube (CAD/CAM Lasertube), ArGo (CAM celle 3D LT-FREE), VGPNext (curvatura, successore di VGP3D), PartViewer, Prometheus (MES, di fatto il successore/evoluzione di ProTube). Per strutture in acciaio contano LT8.20, LT12, LT14 e LT24.

### Cited Findings
- Composizione gruppo (comunicato Tube 2026): BLM SpA di Cantù (CO) "curvatubi, sagomatubi, piegafilo, celle di saldatura e celle di taglio laser 3D"; ADIGE SpA di Levico Terme (TN) "sistemi di taglio laser dei tubi (Lasertube), macchine per il taglio a disco"; ADIGE-SYS SpA (Levico Terme) "sistemi laser lamiera e combinati per tubo, impianti per la lavorazione laser di tubi e profilati di grandi dimensioni" — [BLM, IT_BLM_GROUP_Tube 2026 (PDF)](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)
- Suite software 2026: VGPNext (curvatubi, anche versione ufficio), ArTube ("disegnare, manipolare e progettare pezzi singoli o assiemi tubolari complessi di qualsiasi sezione"), ArGo (CAM per celle laser 3D, risolve collisioni automaticamente), PartViewer (simulazione + stima tempi/costi), Prometheus (MES, interconnessione con ERP) — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)
- ProTube è descritto come "production MES" che riceve info dal CAD/CAM e crea automaticamente gli ordini di produzione — [Expometals, BLMelements](https://expometals.net/en/hall/machines/tube-machinery/stand/blm-group-spa/news/blmelements-a-multi-technology-environment-for-tube-processing-id13741); nel blog LT14/LT24 "Protube" = modulo ordini di produzione e interfaccia ERP — [BLM Blog LT14/LT24](https://blog.blmgroup.com/lt14-and-lt24-the-new-competitiveness-of-laser)
- VGP3D = programmazione 3D/simulazione curvatubi; import IGES, STEP, XT di tubi curvi singoli o assiemi multi-tubo; scambia dati con Artube3 e ProTube — [BLM VGP3D](https://www.blmgroup.com/software/vgp3d?hsLang=en); sostituito/evoluto in "VGP Next" (lancio 18/09/2023) — [Umformtechnik](https://umformtechnik.net/wire/Content/Reports/Revolutionising-the-world-of-bending), [VGPNext PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/VGPNext/VGPNext_EN.pdf). NB: VGP3D/VGPNext riguardano la CURVATURA, non generano incastri laser.
- Pagina settore "Structural": macchine associate ai giunti di strutture in acciaio = LT8.20, LT14/LT24, LT12; arredo urbano/parchi = LT5.10, LT7, LT FIBER EVO; saldatura laser LW-S; celle 3D LT-FREE, LT360 — [BLM Structural](https://www.blmgroup.com/structural)
- LT14 / LT24 (blog BLM): LT14 Ø 25–355 mm, 18 m, 100 kg/m; LT24 Ø 50–610 mm, 18 m, 300 kg/m; tubi tondi/quadri/rettangolari + profili aperti; testa 5 assi per tagli inclinati, smussi e semi-smussi (cianfrini) — [BLM Blog LT14/LT24](https://blog.blmgroup.com/lt14-and-lt24-the-new-competitiveness-of-laser). Coerente con trade press USA: LT24 "200 lb/ft" (~298 kg/m) e carico 60 ft (~18 m), lavora angolari, U, colonne, piatti, travi — [Metal Construction News mar. 2021](https://www.digital.metalconstructionnews.com/march-2021/page-53)
- LT14 FIBER (novità Tube 2026): tubi/profili fino a Ø 355 mm, 100 kg/m, "sorgente laser a fibra multipla", tre mandrini, modalità "sfrido zero" — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)
- Walcarius (Belgio) su LT24: tubi fino Ø 610 mm, IPE500, HEA400, HEB300, travi fino 500×300 mm — [BLM Blog Walcarius, 19/10/2021](https://blog.blmgroup.com/walcarius-shakes-up-the-construction-world-with-3d-laser-cutting)
- LT8.20: testa 3D tilt; dati diametro discordanti: "12–240 mm" (scheda espositore) vs "fino a 220 mm" vs 9,5" (~241 mm), barre 27 lb/ft (~40 kg/m) — [Intec exhibitor](https://www.messe-intec.de/exhibitors-products/product/intec/414408/174010); [SME 2020](https://www.sme.org/technologies/articles/2020/april/blm-group-enhances-automatic-laser-cutting-systems/). Un riepilogo trade riporta LT8 12–220 mm, 35 kg/m (non verificato su scheda ufficiale).
- Active Tools: Active Scan = correzione di freccia e torsione del tubo con camera/scanner laser "in meno di 0,6 s" (dichiarato); Active Tilt = movimento della testa per piccoli dettagli; Active Focus = regola il fuoco, piercing fino a -30% (dichiarato) — [SME 2020](https://www.sme.org/technologies/articles/2020/april/blm-group-enhances-automatic-laser-cutting-systems/). Sul blog LT14/LT24 citati anche Active Piercing, Renishaw, Tap & Drill (maschiatura M3–M16) — [BLM Blog LT14/LT24](https://blog.blmgroup.com/lt14-and-lt24-the-new-competitiveness-of-laser)
- LT7 con unità di inserimento automatico inserti filettati, programmati da Artube — [Industrial Machinery Digest](https://industrialmachinerydigest.com/industrial-news/industry-updates/blm-group-to-demonstrate-lt7-lasertube-with-insertion-unit-at-fabtech)
- LT-FREE: cella laser 5 assi per pezzi 3D (stampati/idroformati/curvi), programmata con ArGo; demo 2020: fino 3 kW, tavola 1.500×1.000 mm, B=140° — [Mfg News 2020](https://mfgnewsdigital.mydigitalpublication.com/article/Five-Axis+Laser+Cutting+System/3585705/647508/article.html); BLM la presenta come "ideale per terzisti" — [BLM Euroblech 2026 preview](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-06-29-euroblech/IT_BLM_GROUP_Euroblech_2026_preview.pdf)

### Inferences
- "ProTube" nelle fonti più recenti (2026) non compare più: il MES citato è Prometheus. Trattare ProTube come nome storico/modulo legacy.
- Per carpenteria edile con travi HEA/HEB/IPE la macchina rilevante è LT24 (o LT14 per profili ≤ Ø355/100 kg/m); LT8.20 copre telai leggeri, arredo, bici, tubi ≤ ~240 mm.
- "LT5, LT8.10, LT-FREE bevel" della richiesta: non ho trovato un modello "LT-FREE bevel"; lo smusso (bevel) lo fanno le teste 3D/5 assi delle Lasertube (LT8.20, LT14/24).

### Gaps
- Schede tecniche ufficiali LT5/LT7/LT8.10/LT12/LT24 non scaricate (pagine /en/lasertube in 404 via fetch). Potenze laser attuali delle versioni fibra non confermate.
- Nessuna fonte su un prodotto chiamato "Synergy/SmartSolutions", "BLM Joint" o tool "Design for laser" dedicato.

## 2. Incastri/giunzioni che ArTube genera (tipi, parametri, limiti)

### Takeaway
ArTube risolve automaticamente intersezioni/raccordi (sagomatura "a bocca di pesce" del tubo che appoggia su un altro) da un modello 3D importato, e ha una LIBRERIA di incastri pronti + incastri definibili dall'utente. Tipi documentati: tab & slot (linguette/asole), giunti passanti, giunti d'appoggio, a baionetta, tasca (pocket) per inserire un tubo nell'altro, denti su staffe che entrano in asole, cut-bend (taglio-e-piega da un solo tubo), marcature laser di posizione. Coda di rondine, "graffe", parametri numerici di gioco: NON trovati in fonti pubbliche.

### Cited Findings
- "Joints and intersections are solved by ARTUBE"; si può migliorare il risultato "inserting one of the many available interlocking joint solutions"; citato un giunto "Hook & Slot" parametrico che "works with all shaped tubes" — [DirectIndustry, ARTUBE](https://directindustry.com/prod/blm-group/product-6136-465935.html) (scheda distributore, non verificata su sito BLM; una ricerca dedicata a "Hook & Slot" non ha trovato altre fonti)
- Workflow documentato: import del 3D dell'intera struttura → "one click" il software riconosce ogni tubo, sezione e tagli → genera i part-program → si modificano componenti e si aggiungono incastri anche non presenti nel progetto originale → taglio, assemblaggio, saldatura — [BLM Blog, Tubular frame fabrication](https://blog.blmgroup.com/tubular-frame-fabrication-endless-innovation-with-lasertube-artube)
- Tipi citati nello stesso post: tubo appoggiato con estremità sagomata sull'altro tubo (fissa la posizione orizzontale), tubo che penetra l'altro, giunti a baionetta "wherever possible", tasca rettangolare dimensionata sul tubo inserito (incluso l'angolo), staffa a C con denti in asole sul tubo ("with the teeth the need for clamping is eliminated"), slot and tab con numero diverso di linguette ai due capi (o stesso numero a quote diverse) come anti-errore di montaggio (poka-yoke), marcature laser (linea/freccia) per quota d'inserimento — [BLM Blog, Tubular frame fabrication](https://blog.blmgroup.com/tubular-frame-fabrication-endless-innovation-with-lasertube-artube)
- Post 27/05/2020: tipi "through joints, supporting joints, bayonet joints, cut-bends"; ArTube "offers a library full of ready-made interlocking solutions", l'utente può disegnare propri giunti; import da altri CAD via formati di scambio; ArTube "riservato ai clienti BLM GROUP" — [BLM Blog, Designing a frame is much easier with joints](https://blog.blmgroup.com/designing-a-frame-is-much-easier-with-joints)
- LT14/LT24: "any type of joint or node between pipes and/or beams"; "Artube creates joints automatically from a library of supports and joints"; testa 5 assi → tagli inclinati, cianfrini e semi-cianfrini per saldatura — [BLM Blog LT14/LT24](https://blog.blmgroup.com/lt14-and-lt24-the-new-competitiveness-of-laser)
- Funzioni ArTube rilevanti (pagina prodotto): ambiente CAD completamente parametrico con libreria di feature; micro-giunzioni (micro-joints, per trattenere lo sfrido — non sono incastri di montaggio); Weld search (posizione del cordone di saldatura longitudinale del tubo, il taglio viene limitato lì); Bent tube analysis (correzione automatica delle distorsioni da curvatura); Cut-bending (unisce elementi di telaio di stessa sezione/spessore in un unico pezzo da piegare); Special Parametric Sections (famiglie di profili, es. serramenti); variabili e ripetizioni; scelta 2D/3D — [BLM, ArTube](https://www.blmgroup.com/software/artube)
- Gioco/tolleranza: tesi PoliMi 2019 sui giunti a T, 45° e 60° tra tubi tagliati laser: il parametro chiave è il "fattore di correzione del diametro di taglio" che determina il gap tra i tubi, con influenza dell'ovalità dei tubi commerciali (non cita BLM) — [Politesi, Doddegowda 2019](https://www.politesi.polimi.it/handle/10589/149721)

### Inferences
- Il "taglio a bocca di pesce" (saddle/cope) è automatico al riconoscimento del 3D; gli incastri tipo tab&slot/baionetta/tasca sono feature da libreria che l'operatore applica (semi-automatico), non generate senza input.
- Il parametro "gioco" esiste di certo (correzione diametro/offset di taglio è standard CAM), ma i nomi/valori esatti in ArTube non sono pubblici.
- Profili: le fonti coprono tondi, quadri, rettangolari, sezioni speciali parametriche e profili aperti/travi (IPE/HEA/HEB) su LT14/LT24.

### Gaps
- Nessuna documentazione pubblica (manuale) con elenco completo di giunti e parametri (lunghezza linguetta, gioco, compensazione spessore). Coda di rondine e "graffe" non trovate. Servirebbe trial ArTube o demo BLM.
- Nesting di giunti/ottimizzazione barra: non verificato in dettaglio (solo "sfrido zero" LT14 FIBER).

## 3. Case study: incastri al posto della saldatura, montaggio senza dime, edilizia

### Takeaway
Il caso più forte per l'edilizia è Walcarius (Belgio, LT24): connessioni maschio-femmina tubo-IPE e strutture/carport montabili senza saldatura. Per il resto BLM posiziona gli incastri soprattutto come riduzione/semplificazione delle dime e preparazione alla saldatura, NON come eliminazione della saldatura.

### Cited Findings
- Walcarius: connessioni maschio-femmina in cui travi e tubi si incastrano direttamente invece di usare piastrine saldate alle colonne; incastri tubo-IPE; asole e fori fatti in un'unica lavorazione; strutture assemblate senza saldatura; kit carport auto-montabili e più leggeri; prospettive per coperture complesse, ponti, lucernari; fino a 2.500 ordini/anno, 5.000 t/anno di materiale; foratura laser "in secondi" vs minuti di trapano — [BLM Blog Walcarius](https://blog.blmgroup.com/walcarius-shakes-up-the-construction-world-with-3d-laser-cutting) (articolo BLM, numeri dichiarati dal cliente)
- Telai "self-fixturing" con slot-and-tab: il telaio si tiene in posizione dopo piegatura a mano, riduzione delle dime di saldatura — [Fabricating & Metalworking, ott. 2020 (inserzione BLM)](https://digital.fabricatingandmetalworking.com/october-2020/page-16)
- Post 2020: le dime costano tanto più per pezzo quanto più piccolo è il lotto; gli incastri laser riducono complessità delle dime e semplificano distanze/angoli; il taglio laser non richiede molatura prima della saldatura; esempi: sedia di design, fitness, telaio veicolo elettrico, copertura tubolare di Piazza Garibaldi a Napoli; nessuna bici citata — [BLM Blog, Designing a frame…](https://blog.blmgroup.com/designing-a-frame-is-much-easier-with-joints)
- Pagina LT14/LT24 applications: immagini di "interlocking of round steel sections for bridges", "steel interlocking for a structural frame", copertura stadio, tirante di funicolare; clienti Kobex, Van Kerkhof, Frea&Frea (LT14, "giunti tra elementi strutturali per semplificare l'installazione"), Gothaer Fahrzeug Technik, CMM — [BLM LT14/LT24 applications](https://blmgroup.com/lasertube/lt14-lt24/applications)
- Caso italiano MAP S.p.A. (LT14): "programmare ogni singolo elemento strutturale e avviarlo in produzione in modo efficiente" (dal riepilogo di ricerca; pagina non leggibile al fetch) — [BLM success story MAP SpA](https://www.blmgroup.com/success-stories/map-spa)
- Pagina "Structural": giunti "easy to assemble and weld", nuove connessioni trave-tubo, riduzione tempi di installazione — [BLM Structural](https://www.blmgroup.com/structural)

### Inferences
- Per una struttura LEGO in acciaio prefabbricato, BLM documenta la logica (maschio-femmina, asole, fori, poka-yoke tab, marcature) ma la verifica strutturale delle connessioni senza saldatura/bulloni resta a carico del progettista (le fonti non parlano di certificazioni EN 1090/NTC).

### Gaps
- Nessun case study BLM trovato su telai bici. Nessun dato pubblico su prove di carico di giunti a incastro BLM.

## 4. Formati file, apertura (API, plug-in, automazione)

### Takeaway
ArTube importa IGES, STEP e IFC (Tekla), esporta 3D; ha plug-in SolidWorks, "Automator" (cartelle watch → part-program automatici) e "Composer" (pezzi da pattern, anche da ERP). Nessuna API/scripting pubblica documentata; DSTV/NC1 non confermato.

### Cited Findings
- "Artube imports IGES, STEP, and IFC (Tekla) files", eliminando la conversione IFC→STEP/IGES/X_T — [BLM Blog LT14/LT24](https://blog.blmgroup.com/lt14-and-lt24-the-new-competitiveness-of-laser)
- Pagina ArTube: import IFC e gestione grandi profili in acciaio; import 3D editabile come nativo; export 3D in qualsiasi momento; un progetto → part-program per più macchine BLM; Composer (GUI o direttamente da ERP); Automator (file 3D in cartelle → part-program automatici); plug-in SolidWorks che richiama le librerie di calcolo ArTube; generazione "AI-assisted" one-click — [BLM, ArTube](https://www.blmgroup.com/software/artube)
- VGP3D/B_Import: IGES, STEP, XT — [BLM VGP3D](https://www.blmgroup.com/software/vgp3d?hsLang=en)
- Prometheus MES: interconnessione dati con ERP — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)

### Inferences
- Da Fusion 360/Inventor: passare da STEP (plug-in nativo solo SolidWorks). Per edilizia BIM: IFC da Tekla/Revit.
- L'automazione "aperta" è a livello file (cartelle Automator, ERP→Composer), non tramite API documentata.

### Gaps
- Supporto DSTV/NC1: nessuna fonte BLM trovata (le ricerche restituiscono solo doc Tekla). Plug-in Inventor/Tekla: non trovato. Formato nativo dei part-program: non documentato.

## 5. Trial, licenze, contatti italiani, fiere, prezzi

### Takeaway
ArTube ha trial gratuito di 30 giorni (dichiarato in pagina prodotto), ma BLM lo descrive anche come "riservato ai clienti". Contatto stampa ufficiale pr@blmgroup.it; BLM SpA in Via Selvaregina 30, Cantù. Nessun prezzo pubblico.

### Cited Findings
- "A 30-day free trial is available, after which you can purchase the software" — [BLM, ArTube](https://www.blmgroup.com/software/artube); ma "Artube… reserved for BLM GROUP customers" (2020) — [BLM Blog 2020](https://blog.blmgroup.com/designing-a-frame-is-much-easier-with-joints)
- Contatto comunicazione: Chiara Vaccari, Corporate Communication Coordinator, pr@blmgroup.it — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)
- BLM SpA: Via Selvaregina 30, 22063 Cantù (CO), REA/CF 08112950152; fax +39 031 715911 (directory UCIMU) — [Bloomberg LEI](https://lei.bloomberg.com/leis/view/8156001B567CF963AA98), [UCIMU catalogo](https://ucimu.it/zh/catalog/companies/v/blm)
- Fiere: Tube 2026 Düsseldorf 13–17/04/2026, Pad. 5 Stand J22 (LT14 FIBER, isola LT6+E-TURN63+LT-FREE, LW-S) — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf); EuroBLECH 2026 (preview) — [BLM Euroblech 2026](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-06-29-euroblech/IT_BLM_GROUP_Euroblech_2026_preview.pdf); Lamiera (Fiera Milano) espositore — [Expoplaza Lamiera](https://expoplaza-lamiera.fieramilano.it/en/exhibitors/blm-group-2)
- Servizi: MyBLM (formazione e affiancamento on-site, monitoraggio), BLMportal, BLManalytics, assistenza remota con Active Eye (AR) — [BLM Tube 2026 PDF](https://www.blmgroup.com/hubfs/BLOG/newsroom/26-02-25-tube26/IT_BLM_GROUP_Tube%202026.pdf)
- Mercato usato: es. BLM Adige LT8 2009 in Lombardia (Concorezzo) su portali d'asta — [Machineseeker](https://www.machineseeker.fr/blm+adige-lt8/i-18883216); LT14 XL usata — [Exapro](https://www.exapro.com/blm-group-adige-lt14-xl-p260401068)

### Inferences
- Per prove con il progetto: chiedere a BLM (Cantù/Levico) trial ArTube + test di taglio su campioni; il sito ADIGE di Levico Terme è il riferimento Lasertube.

### Gaps
- Telefono centralino e indirizzo esatto ADIGE SpA Levico Terme non confermati da fonte (pagina contatti BLM in 404). "BLM Academy", licenze educational, open house: nessuna fonte trovata.
- Prezzi macchine e licenze ArTube: nessuna informazione pubblica.

## 6. Contoterzisti con Lasertube BLM in Lombardia/Valtellina

### Takeaway
Non ho trovato contoterzisti in Valtellina/Sondrio che dichiarino macchine BLM LT. Unici indizi: un'azienda conto terzi a Orsenigo (CO) che cerca operatore laser tubo (marca non indicata) e CMM (cliente BLM su LT14/24, centro servizi laser tubo di livello europeo, sede non confermata nella fonte).

### Cited Findings
- Annuncio operatore laser tubo per azienda conto terzi a Orsenigo (CO) — [Jooble](https://it.jooble.org/jdp/-9085093764670565399) (marca macchina non indicata)
- CMM citata da BLM tra i clienti LT14/LT24 ("high-precision steel structures") — [BLM LT14/LT24 applications](https://blmgroup.com/lasertube/lt14-lt24/applications); profilo che la descrive come centro servizi conto terzi laser tubo/travi/lamiera — [ReteImprese](https://www.reteimprese.it/78825)

### Inferences
- Probabile che BLM/ADIGE possano indicare clienti terzisti vicini (pratica comune), da chiedere direttamente.

### Gaps
- Elenco verificato di contoterzisti BLM in provincia di Sondrio, Lecco, Bergamo, Como: non trovato; servono ricerche mirate su directory (Kompass, ProntoPro, subfornitura) o richiesta a BLM.
