# asmile-logger001: IMU vs video, sessione clip_20261109_085836 (2026-11-09)

Esito breve: **in questa sessione NON c'e' nessun giro in strada**. Assi IMU stimati dal video con 3 assi concordi; **accel/decel longitudinali NON verificabili**. Serve un giro vero.

## 1. Allineamento frame-IMU
- Video: 44 clip x 465 frame = 20460 frame (15 fps). Frames CSV (riletto a sync finito): 20239 righe valide, indici monotoni, **0 gap > 100 ms** (67 ms fissi). Ultimi 221 frame (~14.7 s) senza t_ms (CSV tagliato in coda, aveva anche una riga di NUL): ultimi ~15 s di video non allineabili.
- IMU: 68300 righe a 20 ms, 7 buchi > 40 ms (max 64 ms), nessuno > 500.
- **20237/20239 frame (99.99%) hanno una riga IMU entro 20 ms** (entro 10 ms: 99.98%, max scarto 30 ms). Orologio comune confermato anche dal lag di correlazione = 0 ms.
- Nota: sessione sensors_20261109_085838 ora e' 1366 s (09:21:24); nel primo pull era troncata a 1122 s.

## 2. Movimento dal video (Farneback su left 320x200)
- Frame con moto: ~9% (flusso > 0.05 px). Il tempo e' diviso cosi':
  - frame 0-~900 (08:58:40-08:59:40): rig **in mano** (mano davanti all'obiettivo, immagini bruciate/nere, frame 150, 300, 450, 600): img/logger001_imu_frame00150.jpg
  - frame ~900-2500: rig montato davanti a una **bici su cavalletto in officina**, gente che passa (frame 900 e 1500)
  - frame ~2550-3050 (09:01:50-09:02:00 circa): ultimo trambusto
  - frame ~3050-20239 (~1150 s, 85%): **fermo totale** (IMU: 85.4% fermo, flusso 0.0006 px).
- Nessuna marcia: niente espansione coerente, niente frenata. Quindi **nessuna velocita' metrica dal video e nessuna accelerazione di riferimento** (la calib metro non serve: nessun moto traslatorio da scalare).
- Altre sessioni di oggi con IMU: 084847 (205 s, 23% gyro attivo, nessun video), 100557 (80 s, fermo, video clip_100554). Nessuna marcia.

## 3. IMU
- Fermo (085838, ultimi 30 s): acc (0.0687, 0.0028, 1.1826) g, |a| = 1.1846; 100557: |a| = 1.201. Gyro bias fermo (-1.765, -0.674, +0.968) dps, std 0.03.
- Per 50 s iniziali ax ~ +0.95 g: il rig e' in mano con X verso l'alto; poi X orizzontale, Z su (az +1.18). Quindi **"Z su" confermato** da gravita' a rig montato.
- Gyro vs video (frame attivi, lag cercato +-300 ms):

| coppia | r | lag | lettura |
|---|---|---|---|
| gz vs flusso orizzontale (yaw) | +0.446 | 0 ms | gz>0: scena a destra, camera a sinistra |
| gy vs flusso verticale (pitch) | +0.311 | -10 ms | gy>0: scena in giu', camera su |
| gx vs rotazione immagine (roll) | +0.580 | 0 ms | gx>0: scena oraria |
| incroci (gy-orizz, gz-vert) | 0.05, -0.23 | - | assenti, ok |

  Tre assi coerenti con **X indietro, Y destra, Z su** (destrorso). La freccia "X verso la marcia" e' **smentita** (rispetto all'asse ottico della camera). Pendenze flusso/gyro basse (0.05 px/frame per dps contro 0.27 atteso con f~232 px): flusso Farneback degradato da blur e traslazioni di mano, quindi la **scala del gyro non e' stimata dal video**; con la relazione gravita'/gyro dA/dt = -(w x a) pero' pendenza y 1.02, z 0.88 (positiva): accel e gyro stesso frame, scala gyro ~1.
- Accel: **segno di ax in accelerazione non verificato** (r flusso-accel < 0.1, nessuna marcia). Il segno dedotto dal gyro vale solo se il chip e' un corpo rigido unico, probabile ma non provato.
- Scala acc: |g| 1.18-1.20 invece di 1; scala globale 0.8457. Ellissoide per asse non stimabile (orientamenti tutti Z su).

## 4. Proposta
agents/rapporti/logger001_imu_assi_PROPOSTA_20261109.json: ax_b=-ax, ay_b=-ay, az_b=+az, idem gyro (rotazione 180 gradi su Z), bias gyro, scala acc 0.8457. NON applicata al Pi.

## 5. Da fare
1. Giro vero (partenza, regime, frenata dritta, 2 curve) con video e IMU: confermare segno ax (frenata = ax_b negativo) e correlazione con velocita' video (o sensore ruota BT, che da' il riferimento).
2. Calibrazione acc a 6 posizioni (rig staccato).
3. Ricalcolare bias gyro a inizio di ogni sessione (deriva 0.2 dps fra sessioni).
4. Sync clip: il frames CSV va flushato a fine sessione (ultimi 15 s senza t_ms).

Immagini: agents/rapporti/img/logger001_imu_frame00150.jpg, ..00900, ..01500, ..03000, serie logger001_imu_serie_0_220s.png (flusso, acc, gyro nei primi 220 s).
Frame -> orario: wall = 08:58:38.665 + (t_ms - 78661) ms; frame 0 = 08:58:39.84, ogni 15 frame = 1 s.
