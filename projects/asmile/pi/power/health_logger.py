#!/usr/bin/env python3
"""
Asmile health logger — SEMPRE attivo (systemd), log PERSISTENTE e timestampato.

Registra ogni secondo:
- temperatura CPU
- tensione VERA del rail 5V (EXT5V_V dal PMIC del Pi5) -> si vede se il supercap
  tiene costante o cala
- flag throttling / under-voltage (ADESSO e DAL BOOT): quando il 5V cala di
  qualche decimo, il Pi segnala under-voltage/throttle -> qui si cattura
- tensione core, corrente INA219 (se presente)

Serve a diagnosticare: il supercap non tiene una tensione costante? quando cala
il Pi trottla? Confronta questo CSV (timestamp ISO) con gli altri log.

Log: /var/log/asmile_health.csv   (rotazione a ~100MB, tiene 1 file vecchio .1)
"""
import time
import subprocess
import os
from datetime import datetime

LOG = "/var/log/asmile_health.csv"
INTERVAL = 1.0                      # s — risoluzione fine per catturare i cali
ROTATE_BYTES = 100 * 1024 * 1024
HEADER = ("timestamp,uptime_s,temp_c,throttled_hex,uv_now,freq_capped,"
          "throttled_now,soft_temp,uv_since_boot,throttled_since_boot,"
          "ext5v_v,core_v,current_mA\n")


def vc(args):
    try:
        return subprocess.run(["vcgencmd"] + args, capture_output=True,
                              text=True, timeout=2).stdout.strip()
    except Exception:
        return ""


def read_temp():
    s = vc(["measure_temp"])                 # temp=42.3'C
    try:
        return s.split("=")[1].replace("'C", "")
    except Exception:
        return ""


def read_throttled():
    s = vc(["get_throttled"])                # throttled=0x0
    try:
        hexs = s.split("=")[1]
        v = int(hexs, 16)
    except Exception:
        return ("", "", "", "", "", "", "")
    return (hexs,
            v & 0x1,            # under-voltage ADESSO
            (v >> 1) & 0x1,     # freq capped adesso
            (v >> 2) & 0x1,     # throttled adesso
            (v >> 3) & 0x1,     # soft temp limit adesso
            (v >> 16) & 0x1,    # under-voltage avvenuto dal boot
            (v >> 18) & 0x1)    # throttling avvenuto dal boot


def read_ext5v():
    # Pi5: "EXT5V_V volt(24)=5.0123V"
    s = vc(["pmic_read_adc", "EXT5V_V"])
    try:
        return s.split("=")[1].replace("V", "")
    except Exception:
        return ""


def read_core_v():
    s = vc(["measure_volts", "core"])        # volt=0.8000V
    try:
        return s.split("=")[1].replace("V", "")
    except Exception:
        return ""


def uptime_s():
    try:
        with open("/proc/uptime") as f:
            return f.read().split()[0]
    except Exception:
        return ""


def read_ina219():
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        raw = bus.read_word_data(0x40, 0x04)
        raw = ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)
        if raw > 32767:
            raw -= 65536
        return f"{raw * 0.1:.1f}"
    except Exception:
        return ""


def rotate():
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > ROTATE_BYTES:
            os.replace(LOG, LOG + ".1")
    except Exception:
        pass


def main():
    if not os.path.exists(LOG):
        try:
            with open(LOG, "w") as f:
                f.write(HEADER)
        except Exception:
            pass
    try:
        import smbus2
        smbus2.SMBus(1).write_word_data(0x40, 0x05, 0x1000)   # INA219 config
    except Exception:
        pass

    while True:
        rotate()
        ts = datetime.now().isoformat(timespec="milliseconds")
        t = read_throttled()
        line = (f"{ts},{uptime_s()},{read_temp()},{t[0]},{t[1]},{t[2]},"
                f"{t[3]},{t[4]},{t[5]},{t[6]},{read_ext5v()},{read_core_v()},"
                f"{read_ina219()}\n")
        try:
            with open(LOG, "a") as f:
                f.write(line)
        except Exception:
            pass
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
