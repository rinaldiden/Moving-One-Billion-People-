# logger02: protezione batteria a 3 V (24/11)

Causa: celle a 1,9 V (tester di Daniele) mentre il firmware leggeva 2,03 V (salute_*.csv batt_v, /api/stato). Lo step-up non stacca e il firmware non proteggeva. Decisione di Daniele: "il logger si spegne ai 3 V".

## Cosa fa (sopra HEAD 891eb001, include "sveglio mentre scarica"/"scarico affidabile")
1. Taratura: `L02_BATT_SCALA = 0.936` (2,03 letti -> 1,90 veri), UNICO posto: `main/logger02_batt_logic.h`. Un solo punto a cella scarica: da rifare con 2 punti (cella carica + scarica). Tolto il vecchio "sotto 2 V = partitore scollegato" (nascondeva la cella vera); il pin libero resta escluso dal pull-down.
2. Spegnimento: media mobile di 5 letture (1 Hz), media < 3,0 V per 10 s consecutivi (finestra piena, un ritorno sopra azzera). Poi: ESP_LOGE del motivo + NVS (`salute`: bstop_n/tipo/mv) -> chiude pezzo video, CSV IMU, salute (scrive errori_*.log) -> "Z" alla B -> IMU in sleep, WAKE tenuto basso -> deep sleep SENZA sorgenti (nessun IMU, timer, WAKE): riparte solo con reset/riaccensione. Controllo nel task IMU subito dopo la lettura, prima di ferma/scarico/pausa: prioritario su tutto. Al riavvio il motivo e' rilogato come E nel registro errori.
3. Avvio (solo A, dopo example_video_init, prima di saluto/wifi/rec): 6 letture in 3 s, media < 3,1 V -> niente avvio, WAKE basso 4 s (la B dorme), deep sleep senza risvegli. Isteresi 0,1 V sopra i 3,0 di spegnimento: la cella appena spenta risale a vuoto e senza isteresi ripartirebbe-crollerebbe-si spegnerebbe in loop.
4. Batteria assente (<0,5 V, NaN, pin libero): NON spegne, azzera il conteggio, avviso W ogni 60 s "protezione 3 V NON attiva"; `/api/stato` mostra `protezione_3v` e `batt_media_v`. All'avvio: avvio normale + avviso.

## Prove
- `host_test/test_batt_logic.c`: TUTTO OK (taratura, 10 s, 3,00/3,05 non spegne, dente di sega, picchi isolati, calo breve, ritorno sopra, assente/NaN/0,4, isteresi avvio 3,08 rifiuta / 3,10 parte, caso 24/11). `test_sleep_logic.c` ancora verde.
- Build ESP-IDF 5.5.6 in copia separata: OK, 0x1c6000 byte (56% libero).
- NON VERIFICATO sul dispositivo: spegnimento reale, sonno senza risvegli, B che dorme col WAKE basso, ritardo 3 s avvio, tolleranza della taratura (un punto): a 3 V veri la lettura puo' essere +/-0,2 V. Non caricato su logger02 (Daniele: non toccare).

## Rollback
Nessun deploy fatto. Al deploy: ota.sh con rollback automatico (conferma dopo 3 min di rete). Se la protezione fa danni (spegne con cella buona per taratura sbagliata): reset/riaccensione + OTA del firmware precedente (ac6d8974); `L02_BATT_SCALA` e soglie in un solo header.
