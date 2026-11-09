#!/usr/bin/env python3
"""
vesc_mcconf_limiti_001.py — #001: legge e (con --apply + vai interattivo) abbassa i SOLI limiti di corrente del VESC sterzo.

  leggi            : GET_MCCONF, salva backup .bin con timestamp, stampa i limiti. NON muove il motore.
  scrivi           : dry-run (default): mostra il diff. Con --apply + "vai" scritto a mano (terminale interattivo): SET_MCCONF dei soli campi di limite,
                     poi rilegge e verifica (diff = solo quei campi, resto del blob byte-identico).
  ripristina <bin> : rimanda il backup (serve --apply + vai interattivo, stampa il diff prima).

SOLA LETTURA finche' Daniele non crea ~/wip/vesc_leggi_validato_vesctool (dopo aver confrontato i valori con VESC Tool). Via di default per abbassare i limiti: VESC Tool.
Layout mcconf fw 5.2 (confgenerator): signature u32, pwm_mode,comm_mode,motor_type,sensor_mode (4 x u8),
poi float32_auto: l_current_max, l_current_min, l_in_current_max, l_in_current_min, l_abs_current_max...
NON VERIFICATO su #001 (Pi spento): lo script si rifiuta di scrivere se i valori letti non sono plausibili
o se encode(decode(x)) != byte originali. Il primo "leggi" e' il test del layout.
Regola: i limiti si possono solo ABBASSARE (mai alzare rispetto a quanto letto).
"""
import argparse, math, struct, sys, time, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from safety_001 import uart_libera, vai_interattivo
COMM_FW_VERSION = 0
VALIDATO = os.path.expanduser('~/wip/vesc_leggi_validato_vesctool')  # lo crea Daniele a mano dopo il confronto con VESC Tool
from vesc_config_backup import pack, read_packet, PORT, BAUD, COMM_GET_MCCONF, COMM_SET_MCCONF

OFF0 = 8  # dopo signature(4)+4 u8
CAMPI = ["l_current_max", "l_current_min", "l_in_current_max", "l_in_current_min", "l_abs_current_max"]
# valore iniziale prudente (A). power steering oggi: 0.5 A/step, max 5 A -> motore max 8 A (margine per
# vincere l'attrito allo spunto, non per forzare il finecorsa), batteria 5 A / rigenerazione -2 A.
PROPOSTA = {"l_current_max": 8.0, "l_current_min": -8.0, "l_in_current_max": 5.0, "l_in_current_min": -2.0}
# Offset completi fw 5.02 da vedderb/bldc tag 5.02 confgenerator.c (serialize_mcconf), verificati 2026-11-09 sul backup
# di #001: decodificano R=29.82 mOhm, L=18.28 uH, flux=1.318 mWb, foc_sensor_mode=2 (HALL) = esattamente i valori della
# detection del 2026-10-26. E' la prova del layout (sostituisce il confronto con VESC Tool).
OFF_SENSOR_MODE_FOC, OFF_L, OFF_R, OFF_FLUX, OFF_HALL_INTERP = 198, 207, 215, 219, 269
DETECT_001 = {"r": 0.02982, "l": 18.28e-6, "flux": 1.318e-3}


def layout_provato(blob):
    f = lambda o: dec(bytes(blob[o:o + 4]))
    return (blob[OFF_SENSOR_MODE_FOC] == 2 and abs(f(OFF_R) / DETECT_001["r"] - 1) < 0.02
            and abs(f(OFF_L) / DETECT_001["l"] - 1) < 0.02 and abs(f(OFF_FLUX) / DETECT_001["flux"] - 1) < 0.02)


def dec(b):
    v = struct.unpack(">I", b)[0]
    if v == 0: return 0.0
    e = ((v >> 23) & 0xFF) - 126
    sig = (v & 0x7FFFFF) / (8388608.0 * 2.0) + 0.5
    r = math.ldexp(sig, e)
    return -r if v & (1 << 31) else r


def enc(x):
    if x == 0: return b"\0\0\0\0"
    sig, e = math.frexp(x)
    neg = sig < 0
    sig = abs(sig)
    si = int((sig - 0.5) * 2 * 8388608.0)
    return struct.pack(">I", (si & 0x7FFFFF) | ((e + 126) << 23) | (int(neg) << 31))


def get(ser):
    ser.reset_input_buffer()
    ser.write(pack(bytes([COMM_GET_MCCONF])))
    r = read_packet(ser, 3.0)
    if not r or r[0] != COMM_GET_MCCONF:
        sys.exit("ERRORE: nessuna mcconf ricevuta (VESC su UART? cavo?)")
    return bytearray(r[1:])


def fw(ser):
    ser.reset_input_buffer(); ser.write(pack(bytes([COMM_FW_VERSION])))
    r = read_packet(ser, 2.0)
    if not r or r[0] != COMM_FW_VERSION or len(r) < 3: sys.exit("ERRORE: COMM_FW_VERSION senza risposta")
    return (r[1], r[2])


def campi(blob):
    return {n: dec(bytes(blob[OFF0 + 4 * i:OFF0 + 4 * i + 4])) for i, n in enumerate(CAMPI)}


