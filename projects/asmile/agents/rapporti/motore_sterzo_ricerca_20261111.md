# Motore sterzo #001: ricerca sostituto (2026-11-11)

Autore: asmile-retrofit. Stato: PROPOSTA, da passare al costi-scettico; la spesa la decide Daniele.
Regola: solo dati da pagine produttore/rivenditore leggibili; dove manca, "non trovato". Le righe DERIVATO sono calcoli miei, non dati di scheda.

## 0. Limite delle fonti (leggere prima)
- Le pagine di flipsky.net hanno risposto sempre HTTP 429 (rate limit) durante la ricerca: la scheda Flipsky originale e il suo disegno quotato NON sono stati letti. I dati del 6354 vengono dalla vetrina ufficiale Flipsky su made-in-china (flipskycn) e da rivenditori che copiano la scheda. Rifare la lettura di flipsky.net a freno tolto.
- Le schede CubeMars (cubemars.com) sono state lette direttamente (prezzo, coppie, pesi). I disegni 2D con i fori NON sono stati trovati.
- MyActuator e Steadywin: nessuna scheda ufficiale leggibile, solo rivenditori (dichiarato per riga).

## 1. Quote di montaggio del Flipsky 6354 (motore attuale)
| Dato | Valore | Fonte |
|---|---|---|
| Diametro corpo | 63 mm (un rivenditore: 63.4) | [Flipsky su made-in-china](https://flipskycn.en.made-in-china.com/product/iLkYWCBuXEVh/China-Flipsky-Battle-Hardened-190kv-6354-BLDC-Motor-for-Electric-Skateboards-RC-Cars.html), [rcreviews.lt/Banggood](https://www.rcreviews.lt/rc-item/hglrc-flipsky-6354-190kv-2450w-brushless-sensored-motor-shaft-8mm-for-electric-skateboard-rc-models-11444.html) |
| Lunghezza corpo | 54 mm (Flipsky); 57 mm (Banggood/Newegg): CONFLITTO, misurare sul pezzo | idem |
| Albero | 8 mm tondo, 24 mm (variante lunga 30 mm); la versione "Battle Hardened" ha anche D-shaft 10 mm, 24 mm | made-in-china Flipsky; rcreviews.lt |
| Chiavetta/piatto | 3x1.5 mm (Banggood) oppure 3x3x15 (Amov/ibspot): CONFLITTO. D-shaft solo sulla Battle Hardened | rcreviews.lt, [AmovRobotlab](https://amovrobotlab.com/products/flipsky-6354-190kv-2450w-brushless-belt-motor-motors) (via ricerca) |
| Fori flangia | filetto M4 (viti consigliate M4x8, non incluse). Interasse/bolt circle: NON TROVATO in nessuna fonte | made-in-china Flipsky; rcreviews.lt |
| Indicazione forum (NON verificata, parla di 63xx foil) | 4 fori su cerchio Ø44 a 45 gradi, "forse 27x21": chi scrive dice di non essere sicuro | [foil.zone](https://foil.zone/t/flipsky-6384-motor-bolt-pattern-on-cedrus-foil-drive-integrated-mast-puck-adapter/25887) |
| Peso | 0.56 kg (Banggood) / 0.72 kg (Battle Hardened) | idem |
| Hall | PCB 120 gradi, connettore JST-ZH 6 pin passo 1.5 mm | Flipsky (via ricerca, flipsky.net non letto) |
| Elettrico | 190 KV (140 su richiesta), 0.053 ohm, 14 poli, 65 A max, "7 Nm max" | made-in-china Flipsky |

Nota di coerenza: Kt = 8.27/KV = 0.0435 Nm/A a 190 KV (DERIVATO). "7 Nm" implicherebbe 0.108 Nm/A: è un numero di marketing, non raggiungibile. A 45 A il 6354 dà ~1.96 Nm (DERIVATO); con 1:5 sono ~9.8 Nm al piantone prima delle perdite: coerente col sintomo "poca coppia".
Conseguenza di mestiere: per il montaggio, l'unica via sicura è MISURARE la flangia del pezzo attuale col calibro (interasse fori, pilota/centraggio, lunghezza albero) prima di ordinare adattatori.

## 2. Candidati

Legenda: coppia = al motore/attuatore (uscita). Al piantone con la riduzione conica 1:5 attuale (da verificare, BOM) moltiplicare x5 (rendimento ignorato, ~0.9 reale). Fabbisogno: 5 rpm al piantone (30 gradi/s), 3 Nm di attrito, margine 25-40 Nm.

### Famiglia (a): 63xx a KV basso, stessa flangia da 63 mm
| # | Modello | Dati di scheda | Sensori/VESC | Al piantone (1:5) DERIVATO | Fonte |
|---|---|---|---|---|---|
| A1 | Flipsky 6374 140 KV, 3600 W | 63 mm x 74 mm, albero 8 mm, "9.5 Nm max", prezzo non trovato | hall, VESC ok (usato con VESC, sensor wires) | Kt 0.059 -> a 45 A 2.7 Nm -> 13 Nm | [Hobbywater](https://www.hobbywater.com/products/6374-140kv-brushless-motor-3600w-max-8-16s-ip58-ceramic-bearing) (via ricerca; pagina 429), [racer.lt](https://racer.lt/item/hglrc-flipsky-r-6374-190kv-3250w-brushless-sensored-motor-shaft-8mm-for-electric-skateboard-rc-car-14614.html) |
| A2 | Flipsky 6384 (4000 W) | 63 mm x 84 mm, 4-13S, hall, KV 190 listato; peso/prezzo non trovati | hall, VESC ok | Kt 0.0435 (190 KV) -> circa 2 Nm a 45 A -> 10 Nm | [Flipsky](https://Flipsky.net/collections/e-skateboard/products/bldc-belt-motor-6384-4000w-for-electric-skateboard) (via ricerca) |
| A3 | Flipsky 63100 140/170/190 KV | 63 mm x 100 mm, 100 A max, "10 Nm" a impulsi, hall 5 V | hall, VESC ok | 140 KV a 45 A 2.7 Nm -> 13 Nm | [Flipsky](https://flipsky.net/products/63100-motor-190kv-5000w) (via ricerca) |

Verdetto famiglia (a): NON risolve. Un KV più basso alza solo Kt (0.043 -> 0.059 Nm/A, +36%); la coppia continua resta ~2-3 Nm perché è legata al volume e alla corrente. Per 30 Nm al piantone servirebbero ~100 A. Cogging e scatti restano (stessi hall, stessa meccanica). Non ho trovato 63xx sensored sotto 140 KV. Prezzi non trovati sui link letti (6354: 87 EUR da Banggood come riferimento).

### Famiglia (b): 63xx/BLDC con riduttore planetario integrato
- Nessun motore Flipsky/Maytech 63xx con planetario integrato trovato (ricerca esplicita: solo outrunner da cinghia). 
- Montaggio possibile: planetario NEMA23 con foro sul sole lavorato (suggerimento di un utente ODrive, NON prodotto verificato) [ODrive forum](https://discourse.odriverobotics.com/t/odrive-d5065-d6374-planetary-gearboxes/5701). Lavoro meccanico su misura e outrunner con carcassa rotante: sconsigliato.
- B1 gearmotor BLDC 24 V OMC M82B200-24P-30S/G82-30S1: 15 Nm nominali, 100 rpm, 30:1, hall, 10 poli, Ø82 x 181 mm, albero 19 mm con chiavetta, 4.24 kg, documentato con ODESC 4.2 [roboflock docs](https://roboflock-documentation.readthedocs.io/en/latest/hardware_docs/motors.html). Scartato: 24 V (non 48), 4.2 kg, ingombro, albero 19 mm: rifà tutta la meccanica. Non è nemmeno verificato con VESC HW60.
- B2 RS PRO 500 W 48 V planetario 100:1: scheda RS incoerente (9.8 kg, albero 6 mm, tolleranze in kgf-cm) -> SCARTATO come inaffidabile, non lo propongo.
- Verdetto (b): esiste solo come "motore industriale hall + planetario" pesante; i veri integrati compatti sono gli attuatori di (c).

### Famiglia (c): attuatori robotici (motore + planetario + encoder + driver, controllo CAN)
Dati CubeMars da [tabella comparativa CubeMars](https://www.cubemars.com/goods-1151-AK80-8.html) e pagine prodotto [AK80-9](https://www.cubemars.com/goods.php?id=982), [AK80-64](https://www.cubemars.com/goods.php?id=1143).

| # | Modello | Coppia nom./picco | Giri nom. a 48 V | Corrente nom./picco | Encoder | Dim. / peso | Prezzo | x5 al piantone (DERIVATO nom./picco) |
|---|---|---|---|---|---|---|---|---|
| C1 | CubeMars AK80-8 KV60 (8:1) | 10 / 25 Nm | 243 rpm (vuoto 360) | 6.9 / 21 A | doppio: 14 bit motore + 15 bit uscita | Ø98 x 43.9 mm, 575 g | 469.90 USD | 50 / 125 Nm |
| C2 | CubeMars AK80-9 KV100 (9:1) | 9 / 18 Nm | 390 rpm (vuoto 533) | 10.3 / 22.3 A | singolo 14 bit | Ø98 x 38.5 mm, 485 g | 479.90 USD | 45 / 90 Nm |
| C3 | CubeMars AK60-39 V3.0 KV80 (39:1) | 24 / 72 Nm | 70 rpm (vuoto 98) | 4.5 / 17 A | doppio | Ø79 x 67 mm, 750 g | non trovato (pagina prodotto non letta) | 120 / 360: troppo; usare diretto |
| C4 | CubeMars AK80-64 KV80 (64:1) | 48 / 120 Nm | 23-48 rpm (vuoto 37-75) | 7 / 19 A | singolo 14 bit | Ø98 x 61.9 mm, 850 g | 889.90 USD | solo diretto sul piantone |
| C5 | MyActuator RMD-X8-P36-60 (36:1) | picco 60 Nm; nominale, giri, peso, dimensioni: non trovato su pagina leggibile (un rivenditore dice 25 Nm nom., 40 rpm: NON VERIFICATO) | n.t. | n.t. | predisposto secondo encoder in uscita; tipo non trovato | n.t. | 554.40 EUR, "in stock" (robotshop EU, 2026-11-04) | n.t. |
| C6 | Steadywin GIM8108-8 (8:1) | 7.5 nom. / 22 Nm stallo (solo rivenditori, NON VERIFICATO), 48 V | n.t. | n.t. | n.t. | 375-378 g (rivenditori discordi, uno dice 1 kg) | circa 85 USD segnalato, in backorder: sospetto, non affidabile | 37 / 110 Nm |

AK70-10 (8.3/24.8 Nm, 10:1, Ø89 x 50 mm, 621 g) e AK10-9 V3.0 (18/53 Nm, 940 g, Ø98 x 61.7) sono nella stessa tabella CubeMars, utili come varianti: AK10-9 dà più coppia nominale a pari ingombro.

Cosa cambia nel montaggio e nel controllo (famiglia c):
- Controller: NON è il VESC. L'AK ha driver integrato (48 V nominale, 18-52 V consentiti, 10 A nom./30 A max, CAN 1 Mbps, encoder motore 21 bit nel modulo driver) [Manuale driver CubeMars V3.0.0](https://www.cubemars.com/images/file/20250207/1738921575887499.pdf). Il VESC HW60 resterebbe in avanzo (o in uso per altro). Modi: "servo" e "MIT". Dalla ricerca: il servo mode CubeMars è descritto come basato su VESC e risponde solo con frame CAN estesi (snippet del sito CubeMars, pagina non riaperta: NON VERIFICATO). Config con R-Link/CubeMars upper computer.
- Pi: serve un'interfaccia CAN (HAT tipo MCP2515/Waveshare). Se #001 ne abbia già una: NON TROVATO (non ho acceduto al Pi). Va scritto un nuovo driver (posizione/coppia limitata) al posto del codice VESC UART di sterzo.
- Meccanica: l'AK ha Ø98 con flangia di uscita con fori propri: i fori 63 mm M4 del 6354 NON coincidono. Disegno 2D non trovato (CubeMars lo mette per modello sulla pagina prodotto; AK60-39 non l'aveva): chiedere a info@cubemars.com (bozza, parte solo col tap di Daniele). Serve piastra adattatrice + giunto sull'ingresso conico; l'albero 8 mm con chiavetta sparisce (uscita a flangia).
- Retro-guida: rapporto totale con bevel: C1 8x5=40:1, C2 45:1. Non retro-guidabile a mano da spento -> la Persona perde lo sterzo manuale se manca l'alimentazione. Serve decisione di sicurezza (limite di coppia, frizione/clutch, freno di emergenza). Con C1/C2 montati DIRETTI (8-9:1) la retro-guida resta buona ma coppia nominale 9-10 Nm, picco 18-25 Nm: sotto il target 25-40 nominale, ben sopra i 3 Nm di attrito.
- Disponibilità Europa: CubeMars spedisce dalla Cina (dazi/IVA, tempi da verificare); rivenditore UE trovato per AK80-64: mabrobotics.pl, circa 971 EUR (da ricerca, pagina 404 al fetch, non verificato). MyActuator: robotshop EU, in stock.

## 3. Raccomandazione
Il vero problema non è il KV: è che un 63xx con hall dà ~2-3 Nm continui e scatta a bassa velocità. La famiglia (a) è quindi scartata; (b) non ha prodotti buoni. Si risolve con un attuatore FOC con encoder (famiglia c).

1. SCELTA 1, meno meccanica da rifare: CubeMars AK80-8 KV60 (dual encoder) al posto del 6354 sulla conica 1:5. Perché: coppia 10/25 Nm al motore (circa 45/110 Nm al piantone con 1:5), 575 g (quasi come il 6354 a 560 g), encoder 14+15 bit = fluido a bassa velocità, 5 rpm al piantone = 25 rpm all'uscita, regime comodo. Alternativa a prezzo simile: AK80-9 (485 g, un solo encoder, non consigliato perché perde l'encoder di uscita). Costo 469.90 USD + driver incluso + R-Link.
   Resta da adattare: piastra flangia Ø98 -> alloggio conica, giunto uscita AK -> ingresso conica (albero 8 mm), HAT CAN sul Pi, nuovo modulo sterzo (CAN servo mode, limiti di coppia), decisione sicurezza retro-guida (40:1 totale). Le quote dell'AK80-8 (fori flangia) vanno chieste a CubeMars prima di ordinare.
2. SCELTA 2, se si accetta di togliere la conica (più lavoro meccanico, meno attrito e backlash): AK80-8 o AK10-9 DIRETTO sul piantone. AK80-8 diretto: 10 nom./25 picco Nm al piantone, retro-guidabile, un solo stadio. AK10-9 V3.0 (18/53 Nm, 940 g) se si vuole il margine 25-40 Nm.
Costo/beneficio per il costi-scettico: la cosa software (parametri VESC, flux, interp) è già stata tentata nei commit recenti (flux 2.3-5.4 mWb, interp 20/60) senza risolvere; la limitazione è fisica (Kt basso, hall a 6 stati).

## 4. Prima di ordinare (non fatto, serve il pezzo)
1. Calibro sul 6354 montato: interasse fori, centraggio, sporgenza e diametro albero, chiavetta (risolve i conflitti 54/57 mm e 3x1.5/3x3).
2. Verificare davvero il rapporto della conica (BOM dice "da verificare").
3. Chiedere a CubeMars il disegno 2D AK80-8 (e prezzo/spedizione UE) con bozza email (tap di Daniele).
4. Capire se il Pi ha già CAN.
