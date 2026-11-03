# Fabbricazione dei pezzi di collegamento "casa IKEA": taglio laser + piega + foratura + filettatura (al posto della saldatura)

Ambito: acciaio al carbonio/strutturale (S235/S355, anche zincato a caldo), spessori 3–20 mm, da lamiera e da tubo/trave. Note di ricerca del 2026-11-03. Ogni affermazione ha la sua fonte; ciò che non ho potuto verificare è nei "Gaps". Molte fonti sono di produttori/fornitori di servizi (marketing tecnico), lo segnalo dove conta.

## 1. Filetti nei pezzi tagliati laser: maschiatura, rullatura, flowdrill, PEM, rivetti filettati, bulloni ciechi. Lunghezza minima di avvitamento; cosa dicono EN 1993-1-8 / EN 1090-2; bulloni precaricati EN 14399

### Takeaway
In acciaio la regola pratica è un avvitamento di circa 1×d (in alluminio 2×d), quindi una lamiera da 3–8 mm maschiata NON sviluppa la resistenza piena di un bullone M12–M20. Servono spessore ≥ d, un collare flowdrill (che allunga il filetto), oppure dado/bullone cieco. La nuova EN 1993-1-8:2024 introduce una clausola specifica (5.9.3) per i bulloni in fori filettati, con lunghezze minime di avvitamento lasciate in parte ai National Annex. PEM e rivetti filettati sono prodotti da lamiera sottile, non organi strutturali da costruzione.

