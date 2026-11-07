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
SAMPLE_HZ = 100                     # encoder letto veloce: fa ~6.3 giri per giro ruota → a 5Hz
                                    # sopra ~3 km/h faceva >½ giro tra due letture (aliasing)
WIN_S = 0.5                         # finestra su cui si calcola la velocità encoder
MAX_LAG_S = 2.0                     # ritardo GPS cercato a fine giro (misurato ~0.8s)
OUT_JSON = "/var/lib/asmile/encoder_calibration.json"
# /data = partizione persistente fuori dall'overlay (con sudo "~" sarebbe /root, in RAM)
_LOG_DIR = "/data/logging" if os.path.isdir("/data/logging") else os.path.expanduser("~/wip/logging")
OUT_CSV = os.path.join(_LOG_DIR, "encoder_calib_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))

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
    os.makedirs(_LOG_DIR, exist_ok=True)
    print("[CALIB] avviato. Master OFF, pedala un giro con buon GPS. Ctrl-C per calcolare.", flush=True)
    csv_f = open(OUT_CSV, "w")
    csv_f.write("t,gps_speed_ms,gps_fix,enc_counts,enc_cum,counts_per_s\n")

    last_counts = None
    cum = 0
    last_gps = (None, False)
    win = []                         # (t, cum) dentro la finestra
    rows = []                        # (t, rate_counts_s, gps_speed, fix) uno ogni WIN_S
    dt_target = 1.0 / SAMPLE_HZ
    t_next = time.monotonic()
    t_win = t_next

    while running:
        now = time.monotonic()
        sp, fix = read_gps_rmc(ser)
        if sp is not None:
            last_gps = (sp, fix)
        c = read_enc()
        if c is not None:
            if last_counts is not None:
                d = c - last_counts
                if d > ENC_COUNTS_PER_REV // 2:
                    d -= ENC_COUNTS_PER_REV
                elif d < -ENC_COUNTS_PER_REV // 2:
                    d += ENC_COUNTS_PER_REV
                cum += d
            last_counts = c
            win.append((now, cum))
        if now - t_win >= WIN_S and len(win) >= 2:
            rate = (win[-1][1] - win[0][1]) / (win[-1][0] - win[0][0])   # counts/s SEGNATO
            gps_speed, gps_fix = last_gps
            rows.append((now, rate, gps_speed, gps_fix))
            csv_f.write("%.3f,%s,%d,%d,%d,%.1f\n" % (
                now, ("%.3f" % gps_speed) if gps_speed is not None else "",
                1 if gps_fix else 0, last_counts, cum, rate))
            csv_f.flush()
            win = [win[-1]]
            t_win = now
        t_next += dt_target
        s = t_next - time.monotonic()
        if s > 0:
            time.sleep(s)
        else:
            t_next = time.monotonic()

    csv_f.close()
    ser.close()

    # GPS in ritardo sull'encoder: provo gli shift 0..MAX_LAG_S e tengo il più correlato
    best = None
    for lag in range(int(MAX_LAG_S / WIN_S) + 1):
        pairs = []
        for i in range(len(rows) - lag):
            rate = rows[i][1]
            g, f = rows[i + lag][2], rows[i + lag][3]
            if f and g is not None and g >= GPS_MIN_MS and abs(rate) > 1.0:
                pairs.append((abs(rate), g, rate))
        if len(pairs) < 10:
            continue
        sxx = sum(r * r for r, g, _ in pairs)
        sxy = sum(r * g for r, g, _ in pairs)
        k = sxy / sxx
        err = sum(abs(k * r - g) / g for r, g, _ in pairs) / len(pairs)
        if best is None or err < best[1]:
            best = (lag, err, k, pairs)

    if best is None:
        print("[CALIB] POCHI campioni buoni. Serve un giro con GPS fix in moto (>~4 km/h).", flush=True)
        return

    lag, mean_err, m_per_count, pairs = best
    circ = m_per_count * ENC_COUNTS_PER_REV
    pos = sum(1 for *_, r in pairs if r > 0)
    forward_sign = "+" if pos >= len(pairs) - pos else "-"
    print(f"[CALIB] ritardo GPS stimato {lag * WIN_S:.1f}s", flush=True)

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
