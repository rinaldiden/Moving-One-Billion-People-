#!/usr/bin/env python3
"""
sterzo_rpm_001.py — #001: sterzo comandato IN VELOCITA' DAL VESC (Daniele 2026-11-09: "tu invii il setpoint di velocita'
al VESC ogni tot ms, il VESC gestisce A e corrente come sa lui").

Il Pi manda COMM_SET_RPM ogni --ms (default 10 ms). Il PID di velocita' del VESC decide la corrente, fino a l_current_max
(45 A, in flash). VESC: s_pid_min_erpm 10 (era 900: sotto frenava), s_pid_ramp_erpms_s 400 (partenza dolce).
Conversione: 1 giro elettrico = 16384/35 count = 10.29 deg di piantone -> 1 deg/s = 5.83 ERPM.
Verso: corrente/rpm POSITIVI fanno SCENDERE l'encoder (verso SX), come misurato il 2026-11-09.

Il Pi fa solo: profilo (micro-rampa in partenza --rampa s, velocita' piena, micro-rampa di decel negli ultimi
--rallenta gradi prima del target E negli ultimi --rallenta-fc gradi prima dei limiti encoder sx/dx), arrivo (rpm 0 poi corrente 0 = manubrio libero),
sicurezze: verso sbagliato >=10 count, oltre 30 deg/s (45 con --prova-veloce), limiti 4500/8700 e finecorsa veri -60,
|i_motor| > imax+3, encoder vecchio, VESC muto, bici in movimento, timeout 20 s, SIGTERM/SIGHUP/Ctrl-C.
Log: /data/logging/vesc/sterzo_rpm_<ora>.csv con corrente motore e batteria dalla UART.
Uso: python3 sterzo_rpm_001.py --target RAW --vel 20 [--ms 10] [--dry-run]
     python3 sterzo_rpm_001.py --verso sx|dx --vel 20      (va fino al limite software, rallentando prima)
"""
import argparse, json, os, signal, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from vesc_return_to_center_duty import send_duty, send_current, pkt, UART, BAUD
from safety_001 import uart_libera
import sterzo_fluido_001 as sf      # rd_enc, wheel, q_imotor, TEL, limiti

COMM_SET_RPM = 8
ERPM_PER_DEG_S = 35 * 60 / 360.0    # 5.83
SIGN = +1                           # rpm positivi -> encoder scende


