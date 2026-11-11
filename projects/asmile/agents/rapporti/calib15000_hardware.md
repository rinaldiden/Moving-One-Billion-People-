# Calib 15.000 unita' - angolo HARDWARE: comprare o fare (2026-11-09)

Solo analisi sul Mac. Nessun Pi toccato. Prezzi e specifiche solo da pagine primarie; dove la pagina non li da: NON VERIFICATO.

## Risposta corta
1. Un modulo "gia' calibrato" esiste (Luxonis OAK, Stereolabs ZED, RealSense), ma NESSUNO ha la nostra baseline da 200 mm. Con baseline piccola la depth a 5 m peggiora di 3-5 volte. Non rispetta il target (<=2% sotto 5 m).
2. Il "gia' calibrato in fabbrica" risolve il problema solo se la calibrazione resta valida. Anche Luxonis dice che i moduli senza scatola (FFC) vanno ricalibrati dopo il montaggio, e offre una "Dynamic Calibration" a runtime per le sole estrinseche.
3. La strada piu' semplice e replicabile: costruire NOI una barra rigida con le 2 camere e calibrarla UNA volta in fabbrica (dima fissa, 2 minuti), non in RSA. In RSA zero calibrazione; solo un auto-controllo software (drift_monitor) che dice "ok / chiama assistenza".

## 1. Moduli stereo pronti: confronto (fonti primarie)
| Modulo | Baseline | Shutter | Precisione dichiarata | Tenuta | Prezzo listino | Fonte |
|---|---|---|---|---|---|---|
| Luxonis OAK-D Pro W (PoE) | 75 mm | OV9282 global | <2% sotto 3.5 m; <4% a 3.5-6.5 m; <6% a 6.5-9 m | M8 con tappo "per waterproofing"; nessun IP dichiarato; vibrazioni testate EN 60068-2-6 | USD 529 (singola) | https://docs.luxonis.com/hardware/products/OAK-D%20Pro%20W ; https://shop.luxonis.com/products/oak-d-pro-w ; https://docs.luxonis.com/hardware/products/OAK-D%20Pro%20PoE |
| Luxonis OAK-D SR | 20 mm | OV9782 global | ideale 10 cm-1 m | non dichiarato | non in pagina doc | https://docs.luxonis.com/hardware/products/OAK-D%20SR |
| Luxonis OAK-D LR | 5/10/15 cm (3 opzioni) | non dichiarato in doc | teorica <2% fino a 8.3 m a 60 deg HFOV, con sub-pixel | IP65 (pagina shop) | USD 779 | https://docs.luxonis.com/hardware/products/OAK-D%20LR ; https://shop.luxonis.com/products/oak-d-lr |
| Luxonis OAK-D Lite | non in pagina | non in pagina | non in pagina | non in pagina | USD 269 | https://shop.luxonis.com/products/oak-d-lite-1 |
| Stereolabs ZED 2i | 120 mm | ROLLING (sincronizzato) | <0.8% a 2 m, <4% a 12 m (lente larga) | IP66 | non in pagina | https://docs.stereolabs.com/docs/products/cameras/zed/specifications |
| Stereolabs ZED Mini | 63 mm | rolling | <1% a 2 m, <1.8% a 4 m | nessuna | non in pagina | stessa pagina |
| Intel/RealSense D435 | NON VERIFICATO (pagine Intel non raggiungibili) | NON VERIFICATO | NON VERIFICATO | - | - | RealSense e' ora una societa' autonoma dal 11/07/2025: https://www.intelcapital.com/realsense-completes-spin-out-from-intel-raises-50-million-to-accelerate-ai-powered-vision-for-robotics-and-biometrics/ |
| Arducam stereo OV9281 (pre-allineata) | pagina non raggiungibile (403) | OV9281 global | NON VERIFICATO | NON VERIFICATO | NON VERIFICATO | https://www.arducam.com/product/arducam-1mp-stereo-camera-for-raspberry-pi-nvidia-jetson-nano-xavier-nx-dual-ov9281-monochrome-global-shutter-camera-module/ (403); versione wide-angle segnalata come discontinuata (ricerca web) |

