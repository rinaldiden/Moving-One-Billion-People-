#!/usr/bin/env python3
"""
vesc_mcconf_limiti_001.py — #001: legge e (con --apply --vai) abbassa i SOLI limiti di corrente del VESC sterzo.

  leggi            : GET_MCCONF, salva backup .bin con timestamp, stampa i limiti. NON muove il motore.
  scrivi           : dry-run (default): mostra il diff. Con --apply --vai: SET_MCCONF dei soli campi di limite,
                     poi rilegge e verifica (diff = solo quei campi, resto del blob byte-identico).
  ripristina <bin> : rimanda il backup (serve --apply --vai).

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
COMM_FW_VERSION = 0
VALIDATO = os.path.expanduser('~/wip/vesc_leggi_validato_vesctool')  # lo crea Daniele a mano dopo il confronto con VESC Tool
from vesc_config_backup import pack, read_packet, PORT, BAUD, COMM_GET_MCCONF, COMM_SET_MCCONF

OFF0 = 8  # dopo signature(4)+4 u8
CAMPI = ["l_current_max", "l_current_min", "l_in_current_max", "l_in_current_min", "l_abs_current_max"]
# valore iniziale prudente (A). power steering oggi: 0.5 A/step, max 5 A -> motore max 8 A (margine per
# vincere l'attrito allo spunto, non per forzare il finecorsa), batteria 5 A / rigenerazione -2 A.
PROPOSTA = {"l_current_max": 8.0, "l_current_min": -8.0, "l_in_current_max": 5.0, "l_in_current_min": -2.0}


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
    ok = (0 < c["l_current_max"] < 300 and -300 < c["l_current_min"] < 0 and 0 < c["l_in_current_max"] < 200
          and -200 < c["l_in_current_min"] <= 0 and 0 < c["l_abs_current_max"] < 400)
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
    ap.add_argument("--vai", action="store_true", help="solo dopo il 'vai' esplicito di Daniele")
    for n in PROPOSTA: ap.add_argument("--" + n.replace("_", "-"), type=float, default=PROPOSTA[n])
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
    if not plausibile(blob):
        sys.exit("layout NON plausibile: non scrivo. Verifica offset con VESC Tool.")
    if a.cmd == "leggi": return
    if a.cmd == "ripristina":
        new = bytearray(open(a.file, "rb").read())
        if new[:4] != blob[:4] or len(new) != len(blob): sys.exit("backup con signature/lunghezza diverse dal VESC attuale: rifiuto")
    else:
        new = bytearray(blob)
        for i, n in enumerate(CAMPI):
            if n in PROPOSTA:
                v = getattr(a, n)
                if abs(v) > abs(cur[n]) + 1e-6: sys.exit(f"{n}: {v} ALZEREBBE il limite ({cur[n]:.2f}): rifiutato")
                new[OFF0 + 4 * i:OFF0 + 4 * i + 4] = enc(v)
    if len(new) != len(blob) or new[:4] != blob[:4]: sys.exit("signature/lunghezza incoerenti: rifiuto")
    print("DIFF:")
    for n, v in campi(new).items(): print(f"  {n:20s} {cur[n]:8.2f} -> {v:8.2f}")
    if not (a.apply and a.vai):
        print("DRY-RUN: nessuna scrittura (serve --apply --vai dopo il via di Daniele)."); return
    if not os.path.exists(VALIDATO): sys.exit(f"scrittura bloccata: 'leggi' non ancora validato contro VESC Tool (manca {VALIDATO}). Usa VESC Tool.")
    ser.write(pack(bytes([COMM_SET_MCCONF]) + bytes(new))); time.sleep(0.8)
    chk = get(ser)
    diff = [i for i in range(len(new)) if new[i] != chk[i]]
    print("rilettura:", {k: round(v, 2) for k, v in campi(chk).items()})
    print("OK verificato" if not diff else f"ATTENZIONE: {len(diff)} byte diversi dopo la rilettura -> ripristina dal backup {bk}")


if __name__ == "__main__":
    main()
