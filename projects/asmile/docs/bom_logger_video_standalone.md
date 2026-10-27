# BOM — Logger video standalone (LiPo + USB-C)

Unità **staccata dalla bici**, autonoma, per raccogliere ore di video stereo da
elaborare poi sul Mac (dataset sim2real / vtest / segmentazione / cattura di
situazioni nuove).

## Scopo e carico

Solo **video logging**: niente UART/VESC, IMU, encoder, timestamp logging.
Carico reale sul rail 5V = **solo Pi 5 + Camarray** ≈ **7–9 W (~1.4–1.8 A)**.
⚠️ Da misurare con wattmetro USB. Il collo non è la corrente ma la capacità del
pacco per fare ore.

## BOM

| # | Componente | Modello consigliato | Qty | Note |
|---|---|---|---|---|
| 1 | SBC | Raspberry Pi 5 4GB | 1 | 4GB basta (capture-only <1GB). 8/16GB sprecati |
| 2 | Camera stereo | Arducam Camarray HAT (2× OV9281 mono) | 1 | 2560×800 nativo, 1 porta CSI, `LD_PRELOAD arducam_fix.so` |
| 3 | Storage | SSD USB 256GB (o microSD A2 128GB) | 1 | ~225 MB/h: lo spazio non è il problema, l'affidabilità in scrittura sì |
| 4 | Pacco LiPo 2S | 2S ~13500–14000mAh (7.4V nom, 8.4V full) = **100Wh**, BMS/bilanciamento + lead JST-XH 3-pin. Es. 2× 2S 7000mAh in parallelo | 1 | Target 90Wh (9W×10h) arrotondato a 100Wh. Reali ~8.5–9h a 9W worst-case (buck 90% + no scarica <3.5V/cella); 10h+ se carico 7–8W. 100Wh = tetto bagaglio aereo, non superare |
| 5 | Caricatore USB-C | Modulo carica 2S Type-C step-up 8.4V (balance, es. IP2312) | 1 | Il "facile": qualsiasi alimentatore/telefono USB-C 5V, carica bilanciata |
| 6 | Step-down 5V | Pololu D24V50F5 (5V/5A) | 1 | 7.4V→5V. Alt. più piccolo/economico: D24V22F5 (2.2A, margine ok) |
| 7 | Protezioni pacco | Fusibile 5A + kill switch | 1 | Sul positivo del pacco |
| 8 | Shutdown non presidiato | ADS1115 + partitore | 1 | V_pacco → `shutdown -h`. Soglia LiPo PIÙ ALTA **7.0V (3.5V/cella)**, mai sotto 3.0V/cella |
| 9 | Interruttore 5V | Switch inline rail 5V (opzionale) | 1 | On/off rapido |

## Ricarica — due strade

- **Facile ma lento:** modulo carica 2S step-up Type-C (#5). Carichi il 2S da
  qualsiasi caricatore USB-C 5V, zero config, ma ~1A → pacco 100Wh in ~13–14h.
- **Più veloce/robusta (consigliata con 100Wh):** TP5100 (2S) + trigger USB-C PD
  a 12V → ~2A, pacco 100Wh in ~7h. Serve alimentatore USB-C **PD** (non un 5V qualsiasi).

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
- target ore: ~10h → pacco 100Wh (2S ~13.5–14Ah)
