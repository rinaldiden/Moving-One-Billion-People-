# Soluzioni esistenti di giunti in acciaio senza saldatura (laser/piega/foro/filetto) con incastro a sottosquadra + bulloni, per telai portanti "casa-IKEA"

Legenda: [TESTATO] = prove di laboratorio pubblicate; [CLAIM] = dichiarazione del produttore/fonte non indipendente; [BREVETTO] = solo descritto in brevetto; [NUMERICO] = solo FEM.
Ricerca condotta il 2026-11-03 con circa 20 chiamate. Molti full-text (ScienceDirect, MDPI) erano bloccati (403), quindi parecchi numeri vengono solo dagli abstract.

**Avvertenza trasversale, importante per il progetto:** quasi tutte le soluzioni "plug-in" commerciali e di ricerca sono *bolt-only IN CANTIERE*, ma i pezzi sono comunque **saldati in officina** (collari ConX, connettori a ganci delle scaffalature, piastre dei moduli). Le soluzioni davvero **zero saldature**, cioè solo taglio piano + incastro, sono poche: ISC (Intermeshed Steel Connections), WikiHouse (in legno), alcuni giunti di carpenteria leggera. Questa distinzione va tenuta in evidenza nel report.

## 1. Sistemi commerciali plug-in/drop-in (telai in acciaio da edificio)

### Takeaway
ConXtech ConX è il riferimento commerciale più vicino a un "drop-in con sottosquadra + bulloni": la trave cala dentro un canale rastremato sul collare della colonna, la gravità viene presa per appoggio e il momento dai bulloni. È però saldato in officina e prequalificato AISC. Lindapter dà fissaggi senza forare e senza saldare, ma di portata modesta: sono morsetti a attrito, non incastri.

