#!/usr/bin/env python3
"""
sterzo_campo_001.py — #001: il Raspberry dice al VESC DOVE mettere il campo elettrico (angolo) e con quanti ampere,
ogni 10 ms via UART (Daniele 2026-11-11: "devi mandare via uart al vesc come muoversi... ogni 10ms gli mandi angolo
ricavato da encoder sul piantone sterzo").

Comando VESC fw 5.2 (terminal.c): "rotor_lock_openloop <A> 0 <gradi el.>" = corrente fissa a fase fissa, ritorna subito
e azzera il timeout: rimandato ogni ciclo con l'angolo nuovo, il rotore segue il campo come un passo-passo. Gli hall
NON servono (erano loro a dare i 2 picchi per giro elettrico a bassa velocita').

Angolo elettrico dal piantone: 1 giro elettrico = 16384/35 = 468.1 count encoder (7 coppie polari x riduzione 1:5).
  theta = theta_of + s * pos * 360 / EREV      (theta_of, s imparati con "allinea", salvati in /data)

  allinea : campo a corrente bassa su un angolo, poi lo ruota di +90 gradi el. (~2.6 gradi di manubrio): misura offset,
            verso (s) e scala. Movimento massimo ~5 gradi di manubrio in partenza (il rotore si mette sul campo).
  vai     : riferimento di posizione con micro-rampa in partenza e in arrivo (e vicino ai limiti), campo che lo segue.
Stop: encoder vecchio, manubrio che resta indietro di oltre PERSO_COUNT (passo perso), fuori limiti, FET/motore caldi.
Alla fine (anche Ctrl-C/errore) corrente a zero.
"""
import argparse, json, math, os, signal, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from vesc_return_to_center_duty import send_current, pkt, UART, BAUD
from safety_001 import uart_libera
from sterzo_fluido_001 import rd_enc, q_imotor, TEL, LIM_SW, FINECORSA, MARGINE_FC, DEG

COMM_TERMINAL_CMD = 20
EREV = 16384 / 35.0
CAMPO_FILE = "/data/sterzo_campo_001.json"
PERSO_COUNT = 150          # ~3.3 gradi di manubrio dietro al riferimento = passo perso -> stop
T_FET_MAX, T_MOT_MAX = 70.0, 70.0
I_MAX = 30.0               # = l_current_max del VESC (approvato 09/11)


def campo(ser, amp, theta):
    amp = max(0.5, min(I_MAX, amp))
    ser.write(pkt(bytes([COMM_TERMINAL_CMD]) + f"rotor_lock_openloop {amp:.2f} 0 {theta % 360.0:.2f}".encode()))


def leggi_pos(n=5):
    for _ in range(n):
        p, _t = rd_enc()
        if p is not None: return p
        time.sleep(0.01)
    return None


