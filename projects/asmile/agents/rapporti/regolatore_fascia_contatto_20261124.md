# Regolatore a fascia di contatto - 24/11/2026 (asmile-deploy)

Richiesta Daniele: rilascio dolce se la bici gia' rallenta, poi loop fine nel range in cui il freno sfiora-lavora. NON deployato, non committato.

## Cosa fa
- Nuovi parametri (config/soglie_speed_limiter_v3.json, validati): `freno.angolo_contatto_deg` = 8 (sfiora) e `freno.angolo_lavoro_deg` = 18 (frenata efficace). **SEGNAPOSTO, DA MISURARE A BANCO** (agents/protocolli/freno_contatto_001_20261124.md). Validazione: contatto < lavoro <= tetto <= 50, contatto - margine >= libera_sotto_deg.
- Fasi in `Regolatore` (freno.py), nel log come `fase`:
  1. `libero`: sotto zona-0.5 km/h, angolo 0.
  2. `avvicinamento_contatto`: rampa veloce (25 gradi/s) fino a contatto - margine (6 gradi): le pastiglie NON toccano.
  3. `fine`: PI sulla VELOCITA' (non sull'accelerazione: rumore encoder 0.4 m/s2) attorno a v_obiettivo 13.0 km/h. angolo = (contatto - margine) + kp*e + I; kp ricavata dalla fascia ((lavoro-contatto) gradi alla v_max) x 0.3, piu' un termine solo sopra 15 km/h; ki = kp/5 s. Rampe piccole: 8 gradi/s su, 5 giu.
  4. Rilascio dolce: se decel >= voluta (profilo di zona) l'angolo non sale piu' e l'integrale cala 2 gradi/s; non scende sotto contatto-margine finche' v >= zona - 1.5 km/h (isteresi; ingaggio a zona - 0.5); poi torna a 0 con la rampa di prima.
- Invariati: anti-impuntata, tetti, guardia INA, rilascio/pin (a8536c2c, 3a3551ad), tetto precoce, mai_oltre, picchi massimi. In emergenza le rampe del regolatore sono ignorate.
- Codice: `Rampa.passo(..., r_su, r_giu)` opzionali; `Controllo` le passa; validazione + 12 chiavi di config.

## Sim (agents/prove/freno_001_20261124/sim_fascia.py)
Freno vero: zona morta = contatto (8 gradi), 0.1/0.2/0.3 m/s2 per grado, ritardo 0.25 s, pedalate ~0.4 m/s2, 4 semi, 60 s. "prima" = Regolatore del HEAD (freno_prima.py). "v max 0-10s" include lo stato iniziale; "v max dopo" da 5 s. Jerk = kd x gradi/s oltre il contatto.

