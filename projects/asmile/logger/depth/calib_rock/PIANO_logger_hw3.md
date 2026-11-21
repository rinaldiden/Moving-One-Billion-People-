# Calibrazione automatica dei logger HW3 (Inno-Maker OV9281) — piano (Daniele 21/11/2026)

Parte appena logger02 è montato su una bici e ha registrato **un giro** (scarico automatico sul Mac). Niente tabellone.

## 1. Camere: dal riferimento di #001 al set del logger
- Base: `logger/depth/calib_asmile-001.json` (B30, 11/11, stesse camere Inno-Maker) + gemello `calib_rock/`.
- Metodo B del gemello (`autocal.py`, senza tabellone): corregge il **montaggio** (roll/pitch/yaw relativi, inclinazione e
  lunghezza della baseline, scala), non la lente. Su logger02 manca l'encoder ruota: lo yaw (convergenza, invisibile al dy)
  si stima da IMU + video (moto in avanti: un punto fermo si avvicina quanto avanzi) e dal piano strada.
- Giudice: depth per zona 3×3 e per distanza (1-20 m), mai l'RMS (lezione 10/11). Risultato in `calib_logger02.json`,
  mai sovrascrivere quello di #001. Prima prova = **prova del mock** ("vediamo se funziona alla grande"): esito onesto per zona.
- Limite noto: ai bordi la lente B30 è estrapolata (gate rossi del gemello); al centro regge.

## 2. Altezza e inclinazione della camera (non tutti i logger sono montati uguali)
Ogni logger può stare a un'altezza e con un'inclinazione diverse. Si ricavano **dai video**, per ogni sessione (il logger
si può spostare fra un giro e l'altro):
- piano strada dalla depth stereo nel corridoio davanti (RANSAC sui punti bassi) → altezza della camera dal suolo e
  pitch/roll della camera rispetto alla strada;
- conferma con la gravità dell'IMU a bici ferma (vedi 3).
Serve a riportare ogni video nello stesso riferimento (strada orizzontale, camera a quota nota): depth, ostacoli e
traiettoria confrontabili fra logger diversi.

## 3. IMU ↔ camera (orientamento del montaggio)
- La IMU di logger02 (case v5) non è montata come quella di logger001: al **primo giro** si stima la rotazione IMU→camera
  da gravità (soste) + rotazione vista nei video (giroscopio vs rotazione stimata fra fotogrammi).
- Il risultato vale **per la versione del disegno**, non per il singolo logger: tutti i logger con lo stesso supporto IMU
  hanno la stessa rotazione.
- **v6 (21/11)**: la GY-521 è solo traslata rispetto alla v5 (Y +16,6 mm, Z −6,3 mm, stesso piano X0 −145,5, stessi
  inserti c-c 16) → **stessa rotazione della v5**, cambia solo il braccio di 17,8 mm (trascurabile per gravità e
  pitch). Se una versione futura ruota la IMU, si usa la rotazione dell'ultima versione del disegno (ricalcolata dal CAD)
  e si riverifica col primo giro di quel logger.
- File: `imu_montaggio_<versione_case>.json` (rotazione IMU→camera, braccio, da quale giro, esito).

## Cosa serve da Daniele
Solo il giro. Se ha voglia: altezza del centro fra le lenti misurata col metro, per controllare la stima dal piano strada.
