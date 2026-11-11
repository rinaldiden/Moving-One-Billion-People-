#!/usr/bin/env python3
"""
sterzo_vel_semplice.py
Setpoint di velocità (ERPM) ogni 10 ms + rampa di accel/decel.
(script di Daniele 2026-11-11; aggiunti: limiti sx/dx con rallentamento, UART libera, log CSV, verso sbagliato)
La corrente la decide il VESC (PID di velocità, max l_current_max): il Raspberry manda solo la velocità.
"""

import os
import time
import struct
import signal
import sys
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vesc_return_to_center_duty import pkt, UART, BAUD, send_current
from sterzo_fluido_001 import rd_enc, limiti, DEG
from safety_001 import uart_libera

COMM_SET_RPM = 8
ERPM_PER_DEG_S = 16384 / 448.7 * 60 / 360.0   # ≈ 6.09: 36.5 giri el. per giro di manubrio (misurato 2026-11-11, non 35)

def send_rpm(ser, erpm):
    ser.write(pkt(struct.pack(">Bi", COMM_SET_RPM, int(round(erpm)))))

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, help="posizione encoder target")
    ap.add_argument("--verso", choices=["sx", "dx"], help="vai fino al limite software da quella parte")
    ap.add_argument("--vel", type=float, default=10.0, help="velocità a regime [°/s]")
    ap.add_argument("--ms", type=float, default=10.0, help="intervallo comando [ms]")
    ap.add_argument("--rampa", type=float, default=0.6, help="secondi di rampa accel/decel (0.5-0.8)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    if not 0 < args.vel <= 30: sys.exit("--vel fra 0 e 30 °/s")

    c, lo, hi, hard_lo, hard_hi = limiti()
    if args.verso: target = lo if args.verso == "sx" else hi
    elif args.target is not None: target = max(lo, min(hi, args.target))   # limiti sx e dx
    else: sys.exit("serve --target o --verso")

    p0, ok = rd_enc()
    if not ok or p0 is None:
        sys.exit("Encoder non pronto")
    if not (hard_lo <= p0 <= hard_hi): sys.exit(f"pos {p0} fuori dai finecorsa sicuri [{hard_lo}, {hard_hi}]")
    ok_u, why = uart_libera(UART)
    if not ok_u: sys.exit(f"UART non libera: {why}")

    d = 1 if target > p0 else -1
    print(f"Da {p0} a {target}  ({(target-p0)*DEG:+.1f}°)  a {args.vel}°/s  rampa={args.rampa}s  limiti [{lo}, {hi}]")

    ser = serial.Serial(UART, BAUD, timeout=0.02)
    os.makedirs("/data/logging/vesc", exist_ok=True)
    log = open(time.strftime(f"/data/logging/vesc/sterzo_semplice_%Y%m%d_%H%M%S{args.tag}.csv"), "w")
    log.write("t,pos,v_set,erpm\n")

    def stop():
        send_rpm(ser, 0)
        send_current(ser, 0)

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    t0 = time.monotonic()
    v_set = 0.0          # velocità comandata attuale (°/s)

    try:
        while True:
            now = time.monotonic()
            p, ok = rd_enc()
            if not ok or p is None:
                print("Encoder perso")
                break

            remaining = (target - p) * d * DEG
            rem_lim = ((hi if d > 0 else lo) - p) * d * DEG     # gradi al limite sx/dx da quella parte

            # arrivato
            if remaining < 0.4:
                print(f"Arrivato a {p} in {now - t0:.1f}s")
                break
            if rem_lim < 0 or not (hard_lo <= p <= hard_hi):
                print(f"Limite raggiunto ({p})")
                break
            if (p - p0) * d < -15:
                print(f"Verso sbagliato ({p - p0:+d})")
                break

            # --- calcolo velocità desiderata ---
            # decelerazione in arrivo (stessa durata della rampa), anche verso il limite sx/dx
            dist_rampa = args.vel * args.rampa          # spazio percorso durante la rampa
            dist = min(remaining, rem_lim)
            if dist < dist_rampa:
                v_target = args.vel * (dist / dist_rampa)
            else:
                v_target = args.vel

            v_target = max(v_target, 0.8)               # minima 0.8°/s (VESC: s_pid_min_erpm 3 = 0.5°/s)

            # rampa di accelerazione/decelerazione (limita la derivata)
            max_delta = args.vel * (args.ms / 1000.0) / args.rampa
            if v_set < v_target:
                v_set = min(v_set + max_delta, v_target)
            else:
                v_set = max(v_set - max_delta, v_target)

            erpm = -d * v_set * ERPM_PER_DEG_S
            send_rpm(ser, erpm)
            log.write(f"{now - t0:.4f},{p},{d * v_set:.2f},{erpm:.0f}\n")

            if now - t0 > 25:
                print("Timeout")
                break

            time.sleep(max(0.0, args.ms / 1000.0 - (time.monotonic() - now)))

    finally:
        stop()
        ser.close()
        log.close()
        print("Motore fermato")

if __name__ == "__main__":
    main()
