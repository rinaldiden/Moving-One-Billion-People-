#!/usr/bin/env python3
"""
Freno Asmile — Raspberry Pi 5
Controlla servo freno idraulico a disco con profilo di frenata realistico.

Convertito da: firmware/braking/brake_servo_test.ino

Cablaggio Raspi 5:
  GPIO 12 (PWM0) → Segnale servo (bianco/arancione)
  GND (pin 14)   → GND servo + GND alimentatore 6V
  Alimentatore 6V esterno → +V servo (rosso)

Dipendenze:
  sudo apt install python3-lgpio
"""

import lgpio
import time

# --- Config ---
GPIO_CHIP = 4       # Pi 5 = gpiochip4
PIN_SERVO = 12      # GPIO 12 = PWM0 hardware

# Servo timing
SERVO_FREQ = 50          # 50Hz = periodo 20ms
PULSE_MIN_US = 500       # 0°
PULSE_MAX_US = 2500      # 180°

# Parametri frenata (stessi dello sketch Arduino)
CENTRO = 0
ESCURSIONE_MEDIA = 85                      # Gradi frenata media
GRADI_VELOCI = ESCURSIONE_MEDIA - 29       # 56° fase rapida
RITARDO_SUPER_RAPIDO = 0.001               # 1 ms/grado
RITARDO_FRENO_DOLCE = 0.060                # 60 ms/grado
RIPETIZIONI = 500


def angle_to_duty(angle: int) -> float:
    """Converte angolo (0-180) in duty cycle % per servo a 50Hz."""
    pulse_us = PULSE_MIN_US + (angle / 180.0) * (PULSE_MAX_US - PULSE_MIN_US)
    return (pulse_us / 20000.0) * 100.0


class Servo:
    """Wrapper servo su lgpio PWM hardware."""

    def __init__(self, h, pin):
        self.h = h
        self.pin = pin
        self.angle = 0

    def write(self, angle: int):
        self.angle = max(0, min(180, angle))
        lgpio.tx_pwm(self.h, self.pin, SERVO_FREQ, angle_to_duty(self.angle))

    def read(self) -> int:
        return self.angle

    def stop(self):
        lgpio.tx_pwm(self.h, self.pin, 0, 0)


def move_servo(servo, target: int, delay_per_deg: float):
    """Muove il servo grado per grado con ritardo costante."""
    current = servo.read()
    step = 1 if target > current else -1
    while current != target:
        current += step
        servo.write(current)
        time.sleep(delay_per_deg)


def frenata_realistica(servo, target: int, gradi_veloci: int, ritardo_max: float):
    """Frenata in due fasi: scatto rapido + progressiva."""
    current = servo.read()
    direction = 1 if target > current else -1
    gradi_totali = abs(target - current)
    gradi_veloci = min(gradi_veloci, gradi_totali)

    # Fase 1: scatto rapido (recupero gioco meccanico)
    if gradi_veloci > 0:
        fine_veloce = current + direction * gradi_veloci
        print(f"  → Scatto rapido (primi {gradi_veloci}°)")
        while current != fine_veloce:
            current += direction
            servo.write(current)
            time.sleep(RITARDO_SUPER_RAPIDO)

    # Fase 2: progressiva (frenata modulata)
    gradi_freno = gradi_totali - gradi_veloci
    if gradi_freno > 0:
        print(f"  → Progressiva ({gradi_freno}°)")
        for i in range(gradi_freno):
            progresso = i / max(1, gradi_freno - 1)
            delay = RITARDO_SUPER_RAPIDO + progresso * (ritardo_max - RITARDO_SUPER_RAPIDO)
            current += direction
            servo.write(current)
            time.sleep(delay)


def perform_brake(servo):
    """Esegue un ciclo completo: frenata + rilascio."""
    target = CENTRO + ESCURSIONE_MEDIA
    print(f"FRENATA MEDIA: +{ESCURSIONE_MEDIA}°")
    frenata_realistica(servo, target, GRADI_VELOCI, RITARDO_FRENO_DOLCE)
    print(f"Freno azionato ({target}°)")
    time.sleep(1.0)

    print("Rilascio rapido")
    move_servo(servo, CENTRO, RITARDO_SUPER_RAPIDO)
    time.sleep(1.5)


def main():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    servo = Servo(h, PIN_SERVO)

    print(f"=== SISTEMA FRENO BICI — {RIPETIZIONI}x FRENATA MEDIA ===")

    # Posizione zero
    print("Ricerca ZERO...")
    servo.write(CENTRO)
    time.sleep(1.0)
    print(f"Zero: {CENTRO}°")
    time.sleep(2.0)
    print("Leva in posizione ZERO — Inizio frenate")

    try:
        for i in range(1, RIPETIZIONI + 1):
            print(f"--- Frenata {i}/{RIPETIZIONI} ---")
            perform_brake(servo)

        print(f"=== {RIPETIZIONI} FRENATE COMPLETATE ===")

    except KeyboardInterrupt:
        print("\nStop — servo in posizione zero")
        servo.write(CENTRO)
        time.sleep(0.5)
    finally:
        servo.stop()
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
