#!/usr/bin/env python3
"""
Calibrazione velocità ENCODER ↔ GPS (asmile #001).

Da lanciare durante il PRIMO giro con BUON segnale GPS, con il master switch OFF
(così nient'altro legge la UART GPS). Correla la velocità GPS (NMEA RMC su
/dev/ttyAMA3) con l'avanzamento del conteggio dell'encoder ruota
(/tmp/encoder_wheel, AMT22 assoluto via ponte Arduino-USB) e ricava:
  - m_per_count    : metri per count   → speed_ms = m_per_count × counts_al_secondo
  - wheel_circum_m : circonferenza equivalente (= m_per_count × ENC_COUNTS_PER_REV)
  - forward_sign   : segno del Δcount quando la bici va AVANTI (direzione di marcia)

Scrive il risultato PERSISTENTE in /var/lib/asmile/encoder_calibration.json (il
speed_limiter lo carica da solo al prossimo avvio) + CSV grezzo dei campioni.
Da lì in poi la velocità si misura dall'encoder.

Uso:  sudo python3 encoder_speed_calibration.py     # pedala un giro, Ctrl-C per calcolare
"""
import os
import json
import time
import signal
from datetime import datetime

import serial

ENC_FILE = "/tmp/encoder_wheel"
ENC_COUNTS_PER_REV = 16384          # AMT22 14-bit
GPS_PORT = "/dev/ttyAMA3"
GPS_BAUD = 38400
GPS_MIN_MS = 1.2                    # usa solo campioni con GPS >~4.3 km/h (fix affidabile in moto)
SAMPLE_HZ = 5
OUT_JSON = "/var/lib/asmile/encoder_calibration.json"
OUT_CSV = os.path.expanduser(
    "~/wip/logging/encoder_calib_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))

running = True


def _stop(*_):
    global running
    running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def read_gps_rmc(ser):
    """Ultima RMC pendente → (speed_ms|None, fix_bool)."""
    speed_ms, fix = None, False
    while ser.in_waiting:
        try:
            line = ser.readline().decode("ascii", "ignore").strip()
        except Exception:
            continue
        if "RMC" in line:
            p = line.split(",")
            if len(p) > 7:
                fix = (p[2] == "A")
                try:
                    speed_ms = (float(p[7]) if p[7] else 0.0) * 0.514444
                except ValueError:
                    speed_ms = None
    return speed_ms, fix


def read_enc():
    try:
        with open(ENC_FILE) as f:
            return int(f.readline().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def main():
    ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.2)
    os.makedirs(os.path.expanduser("~/wip/logging"), exist_ok=True)
    print("[CALIB] avviato. Master OFF, pedala un giro con buon GPS. Ctrl-C per calcolare.", flush=True)
    csv_f = open(OUT_CSV, "w")
    csv_f.write("t,gps_speed_ms,gps_fix,enc_counts,enc_cum,counts_per_s\n")

    last_counts = None
    last_t = None
    cum = 0
    last_gps = (None, False)
    pairs = []                       # (|counts/s|, gps_speed_ms) solo campioni buoni
    sign_votes = {"pos": 0, "neg": 0}
    dt_target = 1.0 / SAMPLE_HZ
    t_next = time.monotonic()

    while running:
        now = time.monotonic()
        sp, fix = read_gps_rmc(ser)
        if sp is not None:
            last_gps = (sp, fix)
        gps_speed, gps_fix = last_gps
        c = read_enc()
        if c is not None:
            if last_counts is None:
                last_counts, last_t = c, now
            else:
                d = c - last_counts
                if d > ENC_COUNTS_PER_REV // 2:
                    d -= ENC_COUNTS_PER_REV
                elif d < -ENC_COUNTS_PER_REV // 2:
                    d += ENC_COUNTS_PER_REV
                dt = now - last_t
                last_counts, last_t = c, now
                cum += d
                rate = (d / dt) if dt > 0 else 0.0           # counts/s SEGNATO (direzione)
                csv_f.write("%.3f,%s,%d,%d,%d,%.1f\n" % (
                    now, ("%.3f" % gps_speed) if gps_speed is not None else "",
                    1 if gps_fix else 0, c, cum, rate))
                csv_f.flush()
                if gps_fix and gps_speed is not None and gps_speed >= GPS_MIN_MS and abs(rate) > 1.0:
                    pairs.append((abs(rate), gps_speed))
                    if d > 0:
                        sign_votes["pos"] += 1
                    elif d < 0:
                        sign_votes["neg"] += 1
        t_next += dt_target
        s = t_next - time.monotonic()
        if s > 0:
            time.sleep(s)
        else:
            t_next = time.monotonic()

    csv_f.close()
    ser.close()

    if len(pairs) < 10:
        print("[CALIB] POCHI campioni buoni (%d). Serve un giro con GPS fix in moto (>~4 km/h)."
              % len(pairs), flush=True)
        return

    # Fit passante per l'origine:  gps = k · rate  →  k = Σ(rate·gps)/Σ(rate²)
    sxx = sum(r * r for r, g in pairs)
    sxy = sum(r * g for r, g in pairs)
    m_per_count = (sxy / sxx) if sxx > 0 else 0.0
    circ = m_per_count * ENC_COUNTS_PER_REV
    forward_sign = "+" if sign_votes["pos"] >= sign_votes["neg"] else "-"
    errs = [abs(m_per_count * r - g) / g for r, g in pairs if g > 0]
    mean_err = (sum(errs) / len(errs)) if errs else 0.0

    result = {
        "m_per_count": round(m_per_count, 8),
        "wheel_circum_m": round(circ, 4),
        "enc_counts_per_rev": ENC_COUNTS_PER_REV,
        "forward_sign": forward_sign,
        "n_samples": len(pairs),
        "mean_rel_err": round(mean_err, 3),
        "raw_csv": OUT_CSV,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "note": "speed_ms = m_per_count * counts_per_s. speed_limiter carica wheel_circum_m da qui.",
    }
    try:
        os.makedirs("/var/lib/asmile", exist_ok=True)
        with open(OUT_JSON, "w") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print(f"[CALIB] (non ho potuto scrivere {OUT_JSON}: {e}) — serve sudo", flush=True)

    print("\n[CALIB] RISULTATO:", flush=True)
    for k, v in result.items():
        print(f"  {k}: {v}", flush=True)
    print(f"  → velocità da encoder: speed_ms = {m_per_count:.6f} × (counts/s)", flush=True)
    print(f"  → direzione AVANTI: Δcount {forward_sign}", flush=True)
    print(f"  → scritto in {OUT_JSON} (il speed_limiter lo userà al prossimo avvio)", flush=True)


if __name__ == "__main__":
    main()
