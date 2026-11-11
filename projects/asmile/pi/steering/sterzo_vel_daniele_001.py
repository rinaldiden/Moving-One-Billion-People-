#!/usr/bin/env python3
"""
sterzo_vel_001.py — Controllo servosterzo in velocità (COMM_SET_RPM)
Il Raspberry calcola la velocità desiderata in base all'errore di posizione
e la manda al VESC ogni 10 ms. Il VESC gestisce corrente e FOC.
(script di Daniele 2026-11-11, salvato come sterzo_vel_daniele_001.py per non sovrascrivere sterzo_vel_001.py)
"""

import argparse
import os
import signal
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
from vesc_return_to_center_duty import send_duty, send_current, pkt, UART, BAUD
from safety_001 import uart_libera
import sterzo_fluido_001 as sf          # rd_enc, wheel, q_imotor, TEL, limiti

COMM_SET_RPM = 8
ERPM_PER_DEG_S = 35 * 60 / 360.0       # ≈ 5.833  (35 coppie polari)
SIGN = +1                              # regola questo segno se il verso è invertito


def send_rpm(ser, erpm: float):
    ser.write(pkt(struct.pack(">Bi", COMM_SET_RPM, int(round(erpm)))))


def main():
    ap = argparse.ArgumentParser(description="Servosterzo in velocità (RPM)")
    ap.add_argument("--target", type=int, help="posizione encoder target (default = centro)")
    ap.add_argument("--vel", type=float, default=12.0, help="velocità massima manubrio [°/s] (default 12)")
    ap.add_argument("--ms", type=float, default=10.0, help="intervallo setpoint [ms] (2-50)")
    ap.add_argument("--rampa", type=float, default=0.4, help="secondi di rampa in accelerazione")
    ap.add_argument("--rallenta", type=float, default=6.0, help="gradi prima del target in cui inizia a rallentare")
    ap.add_argument("--rallenta-fc", type=float, default=5.0, help="gradi prima dei limiti in cui rallenta")
    ap.add_argument("--imax", type=float, default=25.0, help="soglia di corrente per stop di sicurezza [A]")
    ap.add_argument("--verso", choices=["sx", "dx"], help="vai fino al limite software da quella parte")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not 0 < a.vel <= 30:
        sys.exit("--vel deve essere tra 0 e 30 °/s")
    if not 2 <= a.ms <= 50:
        sys.exit("--ms deve essere tra 2 e 50")

    c, lo, hi, hard_lo, hard_hi = sf.limiti()
    tgt = (lo if a.verso == "sx" else hi) if a.verso else (c if a.target is None else a.target)

    if not lo <= tgt <= hi:
        sys.exit(f"target {tgt} fuori dai limiti software [{lo}, {hi}]")

    ok, why = uart_libera(UART)
    if not ok:
        sys.exit(f"UART non libera: {why}")

    p0, fresh = sf.rd_enc()
    if not fresh or p0 is None:
        sys.exit("encoder sterzo non fresco")

    if not (hard_lo + 30 <= p0 <= hard_hi - 30):
        sys.exit("troppo vicino ai finecorsa hardware")

    d = 1 if tgt > p0 else -1
    print(f"pos={p0}  target={tgt}  corsa={(tgt-p0)*sf.DEG:+.1f}°  "
          f"vel_max={a.vel}°/s  → {a.vel * ERPM_PER_DEG_S:.0f} ERPM")

    if abs(tgt - p0) < 12 or a.dry_run:
        print("niente da fare / dry-run")
        return

    os.makedirs("/data/logging/vesc", exist_ok=True)
    logname = time.strftime(f"/data/logging/vesc/sterzo_vel_%Y%m%d_%H%M%S{a.tag}.csv")
    log = open(logname, "w")
    log.write("t,pos,v_enc,v_set,erpm,i_mot,i_batt,v_batt,t_fet,t_mot\n")

    ser = serial.Serial(UART, BAUD, timeout=0.02)

    def stop_motore():
        for _ in range(3):
            try:
                send_rpm(ser, 0)
                send_current(ser, 0)
                send_duty(ser, 0)
            except Exception:
                pass
            time.sleep(0.01)

    def _kill(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _kill)
    signal.signal(signal.SIGHUP, _kill)

    hist = []
    reason = None
    t0 = time.monotonic()
    k = 0
    i_mot = 0.0
    qf = 0

    try:
        while True:
            tc = time.monotonic()
            p, fresh = sf.rd_enc()
            if p is None or not fresh:
                reason = "encoder vecchio"
                break

            # velocità encoder (finestra 100 ms)
            hist.append((tc, p))
            hist = [h for h in hist if tc - h[0] <= 0.10]
            dt_h = max(hist[-1][0] - hist[0][0], 0.02)
            v_enc = (hist[-1][1] - hist[0][1]) * sf.DEG / dt_h

            rem = (tgt - p) * d * sf.DEG                    # gradi rimanenti
            if rem < 0.4:
                print(f"ARRIVATO  pos={p}  err={(tgt-p)*sf.DEG:+.2f}°  in {tc-t0:.1f}s")
                break

            # limiti di velocità
            rem_fc = ((hi if d > 0 else lo) - p) * d * sf.DEG
            v_set = a.vel
            if a.rampa > 0:
                v_set *= min(1.0, (tc - t0) / a.rampa)      # rampa iniziale
            v_set = min(v_set, a.vel * rem / a.rallenta)     # rallenta vicino al target
            v_set = min(v_set, a.vel * max(0.15, rem_fc / a.rallenta_fc))
            v_set = max(1.5, v_set)                          # velocità minima (evita di fermarsi troppo presto)

            erpm = -SIGN * d * v_set * ERPM_PER_DEG_S
            send_rpm(ser, erpm)

            # lettura corrente ogni tanto
            k += 1
            if k % 4 == 1:
                im = sf.q_imotor(ser)
                if im is None:
                    qf += 1
                    if qf >= 4:
                        reason = "VESC muto"
                        break
                else:
                    qf = 0
                    i_mot = im

            log.write(f"{tc-t0:.4f},{p},{v_enc:.2f},{d*v_set:.2f},{erpm:.0f},"
                      f"{i_mot:.2f},{sf.TEL['i_batt']:.2f},{sf.TEL['v_batt']:.1f},"
                      f"{sf.TEL['t_fet']:.1f},{sf.TEL['t_mot']:.1f}\n")

            # --- sicurezze ---
            if (p - p0) * d <= -15:
                reason = f"verso sbagliato ({p-p0:+d})"
                break
            if abs(v_enc) > a.vel * 2.2 + 8:
                reason = f"troppo veloce ({v_enc:+.1f}°/s)"
                break
            if not (hard_lo <= p <= hard_hi) or (p < lo and d < 0) or (p > hi and d > 0):
                reason = f"limite raggiunto ({p})"
                break
            if abs(i_mot) > a.imax + 4:
                reason = f"corrente alta ({i_mot:.1f}A)"
                break
            if k % 25 == 0:
                w, _ = sf.wheel()
                if w != sf.wheel()[0]:          # semplice check movimento bici
                    pass                        # puoi rendere più severo se serve
            if tc - t0 > 25:
                reason = "timeout 25s"
                break

            # rispetto del periodo
            time.sleep(max(0.0, a.ms/1000 - (time.monotonic() - tc)))

    except KeyboardInterrupt:
        reason = "Ctrl-C"
    finally:
        stop_motore()
        ser.close()
        log.close()
        if reason:
            print("[STOP]", reason)
        p_fin, _ = sf.rd_enc()
        print(f"fine: pos={p_fin}  cicli={k}  ({k/max(time.monotonic()-t0,0.001):.0f} Hz)")


if __name__ == "__main__":
    main()
