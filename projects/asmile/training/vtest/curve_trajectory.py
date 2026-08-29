#!/usr/bin/env python3
"""
curve_trajectory.py — Traiettoria e raggio di curva SENZA depth (dead reckoning inverso)
========================================================================================
Ricostruisce il percorso guidato e il raggio di sterzata usando SOLO i sensori di bordo,
senza visione ne' depth. Idea (path planning al contrario):

  - Durante una curva ho due misure ridondanti dello STESSO fatto:
      * gyro_z = velocita' di rotazione reale (rad/s). Con la velocita' GPS mi da' il
        RAGGIO VERO in metri:  R = v / omega   (fisica pura, nessuna calibrazione).
      * encoder = i gradi di sterzo letti.
  - Uso il giroscopio come VERITA' di riferimento per calibrare la relazione lineare
        curvatura = 1/R = a*encoder + b
    (curvatura, non angolo: cosi' non mi serve ne' il passo ne' l'angolo assoluto).
  - Una volta calibrata, ricostruisco la traiettoria dal SOLO encoder e la sovrappongo
    a quella vera (gyro+speed) per vedere quanto regge. Serve a: capire lo sterzo del
    modello in metri, e a ricostruire il percorso quando il GPS/gyro non ci sono.

Nota onesta (limiti, "poi la sistemiamo"): dead reckoning => la rotta deriva nel tempo
(bias gyro, slittamento, lean della bici, GPS lento a bassa velocita'). La FORMA locale
delle curve regge; le distanze assolute su percorsi lunghi no.

Uso:
  python3 curve_trajectory.py --session /path/session_X --outdir reports
"""
from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CURVE_GYRO_DEG = 8.0    # |gyro_z| soglia per "sono in curva"
CURVE_VMIN = 0.8        # m/s: sotto, R=v/omega e' instabile


def load(session: Path):
    rows = list(csv.DictReader(open(session / "sensors.csv")))
    t, v, gz, enc = [], [], [], []
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["timestamp"]).timestamp()
        except Exception:
            continue
        t.append(ts)
        v.append(float(r.get("gps_speed_ms") or 0.0))
        gz.append(math.radians(float(r.get("imu_gyro_z") or 0.0)))   # deg/s -> rad/s
        enc.append(float(r.get("encoder_pos") or 0.0))
    return (np.array(t), np.array(v), np.array(gz), np.array(enc))


def integrate_path(dt, v, omega):
    """Dead reckoning: heading = integrale di omega; posizione = integrale di v."""
    theta = np.concatenate([[0.0], np.cumsum(omega[:-1] * dt[:-1])])
    dx = v * np.cos(theta) * dt
    dy = v * np.sin(theta) * dt
    return np.cumsum(dx), np.cumsum(dy), theta


