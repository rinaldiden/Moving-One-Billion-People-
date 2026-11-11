# Calib 15.000 unita' - strada "LA CALIBRA IL FORNITORE" (2026-11-09)

Solo ricerca sul Mac. Nessun Pi toccato, nessuna email inviata (la bozza in fondo parte solo col tap di Daniele).
Fatti solo da pagine/datasheet dei fornitori (URL sotto). Quello che non ho potuto leggere e' marcato NON VERIFICATO.

## Risposta corta
1. **Un modulo MIPI, global shutter, baseline 200 mm, gia' calibrato, a catalogo NON esiste** (tra i fornitori che ho trovato). Per averlo bisogna farselo fare su misura (OEM/ODM).
2. I due fornitori che gia' dichiarano per iscritto di poter cambiare la baseline sono **e-con Systems** (STEEReoCAM, 100 mm di serie, "baseline customization", lenti "pre-calibrated") e **Leopard Imaging** (datasheet di un loro stereo: "for BaseLine 200mm, we can provide the customization services"). Nessuno dei due, nelle pagine lette, dice COME consegna la calibrazione: va chiesto.
3. **Scelta di primo contatto: e-con Systems.** Motivo: e' l'unico con modulo stereo MIPI CSI-2, global shutter (2x OV2311, mono), lenti pre-calibrate, baseline "customizable" scritto sulla pagina del prodotto, contatto sales diretto e form di richiesta. Limite: oggi e' venduto per Jetson, non Pi 5 (lato Pi serve driver: da chiedere). Secondo: Leopard Imaging. Terzo (piano B, cambia architettura): Basler Stereo ace 200 mm, gia' calibrato, ma non MIPI.
4. Onesta': "il fornitore calibra" sposta il lavoro dalla nostra fabbrica alla loro, ma **non lo elimina**: la calibrazione resta valida solo se la barra e' rigida e non si muove in bici (vibrazioni, caldo). Per questo la specifica vera da chiedere e' rigidita' + test di accettazione a campione, non solo "calibrato".

