#!/usr/bin/env python3
"""
sterzo_vel_001.py — #001: porta il manubrio al centro (o a un target) a VELOCITA' BASSA controllata dal Pi.

Perche': il 2026-11-09 il micro-impulso a duty 0.03 ha mosso il manubrio di ~12 deg in 20 ms (~600 deg/s) e nel verso
opposto. In duty la velocita' a vuoto e' proporzionale al duty: 12 deg/s vorrebbe duty ~0.0006, sotto la zona morta.
Quindi qui si comanda la CORRENTE (coppia) e il Pi la regola sull'encoder sterzo per tenere la velocita' obiettivo.
Velocita' obiettivo = media delle sterzate reali di Daniele (giro 2026-11-09 08:53, 14 deg/s), abbassata: 10 deg/s.

Verso: dal micro-impulso, duty/corrente POSITIVA fa SCENDERE l'encoder (verso SX). Per salire serve corrente negativa.
Lo script lo verifica comunque: se l'encoder va dalla parte opposta di 10 count (0.2 deg) -> corrente 0, stop.

STOP immediato (corrente 0): verso sbagliato >=10 count, velocita' > 30 deg/s, pos oltre i limiti software (finecorsa - margine),
|i_motor| > imax (default 30 A, Daniele 2026-11-09), encoder vecchio >100 ms, VESC muto, bici in movimento, timeout, Ctrl-C.
Arrivo: |errore| < 15 count -> corrente 0 e il manubrio resta libero.
Log: /data/logging/vesc/sterzo_vel_<ora>.csv (t, pos, err, rate, i_cmd, i_motor, rpm, tach).
Uso:  python3 sterzo_vel_001.py [--target RAW] [--vel 10] [--imax 30] [--dry-run]
"""
import argparse, json, os, signal, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
import struct
from vesc_return_to_center_duty import send_duty, send_current, pkt, COMM_GET_VALUES, UART, BAUD
from safety_001 import uart_libera

ENC = "/tmp/encoder_steer"; WHEEL = "/tmp/encoder_wheel"; CPR = 16384; DEG = 360.0 / CPR
CAL = "/data/steering_limits_asmile-001.json"
VEL_MAX_DEG_S = 30.0      # oltre (media su 0.3 s): stop
WRONG_COUNTS = 10
# prova 1 (2026-11-09 16:19): stacco a ~5 A, in moto 7-10 A, a scatti perche' il loop girava a 90 ms (lettura VESC lenta)
I_START, I_RAMP = 3.0, 0.10   # A; A per ciclo finche' fermo (4 A/s)
KP, KI = 0.05, 0.60           # A per deg/s; A per (deg/s * s)
CUT_AL_DISTACCO = 0.9         # attrito statico > dinamico: appena parte, corrente x0.8 per non dare lo strappo
HZ = 40


def rd():
    try:
        if time.time() - os.path.getmtime(ENC) > 0.1: return None
        return int(open(ENC).readline())
    except (OSError, ValueError): return None


def q_fast(ser):
    """GET_VALUES leggendo il frame esatto (niente attesa fissa): ~8 ms invece di ~90."""
    try:
        ser.reset_input_buffer(); ser.write(pkt(bytes([COMM_GET_VALUES])))
        if ser.read(1) != b"\x02": return None
        n = ser.read(1)
        if not n: return None
        pl = ser.read(n[0] + 3)[:n[0]]
        if len(pl) < 49 or pl[0] != COMM_GET_VALUES: return None
        p = pl[1:]
        return {"i_motor": struct.unpack(">i", p[4:8])[0] / 100.0, "rpm": struct.unpack(">i", p[22:26])[0],
                "tach": struct.unpack(">i", p[44:48])[0]}
    except (serial.SerialException, OSError, struct.error): return None


