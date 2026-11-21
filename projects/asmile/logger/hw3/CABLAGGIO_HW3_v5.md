# Cablaggio definitivo logger HW3 nella case v5 SENZA modulo wifi/LTE (20/11/2026)

Case: `stl_v5/` (non `stl_v5_wifi/`). Firmware: quello DEFINITIVO HW3 del 18/11 (`logger02/README.md`), **non si tocca**.
Pin del pettine: `PIN_logger002.md` (pin 1 = 3V3 in alto a sinistra, dispari a sinistra, pari a destra).
Un solo step-up MT3608 a 5,1 V sempre acceso alimenta A e B. A dorme in deep sleep, la sveglia l'INT dell'IMU, A sveglia B
col filo WAKE. Caricatore: **HW-775 DollaTek** (1 cella, 4,2 V, fino a 2 A; solo carica) al posto del MH-CD42. Nessun
pulsante "tieni vivo": serviva solo all'uscita 5 V del MH-CD42 (si spegneva sotto ~45 mA); l'MT3608 attaccato al pacco non
si spegne mai da solo.
Le due celle sono in **parallelo**: non serve bilanciarle, si tengono alla stessa tensione da sole. Unica regola: prima di
saldarle insieme portale alla stessa tensione (differenza < 0,1 V), se no una scarica corrente forte nell'altra.
**Protezione da scarica profonda**: l'MT3608 tira la batteria fino a ~2 V e rovina le celle. Serve UNO di questi:
celle 18650 **protette** (col circuitino sul polo −), oppure una scheda protezione 1S (DW01A + 8205, 3 A) fra pacco e tutto
il resto. Se sull'HW-775 ci sono i pad OUT+/OUT− e due chip a 6 piedini (DW01 e 8205), la protezione è già lì: allora
l'MT3608 e il partitore vanno su OUT+/OUT− e non su B+/B−.

## Pezzi (tutti, prima di saldare)
| # | pezzo | q.tà |
|---|---|---|
| 1 | Waveshare ESP32-P4-Module-DEV-KIT (A = con IMU e partitore, B) | 2 |
| 2 | OV9281 Inno-Maker + flat MIPI | 2 |
| 3 | 18650 in parallelo (2P) nella culla | 2 |
| 4 | HW-775 DollaTek (solo carica, 1 cella) | 1 |
| 4b | protezione 1S DW01A+8205 3 A, se le celle non sono protette e l'HW-775 non ce l'ha | 1 |
| 5 | MT3608 step-up con trimmer | 1 |
| 6 | presa USB-C a pannello (2 fili: VBUS, GND) | 1 |
| 8 | MPU6050 (GY-521) | 1 |
| 9 | resistenze 100 kΩ e 33 kΩ 1/4 W (partitore) | 1 + 1 |
| 10 | altoparlante 30×20 (spina nella presa SPK della A) | 1 |
| 11 | fusibile 3 A con portafusibile in linea (consigliato: un 18650 in corto brucia i fili) | 1 |
| 12 | filo AWG 22 rosso/nero (potenza), AWG 28 colori (segnali), guaina | – |

KY-016: il firmware definitivo **non ha codice LED** → non si collega (resta nelle sue guide, spento). Se un giorno serve, firmware nuovo prima.
TRIG J3 delle camere: il firmware definitivo sincronizza in software (filo SYNC) → J3 **non si collega**.

## Ogni nodo e TUTTO quello che ci arriva
Saldi una volta sola: prima di accendere controlla ogni riga col tester (continuità) e che **BAT+ e GND non suonino fra loro**.

