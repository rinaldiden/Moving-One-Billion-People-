# Competitor di BLM Group (ArTube) nel CAD/CAM per taglio laser tubo: generazione automatica di giunti/incastri

> Note di ricerca, 2026-11-03. Ogni affermazione ha la sua URL. Etichette: **[MKT]** = pagina marketing o comunicato stampa del vendor; **[DOC]** = documentazione tecnica, datasheet o help ufficiale; **[FORUM]** = forum o aneddoto; **[TERZI]** = rivenditore o stampa di settore che riprende il vendor.
> Limite del lavoro: circa 20 chiamate di ricerca. Diversi PDF dei vendor (flyer TRUMPF DE, brochure Almacam IT, SigmaNEST) non si sono scaricati (il server ha restituito HTML al posto del PDF). I contenuti di quei PDF quindi NON sono verificati.

## 1. Quali giunti automatici genera ciascun software, e con quali parametri (gioco, tolleranza, compensazione smusso, spessore)?

### Takeaway
Nessun competitor documenta pubblicamente una libreria di incastri tubo-tubo parametrica e ricca come il "many available interlocking joint solutions" che BLM dichiara per ArTube. Tre vendor dichiarano qualcosa di paragonabile:
- **TRUMPF Programming Tube**: "connection and positioning aids" a un clic, più tab/slot di codifica.
- **Lantek Flex3d**: "libreria di connessioni e intersezioni".
- **Radan Radtube**: libreria parametrica di fori con "duck tails, clips, key holes".

Nessuno pubblica i parametri del giunto (gioco, tolleranza, compensazione dello smusso).

### Cited Findings

