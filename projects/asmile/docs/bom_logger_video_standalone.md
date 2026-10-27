# BOM — Logger video standalone (LiPo + USB-C)

Unità **staccata dalla bici**, autonoma, per raccogliere ore di video stereo da
elaborare poi sul Mac (dataset sim2real / vtest / segmentazione / cattura di
situazioni nuove).

## Scopo e carico

Solo **video logging**: niente UART/VESC, IMU, encoder, timestamp logging.
Carico reale sul rail 5V = **solo Pi 5 + Camarray** ≈ **7–9 W (~1.4–1.8 A)**.
⚠️ Da misurare con wattmetro USB. Il collo non è la corrente ma la capacità del
pacco per fare ore.

**Target autonomia: ~6h** (9W × 6h = 54Wh al carico).

## BOM

| # | Componente | Modello consigliato | Qty | Note |
|---|---|---|---|---|
| 1 | SBC | Raspberry Pi 5 4GB | 1 | 4GB basta (capture-only <1GB). 8/16GB sprecati |
| 2 | Camera stereo | Arducam Camarray HAT (2× OV9281 mono) | 1 | 2560×800 nativo, 1 porta CSI, `LD_PRELOAD arducam_fix.so` |
| 3 | Storage | SSD USB 256GB (o microSD A2 128GB) | 1 | ~225 MB/h: lo spazio non è il problema, l'affidabilità in scrittura sì |
| 4 | Pacco LiPo 2S | 2S 10000mAh (7.4V nom, 8.4V full) = **~74Wh**, BMS/bilanciamento + lead JST-XH 3-pin | 1 | Target 6h (9W×6h=54Wh). Reali ~6h a 9W worst-case (buck 90% + no scarica <3.5V/cella), di più se 7–8W. Margine sano |
| 5 | Caricatore USB-C | Modulo carica 2S Type-C step-up 8.4V (balance, es. IP2312) | 1 | Il "facile": qualsiasi alimentatore/telefono USB-C 5V, carica bilanciata |
| 6 | Step-down 5V | Pololu D24V50F5 (5V/5A) | 1 | 7.4V→5V. Alt. più piccolo/economico: D24V22F5 (2.2A, margine ok) |
| 7 | Protezioni pacco | Fusibile 5A + kill switch | 1 | Sul positivo del pacco |
| 8 | Monitor V + shutdown | ADS1115 + partitore | 1 | Legge V_pacco → beep warning + `shutdown -h`. Due soglie, vedi sotto |
| 9 | Buzzer avviso | Buzzer piezo **attivo** (più potente del KY-006) | 1 | Beep acustico quando V_pacco scende |
| 10 | Driver buzzer | 2N2222 (TO-92) + 1kΩ (470Ω se serve più volume) | 1 | GPIO Pi → base via R, buzzer sul collettore |
| 11 | Interruttore 5V | Switch inline rail 5V (opzionale) | 1 | On/off rapido |

### Logica voltaggio (ADS1115 + buzzer)

LiPo 2S, due soglie lette su V_pacco:
- **~7.2V (3.6V/cella) → beep intermittente di avviso** "batteria bassa, sto per spegnermi"
- **~7.0V (3.5V/cella) → `shutdown -h`** (poi beep continuo/morente durante lo spegnimento)
- Mai scaricare sotto **3.0V/cella**. Soglie LiPo più alte del Li-ion per non rovinare il pacco da logger non presidiato.

## Ricarica — due strade

- **Facile:** modulo carica 2S step-up Type-C (#5). Carichi il 2S da qualsiasi
  caricatore USB-C 5V, zero config, ~1A → pacco 10000mAh in ~9h (ok da notte).
- **Più veloce/robusta:** TP5100 (2S) + trigger USB-C PD a 12V → ~2A, pacco
  10000mAh in ~5h. Serve alimentatore USB-C **PD** (non un 5V qualsiasi).

## Note

- **LiPo = più attenzione del Li-ion:** sacca ignifuga per carica/stoccaggio, mai
  gonfio, mai sotto 3.0V/cella. Per logger non presidiato lo shutdown a 7.0V (#8)
  è ciò che protegge il pacco.
- **Offload al Mac:** WiFi rsync al rientro in rete, pattern `deploy/sync_can_logs.sh`.
- **Software:** Pi 5 non ha H264 HW → encode software (regge 2560@15fps, watt/calore
  già contati). Camarray → `rpicam-vid` + `arducam_fix.so`.

## Alternativa idiot-proof

Un **power bank USB-C PD** integra LiPo + caricatore + protezioni + boost 5V in un
unico oggetto certificato: colleghi il Pi via USB-C e via. Perdi il DIY e un filo
di controllo sullo shutdown, ma è la via più semplice e sicura.

## Aperto

- link d'acquisto + prezzi
- scelta default della strada di ricarica (facile vs PD veloce)
- target ore: ~6h → pacco 2S 10000mAh (~74Wh)
