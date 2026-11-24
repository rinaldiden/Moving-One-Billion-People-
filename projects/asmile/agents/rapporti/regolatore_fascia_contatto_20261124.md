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
  m = np.nanmean(np.array([gira(reg, kd, zm, pend, 0, s, pettine=pet, riall=riall) for s in range(3)]), 0)
  m = np.nanmean(np.array([gira(reg, kd, zm, pend, 0, s, pettine=pet, riall=riall) for s in range(3)]), 0)
| contatto vero | freno | scenario | regolatore | inv/min | gradi/s | impulsi/s | v max 0-10s | v max dopo | v media | ang max | decel max | jerk freno | errore contatto appreso (gradi) | inv/min a regime (dopo 20 s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.1 | discesa ripida | prima | 0.0 | 2.6 | 1.2 | 15.4 | 13.0 | 12.1 | 27 | 1.69 | 2.5 | - | 0.0 |
| 5 | 0.1 | discesa ripida | dopo | 0.0 | 4.2 | 2.4 | 17.4 | 15.9 | 13.5 | 22 | 1.24 | 1.2 | 12.0 | 0.0 |
| 5 | 0.1 | discesa forte | prima | 0.0 | 2.3 | 0.9 | 14.0 | 12.8 | 12.2 | 18 | 1.38 | 2.2 | - | 0.0 |
| 5 | 0.1 | discesa forte | dopo | 0.0 | 4.0 | 2.0 | 16.0 | 14.9 | 13.6 | 16 | 1.18 | 1.2 | nan | 0.0 |
| 5 | 0.1 | arrivo a 17 | prima | 46.3 | 3.0 | 1.5 | 16.2 | 13.3 | 12.2 | 31 | 2.85 | 6.0 | - | 0.0 |
| 5 | 0.1 | arrivo a 17 | dopo | 0.0 | 4.3 | 2.4 | 18.3 | 15.1 | 13.7 | 21 | 2.11 | 2.5 | 2.0 | 0.0 |
| 5 | 0.1 | quasi piano | prima | 0.0 | 2.0 | 0.7 | 13.2 | 13.2 | 12.2 | 9 | 1.11 | 0.9 | - | 0.0 |
| 5 | 0.1 | quasi piano | dopo | 0.0 | 3.8 | 1.7 | 14.7 | 14.7 | 13.5 | 9 | 1.15 | 0.8 | 1.3 | 0.0 |
| 5 | 0.2 | discesa ripida | prima | 41.3 | 17.4 | 13.5 | 15.2 | 15.4 | 12.8 | 23 | 2.75 | 12.0 | - | 44.8 |
| 5 | 0.2 | discesa ripida | dopo | 0.0 | 4.8 | 3.0 | 16.1 | 15.7 | 13.5 | 16 | 1.60 | 4.1 | 5.7 | 0.0 |
| 5 | 0.2 | discesa forte | prima | 0.0 | 8.5 | 6.8 | 14.2 | 14.2 | 12.4 | 15 | 1.92 | 5.0 | - | 0.0 |
| 5 | 0.2 | discesa forte | dopo | 0.0 | 4.2 | 2.3 | 15.2 | 14.6 | 13.6 | 13 | 1.38 | 3.3 | 3.9 | 0.0 |
| 5 | 0.2 | arrivo a 17 | prima | 40.3 | 4.2 | 3.0 | 15.4 | 13.2 | 12.2 | 24 | 2.76 | 12.0 | - | 0.0 |
| 5 | 0.2 | arrivo a 17 | dopo | 110.7 | 4.4 | 2.4 | 16.9 | 14.7 | 13.7 | 17 | 2.58 | 12.0 | 1.8 | 0.0 |
| 5 | 0.2 | quasi piano | prima | 0.0 | 2.6 | 1.6 | 13.1 | 13.1 | 12.2 | 8 | 1.24 | 2.1 | - | 0.0 |
| 5 | 0.2 | quasi piano | dopo | 0.0 | 3.7 | 1.7 | 14.5 | 14.5 | 13.5 | 8 | 1.22 | 1.6 | 0.7 | 0.0 |
| 5 | 0.3 | discesa ripida | prima | 58.0 | 20.8 | 15.8 | 16.0 | 17.4 | 14.7 | 21 | 3.57 | 18.0 | - | 57.6 |
| 5 | 0.3 | discesa ripida | dopo | 0.0 | 8.5 | 6.9 | 16.3 | 16.6 | 13.9 | 15 | 2.25 | 6.2 | nan | 0.0 |
| 5 | 0.3 | discesa forte | prima | 41.7 | 12.6 | 9.4 | 14.3 | 14.6 | 12.4 | 16 | 2.77 | 18.0 | - | 39.6 |
| 5 | 0.3 | discesa forte | dopo | 0.0 | 5.1 | 3.7 | 15.4 | 15.5 | 14.0 | 12 | 1.75 | 3.6 | 1.7 | 0.0 |
| 5 | 0.3 | arrivo a 17 | prima | 42.3 | 5.8 | 4.6 | 15.0 | 13.5 | 12.3 | 21 | 3.25 | 18.0 | - | 0.0 |
| 5 | 0.3 | arrivo a 17 | dopo | 80.3 | 4.6 | 2.9 | 16.5 | 14.9 | 13.9 | 15 | 2.97 | 18.0 | nan | 0.0 |
| 5 | 0.3 | quasi piano | prima | 0.0 | 3.0 | 2.1 | 13.1 | 13.1 | 12.2 | 8 | 1.36 | 3.4 | - | 0.0 |
| 5 | 0.3 | quasi piano | dopo | 0.0 | 3.7 | 1.9 | 14.5 | 14.6 | 13.4 | 8 | 1.33 | 2.4 | 0.3 | 0.0 |
| 8 | 0.1 | discesa ripida | prima | 0.0 | 2.7 | 1.4 | 15.9 | 13.2 | 12.1 | 32 | 1.84 | 2.5 | - | 0.0 |
| 8 | 0.1 | discesa ripida | dopo | 0.0 | 4.4 | 2.5 | 18.6 | 16.8 | 13.7 | 25 | 1.28 | 1.2 | 11.7 | 0.0 |
| 8 | 0.1 | discesa forte | prima | 0.0 | 2.5 | 1.2 | 14.6 | 13.0 | 12.1 | 24 | 1.56 | 2.5 | - | 0.0 |
| 8 | 0.1 | discesa forte | dopo | 0.0 | 4.1 | 2.2 | 16.9 | 15.7 | 13.7 | 19 | 1.18 | 1.2 | nan | 0.0 |
| 8 | 0.1 | arrivo a 17 | prima | 47.3 | 3.2 | 1.8 | 16.8 | 13.9 | 12.2 | 35 | 2.88 | 6.0 | - | 0.0 |
| 8 | 0.1 | arrivo a 17 | dopo | 0.0 | 4.5 | 2.6 | 19.2 | 15.7 | 13.5 | 23 | 1.96 | 1.2 | 2.7 | 0.0 |
| 8 | 0.1 | quasi piano | prima | 0.0 | 2.0 | 0.8 | 13.6 | 13.6 | 12.2 | 12 | 1.15 | 1.0 | - | 0.0 |
| 8 | 0.1 | quasi piano | dopo | 0.0 | 3.8 | 1.9 | 15.3 | 15.4 | 13.6 | 12 | 1.11 | 1.2 | 1.1 | 0.0 |
| 8 | 0.2 | discesa ripida | prima | 46.7 | 18.6 | 15.0 | 15.7 | 15.8 | 13.0 | 27 | 2.82 | 12.0 | - | 48.0 |
| 8 | 0.2 | discesa ripida | dopo | 0.0 | 4.5 | 2.6 | 17.2 | 16.3 | 13.8 | 19 | 1.66 | 2.4 | 5.6 | 0.0 |
| 8 | 0.2 | discesa forte | prima | 0.0 | 8.9 | 7.1 | 14.4 | 14.3 | 12.5 | 19 | 2.00 | 5.0 | - | 0.0 |
| 8 | 0.2 | discesa forte | dopo | 0.0 | 4.4 | 2.5 | 16.3 | 15.4 | 13.7 | 16 | 1.48 | 3.3 | 3.4 | 0.0 |
| 8 | 0.2 | arrivo a 17 | prima | 40.0 | 4.3 | 3.1 | 16.1 | 13.6 | 12.2 | 27 | 3.10 | 12.0 | - | 0.0 |
| 8 | 0.2 | arrivo a 17 | dopo | 102.0 | 4.7 | 2.5 | 18.2 | 15.5 | 13.6 | 21 | 2.78 | 12.0 | 1.4 | 0.0 |
| 8 | 0.2 | quasi piano | prima | 0.0 | 2.6 | 1.6 | 13.5 | 13.5 | 12.2 | 12 | 1.24 | 2.2 | - | 0.0 |
| 8 | 0.2 | quasi piano | dopo | 0.0 | 3.9 | 2.0 | 15.2 | 15.2 | 13.4 | 12 | 1.45 | 2.4 | 0.4 | 0.0 |
| 8 | 0.3 | discesa ripida | prima | 58.0 | 22.8 | 18.2 | 17.0 | 18.9 | 15.8 | 24 | 3.48 | 18.0 | - | 59.2 |
| 8 | 0.3 | discesa ripida | dopo | 0.0 | 6.8 | 5.6 | 17.0 | 17.1 | 14.5 | 17 | 2.15 | 3.6 | nan | 0.0 |
| 8 | 0.3 | discesa forte | prima | 46.7 | 16.4 | 12.4 | 15.0 | 15.3 | 12.8 | 21 | 3.07 | 18.0 | - | 48.0 |
| 8 | 0.3 | discesa forte | dopo | 0.0 | 6.2 | 4.8 | 16.0 | 15.8 | 14.0 | 15 | 1.78 | 3.6 | nan | 0.0 |
| 8 | 0.3 | arrivo a 17 | prima | 42.0 | 6.0 | 4.6 | 15.9 | 13.5 | 12.3 | 24 | 3.33 | 18.0 | - | 0.0 |
| 8 | 0.3 | arrivo a 17 | dopo | 76.3 | 4.9 | 3.3 | 17.6 | 15.5 | 13.9 | 19 | 3.14 | 18.0 | 0.7 | 0.0 |
| 8 | 0.3 | quasi piano | prima | 0.0 | 3.1 | 2.1 | 13.5 | 13.5 | 12.2 | 11 | 1.42 | 4.1 | - | 0.0 |
| 8 | 0.3 | quasi piano | dopo | 0.0 | 3.5 | 1.9 | 15.2 | 15.2 | 13.5 | 12 | 1.49 | 4.9 | 0.3 | 0.0 |
| 12 | 0.1 | discesa ripida | prima | 0.0 | 2.8 | 1.3 | 16.6 | 13.3 | 12.2 | 36 | 1.98 | 2.5 | - | 0.0 |
| 12 | 0.1 | discesa ripida | dopo | 0.0 | 4.6 | 2.5 | 20.0 | 17.1 | 13.7 | 31 | 1.48 | 1.2 | 11.9 | 0.0 |
| 12 | 0.1 | discesa forte | prima | 0.0 | 2.7 | 1.3 | 15.3 | 13.2 | 12.1 | 30 | 1.73 | 2.4 | - | 0.0 |
| 12 | 0.1 | discesa forte | dopo | 0.0 | 4.2 | 2.2 | 18.1 | 17.1 | 13.8 | 24 | 1.16 | 1.2 | nan | 0.0 |
| 12 | 0.1 | arrivo a 17 | prima | 49.0 | 3.2 | 1.7 | 17.6 | 14.2 | 12.2 | 36 | 2.72 | 6.0 | - | 0.0 |
| 12 | 0.1 | arrivo a 17 | dopo | 0.0 | 4.4 | 2.7 | 20.0 | 16.0 | 13.6 | 26 | 1.78 | 1.2 | 2.7 | 0.0 |
| 12 | 0.1 | quasi piano | prima | 0.0 | 2.1 | 0.8 | 14.0 | 14.0 | 12.2 | 17 | 1.22 | 1.1 | - | 0.0 |
| 12 | 0.1 | quasi piano | dopo | 0.0 | 3.7 | 1.8 | 15.4 | 15.8 | 13.7 | 17 | 1.17 | 1.2 | nan | 0.0 |
| 12 | 0.2 | discesa ripida | prima | 47.3 | 19.2 | 15.2 | 16.1 | 15.8 | 13.1 | 31 | 2.77 | 12.0 | - | 47.2 |
| 12 | 0.2 | discesa ripida | dopo | 0.0 | 7.6 | 5.7 | 18.9 | 16.8 | 13.7 | 25 | 2.03 | 3.3 | 5.7 | 0.0 |
| 12 | 0.2 | discesa forte | prima | 0.0 | 9.7 | 7.6 | 14.8 | 14.6 | 12.5 | 25 | 2.28 | 5.0 | - | 0.0 |
| 12 | 0.2 | discesa forte | dopo | 0.0 | 4.0 | 2.1 | 17.3 | 16.2 | 13.9 | 20 | 1.42 | 2.4 | 3.3 | 0.0 |
| 12 | 0.2 | arrivo a 17 | prima | 39.3 | 4.5 | 3.3 | 16.9 | 14.2 | 12.2 | 32 | 3.69 | 12.0 | - | 0.0 |
| 12 | 0.2 | arrivo a 17 | dopo | 60.0 | 5.2 | 3.4 | 19.6 | 16.4 | 13.7 | 24 | 2.59 | 9.7 | 1.2 | 0.0 |
| 12 | 0.2 | quasi piano | prima | 0.0 | 2.7 | 1.8 | 13.9 | 13.9 | 12.2 | 16 | 1.36 | 2.3 | - | 0.0 |
| 12 | 0.2 | quasi piano | dopo | 0.0 | 4.1 | 2.5 | 15.4 | 15.9 | 13.8 | 17 | 1.51 | 2.4 | 0.1 | 0.0 |
| 12 | 0.3 | discesa ripida | prima | 57.3 | 22.2 | 17.5 | 17.6 | 19.9 | 16.5 | 29 | 3.46 | 18.0 | - | 59.2 |
| 12 | 0.3 | discesa ripida | dopo | 36.3 | 9.4 | 7.7 | 19.1 | 20.0 | 15.6 | 24 | 2.72 | 18.0 | nan | 34.8 |
| 12 | 0.3 | discesa forte | prima | 46.0 | 18.8 | 14.9 | 15.5 | 15.9 | 13.3 | 26 | 3.33 | 18.0 | - | 48.0 |
| 12 | 0.3 | discesa forte | dopo | 0.0 | 5.5 | 4.1 | 17.1 | 16.0 | 14.0 | 19 | 1.82 | 3.6 | 1.7 | 0.0 |
| 12 | 0.3 | arrivo a 17 | prima | 41.0 | 6.3 | 5.0 | 16.6 | 14.3 | 12.3 | 29 | 3.29 | 18.0 | - | 0.0 |
| 12 | 0.3 | arrivo a 17 | dopo | 67.3 | 4.9 | 3.4 | 19.4 | 16.3 | 14.2 | 23 | 3.10 | 18.0 | 0.3 | 0.0 |
| 12 | 0.3 | quasi piano | prima | 0.0 | 3.1 | 2.3 | 13.9 | 13.9 | 12.3 | 16 | 1.58 | 4.0 | - | 0.0 |
| 12 | 0.3 | quasi piano | dopo | 0.0 | 3.7 | 2.1 | 15.4 | 15.8 | 13.8 | 16 | 1.49 | 3.6 | -0.2 | 0.0 |

Riassunto (36 celle): celle con inversioni sull'intero scenario prima 18/36, dopo 9/36; a regime (dopo 20 s) prima 9/36, dopo 3/36. Impulsi/s max 18.2 -> 9.0. Il contatto e' appreso entro 1 gradi in 10 celle su 28 con stima (mediana |errore| 1.9 gradi: in scenari ripidi la stima e' saltata o peggiore; nei quasi piano e negli arrivi a 17 con freno 0.2-0.3 e' 0-1.5).

## Cosa NON e' riuscito
- **0 inversioni:** non ovunque. A regime e' 0 quasi dappertutto, ma "arrivo a 17" con freno >= 0.2 ha 17 inversioni nel transitorio (il tetto precoce anti-impuntata, invariato, scatta sull'IMU simulata a 3.5 m/s2 appena il freno entra) e le discese ripide a freno 0.3 oscillano (7-9 impulsi/s). Alzare il guadagno peggiora (provato).
- **v max <= 15 a regime anche in discesa:** quasi piano e arrivo a 17 14-16; discesa forte/ripida 15.6-21 (con zm 12 e freno 0.1-0.3 e pendenza 12% il freno non regge, in un caso la fonte di riserva col tetto 15 gradi lascia correre la bici: comportamento del tetto di riserva, non nuovo).
- **Transitorio minimo:** il primo ingaggio senza stima parte da contatto_min-1 e deve attraversare la zona morta: transitorio 16-21 km/h. Un tentativo di salita di ricerca forzata ha instabilizzato a freno 0.3 ed e' stato tolto.
- Il contatto non viene appreso in 70 s con freno debole 0.1 in quasi piano (caso escluso dal test, dichiarato) e nelle discese ripide (a_nat > 0.5).
- La v media sale a 13.9 km/h (prima 12.6): regola attorno a 13 invece di assestarsi a 12.

