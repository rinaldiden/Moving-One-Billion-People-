#!/usr/bin/env python3
"""Prova a secco del servo freno di #001 col PWM HARDWARE del Pi 5 (Daniele 25/11: "muovilo perfetto e con precisione").
SER0062: 50 Hz, 500-2500 us = 0-180 gradi (11,1 us/grado), zona morta 1 us. Il PWM software di lgpio balla di qualche us
e il servo insegue; l'RP1 da' impulsi esatti. Serve l'overlay caricato a runtime: sudo dtoverlay pwm pin=12 func=4.
Pulse-and-free: impulsi solo durante il movimento + tenuta, poi impulso a 0 e pin in ingresso (mai LOW tenuto).
Uso: sudo python3 servo_hw.py DA A [secondi_rampa] [tenuta_s]   (gradi logici: 0 = rilasciato, +N = N gradi di freno)"""
import os, subprocess, sys, time

CHIP, CH, PERIODO_NS = "/sys/class/pwm/pwmchip0", 0, 20_000_000
PIN, MAX_DEG = 12, 50.0
P = f"{CHIP}/pwm{CH}"


def scrivi(f, v):
    with open(f, "w") as h:
        h.write(str(v))


def impulso_ns(angolo):
    raw = 180.0 - angolo                     # servo montato invertito: raw 180 = rilasciato
    return int(round((500.0 + raw / 180.0 * 2000.0) * 1000))


def pin(funz):
    subprocess.run(["pinctrl", "set", str(PIN)] + funz.split(), check=True)


def main():
    da, a = float(sys.argv[1]), float(sys.argv[2])
    rampa = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    tenuta = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    if not (0.0 <= da <= MAX_DEG and 0.0 <= a <= MAX_DEG):
        sys.exit(f"angoli fuori 0-{MAX_DEG}")
    if not os.path.exists(P):
        scrivi(f"{CHIP}/export", CH)
        time.sleep(0.2)
    scrivi(f"{P}/enable", 0)
    scrivi(f"{P}/period", PERIODO_NS)
    scrivi(f"{P}/duty_cycle", impulso_ns(da))
    scrivi(f"{P}/enable", 1)
    pin("a0")                                # da qui escono impulsi veri, gia' alla posizione di partenza
    try:
        n = max(1, int(round(rampa / 0.02)))  # un aggiornamento per periodo PWM (20 ms)
        t0 = time.monotonic()
        for i in range(1, n + 1):
            scrivi(f"{P}/duty_cycle", impulso_ns(da + (a - da) * i / n))
            dorm = t0 + i * 0.02 - time.monotonic()
            if dorm > 0:
                time.sleep(dorm)
        time.sleep(tenuta)
    finally:
        scrivi(f"{P}/duty_cycle", 0)         # niente impulsi (uscita bassa) per un periodo ...
        time.sleep(0.025)
        pin("ip pn")                         # ... poi pin davvero libero: il servo non riceve nulla
        scrivi(f"{P}/enable", 0)
    print(f"{da:g} -> {a:g} gradi in {rampa:g} s (impulso {impulso_ns(a)/1000:.1f} us), tenuta {tenuta:g} s, pin libero")


if __name__ == "__main__":
    main()