**BLM ArTube (il riferimento)**
- [MKT] ArTube risolve automaticamente giunzioni e intersezioni, e i risultati si possono migliorare "inserting one of the many available interlocking joint solutions" — [DirectIndustry ArTube](https://www.directindustry.com/prod/blm-group/product-6136-465935.html)
- [MKT] La pagina ArTube corrente cita micro-giunti per lo scarico sfridi, la ricerca del cordone di saldatura e il "cut-bending" (trasforma più elementi del telaio in un pezzo unico con stessa sezione e spessore). Cita anche le "Special Parametric Sections". In questa pagina non compare un elenco dei tipi di incastro — [BLM ArTube](https://blmgroup.com/software/artube)

**TRUMPF Programming Tube / TruTops Tube**
- [MKT] Il comunicato del 2 luglio 2020 dice: "the software programs bent connections at the touch of a button. These connections replace constructions that normally consist of several individual tubes. Connection and positioning aids between the tubes can also be implemented at the touch of a button … simplify subsequent production steps, e.g. assembly or welding" — [TRUMPF PR Programming Tube (PDF)](https://www.trumpf.com/filestorage/TRUMPF_Master/Corporate/Press/Press_releases/2020_21/Machine_Tools/20200703_PR_Software_Tube/20200702-TRUMPF-PR-Programming-Tube.pdf)
- [MKT] Una storia cliente TRUMPF cita "positioning aids with locating pins and cut-outs" e "encoding tabs and slots" per montare i pezzi nella posizione giusta. Il sistema CAD 3D TRUMPF "automatically suggests numerous design aids for tubes and profiles" — [TRUMPF magazine "Entering the field…"](https://www.trumpf.com/en_INT/magazine/entering-the-field-to-being-experts-in-tube-cutting)
- [MKT] TruTops Tube è il predecessore di Programming Tube. Resta disponibile per le macchine più vecchie e per l'asse tubo delle macchine laser 2D/3D — [TRUMPF TruTops Tube](https://trumpf.com/en_GB/products/software/programming-software/trutops-tube)
- [FORUM] Su un forum Autodesk un utente indica il software tube laser TRUMPF come l'uso "più brillante" del tab & notch — [Autodesk forum "Tab and slot"](https://forums.autodesk.com/t5/fusion-design-validate-document/tab-and-slot/m-p/13983189)

**Lantek Flex3d Tubes / Steelwork**
- [MKT] Il comunicato del 7 settembre 2021 (versione V41, Global Release 2021) parla di "a comprehensive library of connections and intersections for the assembly of complete tube sets". Promette smussi completi o parziali in qualunque punto del tubo e una traiettoria su misura "for any profile" — [Lantek news 2021](https://www.lantek.com/us/news/lantek-improves-its-flex3d-software-to-resolve-variety-of-scenarios-in-manufacturing-cutting-tubes)
- [MKT] Il blog Lantek parla di "solutions in structures with a variety of joints and intersections", smussi totali o parziali e foratura di qualunque forma. Non nomina tab & slot — [Lantek blog](https://www.lantek.com/uk/blog/lantek-flex3d-is-evolving-to-resolve-a-variety-of-issues-in-the-manufacturing-and-cutting-of-tubes)
- [MKT] Le intersezioni tubolari sono calcolate in automatico, con "full control over bevel cutting, angled holes, tubular intersection cuts" — [Lantek tube & profile cutting](https://www.lantek.com/tube-and-profile-cutting-software)
- Nelle fonti trovate i "micro-joints" Lantek sono ponticelli di trattenimento contro le collisioni con la testa, NON incastri strutturali — [The Fabricator su Lantek Flex3d](https://www.thefabricator.com/tubepipejournal/product/tubepipefabrication/lantek-adds-applications-to-flex3d-software-to-address-variety-of-tube-cutting-scenarios)

**Hexagon Radan Radtube**
- [DOC] Il datasheet descrive una "library of parametric hole shapes, again with the option to define 'freeform' shapes; so specialized joint features such as duck tails, clips, and key holes are easily added". Il foro nasce come solido sottratto, che può attraversare una parete o tutte e uscire dal bordo della sezione "creating a gap". Supporta angoli singoli o composti e cinque pattern (Circle, Line at an Angle, Arc, Square, Grid) — [Radtube datasheet (PDF, edge-team)](https://edge-team.com/wp-content/uploads/2020/09/Radtube.pdf)
- [TERZI] Machinery.co.uk conferma "duck tails, clips and key holes" — [Machinery.co.uk](https://www.machinery.co.uk/content/product-launches/radan-offers-radm-ax-5-axis-and-radtube-software-programming-products)

**Alma Almacam Tube**
- [MKT] Nell'assembly (Assembly2cam) si possono "add connections as notches between parts". Le estremità complesse ricevono traiettorie automatiche. Tab & slot e incastri non sono nominati — [Almacam Tube](https://almacam.com/software/3d-cam/almacam-tube)

**SigmaNEST SigmaTUBE**
- [MKT/TERZI] Il software prepara in un clic i tagli di preparazione alla saldatura dei giunti tubo ("one-click weld preparation cuts for pipe joints"). Analizza tutto l'assembly e riconosce sezioni e feature, e permette di sopprimere feature. Gira dentro SolidWorks. Tab & slot non documentati — [SigmaTUBE](https://www.sigmanest.com/tube/sigmatube); [SolidWorks partner SigmaTUBE-SW](https://www.solidworks.com/partner-product/sigmatube-sw)

**Bystronic BySoft CAM Tube**
- [MKT] Programmazione automatica dei piani di taglio, rotazione dei pezzi attorno all'asse e tagli comuni completi o parziali. Nessun generatore di giunti documentato — [The Fabricator guide BySoft CAM](https://www.thefabricator.com/guide/cad-cam-software/5522f9fb1a9f88e838003cf8); [Bystronic news tube](https://www.bystronic.com/can/en/news/170701-bystar-fiber-tube-processing)

**Metalix MTube + cncKad**
- [MKT] MTube fa progettazione 3D di tubi complessi e passa i tubi a cncKad, con tagli comuni automatici. Incastri non menzionati — [Metalix tube processing](https://www.metalix.net/solutions/tube-processing/)

**Mazak**
- [TERZI] Esistono FX Tube (storico), FG CAD/CAM per FabriGear/Space Gear e TUBE DX (attuale, con controllo SmoothTUBE). L'opzione Space CAM può generare il codice di un'attrezzatura di bloccaggio slot-and-tab (un fixture, non un giunto fra tubi). Il nome "FabriWORKS" non risulta — [Mazak laser software](https://mazak.com/moc-en/technology/laser-software); [Mazak release TUBE DX](https://mazak.com/moc-en/news-media/news/Mazak-Optonics-Releases-New-Control-and-Software-for-Tube-Lasers); [The Fabricator FX Tube](https://www.thefabricator.com/tubepipejournal/product/tubepipefabrication/pc-based-software-system-creates-complex-pipe-shapes)

**Bodor / HSG / TubesT (Friendess, ecosistema CypCut)**
- [TERZI] Il software di nesting tubo di Bodor è BodorNest. Le uniche fonti sono rivenditori, con claim generici: "+15% utilizzo materiale" e supporto Tekla e Tribon — [Equipt listing BodorNest](https://www.equipt.com/listings/781975-new-bodor-bodornest-laser-cutters-in-oklahoma)
- Per TubesT/CypNest le uniche fonti trovate sono pagine AliExpress, non affidabili — [AliExpress wiki](https://www.aliexpress.com/s/wiki-ssr/article/tuberd)

**CAD nativo / plug-in**
- [DOC] La feature nativa SolidWorks Tab and Slot (dal 2018) vale per lamiera e weldments, in parti, multibody e assiemi — [SolidWorks help 2025 Tab and Slot](https://help.solidworks.com/2025/English/SolidWorks/Sldworks/c_tab_slot.htm); [blog SolidWorks](https://blogs.solidworks.com/products/solidworks/new-tab-slot-feature-streamlines-manufacturing-fabricated-designs/)
- [FORUM] Un utente segnala che il Tab and Slot di SolidWorks "doesn't recognize the edge of the tube" su un tubo tondo intestato o sagomato su un altro tubo — [forum SolidWorks](https://forum.solidworks.com/thread/246039)
- [TERZI] Regola empirica per il laser: gioco di 0,1–0,2 mm per lato nelle asole (riferita alla lamiera, non specifica per il tubo) — [Fictiv tabs & slots](https://www.fictiv.com/articles/sheet-metal-tabs-and-slots-assembly)

### Inferences
- Per uno studio "libreria giunti" il benchmark più concreto e documentato resta **Radtube**: è un datasheet tecnico, con concetti di foro come solido sottratto, passante su una o tutte le pareti, e forme freeform.
- **TRUMPF** sembra il più avanzato nell'automazione del montaggio (aiuti di posizionamento e codifica a un clic, giunti piegati). Però è legato alle macchine TRUMPF e documentato solo da marketing.
- I generatori nativi dei CAD (Tab&Slot SolidWorks) non sono affidabili sui tubi tondi. Per l'incastro tubo-tubo serve il CAM tubo dedicato oppure una modellazione manuale.

### Gaps
- Nessuna fonte pubblica dà i parametri (gioco, tolleranza, compensazione dello smusso, dipendenza dallo spessore) per nessun prodotto.
- Nessuna fonte conferma dovetail, puzzle, cross-lap o asole per piastre bullonate come tipi automatici in Lantek, Almacam, Bystronic, Metalix o Mazak.
- Fagor (Arrasate) e Han's: nessuna informazione trovata sul software tubo.
- Il flyer TRUMPF "Programming Tube" DE ([link](https://Www.trumpf.com/filestorage/TRUMPF_Master/Products/Software/Brochures/TRUMPF-flyer-Programming-Tube-DE.pdf)) non si è scaricato e va letto a mano.

## 2. Profili supportati (tondo, quadro, rettangolare, ovale, aperti, travi H/I/U/L) e dimensioni massime

### Takeaway
Lantek Flex3d Steelwork e Almacam Tube sono gli unici a dichiarare in modo esplicito travi strutturali e formati di carpenteria (DSTV, IFC). Le dimensioni massime dipendono dalla macchina, non dal software, e nessuna fonte le dà a livello software.

### Cited Findings
- [MKT] Lantek Flex3d Steelwork copre profili I, U, L, H, T e tubi quadri e tondi — [Lantek Flex3D Steelwork](https://www.lantek.com/uk/lantek-flex3d-steelwork)
- [MKT] Almacam Tube supporta "any section type", riconosce automaticamente la sezione all'import e si dichiara specializzato in "tubes, profiles, and beams" — [Almacam Tube](https://almacam.com/software/3d-cam/almacam-tube)
- [DOC] Radtube ha una libreria parametrica di sezioni standard più l'opzione "Freeform": si disegna la linea media o il profilo esterno/interno, ed è tutto 3D — [Radtube datasheet](https://edge-team.com/wp-content/uploads/2020/09/Radtube.pdf)
- [MKT] MTube V23/CL21: trattamento esteso dei profili L/U e travi I, definizione della cucitura per tubi tondi e rettangolari, riconoscimento automatico dei tagli planari sul tondo, "plate tubes" — [Blechexpo novità Metalix 2023](https://www.blechexpo-messe.de/en/Product-Innovations/8530-metalix-software-highlights)
- [MKT] SigmaTUBE fa nesting lineare per tubo tondo, rettangolare e "other cross sections" su macchine a 4, 5 e 6 assi — [SigmaTUBE](https://www.sigmanest.com/tube/sigmatube)
- [MKT] ArTube offre "Special Parametric Sections" (famiglie di profili speciali, per esempio serramenti) — [BLM ArTube](https://blmgroup.com/software/artube)
- [MKT] Lantek: traiettoria personalizzata "for any profile" — [Lantek news 2021](https://www.lantek.com/us/news/lantek-improves-its-flex3d-software-to-resolve-variety-of-scenarios-in-manufacturing-cutting-tubes)

### Inferences
- Per strutture miste (tubi più travi H/I/U/L) i candidati naturali sono Lantek Flex3d Steelwork e Almacam Tube, perché leggono DSTV e IFC e trattano le travi.

### Gaps
- Le dimensioni massime vanno cercate nelle schede macchina (TruLaser Tube, LT BLM, ByTube, FT-150), non nel software.
- Profili ovali: nessuna conferma esplicita, se non tramite le sezioni freeform o "any section".

## 3. Formati di import/export (STEP, IGES, SAT, DSTV/NC1, IFC) e interoperabilità con Tekla / Advance Steel

### Takeaway
Leggono tutti STEP/IGES. **IFC più DSTV** sono dichiarati da Almacam e BLM ArTube (solo IFC). **DSTV** è dichiarato da Lantek (più SAT). La catena Tekla → DSTV ha limiti documentati proprio su tubi e asole.

### Cited Findings
- [MKT] Almacam Tube importa Parasolid, STEP, IGES, SAT/ACIS, CATIA V4/V5, Creo, Inventor, Solid Edge, SOLIDWORKS, IFC e DSTV — [Almacam Tube](https://almacam.com/software/3d-cam/almacam-tube)
- [MKT] Lantek importa "DSTV, SAT and CAM files" dai CAD di carpenteria e li converte nel formato nativo. Il marketing elenca anche Tekla — [Lantek Flex3D Steelwork](https://www.lantek.com/uk/lantek-flex3d-steelwork)
- [DOC] Radtube di serie legge DXF, DWG, Inventor, VISI, SolidWorks, SolidEdge, IronCad e IGES. STEP, CATIA, UG, Pro/E e VDA sono **opzionali** secondo il datasheet storico. Le pagine Hexagon attuali invece dicono STEP integrato: c'è conflitto, da verificare sulla licenza — [Radtube datasheet](https://edge-team.com/wp-content/uploads/2020/09/Radtube.pdf); [Hexagon Radtube](https://hexagon.com/products/radan-radtube)
- [MKT] MTube importa i formati nativi SOLIDWORKS, Solid Edge, CATIA, Creo e Inventor senza bisogno del CAD; ha anche un modulo "3D export" — [Metalix tube processing](https://www.metalix.net/solutions/tube-processing/); [MTube 3D export](https://www.metalix.net/products/mtube/3d-export/)
- [TERZI] Mazak FX Tube legge DXF, IGES, DWG, 3D-IGES e STEP — [The Fabricator FX Tube](https://www.thefabricator.com/tubepipejournal/product/tubepipefabrication/pc-based-software-system-creates-complex-pipe-shapes)
- [MKT] TRUMPF Programming Tube "supports files in all common formats", con import e costruzione di assiemi completi — [TRUMPF PR](https://www.trumpf.com/filestorage/TRUMPF_Master/Corporate/Press/Press_releases/2020_21/Machine_Tools/20200703_PR_Software_Tube/20200702-TRUMPF-PR-Programming-Tube.pdf)
- [MKT] BLM ArTube: "Import IFC files of your structural design", export 3D, Automator a cartelle drag&drop, plug-in SolidWorks — [BLM ArTube](https://blmgroup.com/software/artube)
- [DOC] Tekla: lo standard DSTV non supporta le travi curve, quindi niente NC; si usano polybeam — [Tekla support](https://support.tekla.com/doc/tekla-structures/2024/conn_23_help)
- [DOC] Tekla: il componente Tube-Slotted Hole non funziona sui profili tondi, e i fori bullone sui tubi possono non arrivare all'NC tubo (XML) — [Tekla conn 1 tube slotted hole](https://support.tekla.com/doc/tekla-structures/2023/conn_1_help_tube_slotted_hole); [How to export holes in tubes to XML](https://support.tekla.com/article/how-to-export-holes-in-tubes-to-xml)
- [DOC] Tekla 2026 ha l'opzione avanzata XS_DSTV_CREATE_NOTCH_ONLY_ON_BEAM_CORNERS per gestire le tacche nel DSTV — [Tekla 2026](https://support.tekla.com/doc/tekla-structures/2026/xs_dstv_create_notch_only_on_beam_corners)
- [TERZI] Construsoft descrive le best practice per modellare tubi e connessioni in Tekla per le macchine HGG (export diretto dei dati di connessione al taglio) — [Construsoft blog HGG](https://nordics.construsoft.com/blog/best-practices-for-modeling-tubes-and-beam-connections-in-tekla-for-fabrication-with-hgg-machines)

### Inferences
- Per gli incastri, la via robusta da Tekla/Advance Steel è probabilmente **IFC o STEP del solido** verso il CAM tubo (ArTube, Almacam), non DSTV. DSTV descrive bene fori e tacche su travi, ma ha limiti noti su tubi tondi, asole e curve.

### Gaps
- Nessuna fonte dice se tab e asole sopravvivono come geometria nell'export IFC di Tekla.
- Advance Steel: non ricercato per mancanza di budget di chiamate.

## 4. Demo/trial, licenze educational, rivenditori e contatti in Italia

### Takeaway
L'unico trial pubblico esplicito trovato è proprio quello di BLM ArTube (30 giorni). Almacam offre una demo su richiesta. Per gli altri non ho trovato informazioni pubbliche verificabili.

### Cited Findings
- [MKT] ArTube: "30-day free trial" e BLM Academy con corsi base e avanzati — [BLM ArTube](https://blmgroup.com/software/artube)
- [MKT] Almacam Tube: niente trial (il trial gratuito riguarda il nesting 2D), "Plan a demo"; licenza perpetua on-premise o abbonamento "Almacam Pass". Esiste un sito italiano it.almacam.com con brochure IT — [Almacam Tube](https://almacam.com/software/3d-cam/almacam-tube); [brochure IT](https://it.almacam.com/wp-content/uploads/2020/07/Almacam-tube_it_web.pdf)
- [TERZI] TRUMPF ha organizzato seminari gratuiti di programmazione TruTops (nel Regno Unito) — [Machinery.co.uk](https://www.machinery.co.uk/content/events/free-trumpf-trutops-programming-seminars)
- [TERZI] SigmaTEK: contatto USA 513-674-0005; nel Regno Unito il rivenditore è Solid Solutions — [SolidSolutions SigmaNEST](https://solidsolutions.co.uk/sigmanest)
- ATTENZIONE: circolano copie pirata ("StableWAREZ") di Lantek Flex3d Steelwork, Tubes, 5x e CAD Addins. Da NON usare; è citata solo perché conferma i nomi dei moduli — [risultato di ricerca](https://stablewarez.com/shop/lantek-flex3d-steelwork-tubes-5x-cad-addins-unfolding/)

### Gaps
- Contatti italiani verificati (Lantek Italia, Hexagon Italia, TRUMPF Italia, Bystronic Italia, Metalix Italia): non cercati per mancanza di budget.
- Licenze educational: nessuna fonte trovata per nessun vendor.

## 5. Apertura: API, macro, scripting

### Takeaway
Le API sono poco documentate in pubblico. Gli indizi trovati sono questi:
- Metalix ha una voce di menu "Parametric Programming / API / ERP Integration".
- Radtube permette di configurare postprocessori e macchine su misura.
- ArTube e SigmaTUBE espongono le librerie di calcolo dentro SolidWorks.

### Cited Findings
- [MKT] Metalix: nel sito c'è la sezione "Parametric Programming / API / ERP Integration", senza dettagli nella pagina tubo — [Metalix tube processing](https://www.metalix.net/solutions/tube-processing/)
- [DOC] Radtube ha una "Machine Setup utility" per macchine e post su misura, configurabili per teste e tavole diverse — [Radtube datasheet](https://edge-team.com/wp-content/uploads/2020/09/Radtube.pdf)
- [MKT] Il plug-in SolidWorks di ArTube chiama le librerie di calcolo ArTube; l'Automator lavora a cartelle — [BLM ArTube](https://blmgroup.com/software/artube)
- [MKT] SigmaTUBE-SW lavora dentro SolidWorks (e quindi, in teoria, con l'API SolidWorks) — [SolidWorks partner SigmaTUBE-SW](https://www.solidworks.com/partner-product/sigmatube-sw)
- [TERZI] Lantek ha "Flex3d Addins" per i CAD — [Scribd Lantek Flex3d Addins](https://www.scribd.com/document/97174764/Lantek-Flex3d-Addins-1p-EN-UK)

### Gaps
- Nessuna documentazione SDK pubblica trovata per Lantek, TRUMPF, Bystronic, Almacam o BLM.

## 6. Quale è meglio documentato per studiare una "libreria di giunti"?

### Takeaway
1. **Radan Radtube**: è l'unico con un datasheet tecnico che spiega il meccanismo del giunto (forme parametriche, foro come solido sottratto, passante su una o tutte le pareti, freeform, pattern).
2. **TRUMPF Programming Tube**: concetto di montaggio più evoluto (aiuti di posizionamento, tab di codifica, giunti piegati), ma solo marketing.
3. **Lantek Flex3d**: "libreria di connessioni e intersezioni", solo marketing.

BLM ArTube resta il riferimento dichiarato ("many available interlocking joint solutions"), ma anche lì senza un catalogo pubblico.

### Cited Findings
- [DOC] Radtube, libreria di fori parametrici per i giunti — [Radtube datasheet](https://edge-team.com/wp-content/uploads/2020/09/Radtube.pdf)
- [MKT] TRUMPF, aiuti di connessione e posizionamento a un clic — [TRUMPF PR](https://www.trumpf.com/filestorage/TRUMPF_Master/Corporate/Press/Press_releases/2020_21/Machine_Tools/20200703_PR_Software_Tube/20200702-TRUMPF-PR-Programming-Tube.pdf); [TRUMPF magazine](https://www.trumpf.com/en_INT/magazine/entering-the-field-to-being-experts-in-tube-cutting)
- [MKT] Lantek, libreria di connessioni — [Lantek news 2021](https://www.lantek.com/us/news/lantek-improves-its-flex3d-software-to-resolve-variety-of-scenarios-in-manufacturing-cutting-tubes)
- [MKT] BLM ArTube, incastri multipli — [DirectIndustry ArTube](https://www.directindustry.com/prod/blm-group/product-6136-465935.html)

### Inferences
- Con budget e tempo limitati, il modo più efficace per studiare sul serio una libreria di giunti è il **trial ArTube di 30 giorni** (l'unico pubblico), da affiancare al datasheet Radtube come schema concettuale.
- In seconda battuta conviene chiedere una demo a TRUMPF (Programming Tube) e a Lantek per vedere a video i tipi di giunto.
- Video YouTube e forum (Practical Machinist, Eng-Tips, Reddit) non sono stati esplorati: è la prossima mossa per vedere i giunti all'opera.

### Gaps
- Nessun catalogo pubblico dei giunti (con nomi, immagini e parametri) è stato trovato per nessun vendor, BLM compresa.
- "TubeCAD" nei risultati è di Advanced Tubular (VTube), un prodotto per la **piegatura** tubo, non per gli incastri laser — [Advanced Tubular VTube→TubeCAD](https://advancedtubular.helpsite.com/articles/127051-how-to-transfer-data-from-vtube-step-to-tubecad). "Tube Designer" non verificato.