def theta_di(p, cf):
    return cf["theta_of"] + cf["s"] * p * 360.0 / EREV


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["allinea", "vai"])
    ap.add_argument("--target", type=int, help="raw encoder (vai)")
    ap.add_argument("--vel", type=float, default=20.0, help="deg/s al manubrio (max 30)")
    ap.add_argument("--acc", type=float, default=40.0, help="deg/s^2 (micro-rampa)")
    ap.add_argument("--imax", type=float, default=20.0, help="A del campo (max 30)")
    ap.add_argument("--hz", type=float, default=100.0, help="comandi al secondo (100 = ogni 10 ms)")
    ap.add_argument("--rallenta-fc", type=float, default=5.0, help="deg: rallenta entro questa distanza dai limiti")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    a.vel = min(abs(a.vel), 30.0); a.imax = min(a.imax, I_MAX)
    lo, hi = LIM_SW
    p0 = leggi_pos()
    if p0 is None: sys.exit("encoder sterzo assente o vecchio: non parto")
    if not (FINECORSA[0] + MARGINE_FC <= p0 <= FINECORSA[1] - MARGINE_FC): sys.exit(f"pos {p0} troppo vicino ai finecorsa")
    cf = None
    try: cf = json.load(open(CAMPO_FILE))
    except (OSError, ValueError): pass
    if a.modo == "vai":
        if cf is None: sys.exit("manca l'allineamento (/data/sterzo_campo_001.json): prima 'allinea'")
        if a.target is None: sys.exit("serve --target")
        tgt = max(lo, min(hi, a.target))
        print(f"modo=vai pos={p0} target={tgt} corsa={(tgt - p0) * DEG:+.1f} deg vel={a.vel} deg/s imax={a.imax} A hz={a.hz}")
        print("verso atteso:", "encoder SCENDE (manubrio verso SX)" if tgt < p0 else "encoder SALE (manubrio verso DX)")
    else:
        print(f"modo=allinea pos={p0} imax={min(a.imax, 12.0)} A: campo fermo, poi +90 gradi el. (~2.6 gradi di manubrio)")
    if a.dry_run: print("dry-run: nessun comando"); return
    ok_u, why = uart_libera(UART)
    if not ok_u: sys.exit(f"UART VESC non libera ({why})")
    ser = serial.Serial(UART, BAUD, timeout=0.01)
    stop = [False]
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__(0, True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__(0, True))
    os.makedirs("/data/logging/vesc", exist_ok=True)
    log = open(time.strftime(f"/data/logging/vesc/sterzo_campo_{a.modo}_%Y%m%d_%H%M%S{a.tag}.csv"), "w")
    log.write("t,pos,p_ref,theta,i_set,i_motor,tach,t_fet,t_mot\n")
    dt = 1.0 / a.hz
    t0 = time.monotonic(); nxt = t0; k = 0; motivo = "fine"; im = 0.0

    def ciclo(p_ref, theta, amp):
        nonlocal nxt, k, im
        campo(ser, amp, theta)
        p = leggi_pos(1)
        if k % 10 == 5:
            v = q_imotor(ser)
            if v is not None: im = v
        else:
            ser.reset_input_buffer()
        log.write(f"{time.monotonic() - t0:.4f},{p},{p_ref:.1f},{theta % 360:.2f},{amp:.2f},{im:.2f},{TEL['tach']},{TEL['t_fet']},{TEL['t_mot']}\n")
        k += 1; nxt += dt
        time.sleep(max(0.0, nxt - time.monotonic()))
        return p

    try:
        if a.modo == "allinea":
            ia = min(a.imax, 12.0); th_a = 0.0
            for j in range(int(0.8 * a.hz)):                   # rampa di corrente su angolo fisso
                ciclo(p0, th_a, ia * (j + 1) / (0.8 * a.hz))
            for j in range(int(0.5 * a.hz)): pa = ciclo(p0, th_a, ia)
            for j in range(int(0.5 * a.hz)):                   # +90 gradi el. in 0.5 s
                ciclo(p0, th_a + 90.0 * (j + 1) / (0.5 * a.hz), ia)
            for j in range(int(0.5 * a.hz)): pb = ciclo(p0, th_a + 90.0, ia)
            if pa is None or pb is None: motivo = "encoder perso durante l'allineamento"; return
            dp = pb - pa; atteso = 90.0 / 360.0 * EREV
            print(f"pos a 0 el.: {pa}   pos a +90 el.: {pb}   spostamento {dp:+d} count (atteso +/-{atteso:.0f})")
            if not (0.5 * atteso < abs(dp) < 1.5 * atteso):
                motivo = f"scala non coerente ({dp:+d} count): NON salvo"; return
            s = 1 if dp > 0 else -1
            th_of = 90.0 - s * pb * 360.0 / EREV
            json.dump({"theta_of": th_of % 360.0, "s": s, "erev": EREV, "dp_90": dp, "corrente": ia,
                       "data": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(CAMPO_FILE, "w"), indent=1)
            print(f"salvato: theta_of={th_of % 360:.1f} s={s:+d} ({'encoder scende' if s < 0 else 'encoder sale'} con angolo che cresce)")
            motivo = "allineato"
            return
        # --- vai ---
        th0 = theta_di(p0, cf)
        for j in range(int(0.3 * a.hz)):                       # corrente su a campo fermo dove sta il rotore
            p = ciclo(p0, th0, a.imax * (j + 1) / (0.3 * a.hz))
        d = 1 if tgt > p0 else -1
        x, v = float(p0), 0.0
        vmax_c = a.vel / DEG; acc_c = a.acc / DEG; fc_c = a.rallenta_fc / DEG
        while not stop[0]:
            rem = (tgt - x) * d
            rem_fc = ((hi if d > 0 else lo) - x) * d
            v_fren = math.sqrt(max(0.0, 2 * acc_c * rem))      # micro-rampa d'arrivo
            v_lim = min(vmax_c, v_fren, vmax_c * max(0.1, rem_fc / fc_c))
            v = min(v + acc_c * dt, v_lim) if v < v_lim else max(v - acc_c * dt, v_lim)
            x += d * max(v, 0.0) * dt
            if (tgt - x) * d <= 0.5: x = float(tgt)
            p = ciclo(x, theta_di(x, cf), a.imax)
            if p is None: motivo = "encoder perso"; break
            if not (lo - 20 <= p <= hi + 20): motivo = f"fuori limiti ({p})"; break
            if abs(p - x) > PERSO_COUNT: motivo = f"passo perso: manubrio {p} rif {x:.0f}"; break
            if TEL["t_fet"] > T_FET_MAX or TEL["t_mot"] > T_MOT_MAX: motivo = "temperatura"; break
            if x == tgt and abs(p - tgt) < 10:
                for j in range(int(0.3 * a.hz)):               # tiene fermo e scende di corrente
                    ciclo(x, theta_di(x, cf), a.imax * (1 - (j + 1) / (0.3 * a.hz)))
                motivo = f"ARRIVATO pos={leggi_pos()} in {time.monotonic() - t0:.1f} s"; break
            if time.monotonic() - t0 > 30: motivo = "tempo scaduto"; break
        if stop[0]: motivo = "fermato a mano"
    finally:
        for _ in range(3):
            send_current(ser, 0.0); time.sleep(0.01)
        log.close(); ser.close()
        print(f"{motivo}  (pos finale {leggi_pos()}, cicli {k}, {k / max(1e-3, time.monotonic() - t0):.0f} Hz)")


if __name__ == "__main__":
    main()
