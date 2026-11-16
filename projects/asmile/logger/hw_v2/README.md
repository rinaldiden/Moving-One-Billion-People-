# Logger HW v2 — schema "sistema finale semplificato" (DA REVISIONARE prima di saldare)

Fonte: schema incollato da Daniele il 2026-11-13 ("segna anche questo come schema del logger nuovo per refactorizzare hw;
poi lo aggiorno anche nel logger001"). Unità di destinazione: asmile-logger001 (Camarray SBS, MPU6050) e i logger futuri.
Stato: **PROPOSTA di Daniele + revisione tecnica del capo (sotto). Niente saldature finché i punti ROSSI non sono risolti.**

## Idea
Bici ferma: acceso solo IMU (+ regolatore 3.3 V), Pi spento. Movimento → l'IMU accende il Pi → registra video, legge la
batteria (ADS1115 + partitore), LED RGB stato batteria (verde/arancio/rosso), dongle 4G acceso solo per caricare i file.
Fine movimento → tutto spento tranne IMU.

## Lista pezzi (di Daniele)
| Componente | Q.tà | Note |
|---|---|---|
| Batteria 3S2P 6900 mAh | 1 | già c'è (9.0–12.6 V) |
| AMS1117-3.3 SMD | 1 | |
| MPU6050 | 1 | già c'è |
| MOSFET P (AO3401 o simile) | 1 | high-side, "Vgs ≤ 3 V" |
| Buck 5 V | 1 | già c'è |
| Raspberry Pi 5 | 1 | già c'è |
| Arducam Camarray | 1 | già c'è |
| ADS1115 | 1 | |
| Resistenze 100 kΩ + 33 kΩ | 1+1 | partitore batteria → A0 |
| LED RGB KY-016 | 1 | catodo comune |
| Dongle 4G USB | 1 | |
| Condensatori 10 µF | 2 | in/out AMS1117 (opz.) |

## Collegamenti (di Daniele, per nodo)
- **BAT+**: AMS1117 VIN · MOSFET Source · partitore 100 kΩ (alto)
- **GND comune**: BAT− · AMS1117 GND · IMU GND · gate pull-down 10 kΩ · Buck GND · Pi GND · ADS1115 GND · partitore 33 kΩ (basso) · KY-016 GND
- **3V3_IMU** (AMS1117 VOUT): IMU VCC
- **IMU INT** → MOSFET Gate (+ 10 kΩ a GND)
- **MOSFET Drain** → Buck VIN; **Buck 5 V** → Pi 5V
- **Pi 3V3** → ADS1115 VDD; **Pi SDA/SCL** → ADS1115 SDA/SCL
- **Partitore** centro (100k/33k) → ADS1115 A0
- **Pi GPIO22/23/24** → KY-016 R/G/B; **Pi USB** → dongle 4G

## Revisione tecnica (capo, 2026-11-13) — da risolvere prima di saldare
ROSSI (così non funziona o rompe qualcosa):
1. **Il MOSFET P non si spegne mai.** Source a BAT+ (fino a 12.6 V), gate a 0–3.3 V: Vgs = −9…−12.6 V → sempre ACCESO; il pull-down
   a GND lo tiene acceso anche a riposo. Per un high-side P serve: pull-up gate→Source (es. 100 kΩ) e un **NPN/N-MOS piccolo** che tira il gate
   verso GND quando l'IMU (o il Pi) dice "acceso", con partitore/zener per limitare Vgs.
2. **AO3401: Vgs max ±12 V** → con 3S carica (12.6 V) si supera. Serve un P-MOS con Vgs ±20 V (es. AO3407A, −30 V) o il limite di Vgs del punto 1.
3. **L'IMU non sa dire "fine movimento".** L'MPU6050 dà un impulso breve di "movimento" (o latched), non tiene il segnale alto finché ti muovi
   e non ha un vero "zero motion". Serve l'**autoritenuta**: l'IMU accende, il Pi appena acceso tiene acceso con un suo GPIO (in OR sul transistor
   del punto 1); è il Pi a decidere la fine (nessun movimento per N minuti), chiude i file, fa shutdown e rilascia il GPIO. Così niente spegnimenti
   secchi a metà segmento.
4. **I2C dell'IMU verso il Pi spento.** Il logger legge l'IMU dal Pi (sensor_hub, 50 Hz). Con IMU alimentata e Pi spento, i pull-up del modulo
   GY-521 (al 3.3 V dell'IMU) alimentano i pin I2C del Pi spento (back-powering). Serve un buffer/isolatore I2C con enable alimentato dal Pi
   (es. TCA4307 / PCA9306) oppure togliere i pull-up dal modulo e tenerli lato Pi. Nello schema mancano anche SDA/SCL IMU→Pi.
GIALLI (da decidere):
5. AMS1117: corrente a vuoto ~5 mA, non "µA" (6.9 Ah → ~2 mesi). Per riposo davvero basso: LDO a basso consumo (MCP1700/HT7333, Vin max 6–24 V: verificare per 12.6 V).
6. Buck 5 V: il Pi 5 vuole 5.1 V / fino a 5 A con camera + dongle 4G → verificare taglia del buck che hai.
7. KY-016: verificare se il modulo ha le resistenze sui LED; se no, 220–330 Ω in serie su R/G/B.
8. Dongle 4G "acceso solo per caricare": sul Pi 5 le USB si possono spegnere via software (uhubctl, tutte le porte insieme) — da provare col tuo dongle.
9. Partitore 100k/33k: 12.6 V → 3.13 V su A0, ok con ADS1115 a ±4.096 V; consuma ~95 µA sempre (accettabile).
10. Orologio: senza RTC con batteria il logger riparte da un'ora finta a ogni boot (oggi nomi clip_20261029_163306 sovrascritti fra un boot e l'altro).
    Nel v2: batteria RTC del Pi 5 (connettore J5) oppure nomi dei file con boot_id.

## Prossimi passi
1. Daniele conferma/sceglie sui punti 1–4 (sono la parte "accensione/spegnimento").
2. Lista componenti completa definitiva + net-list per piedino (regola: lista pezzi prima, una saldatura sola).
3. Prova a banco: corrente a riposo, accensione da movimento, autoritenuta, shutdown pulito.

## Schema completo rifattorizzato (2026-11-15)
`logger/hw_v2/schema_cablaggio_logger_v2.html`: BOM, schema a blocchi, net-list per nodo, per piedino, funzionamento, config, prova a banco. Risolve i 4 punti rossi sopra (proposta da validare).
- Montaggio con figure pin per pin (pezzi a foro passante: IRF4905, BS170, MCP1703-3302E/TO, 1N5817): `logger/hw_v2/montaggio_pin_logger_v2.html`.
- PDF unico da stampare (montaggio con figure + schema completo): `logger/hw_v2/collegamento_logger_v2.pdf`.
- Schema elettrico completo su una pagina A3 (etichette di rete, tutti i pin): `logger/hw_v2/schema_elettrico_logger_v2.pdf` (generato da `gen_schema_elettrico.py`); è anche la prima pagina di `collegamento_logger_v2.pdf`.
