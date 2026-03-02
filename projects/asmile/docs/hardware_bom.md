# Bill of Materials — Asmile

Lista completa hardware per il sistema di guida autonoma bicicletta.

## Computazione

| # | Componente | Modello | Quantità | Note |
|---|---|---|---|---|
| 1 | Single Board Computer | Raspberry Pi 5 Model B | 1 | 8GB RAM consigliato |
| 2 | Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | 1 | Global shutter, 1280x400 stereo |

## Sterzo

| # | Componente | Modello | Quantità | Note |
|---|---|---|---|---|
| 3 | Controller motore | VESC (FOC) | 1 | Firmware FOC configurato |
| 4 | Motore sterzo | Flipsky 6354 BLDC | 1 | Collegato al VESC (3 fasi U/V/W) |
| 5 | Encoder assoluto | Briter 5V 12-bit SSI | 1 | Posizione sterzo, uscita differenziale RS-485 |
| 6 | Modulo RS-485 | TTL to RS-485 (MAX485) | 2 | #1 per CLOCK, #2 per DATA |
| 6b | Coppia conica | Rapporto 1:5 (⚠️ DA VERIFICARE) | 1 | Accoppiamento motore Flipsky 6354 ↔ asse sterzo |

## Frenata

| # | Componente | Modello | Quantità | Note |
|---|---|---|---|---|
| 7 | Servomotore freno | PDI-6221MG (20kg, 180°) | 1 | 6V, PWM 500-2500µs |
| 8 | Freno meccanico | Freno idraulico a disco | 1 | Servo collegato al pompante |

## Sensori

| # | Componente | Modello | Quantità | Note |
|---|---|---|---|---|
| 9 | GPS | NEO-M10 | 1 | UART, 9600 baud default |
| 10 | IMU | MPU6050 | 1 | I2C, accelerometro + giroscopio, feedback frenata |

## Alimentazione

| # | Componente | Modello | Quantità | Note |
|---|---|---|---|---|
| 11 | Batteria | 13S Li-ion 48V | 1 | ~54.6V carica, alimenta tutto |
| 12 | Step-down 5V | Pololu D24V55F5 | 1 | 48V→5V, per Raspberry Pi + periferiche |
| 13 | Step-down 6V | Pololu D24V55F6 | 1 | 48V→6V, per servo freno PDI-6221MG |

## Previsti / Futuri

| # | Componente | Note |
|---|---|---|
| 14 | Sensori ultrasuoni | Rilevamento ostacoli laterali/posteriori |
| 15 | Encoder ruota | Velocità/odometria |
| 16 | Kill switch / E-stop | Interruttore emergenza sulla linea 48V |
| 17 | Secondo Raspberry Pi 5 | Ridondanza con failover |

## Interfacce Utilizzate sul Raspi 5

```
UART0 (/dev/ttyAMA0)  → VESC (sterzo)
UART3 (/dev/ttyAMA3)  → GPS NEO-M10
I2C1  (bus 1, 0x68)   → MPU6050 IMU
PWM0  (GPIO 12)       → Servo freno PDI-6221MG
GPIO  (bit-bang SSI)   → Encoder Briter (via RS-485)
CSI   (camera port)    → Arducam Camarray HAT
```

## Documenti Correlati

| Documento | Percorso |
|---|---|
| Schema collegamento pin Raspi | [wiring_raspi5.md](wiring_raspi5.md) |
| Schema alimentazione 48V | [power_48v.md](power_48v.md) |
| Config VESC FOC | [../config/vesc_foc_ok.xml](../config/vesc_foc_ok.xml) |
| Config camera OV9281 | [../config/ov9281_mono_pisp.json](../config/ov9281_mono_pisp.json) |
