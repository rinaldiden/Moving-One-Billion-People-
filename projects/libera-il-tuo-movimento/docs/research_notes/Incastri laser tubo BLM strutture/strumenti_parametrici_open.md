# Strumenti parametrici open/DIY per incastri laser su tubo (alternativa/affianco a BLM ArTube)

> Ricerca del 2026-11-03. Ogni affermazione ha la sua fonte. Dove non ho trovato fonti affidabili, lo scrivo nei Gap.

## 1. Add-in, script e workbench CAD per coping (bocca di lupo), tab&slot e incastri su tubo

### Takeaway
Su Fusion 360 esistono oggi due strade concrete: l'add-in open source **NeoTech/Fusion360-Weldments** (MIT, Python, cope a T tramite combine-cut contro il corpo vicino) e l'add-in commerciale **Steel Frame & Weldments Pro** (12 $/mese, che ha già Notch, cope, Tab/Slot, V-Notch & Fold ed export STEP del tubo). Su FreeCAD c'è **FrameForge** (derivato da MetalWB) per telai con taglio a 45° (mitre), trim e distinta di taglio. Non ho trovato un generatore open e maturo, pensato apposta per gli incastri tab&slot "da tube laser". Il nucleo della nostra pipeline (cope più incastri parametrici) va quindi scritto noi sopra l'API di Fusion, prendendo NeoTech come base o riferimento.

