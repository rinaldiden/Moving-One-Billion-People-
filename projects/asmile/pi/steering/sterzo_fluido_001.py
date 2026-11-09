#!/usr/bin/env python3
"""
sterzo_fluido_001.py — #001: sterzo LENTO e FLUIDO (5-20 deg/s) e "tieni posizione" fino a 30 A.
Ricerca: agents/ricerche/vesc_sterzo_fluido_20261109.md

Perche' cosi' (e non SET_RPM / SET_POS del VESC): a 58 ERPM gli hall danno 5.8 transizioni/s (una ogni 172 ms);
la velocita' del VESC (PLL sulla fase hall, mcpwm_foc.c fw 5.02) e' quindi una scala a gradini e, da fermo, il VESC
continua a interpolare alla velocita' vecchia fino a 0.5 s: lo speed PID non vede lo stacco. SET_POS senza encoder
sul VESC lavora sull'angolo ELETTRICO (si avvolge ogni 10.4 deg di piantone). L'AMT22 sul piantone ha 79x la
risoluzione degli hall (12 bit reali = 0.088 deg): il loop giusto e' sul Pi, ma fatto bene:
  - 200 Hz (prima ~40 Hz reali), SET_CURRENT ogni ciclo, telemetria ridotta (GET_VALUES_SELECTIVE, solo corrente,
    14 byte invece di ~75) 1 ciclo su 5;
  - velocita' stimata con filtro alfa-beta sui campioni dell'encoder datati con l'mtime del file (niente media 50 ms);
  - riferimento a trapezio (accel limitata) + MOLLA RIGIDA (KP A/deg) sul ritardo dal riferimento + smorzatore KD
    + feedforward d'attrito coulombiano (I_COUL, appreso in linea) + integrale piccolo limitato + dither anti-stiction
    solo da fermo. Lo scatto di stick-slip ha ampiezza ~ (I_stacco - I_moto)/KP: con KP 3 A/deg = ~1.5 deg max e
    lo stacco si ripete a frequenza alta -> sembra fluido. Con la molla morbida di prima (1.4 A/deg, lead 3 deg) era
    ~3 deg a 2 Hz.

Modi:
  vai   --target RAW [--vel 10]   porta il manubrio al target a velocita' costante, arriva e lascia libero.
  tieni [--target RAW] [--imax 15] tiene la posizione (prova di resistenza a mano). Molla KP_H, smorzatore, corrente
                                   <= imax (max 30). Soft-start 1 s. Si sgancia se spostato > 10 deg o dopo --durata.
STOP immediato (corrente 0): verso sbagliato >= 10 count (vai), velocita' > 30 deg/s (media 0.3 s), limiti software
4500/8700 (o piu' stretti dalla calib) - oltre si puo' solo rientrare -, mai entro 60 count dai finecorsa veri
4304/8884, |i_motor| > imax + 2 A, encoder vecchio > 100 ms, VESC muto, bici in movimento, stallo, timeout,
surriscaldamento (tieni: > 8 s cumulati sopra 20 A), Ctrl-C, SIGTERM, SIGHUP (SSH caduto).
Il VESC ha anche il suo timeout UART (app_conf timeout_msec, default 1000 ms): se il Pi muore, corrente 0.

Uso:  python3 sterzo_fluido_001.py vai   --target 6600 --vel 10 [--imax 30] [--dry-run]
      python3 sterzo_fluido_001.py tieni --imax 15 --durata 20
Log:  /data/logging/vesc/sterzo_fluido_<modo>_<ora>.csv
NON scrive nulla sul VESC (nessuna mcconf): usa solo SET_CURRENT e GET_VALUES_SELECTIVE.
"""
import argparse, json, math, os, signal, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from vesc_return_to_center_duty import send_duty, send_current, pkt, UART, BAUD
from safety_001 import uart_libera

