#!/usr/bin/env python3
"""
vesc_return_centro_001.py — #001: ritorno al centro a IMPULSI PICCOLI, ogni stadio col "vai" di Daniele (scritto a mano, terminale vero).

Usa la calib per unita' /data/steering_limits_<ASMILE_NAME>.json (da calibrate_steering_limits.py; MAI quella di asmile2, MAI fallback su config/)
e l'encoder AMT22 14 bit /tmp/encoder_steer. Comando = SET_DUTY basso a impulsi (come _duty.py, che su asmile2 funzionava).
Tetti fissi (non alzabili da riga di comando): imax<=5 A, duty<=0.03, step-ms<=100.
Pre-controlli (rifiuto se uno manca): calib valida (unit, 14 bit, center_repeatability_deg<=1), UART libera (fuser + systemctl + pgrep),
bici ferma con encoder ruota fresco (<0.5 s), l_current_max del VESC <= 8 A (sola lettura COMM_GET_MCCONF, fw 5.2).
Stadi (ognuno chiede 'vai'):
  0 solo lettura: posizione, centro, errore, DIREZIONE ATTESA dichiarata.
  1 micro-impulso (20 ms) verso il centro: misura il VERSO reale encoder<->duty. |moved|<5 count -> stop e si torna da Daniele.
  2 gradini da --step-ms (default 60 ms) con pausa 150 ms e rilettura, fino al centro.
STOP automatico (duty 0 + corrente 0): encoder vecchio >100 ms, pos fuori [min+margine, max-margine] (a ogni iterazione e in ogni impulso),
|i_motor| > --imax, VESC muto, salto encoder >200 count, bici in movimento (anche dentro il loop), errore che cresce 2 gradini di fila,
fermo dopo 3 impulsi, attraversato il centro, timeout 20 s, Ctrl-C.
Niente comando se --dry-run. Non e' mai stato eseguito su #001.
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from vesc_return_to_center_duty import send_duty, send_current, query_tach, UART, BAUD
from safety_001 import uart_libera, vai_interattivo
import vesc_mcconf_limiti_001 as mc

IMAX_TETTO, DUTY_TETTO, STEPMS_TETTO, LCURMAX_TETTO = 5.0, 0.03, 100, 8.0
DATA_DIR = "/data"
WHEEL = "/tmp/encoder_wheel"
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


def carica_calib(n):
    """Solo /data/steering_limits_<n>.json, nessun fallback. Valida formato di calibrate_steering_limits.py."""
    pth = os.path.join(DATA_DIR, f"steering_limits_{n}.json")
    if not os.path.exists(pth): sys.exit(f"manca {pth}: calibra prima lo sterzo di {n} (nessun fallback su config/)")
    try: cal = json.load(open(pth))
    except (OSError, ValueError) as e: sys.exit(f"calib illeggibile: {e}")
    if cal.get("unit") != n: sys.exit("calib di un'altra unita': rifiuto")
    if cal.get("encoder_bits") != 14 or cal.get("encoder_steps_per_rev") != CPR: sys.exit("calib non a 14 bit / 16384 passi: rifiuto")
    for k in ("encoder_center_raw", "delta_sx_steps", "delta_dx_steps", "center_repeatability_deg"):
        if not isinstance(cal.get(k), (int, float)): sys.exit(f"calib senza campo numerico '{k}': rifiuto")
    if abs(cal["center_repeatability_deg"]) > 1.0: sys.exit("center_repeatability_deg > 1: centro non affidabile, rifare la calibrazione")
    if not (0 <= cal["encoder_center_raw"] < CPR): sys.exit("encoder_center_raw fuori range")
    if cal["delta_sx_steps"] * cal["delta_dx_steps"] >= 0: sys.exit("delta_sx/delta_dx devono avere segno opposto: calib incoerente")
    return cal


LAST = [0.0]


def in_range(p, c, lo, hi, m):
    return lo + m <= c + err(p, c) <= hi - m


def pulse(ser, duty, ms, imax, p_prev, c, lo, hi, m):
    """Impulso con lettura corrente DURANTE il comando (ogni ~30 ms), controllo salto encoder e range finecorsa.
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
        if not in_range(q, c, lo, hi, m): return f"fuori range durante impulso {q}"
        if time.monotonic() >= t_end: return None


def _wheel():
    """(valore, mtime-fresco) di /tmp/encoder_wheel; None se assente."""
    try:
        v = open(WHEEL).read().strip()
        return v, (time.time() - os.path.getmtime(WHEEL)) < 0.5
    except OSError:
        return None


def ferma_bici(ref=None):
    """True solo se /tmp/encoder_wheel e' FRESCO (mtime<0.5 s) e il valore e' fermo.
    ref=None: attende 1 s e confronta due letture. ref=valore: confronto immediato col riferimento (uso nel loop)."""
    a = _wheel()
    if a is None or not a[1]: return False
    if ref is None:
        time.sleep(1.0)
        b = _wheel()
        return b is not None and b[1] and a[0] == b[0]
    return a[0] == ref


