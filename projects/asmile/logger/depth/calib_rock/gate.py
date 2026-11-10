#!/usr/bin/env python3
"""
gate.py - il GIUDICE: confronta una calibrazione (candidata) con la VERITA' del gemello.

Mai RMS del fit, mai la calib stimata usata due volte: si prendono punti 3D veri (griglia di pixel per zona 3x3 x
distanze 1-20 m), si proiettano con le lenti RICCHE vere, si rettificano con la calib candidata e si legge
  - dy (scarto verticale) per zona,
  - errore % di depth (Z letta con la calib vs Z vera nel frame rettificato) per zona x distanza.
GATE STRETTI (tutti devono passare, per OGNI istanza):
  dy p95 < 1 px in tutte e 9 le zone; depth centro <=2% a 2-5 m e <=3% a 7-10 m; bordi <=3% a 2-5 m;
  1 m e 10-20 m sono RIPORTATI (non nel gate); baseline dal tabellone 200 mm +-3% (non forzata) -> in autocal.
"""
import numpy as np
import cv2

import twin

W, H = twin.W, twin.H
ZS = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
ZNAME = ["alto-sx", "alto-centro", "alto-dx", "mezzo-sx", "centro", "mezzo-dx", "basso-sx", "basso-centro", "basso-dx"]
GATES_A = dict(dy_p95_px=1.5, centro_2_5m_pct=2.0, centro_7_10m_pct=3.0)   # A = SOLO CANDIDATO: bordo = dy < 1.5 px per zona, depth di bordo NON giudicata dal mock
GATES = dict(dy_p95_px=1.0, centro_2_5m_pct=2.0, centro_7_10m_pct=3.0, bordi_2_5m_pct=3.0)


