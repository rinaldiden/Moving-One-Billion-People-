#!/usr/bin/env python3
"""
vesc_return_centro_001.py — #001: ritorno al centro a IMPULSI PICCOLI, ogni stadio col "vai" di Daniele.

Usa la calib per unita' /data/steering_limits_<ASMILE_NAME>.json (da calibrate_steering_limits.py; MAI quella di asmile2)
e l'encoder AMT22 14 bit /tmp/encoder_steer. Comando = SET_DUTY basso a impulsi (come _duty.py, che su asmile2 funzionava).
Stadi (ognuno chiede 'vai' scrivendolo a mano):
  0 solo lettura: posizione, centro, errore, DIREZIONE ATTESA dichiarata.
  1 micro-impulso (20 ms) verso il centro: misura il VERSO reale encoder<->duty. Se muove al contrario -> inverte il segno e riparte da 0.
  2 gradini da --step-ms (default 60 ms) con pausa 150 ms e rilettura, fino al centro.
STOP automatico (duty 0 + corrente 0): encoder vecchio >100 ms, pos fuori [min+margine, max-margine],
|i_motor| > --imax (default 5 A), nessun movimento dopo 3 impulsi, attraversato il centro, timeout 20 s, Ctrl-C.
Niente comando se --dry-run. Non e' mai stato eseguito su #001.
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from vesc_return_to_center_duty import send_duty, send_current, query_tach, UART, BAUD

ENC = "/tmp/encoder_steer"; CPR = 16384


def unit():
    try:
        for l in open(os.path.expanduser("~/asmile_id.conf")):
            if l.startswith("ASMILE_NAME="): return l.split("=", 1)[1].strip()
    except OSError: pass
    sys.exit("ASMILE_NAME non trovato: unita' sconosciuta, niente fallback")


def rd():
    try:
        if time.time() - os.path.getmtime(ENC) > 0.1: return None
        return int(open(ENC).readline())
    except (OSError, ValueError): return None


def err(p, c): return (p - c + CPR // 2) % CPR - CPR // 2


LAST = [0.0]


def pulse(ser, duty, ms, imax, p_prev):
    """Impulso con lettura corrente DURANTE il comando (ogni ~30 ms) e controllo salto encoder.
    Ritorna None se ok, altrimenti il motivo di stop (il chiamante fa stop())."""
    t_end = time.monotonic() + ms / 1000
    while True:
        send_duty(ser, duty)
        time.sleep(0.01)
        t = query_tach(ser)
        if t is None: return "lettura VESC mancante durante impulso"
        LAST[0] = t["i_motor"]
        if abs(t["i_motor"]) > imax: return f"corrente {t['i_motor']:.1f} A > {imax} A"
        q = rd()
        if q is None: return "encoder vecchio durante impulso"
        if abs(err(q, p_prev)) > 200: return f"salto encoder {err(q, p_prev)} count"
        if time.monotonic() >= t_end: return None


def ferma_bici():
    """Rifiuta se la bici si muove: /tmp/encoder_wheel deve restare identico per 1 s (assente = non verificabile = rifiuto)."""
    try:
        a = open("/tmp/encoder_wheel").read().strip(); time.sleep(1.0); b = open("/tmp/encoder_wheel").read().strip()
    except OSError:
        return False
    return a == b


def uart_libera():
    """Nessun altro processo (power_steering, ecc.) deve tenere la UART del VESC."""
    import subprocess
    r = subprocess.run(["fuser", UART], capture_output=True, text=True)
    mine = str(os.getpid())
    return not [x for x in r.stdout.split() if x != mine]


def vai(txt):
    return input(f"\n>>> {txt}\n    scrivi 'vai' per procedere (altro = stop): ").strip().lower() == "vai"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duty", type=float, default=0.020)
    ap.add_argument("--step-ms", type=int, default=60)
    ap.add_argument("--imax", type=float, default=5.0)
    ap.add_argument("--margine", type=int, default=40, help="count dal finecorsa")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    n = unit()
    pth = f"/data/steering_limits_{n}.json"
    if not os.path.exists(pth): pth = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", f"steering_limits_{n}.json")
    cal = json.load(open(pth))
    if cal.get("unit") != n: sys.exit("calib di un'altra unita': rifiuto")
    c = cal["encoder_center_raw"]; r = sorted([c + cal["delta_sx_steps"], c + cal["delta_dx_steps"]])
    lo, hi = r  # srotolati attorno al centro; err() gestisce il wrap
    if not uart_libera(): sys.exit("UART VESC occupata da un altro processo (power_steering?): fermarlo prima e ripetere")
    if not ferma_bici(): sys.exit("bici NON ferma o /tmp/encoder_wheel assente: rifiuto")
    ser = serial.Serial(UART, BAUD, timeout=0.2)
    stop = lambda: [f(ser, 0) for f in (send_duty, send_current, send_duty, send_current)]
    sign, reason = +1, None
    try:
        p = rd()
        if p is None: sys.exit("encoder assente/vecchio")
        e = err(p, c)
        print(f"pos={p} centro={c} limiti=[{lo},{hi}] errore={e:+d}")
        print("direzione attesa: " + ("encoder deve SCENDERE (manubrio verso il lato basso)" if e > 0 else "encoder deve SALIRE"))
        if abs(e) < 15 or a.dry_run: print("niente da fare / dry-run"); return
        if not vai("STADIO 1: micro-impulso 20 ms verso il centro, misura verso reale"): return
        p0 = p
        r0 = pulse(ser, sign * a.duty * (-1 if e > 0 else 1), 20, a.imax, p0)
        stop(); time.sleep(0.3)
        if r0: reason = r0; return
        p1 = rd()
        moved = None if p1 is None else err(p1, p0)
        print(f"mosso di {moved} count")
        if not moved: sys.exit("nessun movimento: alzare --duty o --step-ms solo con nuovo vai; stop")
        if moved * e > 0: sign = -1; print("verso opposto all'atteso: segno invertito, riparto dallo stadio 2")
        if not vai(f"STADIO 2: gradini {a.step_ms} ms, duty {a.duty}, segno {sign:+d}, imax {a.imax} A"): return
        t0 = time.monotonic(); still = 0
        while True:
            p = rd()
            if p is None: reason = "encoder vecchio"; break
            if not (lo + a.margine <= c + err(p, c) <= hi - a.margine): reason = f"fuori range {p}"; break
            if time.monotonic() - t0 > 20: reason = "timeout"; break
            en = err(p, c)
            if abs(en) < 15 or en * e < 0: print(f"FINE pos={p} err={en:+d}"); break
            reason = pulse(ser, sign * a.duty * (-1 if en > 0 else 1), a.step_ms, a.imax, p)
            stop()
            if reason: break
            time.sleep(0.15)
            t = {"i_motor": LAST[0]}
            q = rd()
            still = still + 1 if q is not None and abs(err(q, p)) < 2 else 0
            if still >= 3: reason = "fermo dopo 3 impulsi (attrito/blocco)"; break
            print(f"  pos={q} err={err(q, c) if q is not None else '?':+} i={t['i_motor'] if t else '?'}")
    except KeyboardInterrupt: reason = "Ctrl-C"
    finally:
        stop(); ser.close()
        if reason: print("[ABORT]", reason)


if __name__ == "__main__":
    main()