## Tabella fornitori
| Fornitore / modulo | Baseline | Sensore / shutter | Interfaccia | Calib di fabbrica? come consegnata | Precisione dichiarata | MOQ / prezzo | Fonte |
|---|---|---|---|---|---|---|---|
| **e-con STEEReoCAM** | 100 mm di serie; "Baseline customization" in elenco personalizzazioni | 2x OV2311 mono, global shutter, 2x1600x1300 30 fps (da ricerca web, non letto direttamente) | MIPI CSI-2 2 corsie; pensato per Jetson. Pi 5: NON VERIFICATO | "pre-calibrated S-mount lens pair" (solo le lenti). Calib stereo + formato (EEPROM?): NON VERIFICATO | non in pagina | MOQ non pubblico; prezzo "sample price" solo nello shop | https://www.e-consystems.com/nvidia-cameras/jetson-agx-xavier-cameras/stereo-camera.asp ; https://www.cnx-software.com/2019/10/25/steereocam-is-a-3d-stereo-camera-for-nvidia-jetson-nano-tx2-agx-xavier-dev-kits/ |
| **Leopard Imaging** (famiglia stereo MIPI: LI-OX05C1S-ST80-MIPI-143H, LI-AR0144-MIPI-STEREO) | 80 mm (OX05C1S, global shutter 5 MP) e 70 mm (AR0144, da pagina prodotto). Datasheet del modello USB LI-ESP870-STEREO-M031: baseline 120 mm e riga "BaseLine 200mm" con accuratezza 5%/10%, e frase di personalizzazione a 200 mm (letto nel PDF scaricato) | OX05C1S GS; ESP870 = MT9M031 global shutter 1.2 MP (letto nel datasheet) | MIPI per i due citati; ESP870 e' USB 3.0 (non va su CSI) | Calibrazione: la pagina non la nomina. NON VERIFICATO | ESP870: 5% a 120 e 200 mm (condizioni non lette) | "sales@leopardimaging.com" per volumi; OX05C1S prezzo pagina $299 (da ricerca web) | https://leopardimaging.com/stereoscopic-cameras/ ; https://leopardimaging.com/wp-content/uploads/pdf/LI-ESP870-STEREO-M031_datasheet.pdf ; https://leopardimaging.com/wp-content/uploads/2026/01/LI-OX05C1S-ST80-MIPI-143H_Datasheet.pdf |
| **Arducam** (Camarray stereo kit OV9281) | "variable baseline" (due schede separate); nessun valore fisso in pagina. E' la nostra base logger | OV9281 mono global shutter 1 MP | MIPI via Camarray HAT, Pi 5 elencato | **Nessuna calibrazione**: dichiara di non fornire guida su depth/calibrazione. Pagine prodotto danno 403 al fetch, quindi letto solo da ricerca | - | prezzo non verificato | https://www.arducam.com/blog/?p=28612 (403 al fetch, solo snippet di ricerca) |
| **Luxonis OAK-FFC** | liberi ("place them at various stereo baselines", "customize both horizontal and vertical stereo baseline"; esempio doc con 14.8 cm) | OV9282/OV9782 global shutter | via scheda FFC (USB/PoE), non CSI su Pi | FFC e' modulare: calibra l'utente con i loro tool; nessun servizio di calib OEM trovato. Intrinseche di fabbrica sul modulo (OAK 4 FFC) | - | - | https://docs.luxonis.com/hardware/platform/deploy/ffc.md ; https://docs.luxonis.com/hardware/platform/depth/manual-calibration.md ; https://docs.luxonis.com/hardware/platform/depth/calibration/ |
| **Basler Stereo ace** | 100 / 200 / 300 mm (da snippet di ricerca sul sito Basler; pagina non scaricabile) | non letto | GigE/USB/GMSL (non MIPI) | "factory calibration" + auto-calibrazione dinamica (snippet Basler). Formato consegna: NON VERIFICATO | non letta | prezzo non letto (pagina 406) | https://www.baslerweb.com/en/cameras/basler-stereo-camera/ ; https://www.baslerweb.com/en-sg/shop/sta-200-547m-082616-w/ |
| **Inno-Maker** | Non ho trovato nessun loro stereo; i kit OV9281 trovati sono Arducam | - | - | - | - | - | NON VERIFICATO |
| **Sinoseen (Shenzhen) e altri ODM** | OEM/ODM, FOV e alloggiamento personalizzabili; baseline 200 mm non trovata | OV9732 stereo MIPI (non global shutter, ho letto solo il titolo) ; OV7251/OG02B1B global shutter (USB-first) | MIPI/USB/DVP | calibrazione stereo: nessuna evidenza | - | MOQ: chiedere | https://www.sinoseen.com/ov9732-mipi-csi2-flexible-fpc-stereo-3d-dual-camera-650nm-850nm-filters |
| **Stereolabs, Framos, Vision Components** | Non letti in questa sessione. Stereolabs ZED 2i = 120 mm, rolling (vedi calib15000_hardware.md). Framos / Vision Components: ricerca senza risultati utili | - | - | - | - | - | NON VERIFICATO |
| **Leopard "OEM & ODM Services"** | pagina citata nel sito, non aperta | - | - | - | - | - | https://leopardimaging.com/stereoscopic-cameras/ |

