# Lezioni di asmile-banco-hw

Scritte da palla.py dai VETO dei contro-agenti. Leggile prima di ogni lavoro.

- 2026-11-09 **VETO** di asmile-banco-critico su `agents/rapporti/protocollo_sterzo_freno_001.md`: VETO parziale: A/B/D ok con correzioni, C no. 1) vesc_return_centro_001: i_motor letto con query_tach 150 ms DOPO stop() -> legge ~0, il limite imax non scatta mai; se t e' None (VESC muto) il controllo e' saltato: leggere corrente DURANTE l'impulso e abortire se t None. 2) manca check salto encoder (|delta|>200 count per passo = abort) e bici ferma (/tmp/encoder_wheel=0, altrimenti rifiuta). 3) fermare power_steering/altri che usano la UART VESC prima del test (conflitto) e scriverlo nel pre-test. 4) MCCONF: layout a memoria non basta: prima COMM_FW_VERSION e rifiuto se non 5.2 (loggare), controllare signature e lunghezza blob = backup; ripristina deve controllare stessa signature/lunghezza; round-trip float e' test debole. Alternativa piu' sicura: Daniele abbassa i limiti con VESC Tool (versione giusta, backup XML) e lo script resta solo 'leggi'. Non scrivere mcconf da script finche' leggi non e' validato con VESC Tool. 5) power_steering MAX_CURRENT=15 va portato a 5 A (con vai, modifica codice) prima di abilitarlo. 6) Freno D: gradini 0->15->30 ok, aggiungere abort se servo_ma alto con deg fermo; grep BRAKE_*ANGLE da fare su #001 a Pi acceso (NON VERIFICATO). Ripresentare dopo le correzioni 1-3.
  - 2026-11-09 risolto: PASSA di asmile-banco-critico dopo 1 veto. Riletti protocollo+script: i 6 punti corretti nel codice (corrente durante impulso con stop se manca, salto encoder>200, bici ferma, fuser UART, MCCONF solo lettura+FW5.2+signature/lunghezza+VESC Tool

## 2026-11-09 — sterzo #001: prime prove motore
- Duty 0.03 (valore di asmile2) su #001 = ~600 deg/s al manubrio e verso opposto: MAI copiare duty/segno da asmile2.
  Su #001 corrente POSITIVA fa SCENDERE l'encoder sterzo (verso SX).
- Lento si fa in CORRENTE regolata sull'encoder (sterzo_vel_001.py): stacco ~5-9 A, in moto 7-10 A; velocità obiettivo
  dai log di guida reale di Daniele (media 14 deg/s -> 10).
- Lettura GET_VALUES con attesa fissa = 90 ms di loop: leggere il frame esatto (8 ms).
- Scatti residui = hall a gradini (79 count encoder per passo tach, foc_hall_interp_erpm 500 > 20-150 ERPM di lavoro):
  si sistema nel VESC, non nel Pi.
- Controllo di stallo: tarato sul tetto deciso da Daniele (30 A), non 5 A, altrimenti ferma prove valide.

## 2026-11-09 17:30 — "stai facendo disastri: invece che muoversi martella e vibra" (Daniele)
- La metrica di regolarità guardava solo le prove riuscite: le prove fermate da "corrente 27 A" (oscillazione violenta
  ±25 A, verso SX) restavano fuori o contavano poco -> ho scelto KD 0.75 che in metà prove martellava. Ogni prova
  interrotta (corrente, verso sbagliato, superato) = configurazione BOCCIATA, non scartata dalla media.
- Prima di una serie automatica sul motore: max 2 prove per configurazione nuova e STOP alla prima prova violenta.
- KD alto amplifica il rumore della velocità stimata: oltre 0.5 serve un filtro velocità migliore, non più guadagno.
- pkill -f dentro ssh uccide anche la sessione ssh (il pattern è nella riga di comando).

## 2026-11-09 19:05 — coppia bassa sullo sterzo #001 (Daniele: "non sterza", "il vesc non mente")
- Probabile colpa mia: ho abbassato foc_hall_interp_erpm 500 -> 20 per la fluidità. Codice bldc 5.02 (mcpwm_foc.c ~3978):
  sotto quella soglia il VESC usa l'hall più vicino; sopra INTERPOLA, e il commento avverte "might get stuck at 60
  degrees off if a direction change happens". Con manubrio trattenuto/stick-slip (ERPM -74..+129 rumorosi) l'angolo può
  stare fino a 60° fuori -> Iq dichiarata 45 A ma coppia vera molto minore (cos 60° = 0.5 o peggio). Tutte le prove di
  resistenza (15/20/30/45 A) sono state fatte DOPO il cambio. asmile2 aveva 500 e coppia piena con 8-18 A.
- Prossima volta: rimettere 500 (valore di asmile2) e ripetere la resistenza a 30 A. Mai cambiare un parametro FOC
  di commutazione per la fluidità senza ripetere una prova di COPPIA.
- Non accusare l'hardware ("il VESC mente") prima di aver escluso i parametri cambiati da me.

## 2026-11-10 — coppia bassa #001: confrontare Nm/A, non ampere
Rimesso hall_interp 500: coppia invariata (Daniele "niente da fare"). Gli ampere non si confrontano fra unità: conta
1.5 x flux x (giri elettrici per giro di piantone). asmile2 ~0.54 Nm/A, #001 ~0.07 Nm/A (flux 1.32 vs 5.04 mWb, 35 vs ~72 giri el.).
Prima di cambiare parametri VESC per "più coppia", calcola Nm/A dai dati di detection e dal tach/encoder misurato.
Report: agents/rapporti/sterzo_001_vs_asmile2_coppia_20261110.md
