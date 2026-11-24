# Asmile da A a B da sola, tipo autopilot (piano del capo, 24/11/2026 — Daniele: "tienilo in memoria")

Bici a ~15 km/h su strade e ciclabili. 6 blocchi in catena + guardiano indipendente:

PERCORSO A→B (mappa, GPS) → DOVE SONO (localizzazione) → COSA VEDO (percezione) → COSA SUCCEDERÀ (previsione) → COSA FACCIO (pianificazione) → ATTUATORI (sterzo, freno)
GUARDIANO INDIPENDENTE (ESP32): se qualcosa non torna → STOP.

1. **Percorso**: OpenStreetMap offline sul Pi, tragitto su strade adatte alla bici → punti GPS ogni 5-10 m + manovre (svolta, incrocio, attraversamento). Dice DOVE andare; la traiettoria vera la decide la percezione.
2. **Dove sono**: GPS (2-5 m) fuso con encoder ruota, IMU, encoder sterzo, odometria visiva stereo → decimetro sul breve, GPS riallinea sul lungo.
3. **Cosa vedo**: spazio guidabile e bordi (asfalto, ciclabile, marciapiede, cordoli = "lane detection" della bici; regola Daniele: i bordi sono limiti, sotto il margine si frena o si sterza); ostacoli con distanza (stereo + segmentazione: persone, auto, bici, pali, cancelli, buche — maestro SAM 3 sul Mac, allievo leggero sul Pi); segnali (semafori, strisce, stop, precedenze); per ogni ostacolo distanza, velocità, tempo al contatto (corridoio + TTC già pronti).
4. **Cosa succederà**: tracking di ciò che si muove, posizione fra 1-3 s; la Persona che si gira verso la strada pesa più di quella ferma.
5. **Cosa faccio**: regole (destra, rallenta agli incroci, stop/semafori, precedenza ai pedoni); traiettoria nel corridoio largo come la bici dentro lo spazio guidabile; velocità = min(limite 15, curva, visibilità, TTC); se incerto rallenta e si ferma, mai indovinare; lato non misurato = occupato.
6. **Attuatori**: freno = loop sull'encoder (rilascio dolce, anti-impuntata); sterzo = VESC + encoder sterzo, velocità e forza limitate (L3). DA DECIDERE: chi spinge (Persona che pedala o motore di assistenza).
**Guardiano**: ESP32 con battito dal Pi e controllo dei limiti; se il Pi si blocca o sbaglia frena da solo e taglia il motore; il Pi non lo può riprogrammare (agents/sicurezza/ARCHITETTURA_SICUREZZA.md §8).

## Scala
L0 registra (calibrazioni, dati puliti) → L1 ombra (vede e decide, non tocca: percezione, corridoio, percorso A→B in ombra, confronto con Daniele) → L2 freno (loop freno + TTC + guardiano) → L3 sterzo (VESC + corridoio + bordi) → L4 A→B (navigazione + tutto, provato in sim e banco virtuale). Si sale solo con l'ombra che non sbaglia + firma di Daniele.

## Metodo (Tesla in piccolo)
Tanti giri dai logger su situazioni diverse → maestro sul Mac etichetta → allievo leggero sul Pi → settimane di ombra → livello successivo con firma.

## Domande aperte per Daniele
1. Primi percorsi A→B: ciclabile, strade di paese, misto?
2. In autonomia chi spinge: la Persona pedala e Asmile frena/sterza, o serve un motore?