| freno | scenario | regolatore | inv/min | gradi/s | impulsi/s | v max 0-10s | v max dopo | v media | ang max | decel max | jerk freno oltre contatto m/s3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1 | discesa ripida | prima | 0.0 | 2.7 | 1.5 | 17.4 | 13.2 | 12.1 | 34 | 1.59 | 2.5 |
| 0.1 | discesa ripida | dopo | 0.0 | 3.9 | 1.9 | 20.2 | 16.7 | 14.1 | 27 | 1.07 | 0.8 |
| 0.1 | discesa forte | prima | 0.0 | 2.5 | 1.4 | 16.2 | 13.0 | 12.1 | 28 | 1.42 | 2.5 |
| 0.1 | discesa forte | dopo | 0.0 | 3.8 | 1.7 | 17.2 | 16.0 | 14.0 | 19 | 0.84 | 0.8 |
| 0.1 | arrivo a 17 | prima | 0.0 | 2.4 | 1.2 | 18.0 | 13.2 | 12.1 | 24 | 1.52 | 2.1 |
| 0.1 | arrivo a 17 | dopo | 0.0 | 3.7 | 1.6 | 18.4 | 14.7 | 13.9 | 18 | 1.05 | 0.8 |
| 0.1 | quasi piano | prima | 0.0 | 2.1 | 1.1 | 15.0 | 12.9 | 12.1 | 15 | 0.97 | 1.4 |
| 0.1 | quasi piano | dopo | 0.0 | 3.5 | 1.4 | 15.0 | 14.5 | 13.9 | 11 | 0.80 | 0.8 |
| 0.2 | discesa ripida | prima | 47.2 | 18.1 | 14.4 | 16.7 | 15.9 | 12.8 | 27 | 2.63 | 12.0 |
| 0.2 | discesa ripida | dopo | 0.0 | 4.0 | 2.0 | 18.5 | 16.0 | 14.1 | 20 | 1.27 | 1.6 |
| 0.2 | discesa forte | prima | 23.5 | 11.4 | 9.1 | 15.8 | 14.7 | 12.6 | 23 | 2.25 | 8.5 |
| 0.2 | discesa forte | dopo | 0.0 | 3.8 | 1.8 | 16.4 | 15.0 | 14.0 | 15 | 0.93 | 1.6 |
| 0.2 | arrivo a 17 | prima | 31.0 | 4.3 | 3.2 | 17.9 | 13.6 | 12.2 | 21 | 2.32 | 10.3 |
| 0.2 | arrivo a 17 | dopo | 0.0 | 3.7 | 1.6 | 18.2 | 15.0 | 14.0 | 16 | 1.43 | 1.6 |
| 0.2 | quasi piano | prima | 0.0 | 2.8 | 1.9 | 14.9 | 13.2 | 12.2 | 14 | 1.21 | 3.0 |
| 0.2 | quasi piano | dopo | 0.0 | 3.6 | 1.6 | 14.9 | 14.5 | 13.9 | 11 | 0.88 | 1.6 |
| 0.3 | discesa ripida | prima | 53.2 | 20.9 | 16.3 | 18.8 | 25.8 | 19.5 | 26 | 3.54 | 18.0 |
| 0.3 | discesa ripida | dopo | 0.0 | 4.3 | 2.5 | 18.1 | 15.9 | 14.3 | 17 | 1.40 | 2.4 |
| 0.3 | discesa forte | prima | 47.8 | 16.0 | 12.2 | 15.7 | 15.4 | 12.7 | 22 | 2.85 | 18.0 |
| 0.3 | discesa forte | dopo | 0.0 | 4.1 | 2.3 | 16.2 | 15.3 | 14.2 | 14 | 1.18 | 2.4 |
| 0.3 | arrivo a 17 | prima | 41.8 | 6.2 | 4.9 | 17.9 | 14.0 | 12.3 | 19 | 2.61 | 18.0 |
| 0.3 | arrivo a 17 | dopo | 0.0 | 4.1 | 2.2 | 18.1 | 14.9 | 14.1 | 16 | 1.89 | 7.5 |
| 0.3 | quasi piano | prima | 0.0 | 3.3 | 2.4 | 14.9 | 13.3 | 12.2 | 14 | 1.38 | 4.9 |
| 0.3 | quasi piano | dopo | 0.0 | 3.8 | 1.9 | 14.8 | 14.7 | 14.1 | 11 | 0.98 | 2.4 |

## Obiettivi: riusciti e NO
- 0 inversioni/min: SI in 12/12 casi (prima 24-53/min a freno 0.2-0.3). Impulsi/s 1.4-2.5 (prima 1.1-16), gradi/s 3.5-4.3 (prima 2.1-21).
- Decel picco 0.8-1.9 m/s2 (prima 1.0-3.5; include il rumore delle pedalate). Jerk del freno 0.8-2.4 m/s3 <= 4. Unica eccezione in tabella: arrivo a 17 con freno 0.3 = 7.5, causato dal tetto precoce anti-impuntata (25 gradi/s sull'IMU simulata), non dal regolatore.
- **v max <= 15.0 dopo il transitorio: SOLO in parte.** Quasi piano 14.5-14.7, arrivo a 17: 14.7-15.0, discesa forte (0.8 m/s2): 15.0-16.0, discesa ripida (1.2 m/s2, ~12%): 15.9-16.7. v media 13.9-14.3 (prima 12.1-12.8: ora regola attorno a 13 invece di assestarsi a 12-13).
- **Transitorio <= 15.8 in discesa ripida: NO** (16.4-20.2 partendo da 13 km/h con angolo 0). Con 1.2 m/s2 la bici fa +2.8 km/h in 0.65 s, meno del ritardo servo (0.25 s) + avvicinamento; anche "prima" faceva 17.4-18.8. Alzare il guadagno: provato in griglia, a freno 0.3 il loop oscilla (60-90 inversioni): il guadagno dell'impianto varia 3x (0.1-0.3 m/s2/grado) e finche' non e' misurato non si puo' alzare. Lo da' la misura a banco.
- Il PROPOSTA_calmo non e' adottato.

## Test
115 passati: 98 esistenti invariati (nessuna soglia di sicurezza allargata) + 17 nuovi in test_fascia_contatto.py (validazione contatto/lavoro, avvicinamento senza frenare, rampe piccole, rilascio dolce, isteresi, sim zona morta 3 freni x 3 scenari). Eseguiti con pytest in cartella temporanea (non installato sul Mac).

## NON VERIFICATO
- Contatto 8 e lavoro 18 sono inventati: il comportamento reale e' NON VERIFICATO finche' non c'e' la misura a banco. kd, ritardo servo e zona morta sono ipotesi della sim.
- Con contatto/lavoro misurati: rifare sim_fascia.py e ritoccare kp_scala, ti_s, v_obiettivo.
- La sim non modella isteresi meccanica del servo ne' scivolamento delle pastiglie.
