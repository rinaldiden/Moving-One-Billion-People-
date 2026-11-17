# Logger002 (HW3) — pin definitivi su Waveshare ESP32-P4-Module-DEV-KIT (17/11/2026)

Fonte: tabella GPIO + pinout del pettine Waveshare (docs.waveshare.com/ESP32-P4-Module-DEV-KIT).
Pettine 40 pin: pin 1 = 3V3 in alto a sinistra, dispari a sinistra, pari a destra.
Già occupati sulla scheda: GPIO7/8 I2C (camera SCCB + ES8311), 9-13 audio I2S, 53 PA audio, 14-19 + 6 + 54 C6 (wifi/BT),
39-45 SD, 28-31/34/35/49-52 Ethernet, 37/38 console, 24/25 USB, 35 BOOT.

## IMU MPU6050 → A
VCC→pin1 (3V3) · GND→pin9 · SDA→pin3 (GPIO7) · SCL→pin5 (GPIO8) · INT→pin18 (GPIO4, LP: sveglia dal deep sleep)

## Batteria → A
Per contatto (3 nodi):
- Batteria+ (dopo interruttore): capo 1 R 100 kΩ (+ IN+ buck in scatola)
- Nodo centrale: capo 2 R 100 kΩ + capo 1 R 33 kΩ + pin13 A (GPIO20, ADC1_CH4)
- GND: capo 2 R 33 kΩ + batteria− + pin25 A (GND)  ← batteria− su GND della A OBBLIGATORIO (riferimento ADC)
Prima di collegare pin13: nodo ≈ batteria/4, mai > 3,3 V. Satura sopra ~12,4 V (ok: interessa la soglia bassa).

## A ↔ B
GND pin9↔pin9 · SYNC GPIO21 pin11↔pin11 · WAKE GPIO5 pin16↔pin16 (LP su B) ·
UART incrociata: A pin12 (GPIO22 TX)→B pin7 (GPIO23 RX), B pin12 (TX)→A pin7 (RX).

## Dopo (prova 4)
TRIG camere: A pin19 (GPIO3) → J3 TRIG camera SX + DX; J3 GND → GND.

## Alimentazione
B: buck USB-C. A: Mac via USB per le prove; in scatola buck su pin2 (5V) + pin6 (GND). Mai due alimentazioni sulla stessa scheda.