## Cosa chiedere nella richiesta di offerta (spec minima)
1. **Baseline** 200 mm +/- 0.2 mm, barra unica rigida (alluminio/composito, no due schede flottanti), sensori sulla stessa barra, stessa linea di vista (parallelismo <0.1 deg).
2. **Sensore** global shutter mono 1280x800 (o simile), **sincronizzazione hardware** FSIN/XVS tra i due sensori (la nostra sync oggi e' software `rpicam --sync`, <=0.045 ms; vogliamo equivalente o meglio).
3. **Interfaccia** MIPI CSI-2 compatibile Raspberry Pi 5 (driver libcamera/V4L2 upstream o sorgenti del driver a noi), cavo FFC 22 pin; oppure un solo CSI con 2 sensori (come il nostro Camarray).
4. **Ottiche** M12 fisse, FOV orizzontale ~70-90 deg (a noi serve f circa 930-1300 px), bloccate con colla, IR-cut/no-IR da concordare. Distorsione dichiarata.
5. **Calibrazione di fabbrica per ogni unita'**: intrinseche (f, c, distorsione) + estrinseche (R, T) + residuo di riproiezione, in file per numero di serie **e/o** su EEPROM sul modulo; formato leggibile (OpenCV YAML/JSON), con la scacchiera/dima descritta. Scala: baseline misurata.
6. **Tolleranze di accettazione per lotto**: dy residuo (errore verticale dopo rettifica) < 0.5 px su tutta l'immagine, 9 zone, bordi inclusi; errore di profondita' <= 2% a 2, 3.5 e 5 m su un bersaglio piano; report per pezzo.
7. **Rigidita' / stabilita'**: prova di vibrazione e ciclo termico (es. -10..+50 C) con ri-misura dopo: variazione dy < 0.5 px, deriva T < 0.2 mm. Chiedere i dati di test gia' fatti.
8. **Campionatura**: 10 pezzi prototipo da misurare noi sul banco (muro-test del repo), poi pilota 100, poi serie. MOQ, prezzo a 10/100/1.000/15.000, lead time, garanzia, e **ricambio**: un modulo sostitutivo arriva gia' calibrato (nessun intervento sul posto).
9. Meccanica: fori di montaggio, IP (pioggia, polvere), connettori, peso, temperatura.
10. Diritti: noi possiamo rileggere la calibrazione; nessun blocco su tool proprietari.

## Rischi
- La calibrazione di fabbrica vale solo con barra rigida: una barra da 200 mm in bici fa cambiare l'angolo coi cicli termici/urti; altrimenti serve comunque il controllo software (drift_monitor, auto-check in marcia). Non e' "zero" assoluto.
- Pi 5: i moduli e-con/Leopard sono per Jetson/Holoscan: driver da verificare.
- Costo/MOQ non pubblici per i custom (NON VERIFICATO).
- Il prototipo dovra' dimostrare i numeri sul nostro banco prima di ordinare serie.

## BOZZA email (NON INVIATA, parte solo col tap di Daniele; tocca preventivi e nuova relazione)
A: sales@e-consystems.com (indirizzo dalla loro pagina prodotto)
Oggetto: Custom stereo module, 200 mm baseline, global shutter, factory calibrated - Raspberry Pi 5

Ciao,

sono Daniele, fondatore di Moving One Billion People. Costruiamo Asmile, una bici a trazione umana con guida assistita per Persone con disabilita' in RSA e centri; puntiamo a molte migliaia di unita'.

Ci serve un modulo stereo come la vostra STEEReoCAM ma con:
- baseline 200 mm su barra rigida, global shutter mono (OV2311 o simile), sync hardware;
- MIPI CSI-2 per Raspberry Pi 5 (driver libcamera/V4L2);
- calibrazione di fabbrica per ogni pezzo (intrinseche + estrinseche, per numero di serie o EEPROM), dy < 0.5 px, profondita' entro 2% fino a 5 m;
- prove di vibrazione e temperatura.

Potete dirci: se e' fattibile, tempi e costi di un campione da 10 pezzi, MOQ e prezzo a 1.000 e 15.000 pezzi, formato del file di calibrazione, report di test per pezzo? Possiamo mandarvi la scheda tecnica completa.

Con profonda gratitudine 🙏
Daniele MM
daniele@movingonebillionpeople.org

(Stessa bozza adattata per Leopard Imaging: sales@leopardimaging.com, citando il vostro LI-ESP870 con baseline 200 mm e chiedendo la versione MIPI.)

## Ordine di contatto
1. e-con Systems (MIPI + GS + baseline customizable + lenti pre-calibrate).
2. Leopard Imaging (dichiara 200 mm su misura; MIPI da confermare).
3. Basler Stereo ace 200 mm, solo se accettiamo un'interfaccia non-CSI (GigE/USB) e il prezzo (NON VERIFICATO).
4. Arducam / Luxonis: solo per prototipo da banco, non danno calibrazione di fabbrica.