### Cited Findings
**Lunghezza di avvitamento / filetti maschiati**
- Regola comunemente citata: avvitamento minimo ≈ 1×diametro nominale in acciaio e ≈ 2×d in alluminio, per un foro maschiato che regga quanto il bullone — [Nord-Lock, "Thread engagement in a tapped hole"](https://www.nord-lock.com/insights/bolting-tips/2015/the-experts-thread-engagement-in-a-tapped-hole/)
- SendCutSend consiglia uno spessore pari a 1–1,5 volte il diametro dell'organo filettato. Più la lamiera è sottile, meno filetti completi si formano. Gli acciai tollerano un avvitamento più basso rispetto ad alluminio, ottone e plastiche — [SendCutSend, capabilities tapping](https://sendcutsend.com/blog/capabilities-of-our-online-sheet-metal-tapping-service/); [SendCutSend tapping guidelines](https://sendcutsend.com/guidelines/tapping)
- Nota di qualità: le pagine SendCutSend formulano la regola in modo incoerente (una dice "1–1,5× il diametro del bullone", un'altra "1–1,5× il rapporto diametro/profondità") — [SendCutSend blog](https://sendcutsend.com/blog/capabilities-of-our-online-sheet-metal-tapping-service/)
- Limiti di servizio SendCutSend per la maschiatura: acciaio dolce 0,059"–0,500" (≈1,5–12,7 mm); inox 304 0,060"–0,500"; zincato G90 solo 0,059"–0,074" (≈1,5–1,9 mm). Massimo spessore acciaio maschiabile 0,500" ≈ 12,7 mm. Non fanno eccezioni ai limiti min/max delle misure di maschio per materiale/spessore — [SendCutSend capabilities](https://sendcutsend.com/blog/capabilities-of-our-online-sheet-metal-tapping-service/); [FAQ tap sizes](https://sendcutsend.com/faq/which-tap-sizes-can-i-use-for-my-project/)

**Eurocodice 3 / EN 1090-2**
- La EN 1993-1-8:2024 (seconda generazione) ha la clausola 5.9.3 per i bulloni in fori filettati. Il National Annex di Cipro, che la elenca tra i parametri nazionali, NON fissa una lunghezza minima di avvitamento Lt né requisiti esecutivi aggiuntivi. Quindi il valore dipende dal NA del Paese: da verificare per l'Italia — [prCyprus National Annex EN 1993-1-8:2024](https://www.cys.org.cy/wp-content/uploads/2026/03/prCyprus-National-Annex-EN-1993-1-8-2024-For-CIB-2.docx)
- La bozza EN 1993-1-8 contiene disposizioni per i "bolts in threaded holes" (BTH), fra cui la definizione di lunghezze minime di avvitamento. Uno studio parametrico su giunti trave–colonna tubolare con flangia estesa ne ha verificato l'applicabilità generale — [Ptiček et al., Tehnički vjesnik 2022](https://hrcak.srce.hr/en/279499); [TU Delft, "Structural Steel Joints with Bolts in Threaded Holes"](https://research.tudelft.nl/en/publications/structural-steel-joints-with-bolts-in-threaded-holes/)
- Il National Annex tedesco indica la profondità di avvitamento necessaria a sviluppare la resistenza a trazione piena del bullone. Alcuni giunti non riescono a raggiungerla e lì la capacità resta incerta: c'è una tesi sperimentale specifica sui fori ciechi filettati — [db-thueringen, "Experimental Analyses on the Resistance of Tapped Blind Holes"](https://www.db-thueringen.de/receive/dbt_mods_00062338)
- EN 1090-2 §8.2.2: il bullone deve sporgere dal dado di almeno un passo di filetto. Per i bulloni precaricati EN 14399-3 (HR) e EN 14399-10 (HRC) servono almeno 4 filetti dentro la lunghezza serrata. Diametro minimo, lunghezza bullone, sporgenza, gambo non filettato e lunghezza di serraggio sono tutti governati da §8.2.2 — [New Steel Construction AD 426](https://www.newsteelconstruction.com/wp/ad-426-bolt-head-protrusion-through-nuts-and-threads-in-grip-lengths/); [Steel Buildings in Europe, model specification](https://infosteel.be/images/Steel-Buildings-in-Europe/SSB10/42)
- Le proprietà meccaniche dei bulloni (durezza compresa) stanno nella EN ISO 898-1, non nella EN 1090-2. Per il precarico si rimanda alla EN 14399 — [SAISC](https://www.saisc.co.za/?p=2747)

**Flow drilling (Flowdrill / foratura termica)**
- Il calore d'attrito ammorbidisce il metallo e il materiale spostato forma un collare. Il filetto viene poi formato a freddo (rullato), e l'incrudimento che ne deriva dà un'alta resistenza allo strappo — [Hoffmann Group, HELEX M-Drill](https://eshop.hoffmann-group.com/SG/en/hsg/e/1420990); [creametal](https://creametal.artugo.ch/en/drilling/flow-drilling-thread-forming)
- Dato del produttore: circa +20% di resistenza statica allo strappo rispetto alla filettatura per asportazione, con profondità di filetto fino a 4×D (dato vendor, nessuna conferma indipendente trovata) — [CTE magazine, Thermal Flow Drilling](https://ctemag.com/node/28598)
- Campo di spessore: da 0,8 a 11,0 mm a seconda della misura del filetto (catalogo Centerdrill). La durata dell'utensile cala su spessori pesanti e su materiali ad alta resistenza — [Centerdrill catalogue 2020](https://www.centerdrill.de/media/centerdrill_catalogue_2020.pdf); [Flowdrill user guide](https://pdf.directindustry.com/pdf/flowdrill/user-guide/9213-27160.html)
- Il collare rinforzato, ricavato dal materiale base, aumenta l'avvitamento ed è indicato per i tubi a parete sottile — [Fowkes / Flowdrill](https://www.fowkes.co.za/brand/flowdrill)
- La TruLaser Tube 7000 con opzione tapping fa flowdrill, maschiatura e foratura elicoidale. Un utilizzatore UK esegue un flowdrill e poi un "heavy-duty thread" in macchina — [TRUMPF TruLaser Tube 7000](https://trumpf.com/en_US/products/machines-systems/laser-tube-cutting-machines/trulaser-tube-7000-fiber); [TRUMPF UK press release](https://trumpf.com/en_GB/newsroom/local-press-releases/press-release-detail-page/release/trulaser-tube-7000-will-further-enhance-capability-and-capacity)

**Inserti autoaggancianti PEM**
- Durezza massima della lamiera: PEM CLA ≤ HRB 50 (HB 82); CLS/CLSS ≤ HRB 70 (HB 125); S/SS ≤ HRB 80 (HB 150); SP inox ≤ HRB 90 (HB 185). Bossard riporta HRB 70 per PEM F/AS e HRB 88 per F4 — [PEM catalog S-M12](https://catalog.pemnet.com/item/nuts-types-s-ss-cls-clss-cla-sp/self-clinching-nuts-types-s-ss-cls-clss-sp-metric/s-m121zc); [Bossard PEM F](https://www.bossard.com/eshop/th-en/clinching-technology/clinching-clinch-for-metallic-materials/selfclinching-nuts/pem-f/p/53633)
- Nessuna fonte trovata dà carichi di progetto strutturali per i PEM. Per spessore minimo e foro, vedere la tabella del singolo codice — [PEM catalog](https://catalog.pemnet.com/item/nuts-types-s-ss-cls-clss-cla-sp/self-clinching-nuts-types-s-ss-cls-clss-sp-metric/s-m121zc)

**Rivetti filettati (rivnut / "Rivkle")**
- M10 in acciaio, dati di laboratorio da distributore: taglio ≈ 5.000 N, trazione ≈ 32.000 N. Versione inox A2 flangiata: 8.620 N taglio, 47.070 N trazione — [Farnell datasheet](https://www.farnell.com/cad/2712947.pdf)
- M10, strappo da lamiera d'acciaio: 6,1–10,6 kN secondo lo spessore (tabella parzialmente illeggibile). Lo stesso inserto in lamiera da 0,125" ha più di 4× lo strappo che in 0,030" — [Eugene Fastener, Rivet Nut Engineering Reference](https://www.eugenefast.com/Home/Page/resources/rivet-nut-engineering-reference)
- I modelli standard equivalgono a un dado classe 8; le varianti alto-resistenziali arrivano a classe 10–12 "anche per applicazioni strutturali" (affermazione da rivista di settore) — [FAST magazine 2023](https://fast.mydigitalpublication.co.uk/issue-2-2023/page-16)
- Sotto il grip minimo il rivetto resta lasco, può girare e ha uno strappo scarso — [AIMS Industrial, rivet nut guide](https://aimsindustrial.com.au/blogs/product-guides/rivet-nut-guide)

**Bulloni ciechi (Hollo-Bolt e simili)**
- Lindapter Hollo-Bolt: accesso da un solo lato del profilo cavo, posa in fori predisposti e serraggio a coppia. M16 e M20 hanno il meccanismo "High Clamping Force". Testato secondo EN 1993-1-9 (fatica) — [pgb-europe, Hollo-Bolt](https://www.pgb-europe.com/en-gb/254197/lindapter-hollo-bolt-hexagonal-hb-m8x90-zinc-plated)
- La EN 1993-1-8 (prima generazione) non aveva regole dedicate per i bulloni ciechi. Un'equazione di Yeomans, adattata all'Hollo-Bolt, è stata recepita nella guida CIDECT per i giunti su colonne cave; SCI ha un approccio simile — [Univ. Birmingham, ce/papers 2023](https://research.birmingham.ac.uk/files/206061801/cepa.2749.pdf)

### Inferences
- Gerarchia pratica per un kit da costruzione, dal più robusto al meno: (1) bullone passante + dado (o bullone cieco certificato dove manca l'accesso); (2) foro maschiato in piatto con spessore ≥ 1–1,5×d (es. M12 in piatto ≥ 12–18 mm); (3) flowdrill + rullatura su tubo/lamiera fino a circa 11 mm; (4) rivetto filettato o PEM solo per carichi secondari (tamponamenti, finiture, staffe impiantistiche). Su S355 la durezza ~HB 150–180 è al limite o sopra il campo dei PEM standard.
- In un piatto da 3–8 mm il filetto maschiato non sviluppa un M12–M20 classe 8.8. Se il nodo deve prendere trazione, conviene dado imprigionato/bullone passante, oppure aumentare lo spessore locale (secondo piatto, collare flowdrill).
- I giunti ad attrito (precaricati EN 14399) richiedono coppia/precarico e superfici controllate. Un precarico nominale dentro un foro maschiato in lamiera sottile è da evitare finché non c'è il dato del NA italiano sulla 5.9.3.

### Gaps
- Testo reale della EN 1993-1-8:2024 §5.9.3 (formule e Lt minimo) e scelta del National Annex italiano: non trovati.
- Clausola della EN 1090-2 su fori filettati/maschiati e su giunti ad attrito (classi di superficie, coefficiente μ su zincato): non estratta. Il PDF SCI GN 5.08 non era leggibile come testo.
- Ajax ONESIDE e Molabolt: nessuna fonte raccolta in questo giro (resistenze, omologazioni ETA).
- Thread forming (rullatura con maschio a rullare) contro maschiatura in S355 3–20 mm: nessun dato numerico indipendente.
- Dadi a saldare: esclusi per definizione (si vuole togliere la saldatura), non ricercati.

## 2. Macchine combinate laser + maschiatura e qualità dei fori laser per bulloni secondo EN 1090-2

### Takeaway
La EN 1090-2 ammette fori fatti con taglio termico (laser/plasma), purché rispettino i requisiti di durezza locale e di qualità superficiale della clausola sul taglio (6.4, con riferimento a 6.6.3). Le macchine "combi" (punzonatrice-laser con maschiatura, laser tubo con flowdrill/maschiatura) esistono e sono mature, ma lavorano su lamiera fino a ~8 mm o su tubo.

### Cited Findings
- Il taglio laser, plasma o termico dei fori è accettabile se il foro finito soddisfa i requisiti locali di durezza e qualità superficiale della clausola 6.4 (con riferimento a 6.6.3). Diametri e tolleranze dei fori stanno nelle clausole 6.6.1 (fori normali, maggiorati, asolati) e 6.6.2 (tolleranza per bulloni precaricati). Le tolleranze funzionali di posizione, interasse, svergolamento e forma dei fori stanno nella tabella D.2.8 — [SCI/SteelConstruction.info GN 5.08](https://www.steelconstruction.info/upload/Wiki-Files/archive/1/16/20151125105032%21GN_5-08.pdf) (contenuto riportato dal riassunto di ricerca; il PDF non era estraibile come testo, quindi da verificare); [Steel Buildings in Europe](https://infoacier.be/images/Steel-Buildings-in-Europe/MSB07/54)
- Durezza del bordo tagliato: per acciai al carbonio S≥460 il bordo non deve superare 450 HV10. I processi che possono indurire il bordo (taglio termico, ma anche taglio meccanico e punzonatura) vanno verificati. Rimedi: preriscaldo o leggera molatura del bordo. Serve una qualifica del procedimento di taglio — [BIL-IBS, Cutting Procedure Qualification EN 1090](https://bil-ibs.be/en/node/1878) (fonte secondaria; da confrontare con la tabella della norma)
- Prima Power Combi: punzonatura fino a 300 kN, 1.000 colpi/min, laser 6 kW, con punzonatura, maschiatura, formatura, marcatura e taglio laser su 0,5–8 mm. Maschiatura automatica con utensile multi-maschio; formatura con cilindro servo-elettrico upforming da 200 kN — [Industrial Machinery Digest](https://www.industrialmachinerydigest.com/articles/prima-power-highlights-combination-machines-for-flexible-sheet-metal-fabrication); [Prima Power Combi catalog](https://pdf.directindustry.com/pdf/prima-power/combi/9328-863107.html)
- Salvagnini S1: unità di maschiatura elettrica opzionale fino a 6 maschi, laser fibra 2–3 kW, lamiere fino a 4.064×1.524 mm — [DirectIndustry, Salvagnini](https://www.directindustry.com/prod/salvagnini/product-15483-2836151.html)
- TRUMPF TruLaser Tube 7000: mandrino NC e cambio utensile a 4 posizioni; foratura laser del preforo e maschiatura in meno di 8 s a filetto. L'adattatore regge fino a 8 maschi, con flowdrill, maschiatura e foratura. Lo stesso pacchetto è disponibile dal 2018 sulla TruLaser Tube 5000 — [TRUMPF "Staying in the flow"](https://www.trumpf.com/es_ES/revista/staying-in-the-flow/); [TRUMPF TruLaser Tube 7000](https://trumpf.com/en_US/products/machines-systems/laser-tube-cutting-machines/trulaser-tube-7000-fiber); [TRUMPF PR 2018 TruLaser Tube 5000](https://www.trumpf.com/filestorage/TRUMPF_Master/Corporate/Press/Press_releases/2017_18/Machine_Tools/20180416_PR-TRUMPF-TruLaser-Tube-5000/20180416_PR_TruLaser_Tube_5000_EN.pdf)
- Con il TRUMPF a filettatura integrata la posizione del filetto è riferita al taglio laser dello stesso piazzamento (preforo laser + maschio): nessun ripiazzamento — [TRUMPF "Staying in the flow"](https://www.trumpf.com/es_ES/revista/staying-in-the-flow/)

### Inferences
- Per i pezzi da tubo/trave (nodi colonna) la strada più "industriale" è il laser tubo con flowdrill + maschio in macchina: niente saldatura, filetto allineato al taglio. Per i piatti 3–8 mm la punzonatrice-laser combi può maschiare in linea. Sopra i ~10–12 mm la maschiatura diventa un'operazione di foratrice/centro di lavoro dopo il laser.
- Per S235/S355 (sotto S460) il limite 450 HV10 citato da BIL-IBS non si applica alla lettera, ma la qualifica del procedimento di taglio resta un requisito di classe di esecuzione da gestire con il fornitore.

### Gaps
- Tabella dei fori EN 1090-2 §6.6.1 (gioco nominale: mio ricordo ≈ d+1 mm per M12–M14, d+2 per M16–M24, d+3 da M27; asole corte/lunghe) NON confermata da fonte primaria in questo giro.
- BLM (LT Free/LT8 con unità di maschiatura) e Bystronic: nessuna fonte raccolta.
- Tolleranza di diametro dei fori laser in 10–20 mm (conicità del taglio): non trovata.

## 3. Piegatura dei pezzi laser con incastri: raggio minimo per S355, distanza fori/asole dalla piega, scarichi, ritorno elastico, tolleranze, direzione di laminazione

### Takeaway
Per S355MC (EN 10149-2) i raggi interni minimi a 90° sono piccoli: 0,25t fino a 3 mm, 0,5t da 3 a 6 mm, 1,0t oltre 6 mm. S355JR/J2 da carpenteria (EN 10025-2), non specificamente "da formatura a freddo", richiede raggi più generosi (vedi Gaps). Fori e asole devono stare ad almeno ~2,5t+R dalla piega (asole lunghe 4t+R), le ali minime sono ~4t, e il ritorno elastico va compensato in macchina.

### Cited Findings
- S355MC, raggio interno minimo raccomandato per pieghe ≤90°: 0,25t (t ≤ 3 mm), 0,5t (3 < t ≤ 6 mm), 1,0t (t > 6 mm). Un singolo valore di prova può scostarsi fino al 30% — [Salzgitter Flachstahl, thermomechanically rolled](https://www.salzgitter-flachstahl.de/en/products/hot-rolled-products/steel-grades/high-strength-steels-for-cold-forming-thermomechanically-rolled.html); stesse fasce in [Kalmar, High yield strength steels](https://www.kalmarglobal.com/492a72/globalassets/media/262857/262857_11020.0004---High-yield-strength-steels.pdf)
- SSAB Domex 355MC dichiara valori più bassi (≈0,2t–0,3t a 90°, prodotto specifico; fasce di spessore da verificare sul datasheet) — [SSAB Domex 355MC](https://www.ssab.com/en/brands-and-products/ssab-domex/product-offer/355mc)
- Tata Ympress S355MC: piega a 180° con raggio 0,5t richiesto da EN 10149-2 e 0 garantito, prova trasversale alla direzione di laminazione. La direzione di laminazione conta: la prova di riferimento è trasversale — [Tata Steel Ympress S355MC datasheet](https://products.tatasteelnederland.com/sites/default/files/tata-steel-engineering-ympress-s355mc-high-strength-steel-datasheet-en.pdf)
- Distanza foro–piega: la regola più diffusa è 2,5t + R interno, misurata dal bordo del foro alla linea di piega (anche come regola CAD in Creo). Per asole lunghe 4t + R — [PTC Creo, Design Rules](https://support.ptc.com/help/creo/creo_pma/r7.0/usascii/sheetmetal/sheetmetaldesign/Set_Up/About_Design_Rules.html); [Fabcon DFM guide](https://fabcon.com/articles/?p=127)
- Valori alternativi: 2t dall'inizio del raggio ([The Fabricator](https://www.thefabricator.com/thefabricator/article/bending/design-tips-for-sheet-metal-bend-relief-small-holes-hole-distortion-near-bends-and-minimum-flange-widths)); 3t (guida Xometry, [Scribd](https://www.scribd.com/document/527284786/Xometry-DesignGuide-SheetMetal)); rischio di distorsione entro 3–4t ([Starfish Medical](https://starfishmedical.com/?p=10751))
- In piegatura in aria, le aperture devono stare ad almeno metà dell'apertura della V di matrice dalla linea di piega — [PCBWay bending DFM](https://www.pcbway.com/blog/Sheet_Metal/Sheet_Metal_Bending_DFM_Guide_to_Prevent_Warping_Tearing_and_Bending_Deformation_5c476b7f.html)
- Scarico di piega (bend relief): minimo t + R interno ([Fabcon](https://fabcon.com/articles/?p=127)); oppure larghezza 0,5t ([Proleantech](https://proleantech.com/?p=252660)); approfondimento in [Protolabs, bend relief](https://www.protolabs.com/resources/blog/bend-relief/)
- SendCutSend: i fori e le geometrie troppo vicini o dentro le "die lines" si deformano in piega; tenere i fori maschiati lontano dalle linee di matrice. Ala minima ≥ 0,5" oppure 4t (il maggiore). Fino a ~3,4 mm almeno il 50% della lunghezza di piega deve rispettare l'ala minima; a 4,75 e 6,35 mm il 100% — [SendCutSend capabilities tapping](https://sendcutsend.com/blog/capabilities-of-our-online-sheet-metal-tapping-service/); [SendCutSend bending design considerations](https://sendcutsend.com/blog/design-considerations-when-planning-sheet-metal-bends/)
- Fractory: ogni spessore ha raggio interno e ala minima propri (tabella di piegatura); i fori vicini alla piega vanno oltre la lunghezza d'ala minima — [Fractory CAD tips](https://fractory.com/?p=3439)
- Ritorno elastico: varia con lo snervamento e con il lotto, quindi non è costante. Le presse CNC calcolano la sovrapiega (es. 88° per avere 90°); la coniatura (bottoming) riduce il ritorno elastico rispetto alla piega in aria — [Facturee, bending basics](https://www.facturee.de/en/sheet-metal-bending-basics-tips/); [Fabcon tolerances](https://fabcon.com/articles/?p=1449)
- Tolleranze: ISO 2768-mK è il richiamo generale dominante per la lamiera. ISO 2768-2 risulta ritirata, con le tolleranze geometriche di default passate a ISO 22081:2021 — [Fabcon, ISO 2768-mK](https://fabcon.com/articles/?p=1449)

### Inferences
- Scegliere lamiera S355MC (EN 10149-2, laminata termomeccanica "da formatura a freddo") al posto di S355JR quando un pezzo va piegato. In ordine al laser, specificare la direzione di laminazione e mettere le pieghe critiche trasversali alla laminazione.
- Incastri sottosquadra: le linguette che restano nel piano del pezzo non vengono toccate dalla piega se stanno oltre 2,5t+R (e fuori dalla mezza V di matrice). Le linguette che attraversano la piega vanno evitate, oppure tagliate dopo la piega (con il laser tubo/3D o in seconda fase).
- Sopra i 10–12 mm la piega di un piatto S355 diventa un lavoro da pressa pesante con R ≥ 1t. Per i nodi spessi conviene spesso tagliare dal pieno (pezzi piani incastrati e imbullonati) invece di piegare.

### Gaps
- DIN 6935 (tolleranze di piega per acciaio piegato a freddo) e raggi minimi per S235JR/S355J2 da EN 10025-2 (usualmente più alti di quelli MC): nessuna fonte primaria trovata.
- Valori numerici di ritorno elastico per S355 in 3–20 mm: la tabella Xometry esiste ma il contenuto non era leggibile.
- Come sopravvivono i sottosquadri alla piega (deformazione delle feature nella zona plastica): nessuno studio specifico, solo la regola indiretta della distanza dalla piega.

## 4. Autoposizionamento / poka-yoke per il kit, catena delle tolleranze, effetti della zincatura a caldo su filetti e asole

### Takeaway
Linguette e asole di dimensione diversa, schemi di perni asimmetrici e giochi tarati sul processo rendono il montaggio univoco. La zincatura a caldo aggiunge zinco anche nei filetti: i fori maschiati e i dadi vanno ripassati maggiorati DOPO la zincatura, e le parti mobili e gli incastri vanno disegnati con giochi dell'ordine di 0,8–1,5 mm.

### Cited Findings
**Autoposizionamento / poka-yoke**
- Variare dimensione di linguette e asole così che un pezzo entri in un solo posto e in un solo verso — [SendCutSend, tab and slot](https://sendcutsend.com/blog/designing-sheet-metal-parts-with-tab-and-slots/); [SendCutSend, mastering tab and slot](https://sendcutsend.com/blog/mastering-tab-and-slot-design-for-efficient-metal-fabrication/)
- Schemi di perni asimmetrici per permettere fisicamente solo l'orientamento corretto (self-locating / self-fixturing) — [Fictiv](https://www.fictiv.com/articles/how-to-design-assemblies-to-be-self-locating-and-self-fixturing)
- Dimensioni delle linguette: larghezza ≈ 3–5t con gioco unilaterale 0,1–0,15 mm ([PCBWay](https://www.pcbway.com/blog/Sheet_Metal/Welded_Sheet_Metal_Parts_Design_Guidelines_a79851e3.html)). Linguette ≥ 2t (o 0,125") e asole larghe almeno t per evitare problemi al laser ([Protolabs, notches and tabs](https://www.protolabs.com/resources/blog/designing-sheet-metal-notches-and-tabs/))
- I rivestimenti vanno nel gioco: la verniciatura a polvere vale ≈ 2–3 millesimi di pollice per lato (≈0,05–0,08 mm). Su piano unico, la lamiera sottile flette troppo per autoposizionarsi in modo affidabile — [SendCutSend tab and slot](https://sendcutsend.com/blog/designing-sheet-metal-parts-with-tab-and-slots/)

**Zincatura a caldo**
- Lo zinco aumenta lo spessore dei filetti. I fori maschiati passanti che riceveranno un bullone zincato vanno ripassati maggiorati dopo la zincatura; conviene maschiare tutti i fori dopo, per evitare la doppia maschiatura e il rischio di filetti incrociati. I dadi si zincano grezzi e si maschiano maggiorati secondo ASTM A563 — [AGA, Threaded & moving parts](https://galvanizeit.org/designing-for-hot-dip-galvanizing/design-fabrication/threaded-moving-parts); [AGA, Oversized taps](https://www.galvanizeit.org/education-and-resources/resources/technical-faq-dr-galv/oversized-taps-used-with-galvanized-bolts)
- Dopo la ripassatura il filetto femmina resta nudo: la protezione arriva dallo zinco del bullone — [AGA, Overtapping allowances](https://galvanizeit.org/knowledgebase/article/overtapping-allowances)
- Maggiorazione indicativa: 0,020" (≈0,5 mm) per dado/foro con bullone zincato 3/4"-10 (Portland Bolt). Diametro del bullone zincato + 0,09–0,18 mm secondo una fonte, zinco sui filetti 2–6 mils (0,05–0,15 mm) secondo un'altra — [Portland Bolt FAQ](https://www.portlandbolt.com/technical/faqs/galvanized-nuts-tapped-oversize/); [hotdipgalvanizing.com](https://www.hotdipgalvanizing.com/technical-resources/overtapping-allowances-hot-dip-galvanized-fasteners)
- ASTM F2329 vieta la ripassatura ("thread chasing") dei filetti maschi zincati — [Portland Bolt](https://www.portlandbolt.com/technical/faqs/galvanized-nuts-tapped-oversize/)
- Parti mobili: gioco radiale ≥ 1/16" (1,5 mm); spigoli e superfici di cerniere adiacenti molati di 1/32" (0,8 mm); fori perno alesati di 0,8 mm dopo zincatura. Per filetti > 1,5" si può tagliare il maschio 0,8 mm sottomisura prima della zincatura — [AGA, Threaded & moving parts](https://galvanizeit.org/designing-for-hot-dip-galvanizing/design-fabrication/threaded-moving-parts)

### Inferences
- Per gli incastri sottosquadra zincati a caldo il gioco dell'incastro deve tener conto di zinco su entrambe le facce (ordine 0,1–0,2 mm per faccia sugli spessori strutturali; vedi Gaps per il valore EN ISO 1461) più eventuali colature. La regola AGA di 0,8–1,5 mm per le parti che devono scorrere è il riferimento prudente per gli incastri da montare a mano in cantiere.
- Strategia consigliata: zincare grezzo, poi maschiare/ripassare i fori filettati in officina (non in cantiere). In alternativa, usare bulloni passanti con dado zincato (maschiato maggiorato all'origine) ed evitare filetti femmina nel pezzo zincato.
- Catena delle tolleranze su un telaio da casa: con fori e asole laser referenziati nello stesso piazzamento (macchina combi/laser tubo), l'errore dominante diventa la piega (ritorno elastico) e la zincatura (distorsione termica, colature). Conviene mettere asole di regolazione in UNA direzione per nodo e fori normali sull'altro lato, così le tolleranze si assorbono senza forzare.

### Gaps
- Spessore minimo di zinco secondo EN ISO 1461 per spessore d'acciaio (il ~85 µm indicato per acciaio > 6 mm è il mio ricordo, non verificato in questo giro); distorsione da zincatura su piatti piegati sottili.
- Studio quantitativo di catena delle tolleranze per un telaio da edificio in kit: non trovato.
- Classi di superficie e coefficiente d'attrito per giunti ad attrito su acciaio zincato (EN 1090-2 Annex G): non estratti.

## 5. Fabbricanti italiani/lombardi (taglio+piega+maschiatura da STEP) e servizi online con le loro regole

### Takeaway
Fra i servizi online con regole pubblicate la più documentata è SendCutSend (USA, limiti stretti: maschiatura acciaio fino a 12,7 mm, zincato solo ≈1,9 mm). In Italia non ho trovato un portale con caricamento STEP e preventivo istantaneo che faccia anche la maschiatura; esistono officine con la catena completa (laser + piega + filettatura) da contattare con preventivo classico.

### Cited Findings
- SendCutSend: maschiatura su acciaio dolce 1,5–12,7 mm; zincato G90 solo 1,5–1,9 mm; +1–2 giorni lavorativi, consegna in 6–7 giorni lavorativi; non si possono tappare i fori prima della verniciatura a polvere, quindi i filetti vanno ripassati — [SendCutSend capabilities](https://sendcutsend.com/blog/capabilities-of-our-online-sheet-metal-tapping-service/)
- Laserteile4you (Germania): caricamento DXF/STEP, scelta di materiale e lavorazioni, prezzo e ordine online, da prototipo a serie — [Industrial Production, Industry 4.0 sheet metal](https://www.industrial-production.de/forming/industry-4-0-in-sheet-metal-processing-calculate-laser-cuts-and-sheet-metal-bending-parts-online.htm)
- 3DEXPERIENCE Make (Dassault): rete di fornitori per lamiera in acciaio, inox e alluminio, pagina in italiano. Il preventivo istantaneo dichiarato riguarda stampa 3D/CNC; non è confermato per la lamiera — [3DS Make sheet metal](https://www.3ds.com/it/make/service/sheet-metal-service)
- Almacam (Torino) Almaquote/Webquote: software per i fabbricanti per gestire i preventivi online, non un portale pubblico — [Almaquote brochure](https://it.almacam.com/wp-content/uploads/2022/05/Almaquote_it_web-1.pdf)
- Officine italiane con laser + piega + filettatura (posizione lombarda NON confermata): Laserpoint Srl ([atoka](https://atoka.io/public/it/azienda/laserpoint-srl/99cba75cb1d8)); Nuovareda ([profilo](https://cdn.techpilot.com/public/137307/documents/ec96a358-5cb4-402d-8519-5e9c6e08d2a6/nuovareda_company_profile.pdf)); Laserlam ([presentazione](https://cdn.techpilot.com/public/124619/documents/60d4084b-dd92-446e-92ef-accce6aad141/presentazione_laserlam_2022_-_web.pdf)); Elletielle, che risulta in Veneto ([presentazione](https://cdn.techpilot.com/public/144966/documents/4e1b5be3-79b4-450a-9dd2-f3a967b9f9ec/presentazione%20lunga%20it%20-%20elletielle.pdf))

### Inferences
- Per spessori 3–20 mm in S355 (oltre i limiti di SendCutSend e della maggior parte dei portali "hobby/prototipo"), la via realistica è un'officina carpentiera certificata EN 1090 (classe di esecuzione EXC2 tipica per edifici), con laser piano + laser tubo con flowdrill/maschio + pressa piegatrice, che lavori da STEP e fornisca la qualifica del procedimento di taglio. Questo vale anche per la marcatura CE dei componenti strutturali.

### Gaps
- Weerg, Xometry Italia e Fractory: regole numeriche di maschiatura/piega per acciaio non recuperate. Weerg in particolare risulta orientata a CNC/stampa 3D; l'offerta lamiera non è verificata.
- Elenco verificato di carpenterie in Lombardia (Sondrio/Valtellina, Brescia, Bergamo, Lecco) certificate EN 1090 con laser tubo con maschiatura: non compilato. Prossimo passo: registri degli organismi notificati EN 1090 e siti Trumpf/BLM "reference customers" in Italia.