def wheel():
    try:
        return open(WHEEL).read().strip(), time.time() - os.path.getmtime(WHEEL) < 0.5
    except OSError: return None, False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, help="raw encoder (default: centro della calib)")
    ap.add_argument("--vel", type=float, default=10.0, help="deg/s al manubrio (max 20)")
    ap.add_argument("--imax", type=float, default=30.0, help="A, max 30")
    ap.add_argument("--sign", type=int, default=-1, choices=(-1, 1), help="segno corrente per far SALIRE l'encoder")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not 0 < a.vel <= 20: sys.exit("--vel in (0, 20] deg/s")
    if not 0 < a.imax <= 30: sys.exit("--imax in (0, 30] A")
    cal = json.load(open(CAL))
    c = cal["encoder_center_raw"]
    lo = cal.get("limite_sw_sx_raw", c + cal["delta_sx_steps"] + 200)
    hi = cal.get("limite_sw_dx_raw", c + cal["delta_dx_steps"] - 200)
    tgt = c if a.target is None else a.target
    if not lo < tgt < hi: sys.exit(f"target {tgt} fuori da [{lo},{hi}]")
    ok, why = uart_libera(UART)
    if not ok: sys.exit(f"UART non libera: {why}")
    w0, fresh = wheel()
    if not fresh: sys.exit("encoder ruota assente/vecchio: rifiuto")
    time.sleep(0.5)
    if wheel()[0] != w0: sys.exit("bici in movimento: rifiuto")
    p0 = rd()
    if p0 is None: sys.exit("encoder sterzo vecchio")
    e0 = tgt - p0
    print(f"pos={p0} ({(p0 - c) * DEG:+.1f} deg) target={tgt} errore={e0 * DEG:+.1f} deg  vel={a.vel} deg/s imax={a.imax} A")
    print("verso atteso: encoder deve " + ("SALIRE (manubrio verso DX)" if e0 > 0 else "SCENDERE (manubrio verso SX)"))
    if abs(e0) < 15 or a.dry_run: print("niente da fare / dry-run"); return
    hard_lo = c + cal["delta_sx_steps"] + 60; hard_hi = c + cal["delta_dx_steps"] - 60   # 60 count = 1.3 deg dal finecorsa vero
    if not hard_lo <= p0 <= hard_hi: sys.exit(f"pos troppo vicina al finecorsa vero [{hard_lo},{hard_hi}]: muovere a mano")
    d = 1 if e0 > 0 else -1          # verso encoder voluto
    os.makedirs("/data/logging/vesc", exist_ok=True)
    log = open(time.strftime("/data/logging/vesc/sterzo_vel_%Y%m%d_%H%M%S.csv"), "w")
    log.write("t,pos,err,rate_deg_s,i_cmd,i_motor,rpm,tach\n")
    ser = serial.Serial(UART, BAUD, timeout=0.02)
    def stop():
        for f in (send_current, send_duty, send_current, send_current):
            try: f(ser, 0)
            except Exception: pass
    def _kill(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _kill); signal.signal(signal.SIGHUP, _kill)   # SSH caduto -> corrente 0
    hist = [(time.monotonic(), p0)]; i_cmd = i_base = I_START; moving = False; t_prev = time.monotonic(); reason = None; t0 = time.monotonic(); t_slow = None
    try:
        while True:
            tc = time.monotonic()
            send_current(ser, a.sign * d * i_cmd)
            t = q_fast(ser)
            if t is None:
                t = q_fast(ser)                       # una seconda prova, poi stop
                if t is None: reason = "VESC muto"; break
            p = rd()
            if p is None: reason = "encoder vecchio"; break
            hist.append((tc, p)); hist = [h for h in hist if tc - h[0] <= 0.3]
            def vel(win):
                h = [x for x in hist if tc - x[0] <= win]
                return (h[-1][1] - h[0][1]) * DEG / max(h[-1][0] - h[0][0], 0.02)
            rate, rate_safe = vel(0.15), vel(0.3)
            err = tgt - p
            log.write(f"{tc - t0:.3f},{p},{err},{rate:.2f},{a.sign * d * i_cmd:.2f},{t['i_motor']:.2f},{t['rpm']},{t['tach']}\n")
            if (p - p0) * d <= -WRONG_COUNTS: reason = f"VERSO SBAGLIATO: encoder {p - p0:+d} count"; break
            if abs(rate_safe) > VEL_MAX_DEG_S: reason = f"troppo veloce {rate_safe:+.0f} deg/s"; break
            # oltre i limiti software si puo' solo tornare verso il centro (Daniele 2026-11-09: "da qui vai in centro" a -47 deg)
            if (p < lo and d < 0) or (p > hi and d > 0) or not hard_lo <= p <= hard_hi: reason = f"limite {p}"; break
            if abs(t["i_motor"]) > a.imax: reason = f"corrente {t['i_motor']:.1f} A"; break
            if wheel()[0] != w0: reason = "bici in movimento"; break
            if tc - t0 > 25: reason = "timeout 25 s"; break
            if abs(err) < 14 or err * d < 0: print(f"ARRIVATO pos={p} err={err * DEG:+.2f} deg in {tc - t0:.1f} s"); break
            v_obj = a.vel if abs(err) * DEG > 5 else max(2.0, a.vel * abs(err) * DEG / 5)   # rallenta negli ultimi 5 deg
            v = rate * d
            dt = tc - t_prev; t_prev = tc
            if not moving and v > 2:
                moving = True; i_base = i_cmd * CUT_AL_DISTACCO
            # STALLO: manubrio fermo con corrente alta (bloccato a mano o contro qualcosa) -> stop, mai rampa infinita
            t_slow = (t_slow or tc) if (v < 1 and (moving and i_cmd >= 15 or not moving and i_cmd >= a.imax)) else None
            if t_slow and tc - t_slow > (1.0 if moving else 0.3): reason = f"STALLO a {i_cmd:.1f} A"; break
            if not moving:
                i_base = i_cmd = min(i_cmd + I_RAMP, a.imax)
            else:
                i_base = min(max(i_base + KI * (v_obj - v) * dt, 0.0), a.imax)
                i_cmd = min(max(i_base + KP * (v_obj - v), 0.0), a.imax)
            time.sleep(max(0.0, 1 / HZ - (time.monotonic() - tc)))
    except KeyboardInterrupt: reason = "Ctrl-C"
    finally:
        stop(); ser.close(); log.close()
        if reason: print("[STOP]", reason)
        print(f"fine: pos={rd()} i_cmd_finale={i_cmd:.2f} A")


if __name__ == "__main__":
    main()