## Test (versione precedente)
121 passati: 98 esistenti invariati senza allargare soglie di sicurezza (per il test del distacco encoder ho portato `rampa_fine_su_sopra15_deg_s` a 12 e il default di g a 0.1) + 23 nuovi in test_fascia_contatto.py: stimatore cancella 2.5 Hz (residuo < 0.07 m/s2), ritardo gradino, T limitato, fit a cerniera, contatto appreso entro 1 grado (4 casi), persistenza e file sporco, avvicinamento, rilascio dolce, isteresi, fonti di riserva, IMU morta, validazione.

## NON VERIFICATO
- Tutto sul veicolo vero: il ritardo di compensazione (0.55 s = servo 0.3 + misura 0.25) e' ipotesi della sim; il guadagno reale m/s2 per grado, la zona morta, l'isteresi del servo/idraulica.
- La stima del contatto su dati reali di frenata: servono giri con salita lenta (la sim e' l'unica prova). Con stima assente il regolatore usa default prudenti.
- Rumore residuo 0.28 m/s2 sui dati veri: include la componente a 1 Hz (non cancellata dal pettine a T=0.4 s).

## Correzioni di asmile-sicurezza (24/11, banco ALLOW condizionato, strada BLOCK) - versione v3
(b1) Decel in eccesso PRIMA di arrivare a contatto-margine (>= 0.35 m/s2 sopra a_nat per 8 cicli): il contatto e' sbagliato, la salita si ferma subito, il contatto diventa l'angolo attuale (mai sotto contatto_min), conferme azzerate, file riscritto subito.
(b2) Salto massimo della stima 3 gradi per giro (limite anche validato: > 3 rifiutato). File persistito con data: scade dopo 7 giorni (`contatto_scadenza_s`), data assente o nel futuro = ignorato; reset esplicito `Controllo.reset_contatto()` e flag `<file>.reset` (cambio pastiglie: all'avvio ignora e cancella file e flag).
(b3) Contatto CONFERMATO solo con 3 stime coerenti entro 1.5 gradi. Finche' non lo e': vale come ignoto, base = contatto_min-margine, avvicinamento <= 12 gradi/s, niente avvicinamento rapido, niente cap sull'angolo basato su g. Un file ricaricato vale confermato solo se porta conferme >= 3 ed e' fresco (scelta da rivedere: se vuoi la conferma a ogni avvio si cambia una riga).
(c) `g_default_ms2_per_deg` 0.1 -> 0.2. kp = K/g_eff e rampa (forte-dec)/(g_eff*lag) usano g_eff = g appreso solo se confermato, altrimenti max(g, 0.2): con g incerto non sale piu' in fretta. ATTENZIONE: per non far fallire i test esistenti (discesa forte con freno 0.05, distacco encoder) senza allargarli ho dovuto portare `guadagno_anello_1_s` da 0.8 a 1.6: kp con g non appreso resta 8 gradi per m/s come prima (a K=0.8, 1.0, 1.2 falliscono 2 test esistenti). Quindi (c) riduce solo la rampa, non kp: se vuoi kp piu' basso a g ignoto, i test esistenti sul freno debole vanno rivisti da te.

Prima/dopo (36 celle, stessa sim; "v2" = consegna precedente d97c10d2):
| | prima (main) | v2 | v3 |
|---|---|---|---|
| celle con inversioni | 18/36 | 9/36 | 8/36 |
| inversioni a regime (dopo 20 s) | 9/36 | 3/36 | 2/36 |
| impulsi/s max | 18.2 | 9.0 | 8.0 |
| decel max (con pedalate) | 3.69 | 3.20 | 3.00 |
| contatto appreso: |errore| <= 1 gradi | - | 10/28 | 11/28 |
| mediana |errore| contatto | - | 1.9 | 1.3 |
| v media | 12.6 | 13.9 | 15.1 |
Resta: arrivo a 17 con freno >= 0.2 (60-106 inversioni/min nel transitorio, tetto precoce), discese ripide (v max 17-22, un caso a 93 km/h con contatto vero 12 e freno 0.1: il freno non regge, tetto di riserva 15 gradi). v media 15.1 e' alta: in v3 lo stato non confermato inizia spesso sotto il contatto vero e il PI sale piu' lenta nelle discese; i dati sono in tabella.

Test v3: 126 passati (121 + 5 nuovi: non confermato = ignoto, 3 conferme coerenti + salto massimo, correzione per decel prima di base, persistenza/scadenza/reset/flag, g incerto). Il replay vero del 13/11 e' stato eseguito (CSV del repo principale collegato nel worktree).

## v4 - REGOLA DURA sopra v_max (capo 24/11: la cella a 93 km/h era un fallimento di sicurezza)
Cause trovate in sim (steep, contatto 12, freno 0.1, seed 2): (1) l'encoder veniva scartato come "salto irreale" gia' a 22-24 km/h perche' `max_salto_counts` (8000) e' pensato per un campione a 21 ms: con il jitter e campioni piu' distanti la soglia scattava, il sistema passava a GPS_IMU (tetto 15 gradi per la regola di riserva) e poi a NESSUNA (v>54 km/h scartata) = angolo a 0 con la bici in fuga; (2) il regolatore si fermava a contatto_min-margine / a un contatto stimato e rilasciava per rumore sulla decel. Interventi:
- **Regola dura** (freno.py): se v (stimatore) > v_max e la decel netta attesa < voluta -> l'angolo sale a >= 12 gradi/s (rampa_cerca) fino al tetto, indipendente da contatto stimato/confermato, da g, dal blocco "contatto troppo alto" (che abbassa la stima ma non ferma la salita) e dal cap su g. La decel netta attesa e' a_f - g_eff*(salita comandata nell'ultimo `lag`): la parte di freno "in volo" non ancora nella misura (predittore) - senza, la sim sovrastima (overshoot di rampa*ritardo 0.55 s e scatto del tetto precoce anti-impuntata). Esce quando la bici rallenta (decel netta < -0.1 m/s2, `salita_dura_decel_ms2`) e prosegue il PI fine. Salite a 12 gradi/s scartano la ricerca del contatto. NON ho aggiunto la versione "piu' dolce nella zona 12-15": provata (salita forzata a 4 gradi/s con v>13 e in salita) rovinava l'apprendimento del contatto (5 test) - da rivedere con te.
- **Encoder** (fonti.py): il limite di salto e' scalato con il dt reale del campione (`max_salto_counts * max(1, dt/21 ms)`): non allarga la soglia per il dt nominale, corregge il caso di campioni piu' distanti. Resta il tetto fisico a ~29 km/h per campione da 21 ms: sopra, l'encoder e' ancora "salto irreale" e si cade nel fallback: NON toccato (proposta: ricavare il limite da v_max fisica e dt, da decidere con asmile-sicurezza). Il fallback con tetto 15 gradi e "NESSUNA = 0" non e' stato modificato.
- Nuovi test (falliscono sul codice precedente, verificato: 6 falliti): discesa ripida, contatto vero 12/15/20, freno 0.05/0.1, nessuna stima: v < 30 km/h sempre; se il freno al tetto regge (decel fisica netta >= 1.0) v <= 17 dopo 10 s e media a regime < 15, altrimenti il tetto (a meno di 6 gradi) e' raggiunto; mai crescita della v sopra v_max con l'angolo fermo sotto il tetto. Piu': regola dura unitaria (>= 12 gradi/s anche con contatto 'troppo alto' o non confermato), contatto troppo alto non impedisce di frenare.

Discesa ripida 1.2 m/s2, nessuna stima, 64 s (seed 0; vmax = su tutta la corsa dal rullaggio, dopo 10 s = v[10 s:]):
| contatto vero | freno | v max prima (v3) | v max v4 | v max dopo 10 s v4 | media dopo 20 s v4 | angolo max v4 |
|---|---|---|---|---|---|---|
| 12 | 0.1 | 20.0 (93 su altri semi) | 20.0 | 15.5 | 13.3 | 31 |
| 15 | 0.1 | 21.3 | 21.3 | 15.7 | 13.6 | 35 |
| 20 | 0.1 | 250+ | 23.1 | 15.9 | 13.6 | 41 |
| 12 | 0.05 | 250+ | 22.8 | 17.0 | 13.5 | 46 |
| 15 | 0.05 | 250+ | 24.3 | 19.7 | 13.6 | 48 |
| 20 | 0.05 | 250+ | 27.6 | 25.3 | 13.9 | 50 (tetto) |
Con contatto 20 e freno 0.05 il freno al tetto da una decel netta di 0.3 m/s2: il massimo fisico e' raggiunto (angolo 50), la v scende solo piano: dichiarato, non risolvibile dal regolatore. Il transitorio (da 10 km/h con pendenza 1.2 verso 20+ km/h) resta: la zona morta e il ritardo 0.55 s non si recuperano.

Confronto 36 celle (v3 = precedente, v4 = ora): celle con inversioni 8/36 -> 7/36; a regime 2/36 -> 1/36; v max dopo 5 s: max 93 -> 20.0 (mediana 16.1 -> 15.8); **v media a regime: media 15.1 -> 13.8, massimo 50.9 -> 15.6** (resta una cella >= 15: contatto 12, freno 0.3, discesa ripida, 15.6, con 36 inversioni/min); contatto appreso entro 1 grado 8/27 (mediana 1.7 gradi). Arrivo a 17 con freno >= 0.2: ancora 60-110 inversioni/min nel transitorio (tetto precoce anti-impuntata), invariato.

Test v4: 134 passati (126 + 8 nuovi); nessuna soglia di sicurezza allargata; kp 1.6 (guadagno_anello) invariato come richiesto, da rivedere dopo.
