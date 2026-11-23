"""Prova a SECCO sul Mac: rigioca i CSV veri di #001 e fa prove sintetiche. Nessun Pi, nessun GPIO.
Uso (dalla cartella projects/asmile):  python3 pi/autonomous/speed_limiter_v3/prova_secco.py --out DIR [--tutte]"""
import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from speed_limiter_v3.controllo import Controllo, carica_soglie       # noqa: E402
from speed_limiter_v3.sim import (Guasti, ServoFinto, SimBici, campioni_da_csv, carica_csv,   # noqa: E402
                                  esegui_sintetico)

SENS = "asmile-loggers/asmile-001/_sensors/sensors/sensors_%s.csv"
FONTI = ["NESSUNA", "ENC", "GPS_IMU", "BLE_IMU", "IMU_SOLO", "FERMO_IMU"]


def replay(path, cfg, guasti=None, i0=0, i1=None):
    d = carica_csv(path)
    if d is None:
        return None
    s = ServoFinto()
    ev = []
    ctl = Controllo(cfg, s, log_eventi=lambda *a: ev.append(a))
    cols = ["t", "v", "fonte", "v_enc", "a_enc", "v_fus", "dec_imu", "d03", "angolo", "a_des", "sigma", "gps"]
    R = {k: [] for k in cols}
    gps_ult = 0.0
    n = len(d) if i1 is None else i1
    for c in campioni_da_csv(d, guasti, i0, n):
        s.t = c.t
        if c.gps is not None:
            gps_ult = c.gps[0] if c.gps[1] else float("nan")
        r = ctl.passo(c)
        R["t"].append(r["t"]); R["v"].append(np.nan if r["v"] is None else r["v"])
        R["fonte"].append(FONTI.index(r["fonte"])); R["v_enc"].append(r["v_enc"]); R["a_enc"].append(r["a_enc"])
        R["v_fus"].append(r["v_fus"]); R["dec_imu"].append(r["dec_imu"]); R["d03"].append(r["d03"])
        R["angolo"].append(r["angolo"]); R["a_des"].append(r["a_des"]); R["sigma"].append(r["sigma_v"])
        R["gps"].append(gps_ult)
    ctl.chiudi()
    out = {k: np.array(v) for k, v in R.items()}
    out["ctl"], out["ev"], out["servo"] = ctl, ev, s
    return out


def episodi(mask, t, gap=1.0, minlen=0.0):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    out = []
    a = idx[0]
    p = idx[0]
    for i in idx[1:]:
        if t[i] - t[p] > gap:
            out.append((a, p))
            a = i
        p = i
    out.append((a, p))
    return [(a, b) for a, b in out if t[b] - t[a] >= minlen]


def liscio(angolo, t, ia, ib):
    """Misure di 'dolcezza' del comando in un episodio: slew max (gradi/s), inversioni (>=0.7 gradi di ampiezza)."""
    seg = angolo[ia:ib + 1]
    if len(seg) < 3:
        return 0.0, 0
    dt = np.diff(t[ia:ib + 1])
    dt[dt <= 0] = 0.02
    sl = np.abs(np.diff(seg)) / dt
    inv = 0
    ext = seg[0]
    dirr = 0
    for x in seg[1:]:
        if dirr >= 0 and x < ext - 0.7:
            if dirr == 1:
                inv += 1
            dirr, ext = -1, x
        elif dirr <= 0 and x > ext + 0.7:
            if dirr == -1:
                inv += 1
            dirr, ext = 1, x
        elif (dirr >= 0 and x > ext) or (dirr <= 0 and x < ext):
            ext = x
    return float(sl.max()), inv


def riassunto_sessione(nome, R):
    t, v = R["t"], R["v"]
    moto = np.nan_to_num(R["v_enc"]) > 1.0
    min_moto = moto.sum() * 0.02 / 60
    ctl = R["ctl"]
    sc = ctl.anti.scatti
    ep = ctl.anti.episodi
    sc_ang = [x for x in sc if x[1] > 0.5]
    frenate = episodi(R["angolo"] > 1.0, t, gap=1.0)
    ls = [liscio(R["angolo"], t, a, b) for a, b in frenate]
    src = {FONTI[i]: round(float((R["fonte"] == i).mean() * 100), 1) for i in range(6) if (R["fonte"] == i).any()}
    kmh = R["v_enc"] * 3.6
    return dict(sess=nome, min_tot=round(len(t) * 0.02 / 60, 1), min_moto=round(float(min_moto), 1),
                v_enc_max_kmh=round(float(np.nanmax(kmh)), 1), s_sopra12=round(float((kmh > 12).sum() * 0.02), 1),
                s_sopra15=round(float((kmh > 15).sum() * 0.02), 1), fonti_pct=src, n_cambi_fonte=len(R["ev"]),
                angolo_max=round(float(R["angolo"].max()), 1), episodi_freno=len(frenate),
                slew_max_deg_s=round(max([x[0] for x in ls], default=0.0), 1),
                inversioni_per_freno_max=max([x[1] for x in ls], default=0), inversioni_per_freno_med=round(float(np.mean([x[1] for x in ls])), 2) if ls else 0,
                scatti_anti=len(sc), episodi_anti=len(ep), episodi_anti_con_freno=len({round(x[0]) for x in sc_ang}),
                impulsi_servo=ctl.servo.n_impulsi, ina_arretra=ctl.ina.n_arretra, tetto_precoce=ctl.anti.precoci,
                glitch_enc=ctl.enc.glitch, ep_anti_per_min_moto=round(len(ep) / max(min_moto, 1e-9), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tutte", action="store_true", help="tutte le sessioni (lento), altrimenti solo 13/11 145727")
    ap.add_argument("--soglie", default=None)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = carica_soglie(a.soglie)
    files = sorted(glob.glob(SENS % "*"))
    files = [f for f in files if f.endswith(".csv")]
    if not a.tutte:
        files = [SENS % "20261113_145727"]
    res = []
    for f in files:
        nome = os.path.basename(f)[8:-4]
        R = replay(f, cfg)
        if R is None:
            print(nome, "senza encoder: saltata")
            continue
        rs = riassunto_sessione(nome, R)
        res.append(rs)
        print(json.dumps(rs, ensure_ascii=False), flush=True)
        if nome == "20261113_145727":
            np.savez_compressed(os.path.join(a.out, "principale.npz"), **{k: v for k, v in R.items() if isinstance(v, np.ndarray)})
            json.dump([list(map(lambda z: None if z is None or (isinstance(z, float) and np.isnan(z)) else float(z), x)) for x in R["ctl"].anti.scatti],
                      open(os.path.join(a.out, "scatti_anti.json"), "w"))
            json.dump([[float(x[0]), x[1], x[2], x[3]] for x in R["ev"]], open(os.path.join(a.out, "cambi_fonte.json"), "w"))
    json.dump(res, open(os.path.join(a.out, "riassunto_sessioni.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
