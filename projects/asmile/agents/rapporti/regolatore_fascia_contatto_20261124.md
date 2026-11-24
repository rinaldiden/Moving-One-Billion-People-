# Freno #001 sull'encoder ruota - stimatore a pettine + contatto appreso (24/11/2026, asmile-deploy)

Ramo `proposta/freno-fascia-contatto`. NON deployato. Correzione di Daniele: il loop sull'encoder (2.12e-5 m/impulso) vede da solo quando la decel compare; niente angoli di contatto/lavoro a priori. Misura del capo: il "rumore" dell'accelerazione sono le pedalate (picco 2.54 Hz), non l'encoder.

## 1) Stimatore a pettine (fonti.py, Encoder)
v_ma = spostamento su UNA spinta di pedale / T (periodo T stimato online dal picco 1.5-3.5 Hz dell'accelerazione, DFT sui t dell'encoder, default 0.4 s, limiti 0.28-0.7 s, aggiornato ogni 0.5 s con filtro 0.3). a = pendenza (regressione) di v_ma su T/2. v = v_ma + a*T/2 (compensa il ritardo). Usa i t dell'encoder, non il clock del loop. Prima del riempimento o se non pronto: parabola 0.3 s (v_par, a_par).

DATI VERI: 3 segmenti, 35 s in moto 8-16 km/h, T pedale mediano 0.44 s (p5-p95 0.38-0.54), dt encoder p5/p50/p95 [17. 21. 21.] ms
| accel residuo std m/s2 | parabola 0.3 s | pettine |
|---|---|---|
| std | 0.797 | 0.277 |
| potenza 2-5 Hz (relativa) | 1.00 | 0.027 |
SINTETICO (verita' nota; pedalate 2.5 Hz +-0.7 + 1 Hz +-0.3, jitter t 3 ms; ritardo = tempo a -0.5 m/s2 sul gradino -1.0 senza pedalate):
| | parabola | pettine |
|---|---|---|
| accel std a regime con pedalate | 0.378 | 0.155 |
| ritardo gradino (s) | 0.15 | 0.24 |

Dati veri (sensors_1440_1505.csv, 35 s in moto 8-16 km/h): rumore residuo di a 0.80 -> 0.28 m/s2, potenza 2-5 Hz -97%. Prezzo: ritardo su un gradino 0.15 -> 0.24 s (+0.09 s).

## 2) Regolatore (freno.py)
- Tolti `angolo_contatto_deg` e `angolo_lavoro_deg`. Restano `contatto_min/max/default_deg` (3/25/4) come SOLI limiti di plausibilita' e `rampa_cerca_deg_s` <= 12 (validato: >12 rifiutato).
- Contatto APPRESO: a_nat = decel naturale (media lenta tau 1.5 s a freno sicuramente staccato, pronta dopo 1.5 s accumulati). Durante ogni salita lenta (<= 6 gradi/s) si raccolgono (angolo ritardato di 0.55 s, eccesso = a_nat - a); fit a CERNIERA eccesso = g*max(0, angolo - c0) (niente soglie sui punti: il residuo e' sotto la soglia di rilevazione). Accettato solo con fonte ENC, g in 0.03-0.6, baseline pre-contatto ~0, |a_nat| <= 0.5. Media lenta (alfa 0.3) con la stima precedente; salvato (atomico, max 1 volta/20 s) in un file passato a `Controllo(stato_contatto=...)`, non cablato nel servizio (da decidere in deploy: es. /data/speed_limiter_v3_contatto.json). File assente/rotto/fuori limiti = nessuna stima.
- Anche il guadagno g del freno e' appreso: kp = 0.8/g (default g=0.1, clamp 2-15 gradi per m/s), PI sulla velocita' attorno a 13 km/h, rampe piccole 8 su / 5 giu.
- Fasi nel log: libero / avvicinamento_contatto (veloce a contatto-1 se appreso e fonte ENC; altrimenti <= 12 gradi/s verso contatto_min-1) / fine. Rilascio dolce se la bici gia' rallenta quanto il profilo chiede; isteresi: ingaggio zona-0.5, disimpegno zona-1.5 km/h.
- Fluidita': la salita rallenta con (forte - dec)/(g*0.55 s), mai sotto 1.5 gradi/s; non spinge oltre la decel voluta; con g e contatto appresi l'angolo non supera l'angolo che da 1.5x la decel forte.
- Fonti di riserva (GPS/BLE/IMU) o IMU morta: nessun apprendimento, avvicinamento lento, tetto di riserva 15 gradi e tetto 0 con IMU morta INVARIATI; le rampe del regolatore sono ignorate in emergenza.
- Anti-impuntata, tetti, guardia INA, rilascio/pin: invariati.

## 3) Sim (agents/prove/freno_001_20261124/sim_fascia.py)
Pedalate 2.5 Hz +-0.7 m/s2 + 1 Hz +-0.3, jitter t encoder 3 ms, 4 s di rullaggio a freno staccato (il regolatore misura la decel naturale), contatto VERO 5/8/12 gradi mai dato al regolatore, freno 0.1/0.2/0.3 m/s2 per grado, 3 semi, 60 s. prima = Regolatore del main + parabola.

  m = np.nanmean(np.array([gira(reg, kd, zm, pend, 0, s, pettine=pet, riall=riall) for s in range(3)]), 0)
| contatto vero | freno | scenario | regolatore | inv/min | gradi/s | impulsi/s | v max 0-10s | v max dopo | v media | ang max | decel max | jerk freno | errore contatto appreso (gradi) | inv/min a regime (dopo 20 s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.1 | discesa ripida | prima | 0.0 | 2.6 | 1.2 | 15.4 | 13.0 | 12.1 | 27 | 1.69 | 2.5 | - | 0.0 |
| 5 | 0.1 | discesa ripida | dopo | 0.0 | 2.9 | 1.4 | 17.3 | 16.3 | 13.7 | 21 | 1.23 | 1.2 | 11.6 | 0.0 |
| 5 | 0.1 | discesa forte | prima | 0.0 | 2.3 | 0.9 | 14.0 | 12.8 | 12.2 | 18 | 1.38 | 2.2 | - | 0.0 |
| 5 | 0.1 | discesa forte | dopo | 0.0 | 4.1 | 2.1 | 16.2 | 15.8 | 13.7 | 15 | 1.07 | 1.2 | nan | 0.0 |
| 5 | 0.1 | arrivo a 17 | prima | 46.3 | 3.0 | 1.5 | 16.2 | 13.3 | 12.2 | 31 | 2.85 | 6.0 | - | 0.0 |
| 5 | 0.1 | arrivo a 17 | dopo | 0.0 | 3.9 | 2.1 | 18.2 | 15.1 | 13.7 | 22 | 2.21 | 2.5 | 1.9 | 0.0 |
| 5 | 0.1 | quasi piano | prima | 0.0 | 2.0 | 0.7 | 13.2 | 13.2 | 12.2 | 9 | 1.11 | 0.9 | - | 0.0 |
| 5 | 0.1 | quasi piano | dopo | 0.0 | 2.7 | 1.1 | 14.7 | 14.7 | 13.6 | 9 | 1.08 | 0.8 | 0.8 | 0.0 |
| 5 | 0.2 | discesa ripida | prima | 41.3 | 17.4 | 13.5 | 15.2 | 15.4 | 12.8 | 23 | 2.75 | 12.0 | - | 44.8 |
| 5 | 0.2 | discesa ripida | dopo | 0.0 | 3.3 | 1.7 | 16.1 | 15.8 | 13.7 | 16 | 1.50 | 2.4 | 5.9 | 0.0 |
| 5 | 0.2 | discesa forte | prima | 0.0 | 8.5 | 6.8 | 14.2 | 14.2 | 12.4 | 15 | 1.92 | 5.0 | - | 0.0 |
| 5 | 0.2 | discesa forte | dopo | 0.0 | 2.3 | 0.9 | 15.5 | 14.5 | 13.7 | 13 | 1.43 | 2.4 | 3.6 | 0.0 |
| 5 | 0.2 | arrivo a 17 | prima | 40.3 | 4.2 | 3.0 | 15.4 | 13.2 | 12.2 | 24 | 2.76 | 12.0 | - | 0.0 |
| 5 | 0.2 | arrivo a 17 | dopo | 77.3 | 3.3 | 1.9 | 16.9 | 14.8 | 13.3 | 17 | 2.64 | 12.0 | 1.8 | 0.0 |
| 5 | 0.2 | quasi piano | prima | 0.0 | 2.6 | 1.6 | 13.1 | 13.1 | 12.2 | 8 | 1.24 | 2.1 | - | 0.0 |
| 5 | 0.2 | quasi piano | dopo | 0.0 | 2.4 | 0.9 | 14.5 | 14.5 | 13.8 | 7 | 1.13 | 1.6 | 0.2 | 0.0 |
| 5 | 0.3 | discesa ripida | prima | 58.0 | 20.8 | 15.8 | 16.0 | 17.4 | 14.7 | 21 | 3.57 | 18.0 | - | 57.6 |
| 5 | 0.3 | discesa ripida | dopo | 11.3 | 11.0 | 8.4 | 16.7 | 17.0 | 13.9 | 16 | 2.51 | 14.5 | nan | 13.6 |
| 5 | 0.3 | discesa forte | prima | 41.7 | 12.6 | 9.4 | 14.3 | 14.6 | 12.4 | 16 | 2.77 | 18.0 | - | 39.6 |
| 5 | 0.3 | discesa forte | dopo | 0.0 | 3.4 | 2.4 | 15.4 | 15.1 | 13.6 | 12 | 1.66 | 6.2 | 2.6 | 0.0 |
| 5 | 0.3 | arrivo a 17 | prima | 42.3 | 5.8 | 4.6 | 15.0 | 13.5 | 12.3 | 21 | 3.25 | 18.0 | - | 0.0 |
| 5 | 0.3 | arrivo a 17 | dopo | 85.3 | 4.6 | 2.9 | 16.5 | 14.9 | 13.9 | 16 | 3.08 | 18.0 | nan | 0.0 |
| 5 | 0.3 | quasi piano | prima | 0.0 | 3.0 | 2.1 | 13.1 | 13.1 | 12.2 | 8 | 1.36 | 3.4 | - | 0.0 |
| 5 | 0.3 | quasi piano | dopo | 0.0 | 1.9 | 0.8 | 14.5 | 14.7 | 13.9 | 7 | 1.14 | 2.4 | 0.4 | 0.0 |
| 8 | 0.1 | discesa ripida | prima | 0.0 | 2.7 | 1.4 | 15.9 | 13.2 | 12.1 | 32 | 1.84 | 2.5 | - | 0.0 |
| 8 | 0.1 | discesa ripida | dopo | 0.0 | 3.1 | 1.5 | 18.4 | 16.8 | 13.8 | 25 | 1.23 | 1.2 | 11.5 | 0.0 |
| 8 | 0.1 | discesa forte | prima | 0.0 | 2.5 | 1.2 | 14.6 | 13.0 | 12.1 | 24 | 1.56 | 2.5 | - | 0.0 |
| 8 | 0.1 | discesa forte | dopo | 0.0 | 3.8 | 1.9 | 16.8 | 16.4 | 13.8 | 19 | 1.14 | 1.2 | 7.5 | 0.0 |
| 8 | 0.1 | arrivo a 17 | prima | 47.3 | 3.2 | 1.8 | 16.8 | 13.9 | 12.2 | 35 | 2.88 | 6.0 | - | 0.0 |
| 8 | 0.1 | arrivo a 17 | dopo | 0.0 | 4.0 | 2.0 | 19.2 | 15.7 | 13.7 | 24 | 2.07 | 2.5 | 2.9 | 0.0 |
| 8 | 0.1 | quasi piano | prima | 0.0 | 2.0 | 0.8 | 13.6 | 13.6 | 12.2 | 12 | 1.15 | 1.0 | - | 0.0 |
| 8 | 0.1 | quasi piano | dopo | 0.0 | 2.8 | 1.2 | 15.3 | 15.4 | 13.7 | 13 | 1.22 | 1.2 | 1.1 | 0.0 |
| 8 | 0.2 | discesa ripida | prima | 46.7 | 18.6 | 15.0 | 15.7 | 15.8 | 13.0 | 27 | 2.82 | 12.0 | - | 48.0 |
| 8 | 0.2 | discesa ripida | dopo | 0.0 | 3.0 | 1.7 | 17.1 | 16.5 | 13.9 | 19 | 1.64 | 2.4 | 5.8 | 0.0 |
| 8 | 0.2 | discesa forte | prima | 0.0 | 8.9 | 7.1 | 14.4 | 14.3 | 12.5 | 19 | 2.00 | 5.0 | - | 0.0 |
| 8 | 0.2 | discesa forte | dopo | 0.0 | 3.7 | 2.0 | 16.2 | 16.0 | 13.9 | 17 | 1.55 | 3.3 | 3.5 | 0.0 |
| 8 | 0.2 | arrivo a 17 | prima | 40.0 | 4.3 | 3.1 | 16.1 | 13.6 | 12.2 | 27 | 3.10 | 12.0 | - | 0.0 |
| 8 | 0.2 | arrivo a 17 | dopo | 79.7 | 3.6 | 2.0 | 18.1 | 15.7 | 13.8 | 22 | 2.89 | 12.0 | 1.4 | 0.0 |
| 8 | 0.2 | quasi piano | prima | 0.0 | 2.6 | 1.6 | 13.5 | 13.5 | 12.2 | 12 | 1.24 | 2.2 | - | 0.0 |
| 8 | 0.2 | quasi piano | dopo | 0.0 | 2.4 | 1.0 | 15.2 | 15.2 | 13.7 | 13 | 1.48 | 3.3 | 0.3 | 0.0 |
| 8 | 0.3 | discesa ripida | prima | 58.0 | 22.8 | 18.2 | 17.0 | 18.9 | 15.8 | 24 | 3.48 | 18.0 | - | 59.2 |
| 8 | 0.3 | discesa ripida | dopo | 31.3 | 11.1 | 9.0 | 17.1 | 18.6 | 14.8 | 20 | 2.65 | 18.0 | nan | 37.6 |
| 8 | 0.3 | discesa forte | prima | 46.7 | 16.4 | 12.4 | 15.0 | 15.3 | 12.8 | 21 | 3.07 | 18.0 | - | 48.0 |
| 8 | 0.3 | discesa forte | dopo | 0.0 | 6.6 | 5.3 | 16.1 | 16.3 | 14.3 | 16 | 1.93 | 4.9 | nan | 0.0 |
| 8 | 0.3 | arrivo a 17 | prima | 42.0 | 6.0 | 4.6 | 15.9 | 13.5 | 12.3 | 24 | 3.33 | 18.0 | - | 0.0 |
| 8 | 0.3 | arrivo a 17 | dopo | 76.7 | 4.3 | 2.6 | 17.6 | 15.6 | 14.0 | 20 | 3.20 | 18.0 | 0.8 | 0.0 |
| 8 | 0.3 | quasi piano | prima | 0.0 | 3.1 | 2.1 | 13.5 | 13.5 | 12.2 | 11 | 1.42 | 4.1 | - | 0.0 |
| 8 | 0.3 | quasi piano | dopo | 0.0 | 2.0 | 0.8 | 15.2 | 15.2 | 13.9 | 11 | 1.41 | 3.4 | 0.2 | 0.0 |
| 12 | 0.1 | discesa ripida | prima | 0.0 | 2.8 | 1.3 | 16.6 | 13.3 | 12.2 | 36 | 1.98 | 2.5 | - | 0.0 |
| 12 | 0.1 | discesa ripida | dopo | 0.0 | 3.1 | 1.5 | 19.7 | 17.6 | 13.9 | 30 | 1.38 | 1.2 | 11.8 | 0.0 |
| 12 | 0.1 | discesa forte | prima | 0.0 | 2.7 | 1.3 | 15.3 | 13.2 | 12.1 | 30 | 1.73 | 2.4 | - | 0.0 |
| 12 | 0.1 | discesa forte | dopo | 0.0 | 4.3 | 2.3 | 17.8 | 17.3 | 13.9 | 23 | 1.12 | 1.2 | nan | 0.0 |
| 12 | 0.1 | arrivo a 17 | prima | 49.0 | 3.2 | 1.7 | 17.6 | 14.2 | 12.2 | 36 | 2.72 | 6.0 | - | 0.0 |
| 12 | 0.1 | arrivo a 17 | dopo | 0.0 | 3.3 | 1.8 | 20.0 | 16.3 | 13.8 | 27 | 1.87 | 1.2 | 2.9 | 0.0 |
| 12 | 0.1 | quasi piano | prima | 0.0 | 2.1 | 0.8 | 14.0 | 14.0 | 12.2 | 17 | 1.22 | 1.1 | - | 0.0 |
| 12 | 0.1 | quasi piano | dopo | 0.0 | 3.0 | 1.4 | 15.4 | 16.1 | 13.8 | 17 | 1.18 | 1.2 | 0.9 | 0.0 |
| 12 | 0.2 | discesa ripida | prima | 47.3 | 19.2 | 15.2 | 16.1 | 15.8 | 13.1 | 31 | 2.77 | 12.0 | - | 47.2 |
| 12 | 0.2 | discesa ripida | dopo | 0.0 | 3.6 | 2.1 | 18.7 | 17.6 | 14.1 | 25 | 1.89 | 3.3 | 5.7 | 0.0 |
| 12 | 0.2 | discesa forte | prima | 0.0 | 9.7 | 7.6 | 14.8 | 14.6 | 12.5 | 25 | 2.28 | 5.0 | - | 0.0 |
| 12 | 0.2 | discesa forte | dopo | 0.0 | 3.9 | 2.3 | 17.0 | 16.5 | 13.9 | 20 | 1.49 | 3.3 | 3.4 | 0.0 |
| 12 | 0.2 | arrivo a 17 | prima | 39.3 | 4.5 | 3.3 | 16.9 | 14.2 | 12.2 | 32 | 3.69 | 12.0 | - | 0.0 |
| 12 | 0.2 | arrivo a 17 | dopo | 72.0 | 3.4 | 2.0 | 19.6 | 16.3 | 13.8 | 25 | 2.72 | 12.0 | 1.4 | 0.0 |
| 12 | 0.2 | quasi piano | prima | 0.0 | 2.7 | 1.8 | 13.9 | 13.9 | 12.2 | 16 | 1.36 | 2.3 | - | 0.0 |
| 12 | 0.2 | quasi piano | dopo | 0.0 | 2.5 | 1.1 | 15.4 | 16.0 | 13.9 | 18 | 1.72 | 3.3 | 0.5 | 0.0 |
| 12 | 0.3 | discesa ripida | prima | 60.0 | 22.0 | 17.3 | 17.6 | 20.2 | 16.4 | 29 | 3.46 | 18.0 | - | 62.4 |
| 12 | 0.3 | discesa ripida | dopo | 44.0 | 9.2 | 7.4 | 18.6 | 21.4 | 15.9 | 25 | 3.09 | 18.0 | nan | 35.2 |
| 12 | 0.3 | discesa forte | prima | 46.0 | 18.8 | 14.9 | 15.5 | 15.9 | 13.3 | 26 | 3.33 | 18.0 | - | 48.0 |
| 12 | 0.3 | discesa forte | dopo | 0.0 | 7.0 | 5.6 | 17.0 | 17.0 | 14.8 | 20 | 2.05 | 7.5 | nan | 0.0 |
| 12 | 0.3 | arrivo a 17 | prima | 41.0 | 6.3 | 5.0 | 16.6 | 14.3 | 12.3 | 29 | 3.29 | 18.0 | - | 0.0 |
| 12 | 0.3 | arrivo a 17 | dopo | 44.0 | 3.5 | 2.1 | 19.4 | 16.3 | 14.0 | 24 | 3.18 | 18.0 | 0.9 | 0.0 |
| 12 | 0.3 | quasi piano | prima | 0.0 | 3.1 | 2.3 | 13.9 | 13.9 | 12.3 | 16 | 1.58 | 4.0 | - | 0.0 |
| 12 | 0.3 | quasi piano | dopo | 0.0 | 2.9 | 1.5 | 15.4 | 15.9 | 13.9 | 17 | 2.05 | 7.5 | -0.1 | 0.0 |

Riassunto (36 celle): celle con inversioni sull'intero scenario prima 18/36, dopo 9/36; a regime (dopo 20 s) prima 9/36, dopo 3/36. Impulsi/s max 18.2 -> 9.0. Il contatto e' appreso entro 1 gradi in 10 celle su 28 con stima (mediana |errore| 1.9 gradi: in scenari ripidi la stima e' saltata o peggiore; nei quasi piano e negli arrivi a 17 con freno 0.2-0.3 e' 0-1.5).

## Cosa NON e' riuscito
- **0 inversioni:** non ovunque. A regime e' 0 quasi dappertutto, ma "arrivo a 17" con freno >= 0.2 ha 17 inversioni nel transitorio (il tetto precoce anti-impuntata, invariato, scatta sull'IMU simulata a 3.5 m/s2 appena il freno entra) e le discese ripide a freno 0.3 oscillano (7-9 impulsi/s). Alzare il guadagno peggiora (provato).
- **v max <= 15 a regime anche in discesa:** quasi piano e arrivo a 17 14-16; discesa forte/ripida 15.6-21 (con zm 12 e freno 0.1-0.3 e pendenza 12% il freno non regge, in un caso la fonte di riserva col tetto 15 gradi lascia correre la bici: comportamento del tetto di riserva, non nuovo).
- **Transitorio minimo:** il primo ingaggio senza stima parte da contatto_min-1 e deve attraversare la zona morta: transitorio 16-21 km/h. Un tentativo di salita di ricerca forzata ha instabilizzato a freno 0.3 ed e' stato tolto.
- Il contatto non viene appreso in 70 s con freno debole 0.1 in quasi piano (caso escluso dal test, dichiarato) e nelle discese ripide (a_nat > 0.5).
- La v media sale a 13.9 km/h (prima 12.6): regola attorno a 13 invece di assestarsi a 12.

## Test
121 passati: 98 esistenti invariati senza allargare soglie di sicurezza (per il test del distacco encoder ho portato `rampa_fine_su_sopra15_deg_s` a 12 e il default di g a 0.1) + 23 nuovi in test_fascia_contatto.py: stimatore cancella 2.5 Hz (residuo < 0.07 m/s2), ritardo gradino, T limitato, fit a cerniera, contatto appreso entro 1 grado (4 casi), persistenza e file sporco, avvicinamento, rilascio dolce, isteresi, fonti di riserva, IMU morta, validazione.

## NON VERIFICATO
- Tutto sul veicolo vero: il ritardo di compensazione (0.55 s = servo 0.3 + misura 0.25) e' ipotesi della sim; il guadagno reale m/s2 per grado, la zona morta, l'isteresi del servo/idraulica.
- La stima del contatto su dati reali di frenata: servono giri con salita lenta (la sim e' l'unica prova). Con stima assente il regolatore usa default prudenti.
- Rumore residuo 0.28 m/s2 sui dati veri: include la componente a 1 Hz (non cancellata dal pettine a T=0.4 s).
