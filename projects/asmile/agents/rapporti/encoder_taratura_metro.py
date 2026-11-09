#!/usr/bin/env python3
"""Gate L0.encoder_ruota — taratura COL METRO (riferimento di distanza indipendente dal GPS).

Misura di Daniele (2026-11-09): 15.760 mm = 10 giri completi di ruota  →  ruota #001 C = 1.5760 m.

ATTENZIONE al campo: nel speed_limiter `wheel_circum_m` NON è la circonferenza della ruota, sono i
METRI PER GIRO DELL'ENCODER (k = wheel_circum_m / 16384). L'encoder è rinviato, non sull'asse:
oggi 0.3374 m/giro-encoder (fit GPS 2026-11-07). Scrivere 1.576 lì = velocità ×4.7 → freno sbagliato.

Due modi, sui CSV di sensor_hub (sensors_*.csv, 50 Hz, enc_wheel_cum srotolato dal bridge):
  rotolata  trova nel log la spinta a mano da N giri (fermo ≥2 s → spinta → fermo ≥2 s) e ricava
            m_per_count = metri / |Δcount|  (+ giri encoder per giro ruota). Niente GPS nel conto.
  giro      con un m_per_count dato: distanza encoder vs traccia GPS, velocità vs GPS 10 Hz (blocchi
            1 s, lag stimato), accelerazione encoder (fit 0.3 s, come il limiter) vs derivata GPS.

Uso:
  python3 encoder_taratura_metro.py rotolata <sensors.csv> [--metri 15.760 --giri 10] [--da s --a s]
                                    [--scrivi proposta.json]
  python3 encoder_taratura_metro.py giro <sensors.csv> [--mpc 2.06e-5]
"""
import argparse, json, math, sys
from datetime import datetime
import numpy as np, pandas as pd

CPR = 16384                       # AMT22/AMT223 14-bit
MPC_ATTIVO = 0.3374 / CPR         # quello oggi su #001 (fit GPS 2026-11-07)
FERMO_S, FERMO_COUNTS = 2.0, 200  # fermo = in 2 s si muove meno di 200 count (~4 mm)


def carica_enc(f):
    d = pd.read_csv(f, usecols=["t_ms", "enc_t_ms", "enc_wheel_cum"], low_memory=False)
    d = d.dropna(subset=["enc_wheel_cum"])
    tcol = "enc_t_ms" if d.enc_t_ms.notna().all() else "t_ms"
    d = d.drop_duplicates(tcol)
    return d[tcol].values / 1000.0, d.enc_wheel_cum.values.astype(float)


def segmenti_moto(t, c):
    """Tratti di moto delimitati da fermi ≥FERMO_S. → lista (i0, i1)."""
    n = len(t); fermo = np.zeros(n, bool); j = 0
    for i in range(n):                                  # finestra [i, j) di FERMO_S
        while j < n and t[j] - t[i] < FERMO_S:
            j += 1
        if j - i > 5 and np.ptp(c[i:j]) < FERMO_COUNTS:
            fermo[i:j] = True
    seg, i = [], 0
    while i < n:
        if not fermo[i]:
            k = i
            while k < n and not fermo[k]:
                k += 1
            seg.append((max(i - 1, 0), min(k, n - 1)))
            i = k
        else:
            i += 1
    return seg