### Cited Findings
- **ConXtech ConX/ConXL [BREVETTO + TESTATO + prequalificato AISC]**
  - Geometria (brevetto US11236501B2 "Full moment connection collar systems", assegnatario Conxtech Inc., priorità 9 feb 2018, concesso 1 feb 2022). All'estremità della trave è saldato un "flange assembly"; la trave viene calata finché questo si inserisce tra due "corner assembly" saldati agli spigoli della colonna. Il varco tra il piede e lo standoff a T forma un **canale rastremato** lungo l'altezza del corner. Le ali del flange assembly sono angolate (flange superiore e inferiore non speculari) e seguono quella rastremazione, quindi l'incastro è a cuneo verticale. Strutture di allineamento inferiori hanno la faccia superiore piana e una superficie curva inclinata di circa 15-45° che entra in un recesso della flangia inferiore — [Google Patents US11236501](https://patents.google.com/patent/US11236501)
  - Come passa il carico: la **gravità** va per **appoggio** della flangia inferiore sulle facce piane (gravity stop); la **posizione orizzontale** è data dal contatto contro piede e standoff; il **momento flettente è portato dai bulloni**. Nell'esempio ci sono 4 bulloni per corner, 16 per collare, e il collare può serrare la colonna — [US11236501](https://patents.google.com/patent/US11236501)
  - Il brevetto non usa il termine "undercut". L'incastro è una rastremazione/cuneo a caduta che centra e porta la gravità, non un sottosquadra che lavora a trazione — [US11236501](https://patents.google.com/patent/US11236501)
  - ConXL: travi IPE/W, colonne HSS quadre riempite di calcestruzzo o composte, bulloni AR precaricati a 45° nelle flange del collare. Risulta prequalificato e codificato da AISC (fonte secondaria) — [MaxAPress EMST 2025](https://maxapress.com/article/doi/10.48130/emst-0025-0021); [Modares CEJ](https://mcej.modares.ac.ir/article-16-6545-en.html)
  - [TESTATO/NUMERICO] Senza riempimento di calcestruzzo il ConXL è più duttile ma meno resistente. Un T-stub aggiunto aumenta la resistenza ultima di 1,08/1,11/1,10/1,87× a 20/200/400/600 °C — [Modares CEJ](https://mcej.modares.ac.ir/article-16-6545-en.html); [Bath, post-fire](https://researchportal.bath.ac.uk/en/publications/numerical-analysis-and-post-fire-performance-assessment-of-a-nove/)
- **Lindapter Type AF (girder clamp) [CLAIM + approvazione ETA]**: fissaggio a morsetto sulla flangia del profilo, "no drilling or welding". Carichi tabellati M12/M16/M20/M24: trazione per 1 bullone (coeff. sicurezza 5:1) 8,5/16,0/26,3/40,0 kN. Scorrimento per 2 bulloni (CS 2:1) 3,4/8,0/13,0/24,0 kN su acciaio verniciato e 3,9/10/16/30 kN su zincato. La mappatura delle colonne della tabella è da verificare sulla scheda tecnica — [Lindapter Type AF](https://lindapter.com/product/type-af-high-slip-resistance-girder-clamp?lang=en)
  - ETA 20/0918 (versione zincata a caldo), report ICC-ES, approvato per carichi dinamici EN 1993-1-9, prova al fuoco ISO 834 per 120 min (fonte distributore) — [ANZOR](https://anzor.co.nz/lindapter/girder-clamps/type-af-lindapter-girder-clamp-hdg)
  - Lavora ad **attrito/serraggio**, senza incastro geometrico. È utile per fissaggi secondari, non per nodi portanti principali di un telaio.

### Inferences
- ConX dimostra che un nodo a **caduta + cuneo rastremato** (la gravità porta in appoggio, i bulloni chiudono il momento) è industrializzabile e codificabile. È il modello concettuale più vicino a quello che vogliamo, ma con saldature d'officina.
- Un equivalente senza saldature richiederebbe di ottenere il canale rastremato con piatti tagliati al laser e imbullonati/incastrati. Non ho trovato chi lo commercializzi.

### Gaps
- SidePlate, Peikko (DELTABEAM e piastre con ganci), HALFEN/Schöck, Kee Klamp, Unistrut e i sistemi a cava "item/Bosch Rexroth" su scala edilizia **non verificati** in questa sessione (nessuna fonte consultata).
- Il report AISC 358 di prequalifica del ConX, con capacità in kNm, non è stato recuperato.

## 2. Scaffalature industriali (racking): ganci a sottosquadra + perno/bullone di sicurezza

### Takeaway
Il racking è la tecnologia "hook-in" più matura e normata (EN 15512): linguette/ganci del connettore entrano in asole del montante e portano la gravità per appoggio e incastro; un fermo o un bullone impedisce lo sfilamento verso l'alto. La rigidezza è però bassa (momenti dell'ordine di 1-2 kNm) e ci sono giochi ("looseness"). Inoltre il connettore è di norma saldato alla trave.

### Cited Findings
- EN 15512 (versione ucraina DSTU EN 15512:2015 = EN 15512:2009) prevede prove su connettori trave-montante: momento e taglio di progetto, curva momento-rotazione, annesso con prove di flessione, gioco ("looseness") e taglio — [Budstandart](https://online.budstandart.com/ua/catalog/doc-page.html?id_doc=77615)
- Connettore a **4 ganci (tabs) saldato all'estremità della trave**, provato a mensola secondo EN 15512:2009 — [MDPI Metals 10(2):276 (via scidar)](https://scidar.kg.ac.rs/bitstream/123456789/8245/1/10.3390-met10020276.pdf)
- [TESTATO] Momenti di prova di circa 1,63-1,67 kNm su 4 campioni, momento di progetto circa 1,46 kNm, per un singolo tipo di nodo (S80ML-R100L) — [MDPI Metals 10/2/276](https://www.mdpi.com/2075-4701/10/2/276/xml)
- [TESTATO] Le prestazioni dipendono fortemente da spessore del montante, altezza della trave e **numero di ganci**. La crisi governa dal **gancio più alto** e dalla parete del montante adiacente — [PLOS ONE/ScienceOpen](https://www.scienceopen.com/document_file/830034be-c689-441a-9ac0-c915a06ac7d7/PubMedCentral/830034be-c689-441a-9ac0-c915a06ac7d7.pdf); [Griffith](https://research-repository.griffith.edu.au/bitstream/10072/36198/1/67895_1.pdf)
- Il gioco del connettore va incluso negli effetti P-Δ, soprattutto per i telai non controventati — [ingenio-web](https://www.ingenio-web.it/4399-seismic-behaviour-of-steel-storage-pallet-racking-systems---part-2)
- La capacità di sfilamento (pull-out) del connettore decide se un collasso resta confinato o diventa progressivo. Esistono sistemi con perno di bloccaggio (locking pin) — [Griffith](https://research-repository.griffith.edu.au/bitstream/10072/36198/1/67895_1.pdf)
- [TESTATO] Sotto carichi ciclici la riduzione del momento ultimo non cambia in modo significativo la risposta sismica globale — [TU Delft CST2012](https://webapp.tudelft.nl/proceedings/cst2012/pdf/kwarteng.pdf)

### Inferences
- Il racking conferma che **il sottosquadra a gancio porta bene il taglio/gravità ma non il momento**. Per un telaio-casa servono controventi, oppure bulloni che chiudano il gioco e prendano il momento (logica "aggancia poi imbullona").
- Il gioco iniziale è il nemico principale: un bullone precaricato o un cuneo che annulla il gioco è il pezzo chiave da progettare.

### Gaps
- Non ho trovato numeri pubblicati su connettori con bullone di sicurezza, né confronti con o senza bullone.

## 3. Ricerca: connessioni inter-modulo (edifici modulari in acciaio) plug-in + bulloni

### Takeaway
È il filone con più dati sperimentali. I connettori combinano chiavi di taglio/perni di centraggio a innesto (self-aligning) con bulloni che portano trazione e chiudono il nodo. Le prove mostrano che il **bullone porta comunque una quota significativa del taglio** e che il punto debole è spesso la saldatura trave-colonna dei moduli, non il connettore.

### Cited Findings
- **Han, Wang, He, Hu, Chan, Chung (PolyU), JCSR 2023, doi:10.1016/j.jcsr.2023.108118 [TESTATO]**: due tipi di connessione (A e B) "self-aligning". La chiave di taglio a innesto centra il modulo superiore e allinea da sola i fori; il tipo B ha un bullone precaricato in asse alle colonne e una piastra di ancoraggio, unisce fino a 8 moduli e in cantiere richiede solo la posa dei bulloni. Il programma conta 5 prove di sfilamento e 5 sottoassiemi a carico laterale; nei provini ci sono piastre da 6 e 10 mm e bulloni M12 cl. 6.8 e M20 cl. 8.8 — [PDF PolyU](https://ira.lib.polyu.edu.hk/bitstream/10397/100015/1/Han_Experimental_Investigation_Bolted.pdf)
  - Il provino CON-A-14 ha avuto la rottura di un bullone a **150 kN** di trazione, dopo forte flessione delle piastre di testa. Un sottoassieme è arrivato a un massimo di **118 kN** a 42 mm di spostamento, con rottura delle saldature trave-colonna — [PDF](https://ira.lib.polyu.edu.hk/bitstream/10397/100015/1/Han_Experimental_Investigation_Bolted.pdf)
  - Conclusioni: lo snervamento della piastra va preferito alla rottura del bullone (più duttilità). Nel tipo B, sotto carico laterale, le colonne scorrono finché la chiave di taglio va a contatto, ma "**una forza di taglio significativa si trova nel bullone**", da considerare nel progetto. La crisi principale di tutti i sottoassiemi è la **frattura della saldatura trave-colonna**; il tipo B, con meno saldature, dà maggiore deformabilità — [PDF](https://ira.lib.polyu.edu.hk/bitstream/10397/100015/1/Han_Experimental_Investigation_Bolted.pdf)
- **Lacey, Chen, Hao, Bi, "New interlocking inter-module connection…: Experimental and numerical studies", Eng. Struct. 198 (2019) 109465 [TESTATO]**: bulloni strutturali più elementi a incastro. Studiati gli effetti di elementi a incastro, precarico del bullone, tolleranza dei fori e tolleranze di fabbricazione/montaggio sul comportamento taglio-scorrimento, con un modello empirico proposto. Il problema dichiarato è come dare tolleranza di montaggio senza introdurre scorrimento — [PolyU record](https://research.polyu.edu.hk/en/publications/new-interlocking-inter-module-connection-for-modular-steel-buildi-2/)
- **Lacey et al., Eng. Struct. 227 (2021) 111409 [NUMERICO su base sperimentale]**: modelli ABAQUS, 2 bulloni per colonna per resistere alla rotazione nel piano, modelli semi-empirici per assiale e momento-rotazione — [PolyU record](https://research.polyu.edu.hk/en/publications/new-interlocking-inter-module-connection-for-modular-steel-buildi/)
- Lacey et al., JCSR 2019, doi:10.1016/j.jcsr.2019.105707 (post-tensionato): la rigidezza iniziale a taglio è controllabile tramite precarico e coefficiente d'attrito — [PolyU](https://research.polyu.edu.hk/en/publications/shear-behaviour-of-post-tensioned-inter-module-connection-for-mod/)
- Rajanayagam et al., JCSR 2022 [TESTATO]: connessione bullonata a carico laterale con tendenza a cedere **per scorrimento anche con carichi laterali molto bassi** (dipende da diametro del bullone e tolleranza dei fori) — [Northumbria](https://researchportal.northumbria.ac.uk/en/publications/evaluation-of-inter-modular-connection-behaviour-under-lateral-lo/); [UWE](https://uwe-repository.worktribe.com/output/11623346/evaluation-of-inter-modular-connection-behaviour-under-lateral-loads-an-experimental-and-numerical-study)
- Wang et al., Eng. Struct. 2017: dispositivi plug-in in getto per i giunti orizzontali più bulloni trave-trave, installati in fabbrica, senza saldature in sito — [Arataumodular PDF](https://www.arataumodular.com/app/wp-content/uploads/2022/09/Experimental-Study-On-Interior-Connections-In-Modular-Steel-Buildings.pdf)
- "Spider connector" (Aguayo et al.) per la continuità verticale di moduli in tubolare quadro. Secondo una fonte correlata, nei sistemi alti i plug-in riducono scorrimento e apertura rispetto ai bullonati convenzionali — [UPM](https://oa.upm.es/92536/3/92536.pdf)
- Yang, Xia, Chang, Zhang, Yang (CUMT), "A novel plug-in self-locking inter-module connection for modular steel buildings", 2023, doi:10.1016/j.tws.2023.110774 (Thin-Walled Struct. vol. 187, rivista dedotta). Abstract e numeri non recuperati — [CUMT](https://faculty.cumt.edu.cn/XJW/en/lwcg/61455/content/147242.htm)
- Review Buildings 2026 (doi:10.3390/buildings16193770): confronta 10 connessioni inter-modulo, tra cui una "Mid-Depth Self-Locking Plug-in" — [CiteDrive](https://www.citedrive.com/en/discovery/steel-inter-modular-connections-for-resilient-and-sustainable-modular-buildings-a-structured-comparative-review-and-design-framework/)
- Review Lacey et al. 2019 (J. Building Eng.) sui dettagli e sui metodi di progetto delle connessioni inter-modulo — [PolyU](https://research.polyu.edu.hk/en/publications/review-of-bolted-inter-module-connections-in-modular-steel-buildi/)

### Inferences
- Il pattern validato è questo: **un incastro (chiave/perno/cuneo) per centrare e prendere il taglio, più un bullone precaricato per trazione e serraggio**. Le prove avvertono però che senza precarico e con fori larghi il taglio finisce comunque sul bullone dopo uno scorrimento. Il sottosquadra va progettato **a gioco zero** (cuneo o rastremazione), altrimenti diventa solo un dispositivo di montaggio.
- Anti-pattern emerso: le saldature d'officina (trave-colonna) sono il punto di rottura prematura. È un argomento a favore dei giunti interamente tagliati e imbullonati.

### Gaps
- Geometria e valori numerici (kN di scorrimento, rigidezze) del connettore interlocking di Lacey 2019 non accessibili (full text a pagamento).

## 4. Ricerca: giunti tagliati al laser/plasma a incastro ("Intermeshed" e LASTEICON)

### Takeaway
La ricerca più vicina all'idea "solo lamiera tagliata che si incastra" è l'**ISC — Intermeshed Steel Connections** (progetto AMASS USA-Irlanda-Irlanda del Nord): piatti tagliati a plasma/laser/waterjet che si intrecciano, eliminano la saldatura in sito e gran parte dei bulloni in sito, con prove in scala. LASTEICON (UE, Politecnico di Milano/Kanyilmaz) usa asole laser per far passare la trave attraverso il tubo, ma con saldature ridotte, non nulle.

### Cited Findings
- [TESTATO] McGetrick et al., Proc. ICE Structures and Buildings 2022 (doi:10.1680/jstbu.19.00181): progetto, fabbricazione, FEA e **prove in scala** di ISC laterali per le flange di profili aperti, con correlazione digitale d'immagine (DIC). Procedura di progetto basata sullo **snervamento dei piatti laterali**, affinata per concentrazioni di tensione, tolleranze di fabbricazione e sovraresistenza — [QUB Pure](https://pure.qub.ac.uk/en/publications/experimental-testing-and-analysis-of-the-axial-behaviour-of-inter/)
- Le tecnologie di taglio ad alta definizione (plasma, laser, waterjet) permettono ISC che **eliminano la saldatura in sito e la maggior parte dei bulloni in sito** [CLAIM degli autori] — [TU Delft record](https://research.tudelft.nl/en/publications/experimental-testing-and-analysis-of-the-axial-behaviour-of-inter/)
- [NUMERICO + prove componenti] Shemshadian et al., JCSR 2019: interazione complessa tra capacità assiale, a taglio e a momento, dovuta all'intreccio di flange e anima — [UMN experts](https://experts.umn.edu/en/publications/numerical-study-of-the-behavior-of-intermeshed-steel-connections-/)
- È stato eretto e smontato un telaio a 2 piani con ISC; in una configurazione la trave passa attraverso il nodo ed è fissata con una staffa bullonata, senza saldature tra trave e colonna — [ResearchGate review Kanyilmaz](https://www.researchgate.net/publication/330838224_The_problematic_nature_of_steel_hollow_section_joint_fabrication_and_a_remedy_using_laser_cutting_technology_A_review_of_research_applications_opportunities)
- Progetto AMASS (Advanced Manufacturing for the Assembly of Structural Steel): prove fisiche, FE e modellazione multiscala su concentrazioni di tensione, frattura e modi di rottura — [NRCT DOI](https://doi.nrct.go.th/ListDoi/listDetail/10.12755%2FISEC.res.2019.12)
- **LASTEICON** (RFCS-GA-709807, Kanyilmaz/Castiglioni, PoliMi): profili inseriti attraverso colonne CHS tramite asola tagliata al laser per ridurre dettagli, saldature, tonnellaggio e tempi di montaggio; nella fase di fabbricazione sono testati diversi tipi di saldatura (quindi non è weld-free) — [ScienceDirect abstract S0143974X1731180X](https://www.sciencedirect.com/science/article/abs/pii/S0143974X1731180X)
  - [TESTATO] I giunti I-CHS passanti danno una resistenza 2,5 volte e una rigidezza 10 volte maggiori rispetto a un I-CHS saldato direttamente — [UHasselt](https://documentserver.uhasselt.be/handle/1942/42068)
  - [NUMERICO] Das, Kanyilmaz et al. (NORDIC Steel 2024): giunti di colonna CHS **bullonati** con asole laser e piatti passanti (configurazioni CS-1/2/3) — [UHasselt PDF](https://documentserver.uhasselt.be/bitstream/1942/44713/1/RajarshiDas_NORDIC_Manuscript.pdf)
  - Couchaux, Kanyilmaz et al.: "Passing-through I-beam-to-CHS column joints made by laser cutting technology: Experimental tests and design model" — [HAL Couchaux](https://cv.archives-ouvertes.fr/mael-couchaux)

### Inferences
- ISC è il **parente più stretto** della nostra idea (lamiera tagliata che si incastra a sottosquadra). La sua regola di progetto, cioè far snervare i piatti laterali prima che si rompano i denti, è direttamente trasferibile.
- LASTEICON è un riferimento italiano (PoliMi) contattabile per un giunto passante tagliato al laser più bulloni.

### Gaps
- Capacità numeriche in kN degli ISC non recuperate (full text ICE/JCSR non accessibile).
- Non ho trovato studi peer-reviewed su un giunto **completamente bullonato, senza saldature, a incastro tagliato al laser** provato a scala reale come nodo di telaio edilizio.

## 5. Brevetti: incastro a sottosquadra/coda di rondine/aggancio + bulloni

### Takeaway
Nessun brevetto trovato combina esplicitamente coda di rondine, gancio e bulloni in un nodo trave-colonna in acciaio. I brevetti rilevanti sono il collare rastremato ConX (§1), un incastro a molla "self-locking" per moduli (Hong Kong) e vecchi giunti a coda di rondine.

### Cited Findings
- [BREVETTO] **US11352781B2** "Reversible self-locking interconnection system for modular integrated construction" (Nano and Advanced Materials Institute / HK ASTRI; inventori Wu, Zhang, Lau, Zhu; priorità 15 set 2020; concesso 7 giu 2022). Manicotti interni che entrano nelle colonne dei moduli, con **chiavistello a molla a cuneo + superficie di arresto verticale** (un vero sottosquadra a scatto) che entra nell'apertura della colonna. I cunei superiore e inferiore hanno angoli opposti. Il giunto modulo-modulo è **senza bulloni**; i bulloni servono solo per il fissaggio opzionale al nucleo in calcestruzzo (piastra a L a 90° in apertura regolabile con asole) — [Google Patents](https://patents.google.com/patent/US11352781)
- [BREVETTO] US409893A (Robert Wray, XIX secolo): giunto per travi con gancio appoggiato e **coda di rondine scorrevole in una sede a coda di rondine**; per la versione a solo gancio preferisce travi metalliche — [Google Patents](https://patents.google.com/patent/US409893A/en)
- [BREVETTO] US12163328B2 "Self-sealing building module with a self-aligning connector" — [Google Patents](https://patents.google.com/patent/US12163328)
- [BREVETTO] Altri nodi trave-colonna bullonati senza coda di rondine: US6073405 e US6059482 (ICF Kaiser, raccordo pressofuso bullonato), US4678091 (Konstant), US11725378 (MiTek), US20110252743A1 (piastre "jacket" 3D + tiranti) — [US6059482](https://patents.google.com/patent/US6059482A); [US11725378](https://patents.google.com/patent/US11725378); [US20110252743A1](https://patents.google.com/patent/US20110252743A1/en)
- [BREVETTO] Tab-and-slot nei telai: US8398159 "Frame members with tab and slot connections" e US9802663 (prevedono che dopo il montaggio i pezzi *possano* essere saldati) — [USPTO 8398159](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8398159); [USPTO 9802663](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9802663)

### Inferences
- Lo spazio brevettuale "lamiera laser a coda di rondine + bullone di bloccaggio per nodo strutturale da edificio" sembra **poco presidiato** in base a questa ricerca limitata. Prima di qualsiasi conclusione di libertà d'uso serve però una ricerca vera su Espacenet con classificazioni (E04B1/24, E04B1/19, E04B1/348).

### Gaps
- Ricerca CPC/Espacenet sistematica non eseguita. Brevetti cinesi (CN118187279A e altri "assembled light steel" con innesti) solo intravisti — [CN118187279A](https://patents.google.com/patent/CN118187279A/en)

## 6. Kit "casa-IKEA": WikiHouse e carpenteria leggera

### Takeaway
WikiHouse/Skylark è il riferimento open "IKEA-house": pezzi CNC che si incastrano con tasselli e cunei battuti a mazzuolo, e prove BRE a scala reale. È però in **legno (compensato)**. Sistemi equivalenti in acciaio a incastro non sono stati trovati con dati pubblici.

### Cited Findings
- [TESTATO] Open Systems Lab ha fatto eseguire a BRE, a metà 2021 e per 3 settimane, prove su larga scala di resistenza e rigidezza al racking di pannelli 2D e di un modulo 3D Skylark — [BRE case study](https://bregroup.com/documents/d/bre-group/BRE_Open_Systems_Lab_Case_Study)
- Giunti Skylark: incastri tutto-legno a tassello e asola ("TIE") battuti col mazzuolo (fonte secondaria) — [Studio Matrx](https://www.studiomatrx.org/guides/wikihouse)
- [TESTATO] Granello et al. (Edinburgh): capacità laterale di pareti a taglio in compensato CNC a incastro, con prove e modello analitico; file di taglio pubblicati — [engrxiv](https://engrxiv.org/preprint/download/2266/4446/3381)
- Libreria pubblica di prove strutturali WikiHouse; la responsabilità della verifica resta a un ingegnere strutturista — [WikiHouse structural testing v0.1](https://www.wikihouse.cc/research/wikihouse-structural-testing-version-0-1); [WikiHouse terms](https://www.wikihouse.cc/engineering/terms)
- L'ingegnere AWA afferma che le prove a scala reale hanno migliorato la comprensione del comportamento e dei modi di rottura del sistema — [AWA](https://awaengineers.com/insights/an-interview-with-ben-whitfield-technical-director-at-awa-about-his-experience-working-on-wikihouse-projects/)

### Inferences
- Il **metodo** WikiHouse (file aperti, incastri autolocalizzanti, prove di racking BRE come cancello) si può copiare per un kit in acciaio. Il giunto, invece, va ripensato: nell'acciaio il sottosquadra non si "battezza" a mazzuolo e il gioco va chiuso con bulloni o cunei.

### Gaps
- FRAMECAD, Howick, Vertex, Lindab, Blokable, Vision Modular, Kasita, Cover, Open Source Ecology, U-Build e sistemi italiani **non verificati** in questa sessione (nessuna fonte consultata); da coprire in una ricerca dedicata.
