// encoder_monitor.ino — SOLO LETTURA encoder SSI, nessun comando VESC/motore.
// Apri il Serial Monitor a 115200 baud: vedi la posizione che cambia ruotando lo sterzo.

// Pin encoder SSI (stessi di steering_vesc_encoder.ino)
const int CLOCK_PIN        = 4;
const int DATA_PIN         = 3;
const int CLOCK_ENABLE_PIN = 5;  // HIGH sempre
const int DATA_ENABLE_PIN  = 6;  // LOW sempre

const int BITS    = 12;          // AMT222A / Briter 12-bit → 0..4095
const int SAMPLES = 5;           // median filter

uint16_t lastPos = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }           // attende il monitor (utile su alcune board)

  pinMode(CLOCK_PIN, OUTPUT);
  digitalWrite(CLOCK_PIN, HIGH);

  pinMode(CLOCK_ENABLE_PIN, OUTPUT);
  digitalWrite(CLOCK_ENABLE_PIN, HIGH);

  pinMode(DATA_ENABLE_PIN, OUTPUT);
  digitalWrite(DATA_ENABLE_PIN, LOW);

  pinMode(DATA_PIN, INPUT);

  Serial.println("=== ENCODER MONITOR (solo lettura, nessun motore) ===");
  Serial.println("Ruota lo sterzo: la Posizione deve cambiare.");
  Serial.println("Pos\tGradi\tDelta");
}

uint16_t readSingle() {
  uint16_t raw = 0;
  delayMicroseconds(25);
  for (int i = 0; i < BITS; i++) {
    digitalWrite(CLOCK_PIN, LOW);
    delayMicroseconds(1);
    digitalWrite(CLOCK_PIN, HIGH);
    delayMicroseconds(2);
    raw = (raw << 1) | digitalRead(DATA_PIN);
  }
  delayMicroseconds(25);
  return raw;
}

uint16_t readSSI() {
  uint16_t r[SAMPLES];
  for (int i = 0; i < SAMPLES; i++) r[i] = readSingle();
  // median
  for (int i = 0; i < SAMPLES - 1; i++)
    for (int j = i + 1; j < SAMPLES; j++)
      if (r[i] > r[j]) { uint16_t t = r[i]; r[i] = r[j]; r[j] = t; }
  return r[SAMPLES / 2];
}

void loop() {
  uint16_t pos = readSSI();
  int delta = (int)pos - (int)lastPos;
  float gradi = pos * 360.0 / 4096.0;

  Serial.print(pos);
  Serial.print('\t');
  Serial.print(gradi, 1);
  Serial.print('\t');
  Serial.println(delta);

  lastPos = pos;
  delay(100);   // ~10 letture/sec, leggibile a occhio
}
