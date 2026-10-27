/*
 * AMT22 DUAL bridge - Arduino Uno R3 -> USB serial verso Raspberry Pi
 *
 * Legge DUE encoder AMT22 in bit-bang (metodo validato 0-drop) e manda le due
 * posizioni su USB. Il Pi legge /dev/ttyACM0 come se i dati arrivassero da lui.
 *
 * Cablaggio:
 *   CONDIVISI (in parallelo sui due encoder):
 *     SCLK -> D13 | MISO -> D12 | MOSI -> D2 | 5V -> 5V | GND -> GND
 *   CHIP SELECT dedicati:
 *     STERZO (enc1) CS -> D11
 *     RUOTA  (enc2) CS -> D10   <-- unico filo nuovo del secondo encoder
 *   (switch di ogni encoder in RUN prima di alimentare)
 *
 * Output @500000 baud, una riga per campione:
 *   "<pos_sterzo>,<pos_ruota>\n"   (valore -1 = lettura non valida)
 * pos 0..16383 (14 bit). Latenza bassa: letture ~0.4ms + TX ~0.2ms.
 */
#define PIN_SCLK 13
#define PIN_MISO 12
#define PIN_MOSI 2
#define CS_STEER 11
#define CS_WHEEL 10

uint16_t readRaw(uint8_t cs) {
  digitalWrite(cs, LOW);
  delayMicroseconds(3);
  uint16_t v = 0;
  for (int i = 0; i < 16; i++) {
    digitalWrite(PIN_SCLK, HIGH);
    delayMicroseconds(3);
    v = (v << 1) | digitalRead(PIN_MISO);
    digitalWrite(PIN_SCLK, LOW);
    delayMicroseconds(3);
  }
  digitalWrite(cs, HIGH);
  delayMicroseconds(40);          // T_CS tra letture
  return v;
}

bool ckbit(uint16_t v) {
  bool k1 = (v >> 15) & 1, k0 = (v >> 14) & 1;
  bool od = !(((v>>13)&1)^((v>>11)&1)^((v>>9)&1)^((v>>7)&1)^((v>>5)&1)^((v>>3)&1)^((v>>1)&1));
  bool ev = !(((v>>12)&1)^((v>>10)&1)^((v>>8)&1)^((v>>6)&1)^((v>>4)&1)^((v>>2)&1)^((v>>0)&1));
  return (od == k1) && (ev == k0);
}

int readPos(uint8_t cs) {
  for (int t = 0; t < 3; t++) {
    uint16_t v = readRaw(cs);
    if (v != 0x0000 && v != 0xFFFF && ckbit(v)) return v & 0x3FFF;
  }
  return -1;
}

void setup() {
  Serial.begin(500000);
  pinMode(PIN_SCLK, OUTPUT);
  pinMode(PIN_MOSI, OUTPUT);
  pinMode(CS_STEER, OUTPUT);
  pinMode(CS_WHEEL, OUTPUT);
  pinMode(PIN_MISO, INPUT_PULLUP);
  digitalWrite(PIN_SCLK, LOW);
  digitalWrite(PIN_MOSI, LOW);
  digitalWrite(CS_STEER, HIGH);
  digitalWrite(CS_WHEEL, HIGH);
}

void loop() {
  int s = readPos(CS_STEER);
  int w = readPos(CS_WHEEL);
  Serial.print(s);
  Serial.print(',');
  Serial.println(w);
}