def rotolata(a):
    t, c = carica_enc(a.csv)
    t0 = t[0]
    if a.da is not None or a.a is not None:
        m = (t - t0 >= (a.da or 0)) & (t - t0 <= (a.a if a.a is not None else 1e9))
        t, c = t[m], c[m]
    atteso = a.metri / MPC_ATTIVO
    print("file %s · %.0f s · ruota: %.3f m in %d giri → C = %.4f m" % (a.csv, t[-1] - t[0], a.metri, a.giri, a.metri / a.giri))
    print("con la scala attiva (0.3374 m/giro-enc) %d giri ruota = %.0f count (%.1f giri encoder)" % (a.giri, atteso, atteso / CPR))
    cand = []
    for i0, i1 in segmenti_moto(t, c):
        net = c[i1] - c[i0]; lordo = np.abs(np.diff(c[i0:i1 + 1])).sum()
        if lordo < 1000:
            continue
        r = abs(net) / atteso
        cand.append(dict(da_s=round(t[i0] - t0, 2), a_s=round(t[i1] - t0, 2), dur_s=round(t[i1] - t[i0], 1),
                         dcount=int(net), monotono=round(abs(net) / lordo, 3), rapporto_vs_atteso=round(r, 3)))
    if not cand:
        print("NESSUN tratto di moto tra due fermi: la rotolata non è in questo file (o il Pi non registrava)."); return 2
    print("\ntratti di moto (fermo ≥%.0f s prima e dopo):" % FERMO_S)
    for k in cand:
        print("  %7.1f–%7.1f s  %5.1f s  Δ=%9d count  monotono %.3f  ×atteso %.3f" % (
            k["da_s"], k["a_s"], k["dur_s"], k["dcount"], k["monotono"], k["rapporto_vs_atteso"]))
    # la rotolata vera: spinta in una sola direzione, e Δ nell'ordine di N giri (0.5–2× l'atteso: largo,
    # così anche se la scala GPS fosse sbagliata di molto il tratto viene trovato lo stesso)
    ok = [k for k in cand if k["monotono"] > 0.97 and 0.5 < k["rapporto_vs_atteso"] < 2.0]
    if not ok:
        print("\nnessun tratto compatibile con %d giri (monotono e 0.5–2× l'atteso). Usa --da/--a sul tratto giusto." % a.giri); return 2
    if len(ok) > 1:
        print("\n⚠ %d tratti compatibili: prendo quello più vicino all'atteso, controlla col --da/--a." % len(ok))
    b = min(ok, key=lambda k: abs(math.log(k["rapporto_vs_atteso"])))
    mpc = a.metri / abs(b["dcount"]); m_giro_enc = mpc * CPR; R = abs(b["dcount"]) / CPR / a.giri
    dv = (m_giro_enc / 0.3374 - 1) * 100
    print("\n=== RISULTATO (tratto %.1f–%.1f s) ===" % (b["da_s"], b["a_s"]))
    print("  m_per_count        = %.4e m" % mpc)
    print("  metri/giro encoder = %.4f m   ← valore per il campo wheel_circum_m (oggi 0.3374, %+.1f%%)" % (m_giro_enc, dv))
    print("  giri encoder/giro ruota = %.3f   (la nota '~6.3' nasceva dal placeholder 2.10 m)" % R)
    print("  forward_sign       = %s   (segno del Δ spingendo avanti)" % ("+" if b["dcount"] > 0 else "-"))
    print("  risoluzione        = %.3f mm/count" % (mpc * 1000))
    print("  oggi il limiter legge la velocità %s del %.1f%%" % ("ALTA" if dv < 0 else "BASSA", abs(dv) / (1 + dv / 100)))
    if a.scrivi:
        out = {"m_per_count": float("%.4e" % mpc), "wheel_circum_m": round(m_giro_enc, 4), "enc_counts_per_rev": CPR,
               "forward_sign": "+" if b["dcount"] > 0 else "-",
               "ruota_circonferenza_m": round(a.metri / a.giri, 4), "enc_giri_per_giro_ruota": round(R, 4),
               "metodo": "rotolata %d giri col metro (%.3f m), %s %.1f-%.1f s" % (a.giri, a.metri, a.csv.split("/")[-1], b["da_s"], b["a_s"]),
               "nota_campo": "wheel_circum_m = metri per giro ENCODER (k=wheel_circum_m/16384), non la ruota",
               "stato": "PROPOSTA — non deployata; deploy solo col vai di Daniele (asmile-sicurezza → asmile-deploy)",
               "generated": datetime.now().isoformat(timespec="seconds")}
        with open(a.scrivi, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        print("  proposta scritta in", a.scrivi)
    return 0


def hav(la1, lo1, la2, lo2):
    R = 6371000.0; p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = p2 - p1, np.radians(lo2 - lo1)
    return 2 * R * np.arcsin(np.sqrt(np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2))


def giro(a):
    mpc = a.mpc
    t, c = carica_enc(a.csv)
    g = pd.read_csv(a.csv, usecols=["gps_t_ms", "gps_fix", "gps_lat", "gps_lon", "gps_speed_ms", "gps_hdop"], low_memory=False)
    g = g.dropna(subset=["gps_t_ms", "gps_lat"]).drop_duplicates("gps_t_ms")
    g = g[(g.gps_fix == 1) & (g.gps_hdop < 3)]
    print("file %s · m_per_count %.4e (%.4f m/giro-enc) · GPS validi %d" % (a.csv, mpc, mpc * CPR, len(g)))
    # velocità encoder: fit lineare su 0.3 s (come il limiter), campionata ogni 0.1 s
    tt = np.arange(t[0] + 0.3, t[-1], 0.1)
    def fit(x0, w):
        m = (t > x0 - w) & (t <= x0)
        return np.polyfit(t[m] - x0, c[m], 1)[0] * mpc if m.sum() >= 3 else np.nan
    v = np.abs(np.array([fit(x, 0.3) for x in tt]))
    dist_enc = np.nansum(np.abs(np.diff(c))) * mpc
    print("distanza encoder (|Δ| sommati): %.1f m" % dist_enc)
    if len(g) < 50:
        print("GPS insufficiente per il confronto (servono ≥50 punti con fix e HDOP<3)."); return 2
    gt = g.gps_t_ms.values / 1000.0; gv = g.gps_speed_ms.values
    # distanza GPS solo nei tratti in moto (>1.5 m/s) per non sommare il rumore da fermo
    seg = hav(g.gps_lat.values[:-1], g.gps_lon.values[:-1], g.gps_lat.values[1:], g.gps_lon.values[1:])
    mv = (gv[1:] > 1.5) & (np.diff(gt) < 0.5)
    ce = np.interp(gt, t, c)
    de = np.abs(np.diff(ce))[mv].sum() * mpc
    print("tratti in moto (GPS >1.5 m/s): GPS %.1f m · encoder %.1f m · encoder/GPS = %.3f" % (seg[mv].sum(), de, de / max(seg[mv].sum(), 1e-9)))
    # lag GPS e confronto velocità per blocchi di 1 s
    vi = lambda L: np.interp(gt - L, tt, v)
    best = max(np.arange(0, 2.01, 0.1), key=lambda L: np.corrcoef(vi(L)[gv > 1.5], gv[gv > 1.5])[0, 1])
    ve = vi(best); kmh = gv * 3.6
    blk = np.floor(gt).astype(int); df = pd.DataFrame({"b": blk, "e": ve, "g": gv}).groupby("b").mean()
    df = df[(df.g * 3.6 >= 6) & (df.g * 3.6 <= 25)]
    if len(df):
        err = (df.e - df.g).abs() / df.g * 100; bias = ((df.e - df.g) / df.g * 100).median()
        print("velocità 6-25 km/h, blocchi 1 s (n=%d, lag %.1f s): err mediano %.1f%% p90 %.1f%% bias %+.1f%%  [criterio ≤5%%]" % (
            len(df), best, err.median(), err.quantile(0.9), bias))
        for lo, hi in [(6, 12), (12, 18), (18, 25)]:
            mm = (df.g * 3.6 >= lo) & (df.g * 3.6 < hi)
            if mm.sum() >= 5:
                print("  %d-%d km/h n=%d err med %.1f%% bias %+.1f%%" % (lo, hi, mm.sum(), err[mm].median(), ((df.e - df.g) / df.g * 100)[mm].median()))
    else:
        print("nessun blocco GPS tra 6 e 25 km/h.")
    # accelerazione: derivata della velocità encoder vs derivata GPS (10 Hz), entrambe smussate 1 s
    sm = lambda x, n: np.convolve(x, np.ones(n) / n, mode="same")
    ae = np.gradient(sm(ve, 10), gt); ag = np.gradient(sm(gv, 10), gt)
    m = (gv > 1.5) & np.isfinite(ae) & (np.diff(gt, prepend=gt[0]) < 0.5)
    if m.sum() > 100:
        r = np.corrcoef(ae[m], ag[m])[0, 1]
        fr = m & (ag < -0.5)
        print("accelerazione (1 s): corr enc↔GPS %.2f · std enc %.2f GPS %.2f m/s² · frenate (GPS<-0.5) n=%d enc/GPS mediano %.2f" % (
            r, ae[m].std(), ag[m].std(), fr.sum(), np.median(ae[fr] / ag[fr]) if fr.sum() else float("nan")))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest="modo", required=True)
    r = s.add_parser("rotolata"); r.add_argument("csv"); r.add_argument("--metri", type=float, default=15.760)
    r.add_argument("--giri", type=int, default=10); r.add_argument("--da", type=float); r.add_argument("--a", type=float)
    r.add_argument("--scrivi")
    q = s.add_parser("giro"); q.add_argument("csv"); q.add_argument("--mpc", type=float, default=MPC_ATTIVO)
    a = p.parse_args()
    sys.exit(rotolata(a) if a.modo == "rotolata" else giro(a))