ENC = "/tmp/encoder_steer"; WHEEL = "/tmp/encoder_wheel"; CPR = 16384; DEG = 360.0 / CPR
CAL = "/data/steering_limits_asmile-001.json"
LIM_SW = (4500, 8700)           # limiti software (Daniele 2026-11-09)
FINECORSA = (4304, 8884)        # finecorsa meccanici veri
MARGINE_FC = 60                 # count (1.3 deg): mai piu' vicino di cosi' al finecorsa vero
COMM_GET_VALUES_SELECTIVE = 50  # fw 5.02 datatypes.h
MASK_I_MOTOR = 1 << 2           # avg motor current (float32 * 100)
HZ = 200
VEL_MAX_DEG_S = 30.0
WRONG_COUNTS = 10

# --- guadagni (in unita' di MANUBRIO: deg, deg/s; corrente in A che spinge l'encoder in SU) ---
I_COUL0 = 6.5        # A, attrito in moto misurato 2026-11-09 (6-7 A), poi appreso in linea
KP = 3.0             # A/deg molla sul ritardo dal riferimento (vai)
KD = 0.6             # A/(deg/s) — sweep 2026-11-09: 0.5->16-18%, 0.6->12-15%, 0.75 verso SX martella e vibra. Non oltre 0.6 senza filtro velocita migliore
KI = 4.0             # A/(deg*s), integrale piccolo
I_INT_MAX = 3.0      # A
LAG_MAX = 2.5        # deg: il riferimento non scappa mai piu' di cosi' dal manubrio (anti-strappo)
A_MAX = 40.0         # deg/s^2 rampa del riferimento
I_DITH = 0.0         # A, dither +/- a 100 Hz solo quando dovrebbe muoversi ed e' fermo
V_FERMO = 1.5        # deg/s
# Ripple per giro elettrico (prova 16:58: velocita' 1.7-7.8 deg/s a 5 deg/s, picchi a 1-2 Hz = metà/quarto di giro
# elettrico; hall "significantly misaligned"). Tabella di compensazione per fase elettrica, imparata e salvata in /data.
EREV = 16384 / 35.0          # count per giro elettrico (7 coppie polari x riduzione 5)
NB = 36; K_RIP = 0.03        # bin per giro elettrico; A per (deg/s) di errore per ciclo
RIP_MAX = 4.0                # A
RIP_FILE = "/data/sterzo_ripple_001.json"
KP_H, KD_H, KI_H = 6.0, 0.30, 6.0   # tieni: 6 A/deg -> 30 A a 5 deg di spostamento
SGANCIO_H = 10.0     # deg: tieni, se spostato oltre -> mollo


def rd_enc():
    """(pos, mtime) o (None, None) se vecchio > 100 ms."""
    try:
        mt = os.stat(ENC).st_mtime
        if time.time() - mt > 0.1: return None, None
        return int(open(ENC).readline()), mt
    except (OSError, ValueError):
        return None, None


def wheel():
    try:
        return open(WHEEL).read().strip(), time.time() - os.path.getmtime(WHEEL) < 0.5
    except OSError:
        return None, False


def q_imotor(ser):
    """GET_VALUES_SELECTIVE solo corrente motore media (A). ~2 ms andata+ritorno."""
    try:
        ser.reset_input_buffer()
        ser.write(pkt(struct.pack(">BI", COMM_GET_VALUES_SELECTIVE, MASK_I_MOTOR)))
        if ser.read(1) != b"\x02": return None
        n = ser.read(1)
        if not n or n[0] != 9: return None
        pl = ser.read(n[0] + 3)[:n[0]]
        if len(pl) < 9 or pl[0] != COMM_GET_VALUES_SELECTIVE: return None
        return struct.unpack(">i", pl[5:9])[0] / 100.0
    except (serial.SerialException, OSError, struct.error):
        return None


class AlfaBeta:
    """Stima pos/vel (deg, deg/s) dai campioni encoder datati con l'mtime: ritardo ~20 ms, niente finestre lunghe."""
    def __init__(self, p, t, a=0.35, b=0.05):
        self.x, self.v, self.t, self.a, self.b = p * DEG, 0.0, t, a, b

    def update(self, p, t):
        dt = t - self.t
        if dt <= 0: return
        self.t = t
        xp = self.x + self.v * dt
        r = p * DEG - xp
        self.x = xp + self.a * r
        self.v += self.b * r / dt


