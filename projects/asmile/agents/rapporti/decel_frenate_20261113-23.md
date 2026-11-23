# Decelerazioni nelle frenate 13-23/11/2026 (event-miner) - per tarare lo speed_limiter di #001
CSV: `decel_frenate_20261113-23.csv` (69 righe: 30 #001 + 39 logger001). Codice: `training/eventi/decel_frenate_20261123.py`, `_report_`, `_logger_`. **Dati veri #001 = solo 13/11** (145727, 11,9 min in moto, 2037 m): sul Mac non c'e' nessun altro CSV #001 con encoder dopo il 13/11 (il 2o file 13/11 e' fermo; le sessioni 23/11 sono video senza sensori). Pi non toccato.
**Fonti.** #001: v/decel da encoder ruota, parabola su 0,3 s della distanza (come WheelEncoder._fit), circ 0,3477 (metro, deployata). GPS dice 1,025x: con 0,3374 sarebbe ~1,00. Tutto scala di -3% con 0,3374. Il CSV e' a 25 Hz reali (campioni ripetuti). logger001: BLE 1 Hz, qualita **bassa**; logger02: **escluso** (niente velocita', solo IMU).
## 1. Frenate (30 su #001, v0 med 10,4 km/h, max 15,5; classe: 16 con servo >=5 gr, 7 limiter attivo, 7 solo leva)
- a_media p50 **0,53**, p90 0,91, max 1,66 m/s2. a_picco (media 0,5 s) p50 0,92, p90 1,9, max 3,19. Jerk (da a smussata 0,5 s: SOTTOSTIMA) p50 3,2, p90 4,6, max 9,8 m/s3. Durata 1,5-5 s, spazio p50 5,2 m. Colonne complete nel CSV.
- **Solo 5 arrivano a v<1 km/h** (stop): a_media 0,34-1,66, spazio 1,9-8,1 m. **Nessuna frenata d'emergenza**: tutte a v<=15,5 km/h, picco encoder <=2,0 m/s2 tranne le 2 impuntate.
- **Le 2 impuntate** (15:03:50, 15:08:51): a_media 1,66 e 1,39, picco enc 3,19 e 2,99, IMU 4,45 e 4,01, jerk 9,8 e 5,9; servo <=4,2 gr = leva, non servo. Sono le uniche sopra 2,0 m/s2 di picco encoder.
- **Servo: nessun effetto misurabile.** a_picco vs angolo servo r=-0,13 (16 eventi). Caso limite 15:05:00: servo comandato a 55 gr per ~1 s a 15 km/h, v resta 4,1-4,2 m/s (decel ~0). Non si ricava una mappa gradi->decel: va misurata a banco/prova col freno nuovo (corpo idraulico: gioco prima del contatto pad).
## 2-3. Contesto e decel per contesto (guardato su 4 fotogrammi per evento; SAM3 da solo non discrimina, rileva pole/bollard ovunque)
| contesto | n | a_media p50 / p90 / max | picco max | v0 med km/h | spazio med m |
|---|---|---|---|---|---|
| auto che attraversa davanti | 4 | 0,72 / 1,23 / 1,39 | 2,99 | 10,9 | 4,3 |
| incrocio (auto trasversali) | 5 | 0,51 / 0,60 / 0,62 | 1,08 | 9,9 | 5,2 |
| incrocio con STOP probabile | 1 | 0,81 | 1,28 | 15,1 | 8,7 |
| pedoni in attesa alle strisce | 2 | 0,48 / 0,62 / 0,65 | 0,98 | 11,3 | 9,2 |
| pedone davanti | 3 | 0,41 / 0,43 / 0,44 | 1,05 | 8,2 | 4,0 |
| curva / ostacolo fisso+curva | 4 | 0,64 / 1,13 / 1,31 | 1,96 | 12,8 | 5,9 |
| passaggio stretto (vicolo) | 3 | 0,48 / 0,49 / 0,49 | 0,90 | 9,0 | 6,4 |
| **non chiaro (intent:unknown)** | 6 | 0,58 / 1,26 / 1,66 | 3,19 | 9,8 | 3,9 |
Non in tabella: incrocio con strisce 0,36 (1), auto+pedone in controluce 0,57 (1). n piccolissimi: p90 e max sono praticamente il massimo osservato. Le due impuntate sono nel "non chiaro" (15:03:50, vicolo con arco, causa non visibile) e nell'"auto che attraversa" (15:08:51). Nessuno stop sicuro su STOP con decel chiara. Non c'e' pero' nessun pedone che attraversa davanti e nessun "rallentamento senza motivo" riconoscibile.
**Distanza dall'ostacolo a inizio frenata: NON DISPONIBILE** (depth #001 sui giri del 13/11 fermata al 3o veto, nessun valore stimato: depth:non_disponibile). Dato indiretto: spazio di frenata p50 5,2 m, 2-4 m negli stop.
## 4. Proposta per il controller (DA VALIDARE da Daniele, n=28 frenate + 2 impuntate, 1 giorno, bici ancora da bilanciare)
| livello | decel media | picco (parabola 0,3 s, smussata 0,5 s) | note |
|---|---|---|---|
| normale | **0,5-0,6 m/s2** | <=1,0 | p50 umano; copre pedoni, incroci, strisce |
| forte | **0,9-1,2** | <=1,6 | p90 umano 0,9; arrivato fino a 1,3 senza impuntare |
| massima tollerata | **1,3 media / 2,0 picco** | 2,0 | max visto SENZA impuntata: 1,31 e 1,96 (limite inferiore del vero limite) |
| mai | picco >2,5 | | impuntate a 3,0-3,2 (encoder), 4,0-4,5 (IMU) |
- **Jerk max: 4 m/s3** in salita di decel (p90 non impuntate 4,6, max 6,2 con servo-curva; impuntate 5,9-9,8). In pratica rampa di >=0,4 s fra 0 e 1,6 m/s2.
- Soglia anti-impuntata (dec IMU >=2,0 e muso giu' >=1,5 in 0,3 s): coerente. La sola dec IMU >=2,0 scatta in 8 su 28 frenate NON impuntate (IMU picco p90 2,6, max 3,1): serve il muso giu'. IMU legge ~1,4-2x l'encoder (gia' noto, non spiegato): il tetto 2,0 qui e' in scala ENCODER, quello della soglia in scala IMU, non intercambiabili.
- Il limite vero e' fra 2,0 e 3,0 m/s2 (encoder) a ~10 km/h con questa bici: non si puo' stringere senza nuove prove controllate.
## Limiti / da fare
- Nessun dato #001 dal 14 al 23/11 sul Mac: serve il pull delle sessioni (leggere sul Pi spetta a chi ha il via). logger001 (39 eventi BLE, v0 med 20 km/h, a_media 0,09-0,66, tutti rallentamenti lievi, intent:unknown non esaminati, hw diverso) e' solo controllo di ordine di grandezza, non per la taratura. IMU logger: segno non verificabile (ax medio >0 sempre = offset).
- Contesti e labels da fotogrammi a 240 px, controluce in 4 eventi: confidenza media. 6/30 non chiari.

## CORREZIONE di Daniele (23/11, dopo il verdetto del critico)
«in tutti i giri che hai nessuna frenata è stata automatica. il servo non era collegato al freno, tutte le frenate le ho fatte io».
→ Le 30 frenate sono TUTTE umane, a leva; `brake_out_deg` nel log è solo il comando a un servo non collegato e va ignorato.
→ Le soglie proposte (normale 0,5-0,6, forte 0,9-1,2, max 1,3 media / 2,0 picco, mai >2,5 m/s², jerk ≤4 m/s³) sono "come frena
Daniele", provvisorie (un giorno, n=30). Cadono le osservazioni "il servo non produce decelerazione" e "7 su 30 di sola leva":
il servo non c'entrava. Il ritardo comando→frenata del servo resta da misurare a banco col freno collegato.
