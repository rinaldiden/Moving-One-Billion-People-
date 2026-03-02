#include <SoftwareSerial.h>
#include <VescUart.h>

SoftwareSerial vescSerial(10, 11);  // RX=10, TX=11 per VESC
VescUart UART;

// Pin encoder SSI
const int CLOCK_PIN = 4;
const int DATA_PIN  = 3;
const int CLOCK_ENABLE_PIN = 5;  // HIGH sempre
const int DATA_ENABLE_PIN  = 6;  // LOW sempre

const int BITS = 12;
const int SAMPLES = 5;           // Median filter
const int MIN_CHANGE = 5;        // Min cambio per inviare comando (~mezzo grado)
const float MAX_DUTY = 0.8;      // Limite max velocità (sicurezza sterzo)

uint16_t lastPos = 0;            // Ultima posizione (iniziale 0)

void setup() {
  Serial.begin(115200);
  vescSerial.begin(115200);
  UART.setSerialPort(&vescSerial);

  Serial.println("Encoder → VESC - Motore gira solo con rotazione (orario/antiorario)");

  pinMode(CLOCK_PIN, OUTPUT);
  digitalWrite(CLOCK_PIN, HIGH);

  pinMode(CLOCK_ENABLE_PIN, OUTPUT);
  digitalWrite(CLOCK_ENABLE_PIN, HIGH);

  pinMode(DATA_ENABLE_PIN, OUTPUT);
  digitalWrite(DATA_ENABLE_PIN, LOW);

  pinMode(DATA_PIN, INPUT);

  // Inizia con motore fermo
  UART.setDuty(0.0);
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
  uint16_t currentPos = readSSI();

  int delta;

  // Trattamento speciale SOLO per il wrap-around (da 4095→0/1 o 0→4095)
  if (lastPos >= 4090 && currentPos <= 5) {
    delta = 1;           // movimento positivo: considera +1 step
  }
  else if (lastPos <= 5 && currentPos >= 4090) {
    delta = -1;          // movimento negativo: considera -1 step
  }
  else {
    // tutti gli altri casi → delta normale
    delta = (int)currentPos - (int)lastPos;
  }

  // Invia comando solo se cambiamento significativo
  if (abs(delta) >= MIN_CHANGE) {
    // Duty proporzionale al cambio (delta positivo = orario, negativo = antiorario)
    float duty = (float)delta / 2048.0;  // Range ±1.0 max (regola 2048 per sensibilità)
    duty = constrain(duty, -MAX_DUTY, MAX_DUTY);  // Limite velocità

    UART.setDuty(duty);

    Serial.print("Posizione: ");
    Serial.print(currentPos);
    Serial.print(" | Delta: ");
    Serial.print(delta);
    Serial.print(" | Duty inviato: ");
    Serial.println(duty, 3);

    lastPos = currentPos;
  }

  delay(20);  // Loop reattivo
}