def send_rpm(ser, erpm):
    ser.write(pkt(struct.pack(">Bi", COMM_SET_RPM, int(round(erpm)))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, help="raw encoder (default: centro)")
    ap.add_argument("--vel", type=float, default=20.0, help="deg/s al manubrio")
    ap.add_argument("--ms", type=float, default=10.0, help="ogni quanti ms mando il setpoint (2-50)")
    ap.add_argument("--imax", type=float, default=45.0)
    ap.add_argument("--rallenta", type=float, default=4.0, help="gradi prima del target in cui la velocita' scende")
    ap.add_argument("--rallenta-fc", type=float, default=5.0, help="gradi prima dei limiti encoder sx/dx in cui la velocita' scende")
    ap.add_argument("--rampa", type=float, default=0.3, help="secondi di micro-rampa in partenza (0 -> vel)")
    ap.add_argument("--verso", choices=["sx", "dx"], help="invece di --target: fino al limite software da quella parte")
    ap.add_argument("--prova-veloce", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    vmax, vstop = (35, 45.0) if a.prova_veloce else (20, 30.0)
    if not 0 < a.vel <= vmax: sys.exit(f"--vel in (0,{vmax}]")
    if not 2 <= a.ms <= 50: sys.exit("--ms in [2,50]")
    c, lo, hi, hard_lo, hard_hi = sf.limiti()
    # encoder SCENDE verso SX (misurato 2026-11-09)
    tgt = (lo if a.verso == "sx" else hi) if a.verso else (c if a.target is None else a.target)
    if not lo <= tgt <= hi: sys.exit(f"target fuori da [{lo},{hi}]")
    ok, why = uart_libera(UART)
    if not ok: sys.exit(f"UART non libera: {why}")
    w0, fresh = sf.wheel()
    if not fresh: sys.exit("encoder ruota vecchio")
    p0, _ = sf.rd_enc()
    if p0 is None: sys.exit("encoder sterzo vecchio")
    if not hard_lo <= p0 <= hard_hi: sys.exit("troppo vicino al finecorsa: muovere a mano")
    d = 1 if tgt > p0 else -1
    print(f"pos={p0} ({(p0 - c) * sf.DEG:+.1f} deg) target={tgt} vel={a.vel} deg/s = {a.vel * ERPM_PER_DEG_S:.0f} ERPM, setpoint ogni {a.ms} ms")
    if abs(tgt - p0) < 14 or a.dry_run: print("niente da fare / dry-run"); return
    os.makedirs("/data/logging/vesc", exist_ok=True)
    log = open(time.strftime(f"/data/logging/vesc/sterzo_rpm_%Y%m%d_%H%M%S{a.tag}.csv"), "w")
    log.write("t,pos,v_enc,v_set,erpm_set,i_motor,i_batt,v_batt,t_fet,t_mot\n")
    ser = serial.Serial(UART, BAUD, timeout=0.02)
    def stop():
        for f, v in ((send_rpm, 0), (send_current, 0), (send_duty, 0), (send_current, 0)):
            try: f(ser, v)
            except Exception: pass
    def _kill(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _kill); signal.signal(signal.SIGHUP, _kill)
    hist = []; reason = None; t0 = time.monotonic(); k = 0; i_mot = 0.0; qf = 0
    try:
        while True:
            tc = time.monotonic()
            p, _ = sf.rd_enc()
            if p is None: reason = "encoder vecchio"; break
            hist.append((tc, p)); hist = [h for h in hist if tc - h[0] <= 0.1]
            v_enc = (hist[-1][1] - hist[0][1]) * sf.DEG / max(hist[-1][0] - hist[0][0], 0.02)
            rem = (tgt - p) * d * sf.DEG
            if rem < 0.3: print(f"ARRIVATO pos={p} err={(tgt - p) * sf.DEG:+.2f} deg in {tc - t0:.1f} s: corrente rilasciata"); break
            rem_fc = ((hi if d > 0 else lo) - p) * d * sf.DEG           # gradi al limite encoder nel verso di marcia
            v_set = a.vel * min(1.0, (tc - t0) / a.rampa) if a.rampa > 0 else a.vel
            v_set = min(v_set, a.vel * rem / a.rallenta, a.vel * rem_fc / a.rallenta_fc)
            v_set = max(2.0, v_set)
            erpm = -SIGN * d * v_set * ERPM_PER_DEG_S
            send_rpm(ser, erpm)
            k += 1
            if k % 3 == 1:
                im = sf.q_imotor(ser)
                if im is None:
                    qf += 1
                    if qf >= 3: reason = "VESC muto"; break
                else: qf = 0; i_mot = im
            log.write(f"{tc - t0:.4f},{p},{v_enc:.2f},{d * v_set:.2f},{erpm:.0f},{i_mot:.2f},{sf.TEL['i_batt']:.2f},{sf.TEL['v_batt']:.1f},{sf.TEL['t_fet']:.1f},{sf.TEL['t_mot']:.1f}\n")
            if (p - p0) * d <= -10: reason = f"VERSO SBAGLIATO {p - p0:+d} count"; break
            if abs(v_enc) > vstop: reason = f"troppo veloce {v_enc:+.0f} deg/s"; break
            if (p < lo and d < 0) or (p > hi and d > 0) or not hard_lo <= p <= hard_hi: reason = f"limite {p}"; break
            if abs(i_mot) > a.imax + 3: reason = f"corrente {i_mot:.1f} A"; break
            if k % 20 == 0 and sf.wheel()[0] != w0: reason = "bici in movimento"; break
            if tc - t0 > 20: reason = "timeout 20 s"; break
            time.sleep(max(0.0, a.ms / 1000 - (time.monotonic() - tc)))
    except KeyboardInterrupt: reason = "Ctrl-C"
    finally:
        stop(); ser.close(); log.close()
        if reason: print("[STOP]", reason)
        p, _ = sf.rd_enc(); print(f"fine: pos={p} cicli={k} ({k / max(time.monotonic() - t0, 1e-3):.0f} Hz)")


if __name__ == "__main__":
    main()
