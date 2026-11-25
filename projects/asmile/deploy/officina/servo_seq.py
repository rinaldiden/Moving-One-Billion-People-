#!/usr/bin/env python3
"""Sequenza di corse del servo freno di #001 col PWM HARDWARE + corrente INA219 a ogni periodo (Daniele 25/11, officina).
Una sola sessione PWM per tutta la sequenza (impulsi esatti, aggiornati ogni 20 ms), poi impulso a 0 e pin libero;
dopo il rilascio registra ancora 1,5 s di corrente a pin libero. CSV in /tmp/servo_seq_<ora>.csv.
Uso: sudo python3 servo_seq.py PARTENZA  A1:SEC1  A2:SEC2 ...   (gradi logici 0..50, 0 = rilasciato)"""
import os, subprocess, sys, time
import smbus2

CHIP, CH, PERIODO_NS, PIN, MAX_DEG = "/sys/class/pwm/pwmchip0", 0, 20_000_000, 12, 50.0
P = f"{CHIP}/pwm{CH}"


def scrivi(f, v):
    with open(f, "w") as h:
        h.write(str(v))


def impulso_ns(angolo):
    return int(round((500.0 + (180.0 - angolo) / 180.0 * 2000.0) * 1000))   # montato invertito


def pin(funz):
    subprocess.run(["pinctrl", "set", str(PIN)] + funz.split(), check=True)


def ina_ma(bus):
    try:
        v = bus.read_word_data(0x40, 0x01)
        v = ((v & 0xFF) << 8) | (v >> 8)
        v = v - 65536 if v > 32767 else v
        return abs(v * 1e-5 / 0.1 * 1000.0)        # shunt 0,1 ohm, LSB 10 uV
    except OSError:
        return float("nan")


def main():
    part = float(sys.argv[1])
    tappe = [(float(a), float(s)) for a, s in (x.split(":") for x in sys.argv[2:])]
    if any(not 0.0 <= a <= MAX_DEG for a in [part] + [a for a, _ in tappe]):
        sys.exit(f"angoli fuori 0-{MAX_DEG}")
    bus = smbus2.SMBus(1)
    nome = time.strftime("/tmp/servo_seq_%H%M%S.csv")
    out = open(nome, "w")
    out.write("t_s,fase,comando_deg,ina_ma\n")
    if not os.path.exists(P):
        scrivi(f"{CHIP}/export", CH)
        time.sleep(0.2)
    scrivi(f"{P}/enable", 0)
    scrivi(f"{P}/period", PERIODO_NS)
    scrivi(f"{P}/duty_cycle", impulso_ns(part))
    scrivi(f"{P}/enable", 1)
    pin("a0")
    t0 = time.monotonic()
    k = 0
    def periodo(fase, ang):
        nonlocal k
        k += 1
        out.write(f"{time.monotonic()-t0:.3f},{fase},{ang:.2f},{ina_ma(bus):.0f}\n")
        dorm = t0 + k * 0.02 - time.monotonic()
        if dorm > 0:
            time.sleep(dorm)
    try:
        da = part
        for i, (a, sec) in enumerate(tappe):
            n = max(1, int(round(sec / 0.02)))
            for j in range(1, n + 1):
                ang = da + (a - da) * j / n
                scrivi(f"{P}/duty_cycle", impulso_ns(ang))
                periodo(f"corsa{i+1}", ang)
            da = a
        for _ in range(25):                          # 0,5 s di tenuta all'ultima tappa
            periodo("tenuta", da)
    finally:
        scrivi(f"{P}/duty_cycle", 0)
        time.sleep(0.025)
        pin("ip pn")
        scrivi(f"{P}/enable", 0)
    for _ in range(75):                              # 1,5 s a pin libero
        periodo("libero", da)
    out.close()
    print(nome)


if __name__ == "__main__":
    main()