def lcur_max(ser):
    """Sola lettura COMM_GET_MCCONF: l_current_max. Rifiuta se fw != 5.2 o layout non plausibile."""
    v = mc.fw(ser)
    if f"{v[0]}.{v[1]}" != "5.2": sys.exit(f"fw VESC {v[0]}.{v[1]} != 5.2: rifiuto")
    blob = mc.get(ser)
    if not mc.plausibile(blob): sys.exit("mcconf del VESC non plausibile (layout?): rifiuto")
    return mc.campi(blob)["l_current_max"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--duty", type=float, default=0.020)
    ap.add_argument("--step-ms", type=int, default=60)
    ap.add_argument("--imax", type=float, default=IMAX_TETTO)
    ap.add_argument("--margine", type=int, default=40, help="count dal finecorsa")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not (0 < a.imax <= IMAX_TETTO): sys.exit(f"--imax deve essere in (0, {IMAX_TETTO}] A: rifiuto")
    if not (0 < a.duty <= DUTY_TETTO): sys.exit(f"--duty deve essere in (0, {DUTY_TETTO}]: rifiuto")
    if not (0 < a.step_ms <= STEPMS_TETTO): sys.exit(f"--step-ms deve essere in (0, {STEPMS_TETTO}]: rifiuto")
    if a.margine < 0: sys.exit("--margine negativo: rifiuto")
    n = unit()
    cal = carica_calib(n)
    c = cal["encoder_center_raw"]
    lo, hi = sorted([c + cal["delta_sx_steps"], c + cal["delta_dx_steps"]])  # srotolati attorno al centro; err() gestisce il wrap
    ok_u, why = uart_libera(UART)
    if not ok_u: sys.exit(f"UART VESC non libera ({why}): fermare power_steering/speed_limiter e ripetere")
    if not ferma_bici(): sys.exit("bici NON ferma o /tmp/encoder_wheel assente/vecchio (>0.5 s): rifiuto")
    ref_wheel = _wheel()[0]
    ser = serial.Serial(UART, BAUD, timeout=0.2)
    stop = lambda: [f(ser, 0) for f in (send_duty, send_current, send_duty, send_current)]
    sign, reason = +1, None
    try:
        p = rd()
        if p is None: sys.exit("encoder assente/vecchio")
        e = err(p, c)
        print(f"pos={p} centro={c} limiti=[{lo},{hi}] errore={e:+d}")
        if not in_range(p, c, lo, hi, a.margine): sys.exit(f"pos {p} fuori da [{lo + a.margine},{hi - a.margine}]: rifiuto (muovere a mano)")
        print("direzione attesa: " + ("encoder deve SCENDERE (manubrio verso il lato basso)" if e > 0 else "encoder deve SALIRE"))
        if abs(e) < 15 or a.dry_run: print("niente da fare / dry-run"); return
        lc = lcur_max(ser)
        print(f"VESC l_current_max = {lc:.2f} A (sola lettura)")
        if lc > LCURMAX_TETTO: sys.exit(f"l_current_max {lc:.1f} A > {LCURMAX_TETTO} A: fai prima il passo A (tetto corrente)")
        if not vai_interattivo("STADIO 1: micro-impulso 20 ms verso il centro, misura verso reale"): return
        p0 = p
        r0 = pulse(ser, sign * a.duty * (-1 if e > 0 else 1), 20, a.imax, p0, c, lo, hi, a.margine)
        stop(); time.sleep(0.3)
        if r0: reason = r0; return
        p1 = rd()
        moved = None if p1 is None else err(p1, p0)
        print(f"mosso di {moved} count")
        if moved is None or abs(moved) < 5:
            reason = f"movimento {moved} count < 5: segno non determinabile, stop e si torna da Daniele (niente aumento automatico)"; return
        if moved * e > 0: sign = -1; print("verso opposto all'atteso: segno invertito, riparto dallo stadio 2")
        if not vai_interattivo(f"STADIO 2: gradini {a.step_ms} ms, duty {a.duty}, segno {sign:+d}, imax {a.imax} A"): return
        t0 = time.monotonic(); still = 0; grow = 0; prev = abs(err(p1, c))
        while True:
            if not ferma_bici(ref_wheel): reason = "bici in movimento o encoder ruota vecchio"; break
            p = rd()
            if p is None: reason = "encoder vecchio"; break
            if not in_range(p, c, lo, hi, a.margine): reason = f"fuori range {p}"; break
            if time.monotonic() - t0 > 20: reason = "timeout"; break
            en = err(p, c)
            if abs(en) < 15 or en * e < 0: print(f"FINE pos={p} err={en:+d}"); break
            reason = pulse(ser, sign * a.duty * (-1 if en > 0 else 1), a.step_ms, a.imax, p, c, lo, hi, a.margine)
            stop()
            if reason: break
            time.sleep(0.15)
            q = rd()
            still = still + 1 if q is not None and abs(err(q, p)) < 2 else 0
            if still >= 3: reason = "fermo dopo 3 impulsi (attrito/blocco)"; break
            if q is not None:
                grow = grow + 1 if abs(err(q, c)) > prev + 1 else 0
                prev = abs(err(q, c))
                if grow >= 2: reason = "errore in aumento per 2 gradini di fila (verso sbagliato?)"; break
            es = f"{err(q, c):+d}" if q is not None else "?"
            print(f"  pos={q} err={es} i={LAST[0]:.2f}")
    except KeyboardInterrupt: reason = "Ctrl-C"
    finally:
        stop(); ser.close()
        if reason: print("[ABORT]", reason)


if __name__ == "__main__":
    main()