Calibrazione di fabbrica Luxonis: "La maggior parte delle OAK e' calibrata prima della spedizione (eccetto la linea Modular); il risultato e' scritto nella EEPROM." Nessuna cifra di precisione della calib; la pagina dice anche che i moduli FFC vanno ricalibrati dopo il montaggio. Fonte: https://docs.luxonis.com/hardware/platform/depth/calibration/ . La Dynamic Calibration aggiorna solo le estrinseche a runtime (stessa pagina). (La pagina https://docs.luxonis.com/hardware/platform/deploy/dynamic-calibration/ ha dato 404: NON VERIFICATO nei dettagli.)

Prezzo a 15.000 pezzi: NESSUN fornitore lo pubblica. Luxonis scrive solo "Large order?" e rimanda al commerciale. NON VERIFICATO: serve una richiesta (bozza email, parte solo col tap di Daniele).

## 2. Perche' i moduli pronti non bastano per noi
Errore di depth: dZ = Z^2 * d / (f * B), con d = errore di disparita'.
Esempio a Z=5 m, d=0.25 px (sub-pixel), 1280 px di larghezza (calcolo mio, ipotesi; f derivata dalla HFOV):
- Nostra #001: B=0.200 m, f~930 px (valore dalle note di progetto) -> dZ ~ 3.4 cm = 0.7%.
- OAK-D Pro W: B=0.075 m, HFOV 127 deg -> f ~ 320 px -> dZ ~ 26 cm = 5%. Coerente col "<4%" dichiarato da Luxonis a 3.5-6.5 m.
- OAK-D LR 15 cm: la doc dice <2% fino a 8.3 m a 60 deg: buona, ma USD 779, ed e' un oggetto USB con VPU che non ci serve (il depth lo facciamo sul Pi/Mac).
Quindi: tra i pronti solo OAK-D LR (150 mm) e ZED 2i (120 mm, ma rolling shutter e pensata per GPU NVIDIA/SDK propria) si avvicinano. Entrambi: prezzo molto sopra le 2 OV9281 (nostro costo camere: NON VERIFICATO, pagina Inno-Maker 404), fornitore unico, SDK proprietario, USB invece di CSI (perderemmo lo stesso t_ms e rpicam --sync del nostro metodo unico di timestamp).

Rischio fornitore: Luxonis e ZED sono aziende piccole; RealSense appena uscita da Intel (cambio di gestione 2025). Un solo fornitore per 15.000 unita' = rischio alto di fine produzione/prezzo.

Vibrazioni/acqua: l'unico dato esplicito e' IP66 (ZED 2i) e IP65 (OAK-D LR). OAK-D Pro: vibrazione EN 60068-2-6 testata, IP non dichiarato. Per una bici su strada in RSA, IP65 e' sufficiente; ma va chiuso in una scatola nostra comunque.

Integrazione Pi 5: OAK e ZED sono USB: ok sul Pi 5 ma richiedono depthai/ZED SDK (ZED SDK ufficiale: Windows, Linux, Jetson; Pi non citato nella pagina: NON VERIFICATO).