### Cited Findings
**Fusion 360**
- Fusion non ha uno strumento weldment nativo. Le risposte Autodesk e della community rimandano ad add-in di terze parti — [Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-there-a-way-to-use-structural-weldments-to-design-in-Fusion.html); [Autodesk forum "Weldment package"](https://forums.autodesk.com/t5/fusion-design-validate-document/weldment-package-for-fusion-360/td-p/11325377); thread storico [Tube notching feature](https://forums.autodesk.com/t5/fusion-design-validate-document/tube-notching-feature/td-p/7094984)
- **NeoTech/Fusion360-Weldments**: add-in Python per Fusion. Fa lo sweep di un profilo lungo linee di sketch 3D. Per ogni estremo si sceglie il trattamento d'angolo: None / Butt / Miter / **Cope** / Bend. Include distinta, fazzoletti (gusset) e tabella di piega per curvatura a trafila rotante — [GitHub NeoTech/Fusion360-Weldments](https://github.com/NeoTech/Fusion360-Weldments)
- Come calcola il cope: alla giunzione a T fa un combine-cut dell'estremo contro il corpo del tubo vicino, con un parametro di "cope depth" per aumentare la penetrazione. Su un angolo a vertice condiviso ripiega su un taglio dritto (butt). Le geometrie stanno in moduli puri, solo standard library più API Fusion, con 387 unit test su CPython 3.11+. Licenza MIT (Andreas Pettersson), 88 commit, copyright 2026, ma solo 3 stelle e nessuna release: progetto giovane — [GitHub NeoTech/Fusion360-Weldments](https://github.com/NeoTech/Fusion360-Weldments)
- **Steel Frame & Weldments Pro** (editore VanThanBK, **12,00 $/mese**) offre:
  - estremi a mitre, butt e coped, con override per singolo angolo, più i comandi Notch, Miter e Trim/Extend;
  - giunti **Tab/Slot** e **Plate Tab/Slot**;
  - **V-Notch & Fold**: trasforma più membri in un solo tubo intagliato e piegato, con parametri raggio di piega, K-factor, weld gap e tab size;
  - cutting list PDF/CSV con angoli di taglio, Stock Optimizer, export dei tubi in **STEP** e delle piastre in DXF.
  - Versione e data non indicate sulla pagina — [Autodesk Marketplace – Steel Frame & Weldments Pro](https://marketplace.autodesk.com/apps/b2eee5d6-d48a-4eee-8644-7c05e5932a97)
- Esiste anche la versione Standard "Steel Frame & Weldments", con Frame, Miter, Trim/Extend e Notch. Il V-Notch & Fold è solo nella Pro — [Autodesk Marketplace – Steel Frame & Weldments](https://marketplace.autodesk.com/apps/fb291e10-43f6-4ec3-a151-f3d25167d3e2)
- Workflow manuale in Fusion (Pipe più profilo di coping) discusso nel forum: la soluzione dipende dal modellare il cope insieme ai tubi oppure dopo — [Autodesk forum "Pipe coping question"](https://forums.autodesk.com/t5/fusion-design-validate-document/pipe-coping-question/m-p/11922465/highlight/true)
- Per il tab&slot nativo in Fusion c'è un thread dedicato (senza strumento nativo) — [Autodesk forum "Tab and slot"](https://forums.autodesk.com/t5/fusion-design-validate-document/tab-and-slot/m-p/13983189)

**FreeCAD**
- **FrameForge** (zerr0/frameforge) è un workbench per travi e telai:
  - trim, offset, cut e mitre-cut;
  - export della distinta con angoli e lunghezze di taglio;
  - richiede FreeCAD ≥ 0.21, si installa dall'Addon Manager;
  - è basato su MetalWB, maintainer Vivien Henry.
  - Nell'estratto non risulta un comando di "coping" dedicato — [GitHub zerr0/frameforge](https://github.com/zerr0/frameforge); [FreeCAD wiki FrameForge](https://wiki.freecad.org/FrameForge_Workbench) (pagina protetta da anti-bot, non letta per intero)
- **MetalWB**: workbench per la carpenteria saldata. "WarehouseProfiles" genera profili da linee di sketch, con proprietà Bevel Start/End Cut per smussare le estremità. È ancora in sviluppo e distribuito via Framagit/Cyclonomia — [GrabCAD tutorial MetalWB](https://grabcad.com/tutorials/metalwb-for-welding-part-design); [GrabCAD forum](https://cad.grabcad.com/groups/freecad-help-showcase/discussions/new-workbench-metalwb-for-welding-part-design)
- **FreeCAD_SheetMetal** (shaise) copre la lamiera piegata, non il tubo. È utile per piastre e fazzoletti a incastro — [GitHub shaise/FreeCAD_SheetMetal](https://github.com/shaise/FreeCAD_SheetMetal)
- **rattleCAD** (mondo telai bici) genera le dime sviluppate di taglio a 45° (tube miter) da stampare — [rattleCAD Tube Miter](https://www.rattlecad.com/docs/features/feature_tubeMiter.html). BikeCAD offre anche le "miter templates" — [BikeCAD](https://bikecad.ca/miter_templates)

**Rhino/Grasshopper**
- Non ho trovato un plug-in dedicato al fishmouth o all'export per tube laser. Gli strumenti vicini sono:
  - **Lunchbox** (Unroll), suggerito sul forum McNeel per misurare le intersezioni di tubi sullo sviluppo — [McNeel forum "Measure Wrap pipe intersection"](https://discourse.mcneel.com/t/measure-wrap-pipe-intersection/194974);
  - **FabTools** (unroll di superfici e brep) — [food4rhino FabTools](https://www.food4rhino.com/app/fabtools);
  - **byRhinoGadget** (UnrollCrv) — [food4rhino byRhinoGadget](https://www.food4rhino.com/en/app/byrhinogadget);
  - **SmartSolidNester** (nesting di solidi per il laser piano) — [McNeel forum SmartSolidNester](https://discourse.mcneel.com/t/smartsolidnester-for-laser-cutting/205215).
- Un tubo dritto, cioè un cilindro, si sviluppa senza deformazione. Un tubo curvato è a doppia curvatura e non si sviluppa senza stirare la superficie (sviluppatore McNeel citato) — [Grasshopper forum "How do I unroll pipes?"](https://www.grasshopper3d.com/forum/topics/how-do-i-unroll-pipes)

**Altro / storico**
- **KurtJacobson/TubeNotch**: programma MATLAB che genera G-code per l'intaglio dei tubi (logica utile come riferimento matematico; non è un add-in CAD) — [GitHub TubeNotch](https://www.github.com/KurtJacobson/TubeNotch)
- **TubeWorks** (Unison, partner SolidWorks Gold) importa STEP/IGS per la curvatura dei tubi. È commerciale — [SolidWorks partner TubeWorks](https://www.solidworks.com/partner-product/tubeworks)
- Webinar HP Academy "Notching tubes in CAD – then IRL" (flusso da CAD a officina) — [HP Academy 394](https://www.hpacademy.com/previous-webinars/394-notching-tubes-in-cad-then-irl/)

### Inferences
- Per Fusion la base più sensata per una pipeline nostra è **forkare o studiare NeoTech/Fusion360-Weldments**: MIT, Python, geometria già separata e testata. Il cope via combine-cut contro il corpo vicino è esattamente il metodo "booleano" che si usa a mano. Gli incastri tab&slot su tubo (linguette, asole, finestre d'indicizzazione) vanno aggiunti noi come feature parametriche (corpi utensile più combine-cut, con parametri gioco/kerf).
- Steel Frame & Weldments Pro a 12 $/mese è un buon "banco di confronto": ha già tab/slot e V-notch & fold, cioè lo stesso concetto dei telai autoposizionanti BLM. Conviene provarlo per un mese prima di riscrivere tutto.
- FreeCAD/FrameForge è adatto alle distinte di taglio a 45°, ma per la bocca di lupo su tondo serve comunque un booleano con il corpo vicino (Part Cut), cosa che si fa anche in OpenSCAD/CadQuery con `difference()`/`cut()`.

### Gaps
- **CadQuery / OpenSCAD**: non ho trovato librerie dedicate al coping o al tab&slot su tubo (non cercato a fondo per limite di budget). Il booleano di base `cut()`/`difference()` è banale, ma una libreria "pronta" non è verificata.
- **Inventor Frame Generator** (comando Notch) e **SolidWorks Weldments** (Trim/Extend con coped cut): funzioni note, ma in questa sessione non le ho verificate con fonte primaria.
- **Karamba3D** è analisi strutturale FEM in Grasshopper e non genera tagli. Non ho trovato fonte che lo leghi al tube laser.
- Non ho trovato add-in sull'Autodesk App Store che esportino direttamente nel formato nativo BLM (ArTube).

## 2. Servizi online / contoterzisti di taglio laser tubo: formati, tolleranze, feature minime

### Takeaway
Lo standard di scambio è **STEP con un solo pezzo per file, tagli tutti passanti e perpendicolari alla superficie** ("cut to normal"). Kerf e gioco di saldatura li normalizza spesso il servizio. Le tolleranze tipiche dichiarate sono ±0,13 mm (±0,005") feature-feature e ±0,2 mm di posizionamento. In Europa il servizio online con preventivo istantaneo per il tubo più rilevante è **Fractory**. Per l'Italia ho trovato solo servizi online per la lamiera; il tubo resta da contoterzista con preventivo su richiesta.

### Cited Findings
**SendCutSend (USA)**
- Per il tubo accetta solo **.step/.stp**, un pezzo per file, niente assiemi. Modello in scala 1:1, in pollici o mm, **tubo allineato all'asse Y** — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- Tagli tutti passanti e perpendicolari. Niente multiasse, niente feature cieche, niente maschiature, svasature o incisioni sul tubo. **Kerf e "weld normalization" gestiti in automatico** — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- Tolleranze: **feature tagliata ±0,005"** (≈ ±0,13 mm); **feature tagliata → feature non tagliata ±0,015"** (≈ ±0,38 mm). C'è conicità del taglio, più marcata su pareti spesse e diametri piccoli. Bava e scoria interna restano a carico del cliente — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- Lunghezza massima **60" (1524 mm)**, ordine minimo da 39 $. Materiali: 6061-T6, 4130, Docol, A500/A513, inox 304 — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- Sui tubi quadri e rettangolari non estrusi la **saldatura interna può cadere su una linguetta** e richiedere una limatura — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- ⚠️ La pagina servizio riportava "capacità tubo limitata, nuovi ordini non accettati": disponibilità da verificare — [SendCutSend tube-cutting service](https://sendcutsend.com/services/tube-cutting) (dal riassunto di ricerca; non riletto direttamente)

**Fractory (UK, selettore regione con Italia)**
- Carica file 3D o DXF con preventivo istantaneo, senza ordine minimo, per ordini sotto 2000 £. Profili: tondo, quadro, ovale, scatolati, tubi e profili a C — [Fractory tube laser](https://fractory.com/tube-laser-cutting-services-uk/)
- Lunghezza fino a **8,5 m** (carico automatico), **Ø240 mm** o 240 mm di diagonale. Parete max: acciaio al carbonio 12 mm, inox 8 mm, alluminio 8 mm. **Posizionamento ±0,2 mm**. Sorgenti CO2 o fibra fino a 4 kW — [Fractory tube laser](https://fractory.com/tube-laser-cutting-services-uk/)
- Regola **"cut to normal"**: i tagli inclinati richiedono una testa 3D, meno comune. Alcuni partner ce l'hanno, a costo maggiore — [Fractory tube laser](https://fractory.com/tube-laser-cutting-services-uk/)

**Xometry**
- Accetta STEP, STP, SLDPRT, STL, DXF, IPT, X_T, X_B, 3DXML, CATPART, PRT, SAT, 3MF, JT — [Xometry laser tube design tips](https://www.xometry.com/resources/tube/laser-tube-cutting-design-tips/)
- Fori con **Ø ≥ spessore parete**. Evitare tolleranze foro-feature più strette di **±0,010"** (≈ ±0,25 mm). Prevedere gioco per kerf e conicità, soprattutto su pareti spesse. Telai grandi si possono **piegare a mano da un unico tubo** con tagli di scarico e feature di indicizzazione — [Xometry laser tube design tips](https://www.xometry.com/resources/tube/laser-tube-cutting-design-tips/)
- C'è una guida PDF dedicata a taglio e curvatura tubo, con sezione "Tabs, Slots, and Joints" — [Xometry tube manufacturing design guide](https://www.xometry.com/resources/design-guides/tube-manufacturing-design-guide/)
- Xometry Europa (IT) fa preventivi istantanei di taglio laser da STEP, ma la pagina parla di lamiera — [Xometry EU IT taglio laser](https://xometry.eu/it/taglio-laser/)

**OSH Cut (USA)**
- Tubo tondo, quadro e rettangolare in acciaio, alluminio e inox, fino a **10" di diametro**, con **bevel fino a 45°** — [OSH Cut tube cutting basics](https://oshcut.com/design-guide/tube-cutting-basics)
- Il laser non deve per forza attraversare entrambe le pareti del tubo. Le parti si possono progettare autoposizionanti (self-fixturing) — [OSH Cut tube cutting basics](https://oshcut.com/design-guide/tube-cutting-basics); [OSH Cut design rules](https://www.oshcut.com/design-guide/design-rules)
- Tutorial "Designing a tube part" — [OSH Cut tutorial](https://oshcut.com/tutorials/designing-a-tube-part) (non letto per intero)

**Fabworks (USA)**: taglio laser tubo con file STEP fino a 24 MB — [Fabworks tube laser](https://www.fabworks.com/services/tube-laser-cutting)

**RapidDirect**: preventivo istantaneo da STEP e altri formati 3D, DFM gratuito in 1 giorno, lead time da 3–5 giorni — [RapidDirect laser cutting](https://www.rapiddirect.com/services/laser-cutting/)

**LaserBoost (ES)**: configuratore DXF (taglio) e STEP (taglio più piega lamiera), tolleranza ±0,20 mm, spessori da 0,3 a 8 mm. Non ho trovato un servizio tubo — [LaserBoost design guide](https://laserboost.com/laser-cutting-design-guideline); [LaserBoost FAQ](https://www.laserboost.com/faq/)

**Italia**
- **Laserbend3d**: preventivo istantaneo da DXF/STEP (≤10 MB, uno STEP per pezzo; IGES esaminato a mano) per taglio, piega e saldatura lamiera. Il tubo non è esplicito — [Laserbend3d](https://laserbend3d.it/)
- **Weerg**: taglio laser online da file 2D (ferro decapato, ottone, Al 5754, inox 304). Nessun tubo — [Automazione Plus su Weerg](https://automazione-plus.it/taglio-laser-weerg-servizio-online_167903/)
- Contoterzisti tubo con preventivo su richiesta: per esempio **Elletielle** (San Vito al Tagliamento / Spilimbergo, taglio laser tubi e lamiera) — [presentazione Elletielle](https://cdn.techpilot.com/public/144966/documents/4e1b5be3-79b4-450a-9dd2-f3a967b9f9ec/presentazione%20lunga%20it%20-%20elletielle.pdf)

**Cosa accetta il CAM BLM (per i contoterzisti che hanno un LT)**
- ArTube importa modelli 3D da CAD esterni in **STEP, IGES, XT e IFC** e li converte in modelli nativi — [BLM LT12 programming](https://www.blmgroup.com/lasertube/lt12/programming); [DirectIndustry ArTube](https://directindustry.com/prod/blm-group/product-6136-465935.html)
- Il riconoscimento automatico delle sezioni tubo/profilo all'import è documentato per **Almacam Tube**, prodotto concorrente, non per ArTube — [Almacam Tube brochure](https://almacam.com/wp-content/uploads/2020/07/Almacam-tube_en_web.pdf)

### Inferences
- Per la nostra pipeline Fusion il deliverable universale è **uno STEP per pezzo, con il tubo allineato a un asse e tagli tutti radiali e passanti**. È accettato da SendCutSend, Fractory, Xometry e dai contoterzisti con BLM, perché ArTube importa STEP. Conviene esportare anche una tabella CSV con profilo, lunghezza e quantità.
- Dato che SendCutSend normalizza da sé kerf e weld gap, per chi lo fa conviene modellare la geometria **nominale** (gioco zero) e lasciare la compensazione al servizio. Per i contoterzisti tradizionali invece il gioco va modellato da noi. Ci serve quindi un **parametro globale "gioco_incastro"** attivabile o disattivabile.

### Gaps
- Kerf effettivo dei tube laser fibra (tipicamente qualche decimo di mm): nessun servizio tubo lo dichiara numericamente nelle pagine lette.
- I valori minimi di foro e ponticello per materiale di SendCutSend sono in tabelle che non ho estratto.
- Fractory Italia: non ho verificato condizioni di spedizione e prezzi verso l'Italia (la pagina "Rest of Europe" rimanda al sito UK).
- Non ho trovato un servizio **italiano** online con preventivo istantaneo specifico per il tubo.

## 3. Regole pratiche: gioco tab/slot, kerf, tolleranze del tubo (EN 10219/10210), raggi d'angolo, telai autoposizionanti

### Takeaway
Regola d'oro dei fabbricanti: asola = spessore della linguetta **+ almeno 0,25 mm (0,010") in totale**, cioè circa 0,1–0,2 mm per lato, con angoli dell'asola raccordati (dogbone o raggio pari al kerf). Sui tubi quadri e rettangolari in acciaio il **raggio esterno reale va da 1,5 a 3 volte lo spessore** (EN 10219: circa 1,6–2,4·T per T ≤ 6 mm). Le linguette e le asole vanno quindi tenute **fuori dalla zona del raggio**.

### Cited Findings
- **SendCutSend (tab&slot su lamiera)**: asola **almeno 0,010" (0,25 mm) più grande** della linguetta, sia in larghezza sia in spessore, per un accoppiamento scorrevole. Angoli dell'asola con piccolo raggio (aumentando la linguetta dello stesso raggio), a semicerchio o a **dogbone**. Le linguette smussate vanno bene ma danno un accoppiamento più lasco — [SendCutSend tab & slot](https://sendcutsend.com/blog/designing-laser-cut-tab-and-slot-parts)
- **Formula SendCutSend** (lamiera):
  - larghezza asola = larghezza linguetta + 2 × tolleranza di taglio del materiale della linguetta;
  - altezza asola = spessore linguetta + tolleranza positiva di spessore + 2 × tolleranza di taglio del materiale dell'asola.
  - [SendCutSend tab & slot sheet metal](https://sendcutsend.com/?p=85876)
- **Fictiv**: gioco dell'asola **0,1–0,2 mm per lato** su laser, raccordo d'angolo pari al raggio del kerf (0,1–0,2 mm) — [Fictiv tabs and slots](https://www.fictiv.com/articles/sheet-metal-tabs-and-slots-assembly)
- **Kerf**: una linguetta disegnata al nominale esce circa un kerf più stretta e un'asola circa un kerf più larga, quindi il gioco totale vale circa due kerf se non si compensa — [Fabcon](https://fabcon.com/articles/wp-json/wp/v2/posts/519) (fonte secondaria)
- Gli angoli interni non possono essere vivi: il raggio minimo interno vale circa il kerf. Gli angoli vivi dell'asola concentrano le tensioni — [SendCutSend 3D files](https://sendcutsend.com/guidelines/3d-files); [SendCutSend tab & slot](https://sendcutsend.com/blog/designing-laser-cut-tab-and-slot-parts)
- **Raggio d'angolo RHS/SHS**:
  - SendCutSend modella acciaio e inox con un raggio esterno di 3·t, ma lo stock reale va da **1,5·t a 3·t**; l'alluminio con 0,5·t;
  - il profilo interno si ottiene con un offset pari allo spessore — [SendCutSend tube guidelines](https://sendcutsend.com/guidelines/tube-cutting/)
- **EN 10219-2:2019** (tubi strutturali saldati formati a freddo, fino a 40 mm di parete) è l'edizione vigente: la 2006 è ritirata dal 08/05/2019 — [GENORMA EN 10219-2:2019](https://genorma.com/en/standards/en-10219-2-2019); [GENORMA EN 10219-2:2006](https://genorma.com/en/standards/en-10219-2-2006)
- Sintesi Nippon Steel (fonte secondaria, testo estratto in parte illeggibile): **raggio esterno circa 1,6T–2,4T per T ≤ 6 mm**, tolleranze sui lati in percentuale con un minimo in mm, squadro circa 90° — [Nippon Steel hollow sections EN](https://ns-kenzai.co.jp/english/021hollow_section_EN.html)
- Nell'EN 10219-2 (ed. 1997, estratto Parker Steel) gli angoli interni devono essere arrotondati, ma il loro profilo **non è specificato** — [Parker Steel estratto EN 10219-2](https://parkersteel.co.uk/sharedupgrade/media/pdf/standards/JPSBS0010.pdf)
- **Telai autoposizionanti**: OSH Cut e Xometry citano le parti self-fixturing, cioè giunti con tagli di scarico e feature di indicizzazione che permettono di piegare un telaio da un solo tubo. Steel Frame & Weldments Pro implementa il "V-Notch & Fold" con weld gap e tab size parametrici — [OSH Cut tube basics](https://oshcut.com/design-guide/tube-cutting-basics); [Xometry tips](https://www.xometry.com/resources/tube/laser-tube-cutting-design-tips/); [Steel Frame & Weldments Pro](https://marketplace.autodesk.com/apps/b2eee5d6-d48a-4eee-8644-7c05e5932a97)
- I tube laser lavorano meglio quando il raggio taglia verso il centro del tubo (tagli radiali) — [Xometry tips](https://www.xometry.com/resources/tube/laser-tube-cutting-design-tips/)
- Lo spessore della parete deve stare sotto 1/3 del diametro del tubo da tagliare: vincolo citato per gli script di coping (fonte debole, da riassunto di ricerca) — [KurtJacobson/TubeNotch](https://www.github.com/KurtJacobson/TubeNotch)

### Inferences
- Parametri di partenza proposti per la pipeline:
  - gioco asola-linguetta **0,2–0,3 mm totali** sul nominale (0,1–0,15 per lato);
  - raccordo d'angolo dell'asola ≥ 0,2 mm, oppure dogbone;
  - fori Ø ≥ t;
  - linguette distanti dal raggio d'angolo almeno 3·t dallo spigolo teorico.
- Da tarare con un **provino di taratura** tagliato dal contoterzista scelto: una serie di asole a gioco crescente su uno spezzone di tubo.
- La tolleranza dimensionale del tubo commerciale (EN 10219) si somma a quella del laser. Per gli incastri tubo-in-tubo (telescopici) il gioco va quindi dimensionato sulle tolleranze del lato e della parete del tubo, non solo sul kerf.

### Gaps
- Non ho trovato i valori tabellari esatti EN 10219-2/EN 10210-2 per raggio, lato, spessore e torsione da fonte primaria: la norma è a pagamento. Servono la norma o il catalogo del fornitore di tubi (es. Marcegaglia, Tenaris Dalmine).
- Non ho trovato una guida "design for laser tube" pubblica di BLM con valori numerici di gioco: il blog BLM parla solo del software — [BLM blog](https://blog.blmgroup.com/the-importance-of-software-when-working-on-lasertube).
- Protocase: non consultato.

## 4. Note legali UE: reverse engineering e interoperabilità (Direttiva 2009/24/CE, art. 6)

### Takeaway
L'art. 6 permette la decompilazione senza il consenso del titolare **solo se indispensabile per l'interoperabilità**, fatta da chi ha diritto d'uso, se le informazioni non erano già disponibili e limitata alle parti necessarie. Le informazioni non si possono usare per altri scopi, né per sviluppare un programma sostanzialmente simile. Le clausole contrattuali contrarie sono nulle. Usare formati aperti (STEP, IFC) evita del tutto il problema.

### Cited Findings
- L'art. 6 consente la riproduzione del codice e la traduzione della sua forma senza autorizzazione quando sono indispensabili per ottenere le informazioni necessarie all'interoperabilità di un programma creato autonomamente — [legislation.gov.uk Dir. 2009/24 art. 6](https://www.legislation.gov.uk/eudr/2009/24/article/6)
- Le condizioni sono tre: (a) atti compiuti dal licenziatario o da altra persona con diritto d'uso; (b) informazioni non già facilmente e rapidamente accessibili; (c) atti limitati alle parti del programma necessarie — [legislation.gov.uk art. 6](https://www.legislation.gov.uk/eudr/2009/24/article/6); [SCL su C-13/20](https://www.scl.org/12394-court-of-justice-rules-that-software-buyers-can-decompile-programs-to-correct-errors/)
- Le informazioni ottenute non possono essere usate per fini diversi dall'interoperabilità, né comunicate a terzi salvo necessità. Non possono servire a sviluppare, produrre o commercializzare un programma sostanzialmente simile, né per atti che violino il diritto d'autore. L'articolo non va interpretato in modo da arrecare un pregiudizio ingiustificato al titolare — [legislation.gov.uk art. 6](https://www.legislation.gov.uk/eudr/2009/24/article/6)
- Le disposizioni contrattuali contrarie all'art. 6 o alle eccezioni dell'art. 5(2)-(3) sono **nulle** (art. 8) — [legislation.gov.uk testo Direttiva](https://www.legislation.gov.uk/eudr/2009/24/body/adopted?view=plain)
- La CGUE, nella causa C-13/20 Top System (06/10/2021), ha stabilito che la decompilazione per correggere errori ricade nell'art. 5(1), non nell'art. 6, ed è ammessa se necessaria all'uso conforme — [SCL](https://www.scl.org/12394-court-of-justice-rules-that-software-buyers-can-decompile-programs-to-correct-errors/); [De Bandt](https://www.debandt.eu/en/node/510)
- Un non-paper del maggio 2025 discute l'aggiornamento della Direttiva 2009/24, art. 6 incluso, rimasto invariato dal 1991 — [Interoperable Europe non-paper 2025](https://interoperable-europe.ec.europa.eu/sites/default/files/discussion/attachment/2025-05/Non-paper%20PES%202025-05-09%20on%20updating%20Directive%202009-24-EC%20v01.pdf)

### Inferences
- Per la nostra pipeline non serve decompilare ArTube: BLM importa già STEP, IGES, XT e IFC, quindi l'interoperabilità passa da formati aperti. Un eventuale studio del formato nativo BLM (programmi o macchina) dovrebbe restare nei limiti dell'art. 6: solo per far dialogare il nostro software autonomo, da licenziatario, senza ricreare un CAM concorrente.

### Gaps
- Recepimento italiano (art. 64-quater L. 633/1941) non verificato con fonte in questa sessione. Non ho valutato EULA BLM specifiche né i vincoli su formati e protocolli macchina.
