#!/usr/bin/env python3
"""
calibrate_steering_limits.py — centro e finecorsa dello sterzo, PER UNITÀ, a mano.

NON comanda nessun motore: legge solo l'encoder di sterzo mentre la persona gira il manubrio.
Sequenza guidata (a voce sul terminale):
  1. manubrio DRITTO (ruota allineata al telaio), fermo        → centro
  2. tutto a SINISTRA fino al finecorsa, tieni 2 s             → limite sx
  3. tutto a DESTRA fino al finecorsa, tieni 2 s               → limite dx
  4. di nuovo DRITTO                                            → verifica ripetibilità del centro
Scrive /data/steering_limits_<ASMILE_NAME>.json (persistente fuori dall'overlay; senza /data:
config/). La calibrazione vale SOLO per quell'unità (asmile2 ha la sua in config/steering_limits.json).

Encoder:
  #001  AMT22 14 bit via ponte Arduino-USB → /tmp/encoder_steer (0..16383)
  asmile2 Briter 12 bit → /tmp/encoder_position (0..4095)   →  --file / --bits
Uso:  python3 calibrate_steering_limits.py            (default #001)
"""
import argparse
import json
import os
import statistics
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(HERE, "..", "..", "config")
DATA_DIR = "/data"                    # su #001 la root è overlay (RAM): la calib persistente va su /data


def unit_name():
    try:
        for line in open(os.path.expanduser("~/asmile_id.conf")):
            if line.startswith("ASMILE_NAME="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "sconosciuta"


def read(path):
    try:
        with open(path) as f:
            return int(f.readline().strip())
    except (OSError, ValueError):
        return None


def unwrap(vals, cpr):
    """Srotola il passaggio 0↔cpr-1 rispetto al primo campione."""
    out, ref = [], vals[0]
    for v in vals:
        d = (v - ref + cpr // 2) % cpr - cpr // 2
        out.append(ref + d)
    return out


def phase(path, label, secs, cpr):
    print(f"\n>>> {label}  ({secs:.0f} s)", flush=True)
    for k in (3, 2, 1):
        print(f"    via tra {k}…", flush=True); time.sleep(1)
    print("    REGISTRO", flush=True)
    vals, t0 = [], time.monotonic()
    while time.monotonic() - t0 < secs:
        v = read(path)
        if v is not None:
            vals.append(v)
        time.sleep(0.02)
    if not vals:
        raise SystemExit(f"nessuna lettura da {path}: il ponte encoder gira?")
    return unwrap(vals, cpr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="/tmp/encoder_steer")
    ap.add_argument("--bits", type=int, default=14)
    ap.add_argument("--hold", type=float, default=6.0, help="secondi per fase")
    a = ap.parse_args()
    cpr = 1 << a.bits
    deg = 360.0 / cpr
    name = unit_name()
    print(f"Calibrazione sterzo unità '{name}' — encoder {a.file} ({a.bits} bit, {deg:.4f}°/step)")
    print("Nessun motore viene comandato: gira il manubrio A MANO.")

    c1 = phase(a.file, "Manubrio DRITTO, fermo", a.hold, cpr)
    sx = phase(a.file, "Tutto a SINISTRA fino al finecorsa, tieni", a.hold, cpr)
    dx = phase(a.file, "Tutto a DESTRA fino al finecorsa, tieni", a.hold, cpr)
    c2 = phase(a.file, "Di nuovo DRITTO, fermo", a.hold, cpr)

    # tutto rispetto allo stesso riferimento (primo campione del centro)
    ref = c1[0]
    def rel(vs):
        return [ref + ((v - ref + cpr // 2) % cpr - cpr // 2) for v in vs]
    c1, sx, dx, c2 = rel(c1), rel(sx), rel(dx), rel(c2)
    center = statistics.median(c1[len(c1) // 3:])
    center2 = statistics.median(c2[len(c2) // 3:])
    # la sinistra può corrispondere a count crescenti o calanti: lo dice il dato
    sx_val = min(sx) if statistics.median(sx) < center else max(sx)
    dx_val = max(dx) if statistics.median(dx) > center else min(dx)
    out = {
        "_comment": f"Sterzo {name}: centro e finecorsa misurati a mano (calibrate_steering_limits.py). "
                    "Vale SOLO per questa unità.",
        "unit": name, "date": datetime.now().isoformat(timespec="seconds"),
        "encoder_file": a.file, "encoder_bits": a.bits, "encoder_steps_per_rev": cpr,
        "deg_per_step": round(deg, 5),
        "encoder_center_raw": round(center) % cpr,
        "encoder_sx_max_raw": round(sx_val) % cpr,
        "encoder_dx_max_raw": round(dx_val) % cpr,
        "delta_sx_steps": round(sx_val - center), "delta_dx_steps": round(dx_val - center),
        "delta_sx_deg": round((sx_val - center) * deg, 2), "delta_dx_deg": round((dx_val - center) * deg, 2),
        "encoder_pos_increases_to": "DX (destra)" if dx_val > center else "SX (sinistra)",
        "center_repeatability_steps": round(center2 - center, 1),
        "center_repeatability_deg": round((center2 - center) * deg, 2),
    }
    base = DATA_DIR if os.path.isdir(DATA_DIR) and os.access(DATA_DIR, os.W_OK) else CONFIG_DIR
    path = os.path.join(base, f"steering_limits_{name}.json")
    json.dump(out, open(path, "w"), indent=2)
    print("\nRISULTATO:")
    for k in ("encoder_center_raw", "encoder_sx_max_raw", "encoder_dx_max_raw",
              "delta_sx_deg", "delta_dx_deg", "encoder_pos_increases_to", "center_repeatability_deg"):
        print(f"  {k}: {out[k]}")
    if abs(out["center_repeatability_deg"]) > 1.0:
        print("  ⚠ il centro non si ripete entro 1°: rifai con il manubrio ben dritto")
    if abs(abs(out["delta_sx_deg"]) - abs(out["delta_dx_deg"])) > 5:
        print("  ⚠ sx e dx molto asimmetrici: controlla che il 'dritto' fosse davvero dritto")
    print(f"\nscritto {path}")


if __name__ == "__main__":
    main()