def truth_points(inst, per_zone=5, margin=12):
    """Pixel di cam1 (griglia per_zone x per_zone in ogni zona) -> raggi veri -> punti 3D con Z_cam1 = ZS."""
    pts = []
    zw, zh = W / 3, H / 3
    for z in range(9):
        x0, y0 = (z % 3) * zw, (z // 3) * zh
        xs = np.linspace(x0 + margin, x0 + zw - margin, per_zone)
        ys = np.linspace(y0 + margin, y0 + zh - margin, per_zone)
        uu, vv = np.meshgrid(xs, ys)
        pts.append((z, uu.ravel(), vv.ravel()))
    return pts


def truth_eval(inst, cal, per_zone=5, margin=12):
    """Valuta la calib `cal` (stereo_common.Calib) contro la verita' di `inst`."""
    rect = cal.rectify(alpha=0)
    R1, P1, R2, P2 = rect["R1"], rect["P1"], rect["R2"], rect["P2"]
    f, B = float(P1[0, 0]), cal.baseline_mm / 1000.0
    dy_z = {z: [] for z in range(9)}
    err = {z: {Z: [] for Z in ZS} for z in range(9)}
    n_out = 0
    for z, u, v in truth_points(inst, per_zone, margin):
        rays = inst.cam1.rays(u, v)
        for Z in ZS:
            X1 = rays * Z                                   # Z_cam1 = Z
            p1 = inst.cam1.project(X1)
            p2 = inst.cam2.project(X1 @ inst.R.T + inst.T)
            ok = (p2[:, 0] >= 0) & (p2[:, 0] < W) & (p2[:, 1] >= 0) & (p2[:, 1] < H)
            n_out += int((~ok).sum())
            if not ok.any():
                continue
            q1 = cv2.undistortPoints(p1[ok].reshape(-1, 1, 2), cal.K1, cal.d1, R=R1, P=P1).reshape(-1, 2)
            q2 = cv2.undistortPoints(p2[ok].reshape(-1, 1, 2), cal.K2, cal.d2, R=R2, P=P2).reshape(-1, 2)
            dy = q1[:, 1] - q2[:, 1]
            d = q1[:, 0] - q2[:, 0]
            Zrect = (X1[ok] @ R1.T)[:, 2]                   # profondita' vera nel frame rettificato sinistro
            with np.errstate(divide="ignore", invalid="ignore"):
                Zest = np.where(d > 0.05, f * B / d, np.nan)
            e = (Zest - Zrect) / Zrect * 100
            err[z][Z] += list(e)
            dy_z[z] += list(dy)
    out = dict(dy_p50=[], dy_p95=[], depth={}, punti_fuori_cam2=n_out, zona_valida=[])
    n_tot = per_zone * per_zone * len(ZS)
    for z in range(9):
        a = np.abs(np.array(dy_z[z]))
        # zona senza sovrapposizione stereo (rotazione di montaggio sposta la vista): < 40% dei punti visibili in cam2
        out["zona_valida"].append(bool(len(a) >= 0.4 * n_tot))
        out["dy_p50"].append(float(np.median(a)) if len(a) else None)
        out["dy_p95"].append(float(np.percentile(a, 95)) if len(a) else None)
        cells = {}
        for Z in ZS:
            e = np.array(err[z][Z], float)
            fin = np.isfinite(e)
            # d <= 0.05 px (disparita' nulla/negativa) = errore catastrofico: p95 = inf, mediana = nan
            cells[str(Z)] = None if not len(e) else dict(
                med=float(np.median(e[fin])) if fin.any() else float("nan"),
                p95abs=float(np.percentile(np.abs(np.where(fin, e, 1e9)), 95)),
                n=int(fin.sum()))
        out["depth"][ZNAME[z]] = cells
    return out


def _cell(ev, zname, Z):
    c = ev["depth"][zname][str(Z)]
    return None if c is None else c["p95abs"]


def summary_err(ev):
    """Numero unico per confronto 'prima/dopo': media su zone x [2,3,5,7,10] m del p95|err|% (NaN = errore enorme)."""
    v = []
    for zn in ZNAME:
        for Z in (2.0, 3.0, 5.0, 7.0, 10.0):
            c = _cell(ev, zn, Z)
            v.append(100.0 if c is None or not np.isfinite(c) else min(c, 100.0))
    return float(np.mean(v))


def zone_worsening(ev0, ev1, distances=(2.0, 3.0, 5.0, 7.0, 10.0)):
    """Peggioramento PER ZONA: per ognuna delle 9 zone x distanze, p95|err|% dopo meno prima (NaN/inf = 100, tetto 100).
    Ritorna (peggior_delta_punti, lista celle che peggiorano di piu', dict zona->Z->delta). Una media puo' nascondere un
    peggioramento al bordo compensato al centro: qui si guarda la cella peggiore."""
    cap = lambda c: 100.0 if c is None or not np.isfinite(c) else min(c, 100.0)
    delta, worst = {}, (-1e9, None)
    for zn in ZNAME:
        delta[zn] = {}
        for Z in distances:
            d = cap(_cell(ev1, zn, Z)) - cap(_cell(ev0, zn, Z))
            delta[zn][str(Z)] = round(d, 3)
            if d > worst[0]:
                worst = (d, (zn, Z))
    return float(worst[0]), worst[1], delta


def edge_errors(ev, Zs=(2.0, 3.0, 5.0)):
    """Errore p95|%| di depth peggiore sulle 8 zone di bordo a 2-5 m: (valore, zona, Z)."""
    best = (0.0, None, None)
    for zn in ZNAME:
        if zn == "centro":
            continue
        for Z in Zs:
            c = _cell(ev, zn, Z)
            c = 100.0 if c is None or not np.isfinite(c) else c
            if c > best[0]:
                best = (float(c), zn, Z)
    return best


def check_gates(ev, G=GATES):
    """Applica i gate stretti. Ritorna dict(verdetto, motivi, tabella...). Ogni cella mancante = ROSSO."""
    motivi = []
    valide = ev.get("zona_valida", [True] * 9)
    escluse = [ZNAME[i] for i in range(9) if not valide[i]]
    if sum(valide) < 6 or not valide[4]:
        motivi.append(f"sovrapposizione stereo insufficiente: zone senza punti visibili in entrambe le camere {escluse}")
    for i, zn in enumerate(ZNAME):
        if not valide[i]:
            continue
        p = ev["dy_p95"][i]
        if p is None or not np.isfinite(p) or not p < G["dy_p95_px"]:
            motivi.append(f"dy p95 {zn} = {p if p is None else round(p, 2)} px >= {G['dy_p95_px']}")
    for zi, zn in enumerate(ZNAME):
        if not valide[zi]:
            continue
        for Z in (2.0, 3.0, 5.0, 7.0, 10.0):
            c = _cell(ev, zn, Z)
            if zn == "centro":
                lim = G["centro_2_5m_pct"] if Z <= 5 else G["centro_7_10m_pct"]
            elif Z <= 5:
                lim = G["bordi_2_5m_pct"]
            else:
                continue
            if c is None or not np.isfinite(c) or c > lim:
                motivi.append(f"depth {zn} {Z:g} m: p95|err| = {c if c is None else round(c, 2)}% > {lim}%")
    return dict(verdetto="VERDE" if not motivi else "ROSSO", motivi=motivi, zone_escluse_senza_sovrapposizione=escluse)


def table_text(ev):
    rows = ["zona        " + " ".join(f"{Z:>6g}m" for Z in ZS) + "   dy p50/p95"]
    for i, zn in enumerate(ZNAME):
        cells = []
        for Z in ZS:
            c = ev["depth"][zn][str(Z)]
            cells.append("     - " if c is None else f"{c['med']:+6.2f}")
        rows.append(f"{zn:<12s}" + " ".join(cells) + f"   {ev['dy_p50'][i]:.2f}/{ev['dy_p95'][i]:.2f}")
    return "\n".join(rows)


def check_gates_A(ev, G=GATES_A):
    """Criterio del CANDIDATO di A (il bordo si certifica col banco fisso reale, mai dal mock): dy p95 < 1.5 px in OGNI zona
    con sovrapposizione stereo + depth del CENTRO entro i limiti stretti. La depth di bordo e' riportata (edge_errors), non giudicata.
    Un candidato con una zona sopra 1.5 px di dy NON e' un candidato."""
    motivi = []
    valide = ev.get("zona_valida", [True] * 9)
    if sum(valide) < 6 or not valide[4]:
        motivi.append("sovrapposizione stereo insufficiente")
    for i, zn in enumerate(ZNAME):
        if not valide[i]:
            continue
        p = ev["dy_p95"][i]
        if p is None or not np.isfinite(p) or not p < G["dy_p95_px"]:
            motivi.append(f"dy p95 {zn} = {p if p is None else round(p, 2)} px >= {G['dy_p95_px']}")
    for Z in (2.0, 3.0, 5.0, 7.0, 10.0):
        c = _cell(ev, "centro", Z)
        lim = G["centro_2_5m_pct"] if Z <= 5 else G["centro_7_10m_pct"]
        if c is None or not np.isfinite(c) or c > lim:
            motivi.append(f"depth centro {Z:g} m: p95|err| = {c if c is None else round(c, 2)}% > {lim}%")
    return dict(verdetto="VERDE" if not motivi else "ROSSO", motivi=motivi)
