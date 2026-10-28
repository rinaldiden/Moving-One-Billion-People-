#!/usr/bin/env python3
"""
Asmile FAST voltage logger — cattura l'ANDAMENTO del rail 5V ad alta frequenza
durante lo stacco (si vede il calo di tensione e QUANDO parte il throttle).

Si lancia PRIMA di uno stacco di prova (detached). Gira alla massima frequenza e
scrive OGNI campione su /var/log/asmile_fastv.csv con fsync → i dati sopravvivono
al power-off del Pi. Timestamp monotonico in ms (per il profilo) + ISO (per
correlare con safe_shutdown.log = la SEQUENZA).

Fonte della tensione 5V, in ordine di preferenza:
  1) INA219 su I2C all'indirizzo --ina (es. 0x41) CABLATO sul rail 5V →
     bus voltage via I2C, ~1ms → risoluzione vera al ms
  2) vcgencmd pmic_read_adc EXT5V_V (PMIC Pi5) → piu' lento (~5-10ms)

Uso:
  python3 fast_voltage_logger.py                 # vcgencmd, per sempre (muore col Pi)
  python3 fast_voltage_logger.py --ina 0x41      # INA219 sul 5V (ms veri)
  python3 fast_voltage_logger.py --secs 90       # ferma dopo 90s
"""
import sys
import time
import subprocess
import os
import argparse
from datetime import datetime

LOG = "/var/log/asmile_fastv.csv"


def read_ext5v_vcgencmd():
    try:
        s = subprocess.run(["vcgencmd", "pmic_read_adc", "EXT5V_V"],
                           capture_output=True, text=True, timeout=1).stdout
        return s.split("=")[1].replace("V", "").strip()
    except Exception:
        return ""


def read_throttled():
    try:
        s = subprocess.run(["vcgencmd", "get_throttled"],
                           capture_output=True, text=True, timeout=1).stdout
        return s.split("=")[1].strip()
    except Exception:
        return ""


def ina_open(addr):
    import smbus2
    bus = smbus2.SMBus(1)
    bus.read_word_data(addr, 0x02)      # reg bus-voltage: verifica presenza
    return bus


def ina_busv(bus, addr):
    # INA219 reg 0x02 (bus voltage): valore >>3, LSB = 4mV
    raw = bus.read_word_data(addr, 0x02)
    raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
    return (raw >> 3) * 0.004


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ina", default=None, help="indirizzo I2C INA219 sul 5V (es. 0x41)")
    ap.add_argument("--secs", type=float, default=0, help="durata (0 = per sempre)")
    a = ap.parse_args()

    bus = None
    addr = None
    if a.ina:
        try:
            addr = int(a.ina, 16)
            bus = ina_open(addr)
        except Exception:
            bus = None
    mode = ("ina219@" + a.ina) if bus else "vcgencmd_EXT5V_V"

    f = open(LOG, "w", buffering=1)
    f.write("# fast_voltage_logger mode=%s start=%s\n" % (mode, datetime.now().isoformat()))
    f.write("t_mono_ms,ts_iso,v5,throttled_hex\n")
    f.flush()
    os.fsync(f.fileno())

    t0 = time.monotonic()
    last_thr = 0.0
    thr = ""
    n = 0
    while True:
        now = time.monotonic()
        if a.secs > 0 and (now - t0) > a.secs:
            break
        if bus:
            try:
                v = "%.4f" % ina_busv(bus, addr)
            except Exception:
                v = ""
        else:
            v = read_ext5v_vcgencmd()
        # throttled: solo ogni ~100ms (subprocess lento, non deve frenare il loop)
        if now - last_thr > 0.1:
            thr = read_throttled()
            last_thr = now
        f.write("%.2f,%s,%s,%s\n" % ((now - t0) * 1000.0,
                                     datetime.now().isoformat(timespec="milliseconds"),
                                     v, thr))
        f.flush()
        os.fsync(f.fileno())       # durabilita': i dati devono essere su disco prima del power-off
        n += 1

    print("fast logger: %d campioni in %s (mode=%s)" % (n, LOG, mode))


if __name__ == "__main__":
    main()
