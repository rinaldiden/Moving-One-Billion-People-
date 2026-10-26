/*
 * AMT223B-V - lettore DEDICATO pulito (bit-bang) - Arduino Uno R3
 * Cablaggio REALE trovato: SCLK=D13, MISO=D12, CS=D11, MOSI=D2
 * (nel connettore CS e MOSI erano incrociati rispetto allo standard).
 *
 * Valida il checkbit e SCARTA le letture sbagliate (niente salti).
 * Serial @115200: pos 0..16383. Gira l'albero piano per un giro completo:
 * deve salire/scendere liscio e wrappare 16383<->0, senza salti random.
 * Segnala "[SALTO]" se due letture valide distano troppo, e "[drop]" sui bad.
 */
#define PIN_SCLK 13
#define PIN_MISO 12
#define PIN_CS   11
#define PIN_MOSI 2

uint16_t amtReadRaw() {
  digitalWrite(PIN_CS, LOW);
  delayMicroseconds(3);
  uint16_t v = 0;
  for (int i = 0; i < 16; i++) {
    digitalWrite(PIN_SCLK, HIGH);
    delayMicroseconds(3);
    v = (v << 1) | (digitalRead(PIN_MISO) & 1);
    digitalWrite(PIN_SCLK, LOW);
    delayMicroseconds(3);
  }
  digitalWrite(PIN_CS, HIGH);
  delayMicroseconds(45);          // T_CS tra letture
  return v;
}

bool okCheckbit(uint16_t v) {
  bool k1 = (v >> 15) & 1, k0 = (v >> 14) & 1;
  bool od = !(((v>>13)&1)^((v>>11)&1)^((v>>9)&1)^((v>>7)&1)^((v>>5)&1)^((v>>3)&1)^((v>>1)&1));
  bool ev = !(((v>>12)&1)^((v>>10)&1)^((v>>8)&1)^((v>>6)&1)^((v>>4)&1)^((v>>2)&1)^((v>>0)&1));
  return (od == k1) && (ev == k0);
}

// ritorna pos valido 0..16383, oppure -1 se nessuna lettura valida (dopo retry)
int readPos() {
  for (int t = 0; t < 5; t++) {
    uint16_t v = amtReadRaw();
    if (v != 0x0000 && v != 0xFFFF && okCheckbit(v)) return v & 0x3FFF;
    delayMicroseconds(80);
  }
  return -1;
}

int lastPos = -1;
unsigned long nValid = 0, nDrop = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SCLK, OUTPUT);
  pinMode(PIN_CS, OUTPUT);
  pinMode(PIN_MOSI, OUTPUT);
  pinMode(PIN_MISO, INPUT_PULLUP);
  digitalWrite(PIN_SCLK, LOW);
  digitalWrite(PIN_CS, HIGH);
  digitalWrite(PIN_MOSI, LOW);
  delay(300);
  Serial.println("AMT223B lettore dedicato start (SCLK=13 MISO=12 CS=11 MOSI=2)");
}

void loop() {
  int p = readPos();
  if (p < 0) {
    nDrop++;
  } else {
    nValid++;
    int d = -1;
    if (lastPos >= 0) {
      d = abs(p - lastPos);
      if (d > 8192) d = 16384 - d;   // wrap 16383<->0
    }
    Serial.print("pos="); Serial.print(p);
    Serial.print("  d="); Serial.print(d);
    Serial.print("  valide="); Serial.print(nValid);
    Serial.print("  drop="); Serial.println(nDrop);
    lastPos = p;
  }
  delay(40);                         // ~20-25 Hz: leggibile e segue bene lo sterzo
}
