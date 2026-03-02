#include <Servo.h>

// Oggetto Servo
Servo mioServo;

// Pin e posizioni base
const int PIN_SERVO = 9;
const int CENTRO = 0;  // ← CAMBIA QUI per spostare la posizione di partenza

// Escursioni frenata (in gradi da centro)
const int ESCURSIONE_MEDIA = 85;  // Frenata media: 47°

// Ritardi velocità (ms/grado)
const int RITARDO_SUPER_RAPIDO = 1;\
const int RITARDO_FRENO_DOLCE = 60;

// Gradi per fase rapida iniziale
const int GRADI_VELOCI = ESCURSIONE_MEDIA - 29;

const int RIPETIZIONI = 500;  // ← CAMBIA QUI per il numero di ripetizioni

void setup() {
  Serial.begin(9600);
  Serial.println("=== SISTEMA FRENO BICI - 500x FRENATA MEDIA ===");

  initServo();
  ricercaZeroDolce();

  Serial.println("Leva in posizione ZERO - Inizio 500 frenate");
  delay(2000);
}

void loop() {
  static int contatore = 0;
  if (contatore >= RIPETIZIONI) return;

  contatore++;
  Serial.print("--- Frenata ");
  Serial.print(contatore);
  Serial.print("/");
  Serial.print(RIPETIZIONI);
  Serial.println(" ---");

  performBrake(ESCURSIONE_MEDIA, GRADI_VELOCI, RITARDO_FRENO_DOLCE, "FRENATA MEDIA: +47°");

  if (contatore >= RIPETIZIONI) {
    Serial.println("=== 500 FRENATE COMPLETATE ===");
  }
}

void initServo() {
  mioServo.attach(PIN_SERVO, 500, 2500);
}

void ricercaZeroDolce() {
  Serial.println("Ricerca ZERO...");
  mioServo.write(CENTRO);
  delay(1000);
  Serial.print("Zero: ");
  Serial.print(CENTRO);
  Serial.println("°");
}

void performBrake(int escursione, int gradiVeloci, int ritardoMaxFreno, const char* descrizione) {
  int posizioneFinale = CENTRO + escursione;

  Serial.println(descrizione);
  muoviFrenoRealistico(posizioneFinale, gradiVeloci, ritardoMaxFreno);
  Serial.print("Freno azionato (");
  Serial.print(posizioneFinale);
  Serial.println("°)");
  delay(1000);

  Serial.println("Rilascio rapido");
  moveServo(CENTRO, RITARDO_SUPER_RAPIDO);
  delay(1500);
}

void moveServo(int angoloFinale, int ritardo) {
  int attuale = mioServo.read();
  int step = (angoloFinale > attuale) ? 1 : -1;

  while (attuale != angoloFinale) {
    attuale += step;
    mioServo.write(attuale);
    delay(ritardo);
  }
}

void muoviFrenoRealistico(int angoloFinale, int gradiVeloci, int ritardoMaxFreno) {
  int attuale = mioServo.read();
  int direzione = (angoloFinale > attuale) ? 1 : -1;
  int gradiTotali = abs(angoloFinale - attuale);

  gradiVeloci = min(gradiVeloci, gradiTotali);
  int fineVeloce = attuale + direzione * gradiVeloci;

  if (gradiVeloci > 0) {
    Serial.print("  → Scatto rapido (primi ");
    Serial.print(gradiVeloci);
    Serial.println("°)");
    while ((direzione > 0 ? attuale < fineVeloce : attuale > fineVeloce)) {
      attuale += direzione;
      mioServo.write(attuale);
      delay(RITARDO_SUPER_RAPIDO);
    }
  }

  int gradiFreno = gradiTotali - gradiVeloci;
  if (gradiFreno > 0) {
    Serial.print("  → Progressiva (");
    Serial.print(gradiFreno);
    Serial.println("°)");
    for (int i = 0; i < gradiFreno; i++) {
      float progresso = (float)i / (gradiFreno - 1.0f);
      int delayAttuale = RITARDO_SUPER_RAPIDO + (int)(progresso * (ritardoMaxFreno - RITARDO_SUPER_RAPIDO));
      attuale += direzione;
      mioServo.write(attuale);
      delay(delayAttuale);
    }
  }
}