| nodo | cosa ci arriva (tutto) |
|---|---|
| **PACCO+** | + dei due 18650 · capo 1 del fusibile |
| **BAT+** | capo 2 del fusibile · **B+ dell'HW-775** · **IN+ dell'MT3608** · capo 1 della R 100 kΩ |
| **ADC** | capo 2 della R 100 kΩ · capo 1 della R 33 kΩ · **pin 13 della A (GPIO20)** |
| **USB 5V** | VBUS della presa USB-C · **IN+ (5V) dell'HW-775** |
| **5V SCHEDE** | **OUT+ dell'MT3608** · **pin 2 (5V) della A** · **pin 2 (5V) della B** |
| **GND comune** | − dei due 18650 · B− e IN− dell'HW-775 · GND della presa USB-C · IN− e OUT− dell'MT3608 · capo 2 della R 33 kΩ · pin 6 e pin 25 (GND) della A · pin 6 (GND) della B · GND del MPU6050 |
| 3V3 A | pin 1 della A · VCC del MPU6050 (niente altro: mai l'IMU su un altro 3,3 V, lezione 17/11) |
| SDA | pin 3 della A (GPIO7) · SDA del MPU6050 |
| SCL | pin 5 della A (GPIO8) · SCL del MPU6050 |
| INT IMU | pin 18 della A (GPIO4) · INT del MPU6050 |
| WAKE | pin 16 della A (GPIO5) · pin 16 della B (GPIO5) |
| SYNC | pin 19 della A (GPIO3) · pin 11 della B (GPIO21) |
| UART A→B | **pin 10** della A (GPIO22, TX) · **pin 7** della B (GPIO23, RX) |
| UART B→A | **pin 10** della B (GPIO22, TX) · **pin 7** della A (GPIO23, RX) |
| camere | flat camera SINISTRA → connettore CSI della A · flat camera DESTRA → CSI della B |
| altoparlante | presa SPK della A (spina sua) |
| (se c'è la protezione 1S) | pacco → B+/B− della protezione; il suo P+/P− (o OUT+/OUT−) diventa PACCO+ e GND comune |
| USB-C della A e della B | **niente in scatola**: solo per flash/prove al banco. Mai cavo USB e MT3608 insieme sulla stessa scheda |

Niente interruttore (Daniele 21/11: "non serve, deve andare in automatico"): il logger dorme da solo dopo 2 minuti fermo e si sveglia col movimento (INT dell'IMU). Il partitore consuma ~30 µA sempre.
Pin 7 = GPIO23 e pin 10 = GPIO22: letti dallo schema Waveshare (P6) il 20/11, con la stessa numerazione di questo file (pin 1 = 3V3; nello schema Waveshare la numerazione è a specchio: loro 1 = 5V).

## Ordine di lavoro
1. **MT3608 da solo** sul pacco (fusibile già messo): gira il trimmer fino a **5,1 V** a vuoto col tester. Solo dopo lo colleghi alle schede.
2. Partitore: prima di saldare il filo al pin 13 misura il nodo ADC: deve essere **≈ batteria × 0,25** (4,2 V → 1,04 V), mai sopra 3,3 V.
3. USB-C → HW-775: attacca un caricatore e guarda il LED di carica dell'HW-775 (si vede dalla finestra LED carica).
4. IMU, fili A↔B, flat, altoparlante. Poi 5V SCHEDE.
5. Prova: colleghi il pacco → saluto "Narmade Har!" → `stato` dal Mac (batteria letta ≈ tensione del pacco) → lascialo fermo 2 min (col wifi: finito lo scarico) → dorme → scossone → si risveglia.
6. **Consumo da fermo**: tester in serie fra fusibile e BAT+, in deep sleep. Scrivilo qui sotto: decide quanti giorni sta in garage.

## Limiti (onesti)
- MT3608 da 3,0-4,2 V regge ~1-1,5 A continui a 5,1 V (stima): 2 P4 che registrano ci stanno, ma **misura** la corrente a registrazione piena; se l'MT3608 scalda troppo o le schede si riavviano, step-up più grosso.
- Il pacco sotto 3,0 V: il firmware non lo spegne (soglia batteria non nel firmware def). L'MT3608 continua a tirare: non lasciarlo mesi acceso scarico.

## Misure (da riempire)
| cosa | valore | data |
|---|---|---|
| consumo in deep sleep (mA a BAT+) | | |
| consumo in registrazione (mA a BAT+) | | |
