# Encoder Briter SSI — Conversazione Grok (Arduino setup che funzionava)

Conversazione completa con Grok dove l'encoder Briter BRT38 SSI 12-bit
veniva letto con successo da Arduino via 2 moduli RS-485 (MAX485 C25B).

Source: https://grok.com/share/c2hhcmQtNA_fb7c6489-e50b-4b41-88e7-7b2085a03795

---

## Encoder Model
- BRT38 ROM 1024 D24 R71 IP68
- SSI interface protocol
- 12-bit (ma nel modello dice 1024 = 10-bit, verificare)
- 6 fili: Red, Black, Green, White, Yellow, Orange

## Wire Colors (confirmed from working Arduino setup)
| Wire    | Function                        |
|---------|---------------------------------|
| Red     | VCC (5V)                        |
| Black   | GND                             |
| Green   | CLK (clock, via RS-485 #1)      |
| White   | DO/DATA (data out, via RS-485 #2) |
| Yellow  | ZR (zero reset) — DO NOT CONNECT |
| Orange  | Config mode — DO NOT CONNECT     |

## LED Status
- **Green** = normal SSI mode (working)
- **Blue flashing** = Biss/config mode (WRONG — needs reset)
- Blue mode triggered if Yellow or Orange touch GND during power-on

## Reset Procedure (if LED is blue)
1. Disconnect Yellow and Orange (leave floating/insulated)
2. Power off encoder (remove 5V from Red)
3. Connect Orange to GND (Black) for 5 seconds
4. Disconnect Orange from GND
5. Reconnect 5V to encoder
6. Wait 10 seconds — LED should return to green

## SSI Protocol Parameters (from datasheet)
- Clock idle: HIGH
- Data latch: on falling edge
- Data stable/read: on rising edge
- Bit order: MSB first
- Encoding: raw binary (NOT Gray code despite datasheet saying Gray)
- t1 < 1us (clock low time)
- t2 + t3 > 0.5us (clock high time + data delay)
- t4 > 20us (monoflop timeout between reads)
- T = 500ns ~ 10us (suggested clock period)

## Arduino Pin Setup (worked)
- CLOCK_PIN = 4 (output)
- DATA_PIN = 3 (input)
- CLOCK_ENABLE_PIN = 5 (output, always HIGH — RS-485 #1 DE)
- DATA_ENABLE_PIN = 6 (output, always LOW — RS-485 #2 RE)

## Arduino Sketch That Worked (raw binary, no Gray conversion)

```cpp
#include <SoftwareSerial.h>
#include <VescUart.h>

const int CLOCK_PIN = 4;
const int DATA_PIN  = 3;
const int CLOCK_ENABLE_PIN = 5;  // HIGH sempre
const int DATA_ENABLE_PIN  = 6;  // LOW sempre

const int BITS = 12;
const int SAMPLES = 5;
const int MIN_CHANGE = 5;  // ~mezzo grado

uint16_t lastPos = 2048;

SoftwareSerial vescSerial(10, 11);  // RX=10, TX=11 per VESC
VescUart UART;

void setup() {
  Serial.begin(115200);
  vescSerial.begin(115200);
  UART.setSerialPort(&vescSerial);

  pinMode(CLOCK_PIN, OUTPUT);
  digitalWrite(CLOCK_PIN, HIGH);  // Idle HIGH

  pinMode(CLOCK_ENABLE_PIN, OUTPUT);
  digitalWrite(CLOCK_ENABLE_PIN, HIGH);

  pinMode(DATA_ENABLE_PIN, OUTPUT);
  digitalWrite(DATA_ENABLE_PIN, LOW);

  pinMode(DATA_PIN, INPUT);

  UART.setDuty(0.0);
}

uint16_t readSingle() {
  uint16_t raw = 0;

  delayMicroseconds(25);  // t4 >20us

  for (int i = 0; i < BITS; i++) {
    digitalWrite(CLOCK_PIN, LOW);   // Falling edge - latch
    delayMicroseconds(1);           // t1 <1us

    digitalWrite(CLOCK_PIN, HIGH);  // Rising edge - data stable
    delayMicroseconds(2);           // t2+t3 >0.5us

    raw = (raw << 1) | digitalRead(DATA_PIN);  // MSB first
  }

  delayMicroseconds(25);

  return raw;  // Raw binary = position (no Gray conversion needed)
}

uint16_t readSSI() {
  uint16_t readings[SAMPLES];

  for (int i = 0; i < SAMPLES; i++) {
    readings[i] = readSingle();
  }

  // Median filter
  for (int i = 0; i < SAMPLES - 1; i++) {
    for (int j = i + 1; j < SAMPLES; j++) {
      if (readings[i] > readings[j]) {
        uint16_t temp = readings[i];
        readings[i] = readings[j];
        readings[j] = temp;
      }
    }
  }

  return readings[SAMPLES / 2];
}

void loop() {
  uint16_t position = readSSI();

  if (abs(position - lastPos) >= MIN_CHANGE) {
    float duty = (position - 2048.0) / 2048.0;
    UART.setDuty(duty);
    lastPos = position;
  }

  delay(20);
}
```

## Key Findings from Arduino Testing
1. Raw BIN changed only 1 bit at a time (proper Gray code from encoder)
2. Raw DEC increased almost linearly (+1, +2, +3 increments)
3. Gray-to-binary conversion FAILED (made jumps worse) — encoder sends raw binary, not true Gray
4. Using raw DEC directly as position = smooth, linear, perfect
5. Median filter (5 samples) eliminates remaining spikes
6. RS-485 modules (MAX485 C25B) at 5V worked fine
7. 120 ohm termination resistor between A/B helped but wasn't critical
8. Wrap-around at 0/4095 boundary caused motor to spin full speed — needs wrap handling

## VESC Integration (worked on Arduino)
- Library: VescUart 1.0.1 by SolidGeek
- Baud: 115200
- SoftwareSerial on pins 10 (RX), 11 (TX)
- Level shifter needed: Arduino 5V TX -> 3.3V VESC RX
- VESC RX 3.3V -> Arduino RX 5V: direct (no shifter needed)
- VESC COMM connector (8-pin): pin 3=TX, pin 4=RX, pin 1=3.3V, pin 6=GND
- Duty mapping: (position - 2048) / 2048 = -1.0 to +1.0
- Differential mode: duty based on delta (change in position), not absolute position
- MIN_CHANGE = 5 units (~0.5 degree) filter before sending command

## Transition to Raspberry Pi
- Same 2x RS-485 module setup
- Pi GPIO 17 = clock out, GPIO 27 = data in
- RS-485 modules need 5V (MAX485 doesn't work at 3.3V)
- Level shifter (BSS138 bidirectional) between Pi 3.3V GPIO and RS-485 5V TTL
- PROBLEM: LED turned blue = encoder entered wrong mode during wiring
- SOLUTION: Reset encoder (see procedure above), keep Yellow/Orange insulated

## Raspberry Pi Wiring (current, from wiring_raspi5.md)
See: projects/asmile/docs/wiring_raspi5.md

RS-485 #1 (CLOCK, transmit):
- VCC: 5V (via level shifter HV)
- DI: GPIO 17 via level shifter LV1->HV1
- DE: 5V (always TX)
- RE: 5V (always TX)
- GND: common
- A -> Green wire (CLK)
- B -> Brown wire (but should be second CLK wire or unused)

RS-485 #2 (DATA, receive):
- VCC: 5V
- RO: GPIO 27 via level shifter HV2->LV2
- DE: GND (always RX)
- RE: GND (always RX)
- GND: common
- A -> White wire (DATA)
- B -> Gray wire (but should be second DATA wire or unused)

## TODO for Next Session
1. **Reset encoder to SSI mode** (green LED) using Orange wire procedure
2. Verify Yellow and Orange are insulated/not connected
3. Run test_encoder_diag.py to check if encoder responds
4. If still 4095, check physical wire connections Green->A, White->A on correct modules
5. Once reading works, port the Arduino duty control to Python for VESC