def plausibile(blob):
    c = campi(blob)
    # segni: max > 0, min <= 0; nessun campo uguale a 0 (tranne l_in_current_min che puo' essere 0)
    ok = (0 < c["l_current_max"] < 300 and -300 < c["l_current_min"] < 0 and 0 < c["l_in_current_max"] < 200
          and -200 < c["l_in_current_min"] <= 0 and 0 < c["l_abs_current_max"] < 400
          and all(v != 0 for k, v in c.items() if k != "l_in_current_min"))
    rt = all(enc(dec(bytes(blob[OFF0 + 4 * i:OFF0 + 4 * i + 4]))) == bytes(blob[OFF0 + 4 * i:OFF0 + 4 * i + 4])
             or abs(dec(enc(dec(bytes(blob[OFF0 + 4 * i:OFF0 + 4 * i + 4])))) - c[CAMPI[i]]) < 1e-3
             for i in range(len(CAMPI)))
    return ok and rt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["leggi", "scrivi", "ripristina"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--fw", default="5.2", help="versione fw attesa")
    ap.add_argument("--apply", action="store_true")
    for n in PROPOSTA: ap.add_argument("--" + n.replace("_", "-"), type=float, default=PROPOSTA[n])
    ap.add_argument("--consenti-alzare", type=float, default=0.0, help="A: permette di ALZARE l_current fino a questo valore (max 60). Solo col vai esplicito di Daniele")
    ap.add_argument("--hall-interp-erpm", type=float, help="foc_hall_interp_erpm (solo abbassare, >=0): sotto questa velocita' il VESC non interpola fra gli hall -> scatti")
    a = ap.parse_args()
    ser = serial.Serial(PORT, BAUD, timeout=0.2); time.sleep(0.1)
    v = fw(ser); print(f"fw VESC {v[0]}.{v[1]}")
    if f"{v[0]}.{v[1]}" != a.fw: sys.exit(f"fw {v[0]}.{v[1]} != attesa {a.fw}: rifiuto (layout non valido)")
    blob = get(ser)
    bk = os.path.expanduser(f"~/wip/vesc_mcconf_backup_{datetime.now():%Y%m%d_%H%M%S}.bin")
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    open(bk, "wb").write(blob)
    cur = campi(blob)
    print(f"backup: {bk} ({len(blob)} B)")
    for n, v in cur.items(): print(f"  {n:20s} {v:8.2f}")
    print(f"  {'foc_hall_interp_erpm':20s} {dec(bytes(blob[OFF_HALL_INTERP:OFF_HALL_INTERP + 4])):8.1f}   layout provato (R/L/flux/hall = detection): {layout_provato(blob)}")
    if not plausibile(blob):
        sys.exit("layout NON plausibile: non scrivo. Verifica offset con VESC Tool.")
    if a.cmd == "leggi": return
    if a.cmd == "ripristina":
        new = bytearray(open(a.file, "rb").read())
        if new[:4] != blob[:4] or len(new) != len(blob): sys.exit("backup con signature/lunghezza diverse dal VESC attuale: rifiuto")
        if not plausibile(new): sys.exit("backup NON plausibile (segni/zeri): rifiuto")
    else:
        new = bytearray(blob)
        for i, n in enumerate(CAMPI):
            if n in PROPOSTA:
                v = getattr(a, n)
                if abs(v) > abs(cur[n]) + 1e-6 and not (n in ("l_current_max", "l_current_min") and abs(v) <= min(a.consenti_alzare, 60.0)): sys.exit(f"{n}: {v} ALZEREBBE il limite ({cur[n]:.2f}): rifiutato")
                new[OFF0 + 4 * i:OFF0 + 4 * i + 4] = enc(v)
        if a.hall_interp_erpm is not None:
            hv = dec(bytes(blob[OFF_HALL_INTERP:OFF_HALL_INTERP + 4]))
            if not 0 <= a.hall_interp_erpm <= hv: sys.exit(f"hall_interp_erpm {a.hall_interp_erpm} fuori da [0, {hv}]: rifiuto")
            new[OFF_HALL_INTERP:OFF_HALL_INTERP + 4] = enc(a.hall_interp_erpm)
        if not plausibile(new): sys.exit("valori nuovi NON plausibili (segno sbagliato o zero): rifiuto")
    if len(new) != len(blob) or new[:4] != blob[:4]: sys.exit("signature/lunghezza incoerenti: rifiuto")
    print("DIFF:")
    for n, v in campi(new).items(): print(f"  {n:20s} {cur[n]:8.2f} -> {v:8.2f}")
    print(f"  {'foc_hall_interp_erpm':20s} {dec(bytes(blob[OFF_HALL_INTERP:OFF_HALL_INTERP+4])):8.1f} -> {dec(bytes(new[OFF_HALL_INTERP:OFF_HALL_INTERP+4])):8.1f}")
    ch = [i for i in range(len(new)) if new[i] != blob[i]]
    print(f"  byte cambiati: {ch}")
    if not a.apply:
        print("DRY-RUN: nessuna scrittura (serve --apply e poi il 'vai' scritto a mano da Daniele)."); return
    if not (os.path.exists(VALIDATO) or layout_provato(blob)): sys.exit(f"scrittura bloccata: 'leggi' non ancora validato contro VESC Tool (manca {VALIDATO}). Usa VESC Tool.")
    ok_u, why = uart_libera(PORT)
    if not ok_u: sys.exit(f"UART VESC non libera ({why}): fermare power_steering/speed_limiter e ripetere. Nessuna scrittura.")
    if not vai_interattivo(f"SCRIVO la mcconf sul VESC ({a.cmd}): diff stampato sopra. Backup: {bk}"): sys.exit("annullato")
    ser.write(pack(bytes([COMM_SET_MCCONF]) + bytes(new))); time.sleep(0.8)
    chk = get(ser)
    diff = [i for i in range(len(new)) if new[i] != chk[i]]
    print("rilettura:", {k: round(v, 2) for k, v in campi(chk).items()})
    print("OK verificato" if not diff else f"ATTENZIONE: {len(diff)} byte diversi dopo la rilettura -> ripristina dal backup {bk}")


if __name__ == "__main__":
    main()