def main() -> int:
    ap = argparse.ArgumentParser(description="Traiettoria + raggio di curva senza depth")
    ap.add_argument("--session", required=True)
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()
    session = Path(args.session)
    name = session.name
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    t, v, gz, enc = load(session)
    dt = np.diff(t, prepend=t[0])
    dt = np.clip(dt, 0, 0.5)                      # tappa i buchi (dropout): non integrare gap

    # verita' di riferimento: curvatura reale dai sensori, solo in curva
    mask = (np.abs(gz) > math.radians(CURVE_GYRO_DEG)) & (v > CURVE_VMIN)
    kappa_gt = gz[mask] / v[mask]                # 1/R in 1/m (segno = verso curva)
    enc_c = enc[mask]

    if mask.sum() < 30:
        print(f"[curve] troppe poche curve valide ({int(mask.sum())}): sessione non adatta.")
        return 1

    # salute encoder: se e' railato o non correla con l'imbardata, la calibrazione e' aria
    sat = int((enc > 4090).sum()) + int((enc < 5).sum())
    cc = float(np.corrcoef(enc[mask], gz[mask])[0, 1])
    if abs(cc) < 0.4 or sat > len(enc) * 0.05:
        print(f"[curve] ATTENZIONE encoder poco affidabile in questa sessione: "
              f"corr(enc,imbardata)={cc:+.2f}, saturati={sat}. "
              f"La calibrazione sara' debole — scegli una sessione con encoder centrato.")

    # fit lineare: kappa = a*enc + b  (minimi quadrati)
    A = np.vstack([enc_c, np.ones_like(enc_c)]).T
    (a, b), *_ = np.linalg.lstsq(A, kappa_gt, rcond=None)
    e0 = -b / a                                  # encoder "dritto" (curvatura 0)
    kappa_pred = a * enc_c + b
    ss_res = float(np.sum((kappa_gt - kappa_pred) ** 2))
    ss_tot = float(np.sum((kappa_gt - kappa_gt.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    # traiettorie: riferimento (gyro) vs solo-encoder (via calibrazione)
    omega_enc = (a * enc + b) * v                # ricostruisce omega dal solo encoder
    xr, yr, _ = integrate_path(dt, v, gz)        # riferimento
    xe, ye, _ = integrate_path(dt, v, omega_enc) # solo encoder
    drift = math.hypot(xr[-1] - xe[-1], yr[-1] - ye[-1])
    path_len = float(np.sum(v * dt))

    # ---- stampa calibrazione + tabella encoder->raggio ----
    print("=" * 68)
    print(f"TRAIETTORIA SENZA DEPTH — {name}")
    print("=" * 68)
    print(f"campioni in curva usati : {int(mask.sum())}")
    print(f"encoder 'dritto' (e0)   : {e0:.0f}  (curvatura 0)")
    print(f"guadagno curvatura (a)  : {a:.3e} 1/m per conteggio encoder")
    print(f"bonta' del fit (R^2)    : {r2:.3f}   <-- quanto l'encoder spiega il raggio")
    print(f"percorso totale         : {path_len:.0f} m")
    print(f"deriva finale enc-vs-gyro: {drift:.1f} m  (dead reckoning, cresce nel tempo)")
    print("\nencoder -> raggio di curva previsto (dal solo encoder):")
    for de in (-400, -250, -120, -40, 40, 120, 250, 400):
        e = e0 + de
        k = a * e + b
        R = (1 / k) if abs(k) > 1e-4 else float("inf")
        verso = "dritto" if abs(R) > 200 else ("SX" if k > 0 else "DX")
        print(f"  enc={e:6.0f} ({de:+4d})  R={R:8.1f} m  {verso}")

    # ---- grafico 1: traiettoria a volo d'uccello ----
    plt.figure(figsize=(7, 7))
    plt.plot(xr, yr, '-', color='#2a7', lw=2, label='vera (gyro+speed)')
    plt.plot(xe, ye, '-', color='#f80', lw=1.5, label='solo encoder (calibrato)')
    plt.scatter([xr[0]], [yr[0]], c='k', s=40, zorder=5, label='partenza')
    plt.axis('equal'); plt.grid(alpha=.3); plt.legend()
    plt.title(f"Traiettoria ricostruita senza depth — {name}\n"
              f"percorso {path_len:.0f} m · deriva {drift:.1f} m")
    plt.xlabel("m"); plt.ylabel("m")
    p1 = outdir / f"traiettoria_{name}.png"
    plt.tight_layout(); plt.savefig(p1, dpi=110); plt.close()

    # ---- grafico 2: calibrazione encoder -> curvatura ----
    plt.figure(figsize=(7, 5))
    plt.scatter(enc_c, kappa_gt, s=6, alpha=.3, color='#37a', label='curve reali (gyro/speed)')
    xs = np.linspace(enc_c.min(), enc_c.max(), 50)
    plt.plot(xs, a * xs + b, 'r-', lw=2, label=f'fit lineare (R²={r2:.2f})')
    plt.axvline(e0, color='k', ls='--', alpha=.5, label=f'dritto e0={e0:.0f}')
    plt.axhline(0, color='k', alpha=.2)
    plt.xlabel("encoder (conteggi)"); plt.ylabel("curvatura 1/R  (1/m)")
    plt.title(f"Calibrazione encoder→curvatura — {name}")
    plt.grid(alpha=.3); plt.legend()
    p2 = outdir / f"calib_encoder_curvatura_{name}.png"
    plt.tight_layout(); plt.savefig(p2, dpi=110); plt.close()

    print(f"\ngrafici: {p1}\n        {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
