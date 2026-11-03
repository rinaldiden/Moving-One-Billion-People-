# Software tubo-laser: tecnologia interna (kernel/librerie) e equivalenti open-source su GitHub per un nostro generatore di giunti

> Note di ricerca, 2026-11-03. Fonti verificate con WebSearch/WebFetch. Dove una cifra/licenza non è stata verificata in questa sessione è marcato "(da verificare)". Le stelle/ultimo commit dei repo NON sono stati misurati salvo dove indicato.

## 1. Su quale kernel geometrico / librerie sono costruiti i CAD/CAM tubo-laser commerciali?

### Takeaway
L'unica evidenza diretta trovata riguarda BLM ArTube, che è elencato come prodotto basato su **Parasolid** (Siemens). Per Lantek, Radan Radtube, Trumpf Programming Tube, Almacam Tube, SigmaTUBE, Metalix MTube e Friendess TubesT nessuna fonte pubblica dichiara il kernel: le pagine prodotto elencano solo i formati importati (Parasolid, STEP, IGES, SAT/ACIS, IFC, DSTV), che indicano librerie di import/traduzione ma non il kernel interno.

### Cited Findings
- **BLM ArTube → Parasolid.** La tabella "which geometric modeling kernel" di TransMagic riporta la riga "Artube – Tubular Design – Parasolid" e la elenca sotto Parasolid. È una compilazione di terzi e potrebbe essere datata — [TransMagic](https://transmagic.com/which-geometric-modeling-kernel/)
- Pagina prodotto ArTube (BLM) — [BLM Group ArTube](https://www.blmgroup.com/en-us/software/artube)
- Parasolid è strettamente integrato con i prodotti Tech Soft 3D, HOOPS Exchange compreso (quindi la coppia "Parasolid + HOOPS Exchange per l'import" è un pattern di settore plausibile), ma nessuna fonte collega ArTube a HOOPS — [Tech Soft 3D Parasolid](https://techsoft3d.com/products/parasolid)
- **Lantek Flex3D Tubes:** "si integra con vari importatori di geometria tubolare come SAT e IGES". SAT è il formato nativo ACIS, il che suggerisce compatibilità ACIS ma non conferma il kernel — [Lantek Flex3D Tubes](https://www.lantek.com/us/lantek-flex3d-tubes); [Lantek (pagina vecchia)](https://www.lanteksms.com/world/lantek_flex3d_tubes.asp)
- **Almacam Tube:** importa formati neutri (Parasolid, STEP, IGES, SAT/ACIS), nativi (CATIA, Creo, Inventor, Solid Edge, SOLIDWORKS, Unigraphics) e "strutturali: IFC, DSTV". Riconosce automaticamente "fori, asole, smussi" dal modello CAD, tiene conto dello smusso (bevel), nidifica pezzi diversi sulla stessa barra se materiale e sezione sono compatibili, e registra le rimanenze di barra come sfridi riutilizzabili. Kernel non dichiarato — [Almacam Tube FAQ](https://almacam.com/?p=51257); [Almacam Tube](https://almacam.com/software/3d-cam/almacam-tube); [brochure PDF](https://almacam.com/wp-content/uploads/2020/07/Almacam-tube_en_web.pdf)
- **Metalix MTube:** importa tubi e assiemi di tubi in tutti i formati nativi (SOLIDWORKS, Solid Edge, CATIA, Creo, Inventor) senza bisogno di altro software CAD. Fa parte del flusso cncKad/AutoNest. Kernel non dichiarato (l'import multi-formato nativo è tipico di librerie tipo HOOPS Exchange/CAD Exchanger, ma non è confermato) — [Metalix tube processing](https://www.metalix.net/solutions/tube-processing/)
- **TRUMPF:** TruTops Tube è il predecessore di Programming Tube e resta disponibile per le macchine più vecchie. Nessuna fonte dice che sia basato su SolidWorks. L'unico prodotto TRUMPF dichiarato "stesso kernel, stessa interfaccia" di SolidWorks è TopsWorks (lamiera, non tubo) — [TRUMPF TruTops Tube](https://trumpf.com/en_GB/products/software/programming-software/trutops-tube); [TRUMPF Programming Tube](https://www.trumpf.com/en_GB/products/software/programming-software/programming-tube/); [comunicato stampa 2020](https://www.trumpf.com/filestorage/TRUMPF_Master/Corporate/Press/Press_releases/2020_21/Machine_Tools/20200703_PR_Software_Tube/20200702-TRUMPF-PR-Programming-Tube.pdf); [industrial-production.de su TopsWorks](https://www.industrial-production.de/additive-fertigung/gut-im-blech.htm)
- **SigmaTUBE / SigmaNEST:** esiste SigmaTubeSW, integrato in SolidWorks (Solution Partner), quindi gira come add-in dentro l'API SolidWorks. Il kernel del SigmaNEST standalone non è dichiarato — [sigmaTEK SigmaTubeSW PDF](https://dev.solidsolutions.co.uk/Uploaded/Documents/Partner%20Products/SigmaTEK/sigmaTEK_SigmaTubeSW.pdf); [SigmaNEST Tube Cutting PDF](https://www.solidsolutions.co.uk/Uploaded/Documents/Partner%20Products/SigmaNEST/SigmaNEST-Tube-Cutting.pdf); [SigmaNEST tube](https://www.sigmanest.com/en/supported-machine-types/tube)
- Panorama dei kernel: il mercato è dominato da Parasolid (Siemens) e ACIS (Spatial, di Dassault dal 2000). Open CASCADE è il kernel B-rep open source — [Wikipedia: Geometric modeling kernel](https://en.wikipedia.org/wiki/Geometric_modeling_kernel); [Wikipedia: Spatial Corp](https://en.wikipedia.org/wiki/Spatial_Corp)
- Una ricerca mirata non ha trovato **nessun CAM tubo-laser commerciale dichiaratamente basato su OCCT**. OCCT è pensato per CAD/CAM/CAE, offre un "CAM Library Component" (approssimazione di curve 2D in archi e segmenti, sezioni piane e offset) ed è LGPL 2.1 con eccezione, con licenza commerciale disponibile — [OCCT components](https://dev.opencascade.org/resources/components); [OCCT project overview](https://dev.opencascade.org/about/project_overview); [OCCT GitHub](https://github.com/Open-Cascade-SAS/OCCT)

### Inferences
- Il pattern dei commerciali europei sembra essere: kernel commerciale (Parasolid o ACIS), libreria di traduzione per i formati nativi, poi moduli propri di riconoscimento delle feature del tubo, nesting su barra e post-processor per macchina. Il vero "know-how" (riconoscimento della sezione, tecnologia di taglio, compensazione, post-processor) è proprietario e non viene dal kernel.
- Per noi un kernel B-rep open source (OCCT, tramite pythonOCC/CadQuery/build123d) copre tutto ciò che serve al **generatore di giunti**: booleane tubo-tubo, sezioni, sviluppo del cilindro, offset. Non serve un kernel commerciale.

### Gaps
- Nessuna third-party notice, EULA o offerta di lavoro trovata che dichiari il kernel di Lantek, Radan Radtube (Hexagon), Programming Tube, Almacam, MTube o TubesT. Prossimo passo: aprire la cartella di installazione (DLL tipo `pskernel.dll`/`SPA*.dll`/`TKernel.dll`/`A3DLIB*.dll`) e leggere i file "third party notices". È lecito sul software di cui si ha licenza e serve all'interoperabilità.
- Le liste clienti di Spatial e Tech Soft 3D non sono state scorse sistematicamente: le case study viste (Xeometric, Lubansoft, Mitutoyo, NIS) non citano vendor tubo — [Spatial case study Xeometric](https://www.spatial.com/case-studies/xeometric)

## 2. Friendess (BOCHU) TubesT / CypTube / TubePro: cosa fanno, funzioni di giunto, gratis con la macchina?

### Takeaway
TubesT è il software BOCHU di nesting 3D per tubi abbinato ai controller CypTube/TubePro (famiglia FSCUT). Il sito ufficiale elenca disegno e modifica del pezzo, compensazione, nesting strategico, taglio a filo comune e report. Lo smusso (bevel) è dichiarato per controller e testa con asse B. Funzioni esplicite di "giunto" (tab/slot, incastri) e la licenza (gratuita o meno con la macchina) non risultano da fonti ufficiali.

### Cited Findings
- fscut.com reindirizza a bochu.com (Friendess = Shanghai BOCHU) — [bochu.com](https://www.bochu.com/en/)
- **TubesT** è descritto come "software di nesting 3D per tubi per i sistemi di taglio laser CypTube/TubePro". Funzioni: disegno e modifica del pezzo, compensazione di tutti i tipi, nesting strategico, generazione di report — [BOCHU TubesT](https://www.bochu.com/en/soft/tubest/)
- Controller tubo: FSCUT5000A (3 e 4 mandrini, coda zero, bevel su travi H/U/L), FSCUT5000B/BH (2 mandrini EtherCAT, taglio a filo comune con TubesT), FSCUT3000DE, FSCUT3000S (tubi tondi, quadri, ovali, ellittici, profili L/U). Le teste combinate con l'asse B fanno bevel su vari tubi — [FSCUT5000A](https://www.bochu.com/pro_en/heavy-tube-cutting-controller-fscut5000a/); [FSCUT5000B](https://www.bochu.com/pro_en/2-chuck-regular-tube-cutting-controller-fscut5000b/); [FSCUT3000S](https://www.bochu.com/pro_en/2-chuck-regular-tube-cutting-controller-fscut3000s/); [heavy tube cutting](https://www.bochu.com/pro_en_mix/heavy-tube-cutting/)
- RayBox (Industria 4.0) trasferisce e archivia i disegni e si collega a CypCut, CypNest, HypCut, TubePro e MES — [BOCHU RayBox](https://www.bochu.com/en/soft/raybox/)
- CypNest (nesting lamiera di Friendess) è recensito su G2. Fonti terze lo descrivono come software per CypCut/HypCut — [G2 CypNest](https://www.g2.com/products/cypnest/reviews)
- Attenzione: in rete circolano pagine "crack"/"free download" (FileCR, accio "cypnest-crack") con contenuti incoerenti. Non sono affidabili né lecite — [FileCR (inaffidabile)](https://filecr.com/windows/shanghai-bochu-tubepro)

### Inferences
- Visto che TubesT è legato ai controller BOCHU, molto diffusi sui laser tubo cinesi, è probabile che arrivi in dotazione con la macchina. Non è confermato: chiedere al rivenditore della macchina o a [BOCHU contatti](https://www.bochu.com/contactus_en).
- Per il nostro generatore la cosa che conta è il **formato di ingresso** accettato da TubesT (tipicamente STEP/IGES/SAT del pezzo 3D). Se generiamo il tubo con giunto già tagliato come solido STEP, TubesT/CypTube fa il resto (riconoscimento, nesting, bevel). Il nostro lavoro si riduce quindi a "geometria giusta + STEP pulito".

### Gaps
- Nessuna documentazione ufficiale (manuale TubesT) trovata online su funzioni di intersezione/giunto, libreria di incastri o licenza. Servirebbe il manuale dal rivenditore o dall'installazione.

## 3. Progetti open-source / GitHub da riusare per ogni funzione

### Takeaway
Ogni blocco della catena ha un equivalente open source: OCCT/pythonOCC/CadQuery/build123d per riconoscimento, intersezione e sviluppo; FrameForge (FreeCAD) per i giunti a cartella e i tagli a misura; dstvparser per DSTV; IfcOpenShell per IFC; emadehsan/csp per il nesting 1D su barra; RotatoCAM e gli script di "wrapping" per il G-code con asse rotativo. Non esiste invece una "libreria di giunti per tubo-laser" open (tab/slot, coda di rondine) matura: quello è il pezzo da scrivere noi.

### Cited Findings
**Kernel e modellazione (riconoscimento del tubo da STEP, intersezione/fish-mouth, sviluppo)**
- **OCCT** (C++, LGPL 2.1 con eccezione + licenza commerciale opzionale) — [GitHub Open-Cascade-SAS/OCCT](https://github.com/Open-Cascade-SAS/OCCT); [overview](https://dev.opencascade.org/about/project_overview)
- FreeCAD, IfcOpenShell e Topologic si basano su Open CASCADE — [OSArch wiki](https://wiki.osarch.org/open-cascade/)
- pythonOCC-core (binding Python di OCCT) — [GitHub tpaviot/pythonocc-core](https://github.com/tpaviot/pythonocc-core) (licenza LGPL-3.0, stelle e attività da verificare)
- CadQuery — [GitHub CadQuery/cadquery](https://github.com/CadQuery/cadquery) (Apache-2.0, da verificare)
- build123d — [GitHub gumyr/build123d](https://github.com/gumyr/build123d) (Apache-2.0, da verificare)

**Giunti / tagli su profili**
- **FrameForge** (FreeCAD): workbench per travi e telai con taglio, giunti a cartella (miter), trim, offset ed export della distinta con angoli di taglio, lunghezze e materiale. Richiede FreeCAD ≥ 0.21 e si installa da Addon Manager. Il README dice GPLv3, mentre la lista addon FreeCAD dice LGPL-3.0-only (v0.1.7, 2026-01-16): conflitto da verificare nel file LICENSE — [GitHub zerr0/frameforge](https://github.com/zerr0/frameforge); [FreeCAD wiki FrameForge](https://wiki.freecad.org/FrameForge_Workbench); [FreeCAD addons](https://www.freecad.org/addons.php?lang=eng)
- Fork FrameForge_Mod per profili in alluminio: "End Miter" su due facce adiacenti, con calcolo automatico dell'angolo e del gioco. README in parte in cinese — [GitHub q921057310-byte/FrameForge_Mod](https://github.com/q921057310-byte/FrameForge_Mod)
- Generatori di dime di coping (fish-mouth): la ricerca ha trovato soprattutto pagine generiche o di qualità dubbia, che citano un generatore OpenSCAD senza link al repo. Nessun repo GitHub verificato — [esempio pagina dima](https://cmd.hexagon.com/en/tube-notching-template.html) (dominio sospetto, non usare come fonte tecnica)

**Import strutturale**
- **dstvparser** (Python ≥ 3.9, pip): legge .nc e .nc1, estrae header del profilo e geometria, rileva i tagli inclinati. Alcune feature NC1 sono incomplete per mancanza di file di esempio — [PyPI dstvparser](https://pypi.org/project/dstvparser/) → repo [github.com/serg-you-lin/dstvparser](https://github.com/serg-you-lin/dstvparser)
- Crate Rust `dstv` per DSTV — [docs.rs dstv](https://docs.rs/crate/dstv/latest/source/)
- IfcOpenShell (IFC, basato su OCCT) — [OSArch wiki](https://wiki.osarch.org/open-cascade/); repo [github.com/IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) (LGPL-3.0, da verificare)

**Nesting lungo barra (cutting stock 1D)**
- **emadehsan/csp**: tool Python su Google OR-Tools, `stock_cutter_1d.py`. Lavora solo con interi (i decimali vanno scalati). Codice derivato dal libro di Serge Kruk *Practical Python AI Projects* — [GitHub emadehsan/csp](https://www.github.com/emadehsan/csp); fork [TheDammedSon/csp](https://github.com/TheDammedSon/csp)
- Il topic GitHub "cutting-stock-problem" include implementazioni column generation con OR-Tools, adatte a istanze più grandi — [GitHub topic cutting-stock-problem](https://github.com/topics/cutting-stock-problem)

**Toolpath / G-code con asse rotativo**
- **RotatoCAM**: CAM rotativo 4 assi gratuito che da STL/STEP genera G-code con rotazione simultanea per grblHAL, GRBL, FluidNC, LinuxCNC, Mach3/4. Gestisce anche il taglio 2D laser/plasma. Esiste una versione Pro a pagamento; quella open è "as-is" — [GitHub revjmoney/RotatoCAM](https://github.com/revjmoney/RotatoCAM)
- LaserWeb3: issue aperta sul supporto rotativo (Y convertita in gradi per l'asse A) — [LaserWeb3 issue #51](https://github.com/LaserWeb/LaserWeb3/issues/51)
- "Wrapping" del G-code 2D su un diametro: Scorchworks gcode-ripper e lo script axes_swapper (solo movimenti lineari). Sostituire X con A non funziona sugli archi, solo sulle rette — [forum V1E](https://forum.v1e.com/t/rotary-axis-gcode-generation/37475); [LinuxCNC forum](https://forum.linuxcnc.org/20-g-code/31434-convert-x-axis-to-a-axis); [cncarena wrapper script](https://en.cncarena.com/forum/thread/266574-rotary-axis-wrapper-script/)

### Inferences
- **Architettura consigliata per il nostro generatore di giunti** (tutto open, licenze permissive o LGPL):
  1. Modello parametrico del giunto in build123d/CadQuery (OCCT sotto): tubo A ∩ tubo B → booleana, che produce il fish-mouth esatto. Tab/slot, sottosquadri e code di rondine sono solidi di taglio parametrici sottratti al tubo.
  2. Sviluppo 2D: per il tubo tondo si mappa ogni punto della curva di taglio come (s = R·θ, z). Per il tubo quadro/rettangolare lo sviluppo è per facce. Le sezioni si ottengono con OCCT (BRepAlgoAPI_Section) e lo sviluppo si fa con codice nostro di qualche centinaio di righe. Lo sviluppo diventa anche la dima di carta per i prototipi.
  3. Output primario: **STEP del tubo già tagliato**, da far mangiare a TubesT/CypTube, Lantek o Almacam. Così non scriviamo un post-processor macchina.
  4. Nesting su barra: csp/OR-Tools per la distinta di taglio.
  5. Opzionale: G-code 4 assi stile RotatoCAM solo per una macchina nostra/DIY.
  6. Import di strutture esistenti: dstvparser (DSTV) + IfcOpenShell (IFC).
- Attenzione alle licenze: FrameForge è GPL/LGPL (conflitto). Se lo forkiamo e distribuiamo, il codice derivato eredita il copyleft. Usarlo come riferimento di algoritmo, riscrivendo, evita il problema. OCCT LGPL 2.1 con eccezione permette il linking in software chiuso.
- Il "Fusion360-Weldments"/NeoTech già noto copre l'ambiente Fusion. Per la pipeline automatica (REGOLA "un modello parametrico → tutto") build123d è più adatto perché è headless e scriptabile.

### Gaps
- Stelle e ultimo commit dei repo non misurati in questa sessione (servono `gh api repos/<owner>/<repo>` o la pagina GitHub).
- Non trovati: un DSTV parser JS maturo, una "joint library" open specifica per tubo-laser (tab/slot/coda di rondine), un workbench FreeCAD "MetalWB" verificato, plug-in Grasshopper/Blender per il coping (non cercati per limite di chiamate), configurazioni LinuxCNC specifiche per laser tubo, supporto rotativo nella CAM di FreeCAD (Path/CAM).
- Nessun esempio open trovato di bevel 5 assi su tubo (compensazione dell'inclinazione della testa con asse B).

## 4. REA (github.com/morluto/rea): cos'è, uso per lo studio di interoperabilità, limiti legali UE

### Takeaway
REA ("Reverse Engineer Anything") è un server MCP e CLI open source (MIT) che permette ad agenti AI (Claude Code, Codex, Cursor) di analizzare binari e app pilotando Ghidra/IDA/Hopper. Per noi può servire **solo** a studiare i formati di scambio (cosa accetta TubesT/CypTube, la struttura dei file di progetto) sul software di cui abbiamo licenza, entro l'art. 6 della Direttiva 2009/24/CE. Non può servire a copiare algoritmi o ad aggirare licenze.

### Cited Findings
- Si descrive come "Reverse engineer anything with agents, from app behavior down to native binaries". Funziona come server MCP e come CLI. Dai binari nativi estrae pseudocodice, assembly, stringhe, simboli e riferimenti usando un Hopper/Ghidra/IDA/Kuna già installato. Analizza JS/Electron, .NET, APK, siti, comportamento dei processi e molti formati di file (PE/ELF, WebAssembly, SQLite, pcap, …). Licenza MIT per il codice proprio; circa 426k stelle e 6.385 commit su main al momento del fetch. Il disclaimer lo limita a "ricerca lecita, educazione, interoperabilità, preservazione, software che possiedi o sei autorizzato a esaminare" e precisa che non fornisce licenze di IDA/Hopper/JEB e non autorizza crack — [GitHub morluto/rea](https://github.com/morluto/rea)
- Repo creato il 14/04/2026. Le stelle riportate dagli articoli sono incoerenti tra loro. Si installa da npm `rea-agents`. Il README avverte di scaricarlo solo da GitHub, rea.tools o npm, perché esistono repo imitazione — [aitoolly](https://aitoolly.com/de/ai-news/article/2026-10-15-rea-emerges-on-github-trending-to-enable-ai-agents-to-reverse-engineer-software-and-native-binaries); [ossinsight](https://ossinsight.io/analyze/morluto/rea); [pasqualepillitteri.it](https://pasqualepillitteri.it/fr/news/23846/rea-reverse-engineer-anything-github-vrai-faux)

### Inferences
- **Limiti della Direttiva 2009/24/CE** (testo da citare: [EUR-Lex 32009L0024](https://eur-lex.europa.eu/eli/dir/2009/24/oj); in Italia recepita negli artt. 64-bis/64-quater L. 633/1941). Il riepilogo che segue viene dalle mie conoscenze e va verificato sul testo:
  - Art. 5(3): chi ha una licenza può osservare, studiare e testare il funzionamento del programma per capirne idee e principi, senza decompilare.
  - Art. 6: la decompilazione è ammessa solo se (a) la fa un licenziatario, (b) le informazioni per l'interoperabilità non sono già disponibili, (c) si limita alle parti necessarie all'interoperabilità con un programma creato in modo indipendente. Le informazioni non si possono usare per altri scopi, né cedere a terzi, né usare per sviluppare un programma sostanzialmente simile nella sua espressione.
  - Una clausola EULA contraria all'art. 6 è nulla (art. 8).
- In pratica: lecito usare REA sulla **nostra** copia licenziata di TubesT/Lantek per capire il formato di import/export e le DLL di terze parti (per esempio quale kernel caricano, da nomi e notice); per i formati di file, meglio prima l'osservazione black-box (art. 5(3)). Non lecito estrarre gli algoritmi di riconoscimento/nesting per replicarli, né toccare la protezione delle licenze (dongle/attivazione).
- Il metodo più semplice e pulito per la domanda "quale kernel usano" non richiede RE: basta leggere i nomi delle DLL e i file third-party-notices nella cartella di installazione.

### Gaps
- Non ho letto DISCLAIMER.md né l'elenco dei componenti di terze parti di REA. Né l'art. 6 né la Direttiva sono stati recuperati e verificati in questa sessione: il riassunto giuridico sopra va confermato sul testo EUR-Lex (e, per l'uso concreto, con un legale).