## 3. Alternativa: supporto rigido nostro
Il punto vero: la calibrazione si perde se le camere si muovono tra loro (vibrazione, urti, dilatazione termica, lente M12 che gira). Per tenerla:
- Barra unica (alluminio CNC o estrusione + due fresature) con le 2 sedi camera lavorate insieme, 2 spine di riferimento, viti con frenafiletti. Le lenti M12 vanno bloccate con grano o colla UV dopo la messa a fuoco in fabbrica.
- Alternativa piu' semplice: UNA sola scheda con 2 sensori (come Camarray di asmile-logger001): la baseline la fissa il PCB, non c'e' sync da gestire. Ma ha 1 solo CSI (SBS 2560x800) e le camere a 200 mm sono quelle che gia' abbiamo; costo e disponibilita' Arducam: NON VERIFICATO (pagine 403).
- Costo supporto (STIMA mia, NON VERIFICATO da fonte): barra CNC alluminio 200 mm a 15.000 pz ~ 6-12 EUR/pezzo; estrusione + 2 staffe stampate ~ 3-6 EUR; plastica PA-GF stampata/stampata a iniezione a volume ~ 1-3 EUR ma flette e dilata di piu' (da evitare per la calibrazione). Serve preventivo di un'officina (bozza al fornitore, tap di Daniele).
- Un tubo/profilo cavo e' piu' rigido a parita' di peso: a 200 mm la flessione e' trascurabile se il pezzo e' pieno; il rischio vero e' la dilatazione termica (alluminio ~23 um/m/K: su 200 mm, 30 K = 0.14 mm; sul disparita' a f~930 px e' <1 px come variazione di baseline ma cambia la scala di appena lo 0.07%, accettabile). Calcolo mio.
- Cosa NON risolve: le rotazioni di una camera rispetto all'altra (pochi decimi di grado = decine di pixel in dy). Per questo serve la calib di fabbrica una tantum: il supporto rigido fa si' che resti valida, non che sia gia' giusta.

## 4. Raccomandazione (la piu' semplice e replicabile)
1. NON comprare moduli pronti: baseline troppo corta, fornitore unico, prezzo 15k non pubblico. Eccezione da valutare solo se una richiesta di offerta mostra OAK-D LR sotto ~300 EUR a volume (improbabile, listino USD 779).
2. Fare una barra rigida con 2 OV9281 + lenti bloccate + CSI sync (stesso hardware di #001, ma meccanicamente bloccato).
3. Calibrare in FABBRICA con una dima fissa (tabellone ChArUco su parete a 1-3 m, posizione nota, 2 minuti, nessun operatore RSA): riusa logger/depth/calib_charuco_dual.py e validate.py. Il JSON esce come calib_<serial>.json e va nella partizione /data dell'unita' + backup in cloud/repo per numero di serie. Mai fallback tra unita'.
4. In RSA: zero metro, zero laptop. Solo drift_monitor (software, file esistente logger/depth/drift_monitor.py) che segnala "calib ok / fuori tolleranza"; se fuori, si rilancia selfcalib_essential.py in automatico sui frame di guida, e se non rientra l'unita' torna alla dima.
5. Collaudo: ogni unita' prova la dima e scrive dy per le 9 zone (<1 px) e un test a distanza nota (1 target a 3 m). Criterio di uscita: depth <=2% sotto 5 m, altrimenti scarto/ricalibra.

## Rischi
- Il costo reale di una dima di fabbrica per 15.000 pezzi (tempo-macchina, ~2 min x 15.000 = 500 ore) e' da verificare con un assemblatore: NON VERIFICATO.
- Fuoco M12 e lenti che si muovono: va bloccato con colla UV; test d'urto/vibrazioni non fatto.
- Il supporto rigido non c'e' ancora: si puo' provare con un pezzo stampato in PA-CF e confrontare dy prima/dopo un giro: serve un unita' #001 (Daniele).
- Rolling shutter ZED e baseline piccole sono scartate; ma se il target "<=2% sotto 5 m" si rilassasse a 4%, OAK-D Pro W diventerebbe accettabile: decide Daniele.

## Domande aperte (da inviare, non partono da sole)
- Luxonis: prezzo a 15.000 pz di OAK-D LR e di un modulo OAK-FFC senza scatola; tolleranza di calib in EEPROM.
- Inno-Maker / Arducam: prezzo a volume di 2 OV9281 + obiettivo M12, disponibilita' a montare in barra rigida con lenti bloccate.
- Officina CNC: preventivo barra 200 mm in alluminio, tolleranza delle sedi.