def limiti():
    cal = json.load(open(CAL))
    c = cal["encoder_center_raw"]
    lo = max(cal.get("limite_sw_sx_raw", LIM_SW[0]), LIM_SW[0])
    hi = min(cal.get("limite_sw_dx_raw", LIM_SW[1]), LIM_SW[1])
    return c, lo, hi, FINECORSA[0] + MARGINE_FC, FINECORSA[1] - MARGINE_FC


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["vai", "tieni"])
    ap.add_argument("--target", type=int, help="raw encoder (vai: default centro calib; tieni: default pos attuale)")
    ap.add_argument("--vel", type=float, default=15.0, help="deg/s al manubrio, (0,20]")
    ap.add_argument("--imax", type=float, default=None, help="A, max 30 (default: vai 30, tieni 15)")
    ap.add_argument("--durata", type=float, default=20.0, help="s, tieni (max 60)")
    ap.add_argument("--kp", type=float, default=None, help="A/deg (vai %.1f, tieni %.1f)" % (KP, KP_H))
    ap.add_argument("--dither", type=float, default=I_DITH, help="A (0 = spento)")
    ap.add_argument("--kd", type=float, default=KD, help="A/(deg/s), vai")
    ap.add_argument("--rip", type=int, default=0, choices=(0, 1), help="compensazione ripple (vai)")
    ap.add_argument("--tag", default="", help="etichetta nel nome del log")
    ap.add_argument("--ab", type=float, nargs=2, default=(0.35, 0.05), help="filtro velocita' alfa beta")
    ap.add_argument("--sign", type=int, default=-1, choices=(-1, 1), help="segno corrente VESC per far SALIRE l'encoder")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    imax = a.imax if a.imax is not None else (30.0 if a.modo == "vai" else 15.0)
    if not 0 < a.vel <= 20: sys.exit("--vel in (0, 20] deg/s")
    if not 0 < imax <= 30: sys.exit("--imax in (0, 30] A")
    if not 0 < a.durata <= 60: sys.exit("--durata in (0, 60] s")
    if not 0 <= a.dither <= 3: sys.exit("--dither in [0, 3] A")
    c, lo, hi, hard_lo, hard_hi = limiti()

    ok, why = uart_libera(UART)
    if not ok: sys.exit(f"UART non libera: {why}")
    w0, fresh = wheel()
    if not fresh: sys.exit("encoder ruota assente/vecchio: rifiuto")
    time.sleep(0.5)
    if wheel()[0] != w0: sys.exit("bici in movimento: rifiuto")
    p0, mt0 = rd_enc()
    if p0 is None: sys.exit("encoder sterzo vecchio")
    if not hard_lo <= p0 <= hard_hi: sys.exit(f"pos {p0} troppo vicina al finecorsa vero [{hard_lo},{hard_hi}]: muovere a mano")

    if a.modo == "vai":
        tgt = c if a.target is None else a.target
        kp = KP if a.kp is None else a.kp
    else:
        tgt = p0 if a.target is None else a.target
        kp = KP_H if a.kp is None else a.kp
        if abs(tgt - p0) * DEG > 1.0: sys.exit("tieni: target a piu' di 1 deg dalla posizione attuale: usa prima 'vai'")
    if not 0 < kp <= 10: sys.exit("--kp in (0, 10] A/deg")
    if not lo <= tgt <= hi: sys.exit(f"target {tgt} fuori da [{lo},{hi}]")
    e0 = tgt - p0
    d = 1 if e0 > 0 else -1
    print(f"modo={a.modo} pos={p0} ({(p0 - c) * DEG:+.1f} deg) target={tgt} errore={e0 * DEG:+.1f} deg "
          f"vel={a.vel} deg/s imax={imax} A kp={kp} A/deg dither={a.dither} A")
    if a.modo == "vai":
        print("verso atteso: encoder deve " + ("SALIRE (manubrio verso DX)" if d > 0 else "SCENDERE (manubrio verso SX)"))
        if abs(e0) < 15: print("gia' al target"); return
    if a.dry_run: print("dry-run: nessun comando"); return

    os.makedirs("/data/logging/vesc", exist_ok=True)
    log = open(time.strftime(f"/data/logging/vesc/sterzo_fluido_{a.modo}_%Y%m%d_%H%M%S{a.tag}.csv"), "w")
    log.write("t,pos,lag_deg,v_est,v_ref,sp_deg,i_cmd,i_motor,i_coul,i_int\n")
    ser = serial.Serial(UART, BAUD, timeout=0.01)

    def stop():
        for f in (send_current, send_duty, send_current, send_current):
            try: f(ser, 0)
            except Exception: pass

    def _kill(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _kill); signal.signal(signal.SIGHUP, _kill)

    ab = AlfaBeta(p0, mt0, a.ab[0], a.ab[1]); last_mt = mt0
    hist = [(time.monotonic(), p0)]
    sp = p0 * DEG; v_ref = 0.0; i_int = 0.0; i_coul = I_COUL0; i_cmd = 0.0; i_mot = 0.0
    k = 0; t0 = t_prev = time.monotonic(); reason = None; t_stallo = None; t_caldo = 0.0; q_fail = 0
    tgt_deg = tgt * DEG
    try: rip = json.load(open(RIP_FILE))
    except (OSError, ValueError): rip = {"+1": [0.0] * NB, "-1": [0.0] * NB}
    kd_ = "+1" if d > 0 else "-1"
    rt = rip.get(kd_, [0.0] * NB) if a.modo == "vai" else [0.0] * NB
    t_arr = None
    try:
        while True:
            tc = time.monotonic()
            dt = min(tc - t_prev, 0.02); t_prev = tc
            p, mt = rd_enc()
            if p is None: reason = "encoder vecchio"; break
            if mt != last_mt: ab.update(p, mt); last_mt = mt
            v = ab.v
            hist.append((tc, p)); hist = [h for h in hist if tc - h[0] <= 0.3]
            rate_safe = (hist[-1][1] - hist[0][1]) * DEG / max(hist[-1][0] - hist[0][0], 0.05)
            x = p * DEG

            # ---------------- controllo ----------------
            if a.modo == "vai":
                rem = (tgt_deg - sp) * d                                  # deg ancora da percorrere col riferimento
                v_lim = min(a.vel, math.sqrt(max(2 * A_MAX * max(rem, 0.0), 0.0)))   # frenata trapezio
                v_ref = d * min(abs(v_ref) + A_MAX * dt, v_lim)
                sp += v_ref * dt
                if (tgt_deg - sp) * d < 0: sp = tgt_deg; v_ref = 0.0
                sp = x + max(min(sp - x, LAG_MAX), -LAG_MAX)              # mai piu' di LAG_MAX dal manubrio
                lag = sp - x
                moving = abs(v) > V_FERMO
                if moving and abs(v - v_ref) < 3 and v * d > 0:           # apprendo l'attrito in moto
                    i_coul = min(max(0.99 * i_coul + 0.01 * abs(i_cmd - kp * lag - i_int), 3.0), 12.0)
                ff = d * i_coul if abs(v_ref) > 0.1 else 0.0
                i_int = max(min(i_int + KI * lag * dt, I_INT_MAX), -I_INT_MAX)
                dith = (a.dither if k % 2 else -a.dither) if (not moving and abs(v_ref) > 0.1) else 0.0
                b = int((p % EREV) / EREV * NB) % NB
                if moving and abs(v_ref) > 0.1 and v * d > 0:         # imparo il ripple della fase elettrica
                    rt[b] = rt[b] if not a.rip else max(min(rt[b] + K_RIP * (v_ref - v) * d, RIP_MAX), -RIP_MAX)
                i_cmd = ff + kp * lag + a.kd * (v_ref - v) + i_int + dith + (d * rt[b] if (abs(v_ref) > 0.1 and a.rip) else 0.0)
                cap = imax
            else:
                lag = tgt_deg - x
                i_int = max(min(i_int + KI_H * lag * dt, I_INT_MAX), -I_INT_MAX)
                i_cmd = kp * lag - KD_H * v + i_int
                cap = imax * min(1.0, (tc - t0) / 1.0)                    # soft-start 1 s
            i_cmd = max(min(i_cmd, cap), -cap)
            send_current(ser, a.sign * i_cmd)
            k += 1

            if k % 5 == 1:                                                # telemetria 40 Hz
                im = q_imotor(ser)
                if im is None:
                    q_fail += 1
                    if q_fail >= 3: reason = "VESC muto"; break
                else:
                    q_fail = 0; i_mot = im
            log.write(f"{tc - t0:.4f},{p},{lag:.3f},{v:.2f},{v_ref:.2f},{sp:.3f},{i_cmd:.2f},{i_mot:.2f},{i_coul:.2f},{i_int:.2f}\n")

            # ---------------- sicurezze ----------------
            if a.modo == "vai" and (p - p0) * d <= -WRONG_COUNTS: reason = f"VERSO SBAGLIATO: encoder {p - p0:+d} count"; break
            if abs(rate_safe) > VEL_MAX_DEG_S: reason = f"troppo veloce {rate_safe:+.0f} deg/s"; break
            if not hard_lo <= p <= hard_hi: reason = f"vicino al finecorsa vero: {p}"; break
            if (p < lo and i_cmd < 0) or (p > hi and i_cmd > 0): reason = f"limite software {p} (spinta verso l'esterno)"; break
            if abs(i_mot) > imax + 2.0: reason = f"corrente {i_mot:.1f} A"; break
            if k % 20 == 0 and wheel()[0] != w0: reason = "bici in movimento"; break
            if a.modo == "vai":
                if tc - t0 > 25: reason = "timeout 25 s"; break
                # ARRIVO: riferimento al centro -> entro 1 deg e fermo, oppure 0.8 s dopo: corrente a ZERO (Daniele)
                if abs(v_ref) < 0.1 and sp == tgt_deg: t_arr = t_arr or tc
                if t_arr and ((abs(tgt - p) < 46 and abs(v) < V_FERMO) or tc - t_arr > 0.8):
                    print(f"ARRIVATO pos={p} err={(tgt - p) * DEG:+.2f} deg in {tc - t0:.1f} s: corrente rilasciata"); break
                if (tgt - p) * d < -20: print(f"superato di {(p - tgt) * d * DEG:.2f} deg: mollo"); break
                stuck = abs(v) < V_FERMO and (abs(lag) >= LAG_MAX * 0.95 or abs(i_cmd) >= 0.95 * cap)
                t_stallo = (t_stallo or tc) if stuck else None
                if t_stallo and tc - t_stallo > 1.5: reason = f"STALLO a {i_cmd:.1f} A"; break
            else:
                if tc - t0 > a.durata: print(f"tieni: fine durata {a.durata:.0f} s"); break
                if abs(lag) > SGANCIO_H: reason = f"spostato di {lag:+.1f} deg (> {SGANCIO_H}): mollo"; break
                if abs(i_mot) > 20.0: t_caldo += dt
                if t_caldo > 8.0: reason = "caldo: > 8 s sopra 20 A"; break
            time.sleep(max(0.0, 1.0 / HZ - (time.monotonic() - tc)))
    except KeyboardInterrupt:
        reason = "Ctrl-C/segnale"
    finally:
        stop(); ser.close()
        try:
            if a.modo == 'vai': rip[kd_] = [round(x, 3) for x in rt]; json.dump(rip, open(RIP_FILE, 'w'))
        except Exception: pass
        log.close()
        if reason: print("[STOP]", reason)
        print(f"fine: pos={rd_enc()[0]} i_cmd_finale={i_cmd:.2f} A i_coul_appreso={i_coul:.2f} A cicli={k} "
              f"({k / max(time.monotonic() - t0, 1e-3):.0f} Hz)")


if __name__ == "__main__":
    main()
