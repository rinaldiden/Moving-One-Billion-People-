# Calibrazione per 15.000 unita': metodo "quasi zero" (2026-11-09)

Sintesi delle tre strade (fornitore, progetto online, rete robusta) con i VETO dei contro-agenti.
Tutti e tre hanno dato PASSA_CON_CONDIZIONI. Tutti e tre dicono: "zero calibrazione" non e' vero. Cambia chi la fa e quando.

## 1. La soluzione in 3 righe per Daniele
1. Il fornitore consegna una barra stereo monoblocco da 200 mm, calibrata per numero di serie. Il file di calibrazione lo leggiamo noi.
2. In bici un software tiene la calibrazione aggiornata da solo (dy e rotazione dai match, scala e d0 dal movimento con l'encoder ruota). Se la deriva supera la soglia, la depth non frena e non sterza piu'.
3. Noi facciamo solo un collaudo a campione per lotto. Niente stazione in fabbrica, niente cartello in RSA. Il tabellone A3 serve una volta sola, come prova di tutto questo.

Onesta': non e' "noi non calibriamo niente". E' "noi non calibriamo pezzo per pezzo".

## 2. Chi fa cosa
- Fornitore: barra monolitica rigida, baseline 200 mm, lenti con tolleranze strette, calibrazione per pezzo, file seriale (OpenCV), report per pezzo, descrizione della dima, diritto per noi di ricalibrare.
- Software in bici: calibrazione nominale di lotto in partenza; stadio 1 dy/pitch/roll con prior stretti (stile selfcalib_essential.py); stadio 2 focale e d0 da coppie di frame a ~1 m con encoder ruota; drift_monitor continuo; depth "non validata" finche' non e' stabile.
- Noi: collaudo a campione (muro-test, dy su 9 zone, profondita' a 2/3.5/5 m), banco fisso su pochi pezzi, gate in lavagna.
- RSA: niente. Il ricambio arriva calibrato e si riconverge da solo in marcia.

## 3. Cosa cambia rispetto al metodo con stazione nostra
- Via: stazione pan/tilt, modulo oro, 2 min per modulo, cartello fisso in ogni RSA.
- Resta: collaudo a campione (un banco semplice, non una linea).
- Nuovo: dipendenza dal fornitore (rischio con un solo fornitore a 15.000 pezzi) e un software di auto-registrazione da finire e validare.
- Dai rapporti: il software da solo non basta. Da nominale il centro arriva a 1-2% mediano, i bordi a 3-4% mediano e ~11% p90 (rapporto progetto). Il fornitore da solo non garantisce il 2% (Leopard ESP870 dichiara 5% a 200 mm, solo USB). Insieme si coprono: la calibrazione di fabbrica toglie l'errore grosso, il software tiene il resto.
- La strada "rete robusta" da sola e' scartata: SGBM e FoundationStereo tollerano dy fino a 4 px, ma 1 px di d0 vale 2% a 5 m e 0.1 gradi di yaw circa 4.5% a 5 m. Nessuna rete lo vede. Si tiene solo l'idea della rete come maestro offline sul Mac.
- Correzione dal VETO: il piano strada misura B/h, non f*B, quindi non da' la scala. La scala viene dalla focale per lotto (specifica + campione) e dal moto con encoder.

## 4. Costo per unita'
- Fornitore custom: NON VERIFICATO (prezzo e MOQ non pubblici). Riferimenti citati: Leopard LI-OX05C1S-ST80-MIPI 299 USD a catalogo (80 mm, non e' il nostro 200 mm, letto solo da ricerca web).
- Calibrazione in fabbrica nostra: 0 minuti. Collaudo a campione: STIMA, pochi minuti per pezzo campionato, non per ogni pezzo.
- Convergenza in bici: circa 6-10 minuti di guida (rapporto progetto: 115 coppie in ~11 min danno sd 1.2% su f; 30 coppie in ~1.5 min danno 2.7%).
- Sovrapprezzo per specifica stretta: NON VERIFICATO, da chiedere nella richiesta d'offerta.

## 5. Primo passo concreto
Tutto sul Mac finche' non c'e' un "vai" di Daniele. Niente va inviato senza il suo tap.

A. Bozza richiesta d'offerta (parte solo col tap di Daniele). Prima e-con Systems (sales@e-consystems.com), poi variante per Leopard Imaging.

> Oggetto: Richiesta campione 10 pezzi, modulo stereo MIPI su misura, baseline 200 mm
>
> Buondi, siamo Asmile: bici a trazione umana con guida assistita per Persone con disabilita'. Cerchiamo un modulo stereo con: baseline 200 mm in barra monolitica rigida; global shutter, 1280x800 o simile; MIPI CSI-2 su Raspberry Pi 5 (driver libcamera/V4L2 e sincronizzazione hardware, chiediamo cosa avete); calibrazione di fabbrica per numero di serie, in file leggibile (OpenCV) o EEPROM, con report per pezzo; descrizione della vostra dima e del metodo; diritto per noi di ricalibrare. Target: errore di profondita' entro 2% sotto 5 m e dy sotto 0.5 px su tutta l'immagine, anche ai bordi. Sappiamo che a catalogo non esiste un modulo MIPI a 200 mm: chiediamo fattibilita', MOQ, prezzo a 10, 100 e 15.000 pezzi, lead time, tolleranze (focale, centratura lente-sensore, angolo relativo tra sensori), stabilita' con vibrazioni e temperatura.
>
> Con profonda gratitudine 🙏 Daniele MM

B. Criterio di stop prima del campione: se i 10 pezzi non reggono vibrazione e ciclo termico con dy < 0.5 px, la strada fornitore e' chiusa o si cambia barra. Decidere prima chi paga i test.

C. Prova di domani con il tabellone A3 (logger/depth/board_charuco_A3_10x7_38mm.pdf) su #001 e logger001, ognuno con la sua calibrazione, mai incrociate:
- Il tabellone fa da verita' indipendente: NON da calibrazione per il prodotto, ma da giudice dell'auto-registrazione.
- Ripresa a distanze note col metro (2, 3.5, 5 m) e con il tabellone ai lati, per misurare i bordi.
- Confronto: stima software (dy, f, d0 da moto) contro il tabellone. Punti mai usati nel fit.
- Per #001 prima chiarire l'unita' di enc_wheel_cum e rifare la scala con la ruota misurata (1.576 m/giro) senza GPS.
- Ripetere su una seconda corsa e confrontare f e d0 (stabilita').
- Per il logger (Camarray SBS, niente encoder ne' GPS): la scala dal moto non c'e'. Serve un'altra fonte (IMU + video o ruota BT): NON VERIFICATO, da decidere.
- Dati e video restano locali.

D. In parallelo: test eseguibile su cosa fa la bici quando la depth e' non validata (velocita' limitata, niente frenata o sterzata da depth).

## 6. DA FIRMARE per Daniele
- Passare a "calibrazione di fabbrica del fornitore + auto-registrazione + collaudo a campione" al posto della stazione nostra.
- Tap per la bozza e-con e per la variante Leopard.
- Gate ai bordi: restano +-2% sotto 5 m o si allargano (oggi i bordi sono 3-4% mediano)?
- Soglia di drift (proposta 0.5 px) sopra cui la depth non alimenta freno e sterzo, e il degrado a "solo freno sicuro".
- "Vai" per eventuali nuove registrazioni su #001 (tocca il Pi). Niente su strada senza gate della lavagna e firma nel DECISION_LOG.
- Chi paga i test di vibrazione e temperatura sul campione.

## 7. NON VERIFICATO
- Prezzi, MOQ, lead time e fattibilita' a 15.000 pezzi di qualunque modulo custom.
- Esistenza di un modulo MIPI + global shutter + 200 mm (nessuno trovato a catalogo). Leopard 200 mm (ESP870) e' USB, 5% di accuratezza dichiarata.
- Driver Pi 5 e sync hardware dei moduli e-con e Leopard (pensati per Jetson).
- Basler Stereo ace, Arducam, e-con STEEReoCAM, Leopard 80 mm: solo snippet o pagine non lette in dettaglio.
- Formato di consegna della calibrazione (EEPROM o file).
- Stabilita' meccanica della barra 200 mm in bici (vibrazioni, caldo).
- Scala assoluta da encoder senza GPS (nei test e' stata ancorata al GPS: il bias di f -2.3% contiene l'errore GPS).
- d0 da odometria: solo simulazione nel rapporto "rete", un solo percorso nel rapporto "progetto".
- Bordi con metro: la verita' dei bordi era la calib attuale, mai validata ai bordi.
- dy sub-pixel: p95 3.4 px (pipeline) contro il gate p95 < 1 px, non soddisfatto.
- Dispersione tra pezzi: servono 3-5 monoblocchi veri.
- Non ho rifatto i conti dei tre rapporti: li ho presi come dichiarati, con i VETO.

Rapporti di origine: calib_zero_fornitore.md, calib_zero_progetto_online.md, calib_zero_rete_robusta.md (stessa cartella).
