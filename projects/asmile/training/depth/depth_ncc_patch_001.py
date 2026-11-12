#!/usr/bin/env python3
"""depth_ncc_patch_001.py — distanza per oggetto con patch 23x23 verificate nei due sensi (asmile #001, calib B30 SENZA correzione Z).
Metodo della prova 'Sera 18:26' (agents/rapporti/depth_prova_001_20261111.md), reso riproducibile il 2026-11-12.
Per ogni punto della griglia nel box: patch 23x23 della sinistra rettificata cercata sulla destra (stessa riga, d 0..DMAX, NCC),
poi ritorno destra->sinistra: accettata se torna entro 1.5 px e NCC>=0.75. Z = f*B/d (d0=0; f_rect=1379.89 e B=baseline_m=0.19656 dalla calib, NON 0.2). Mediana sulle patch e sui fotogrammi.
Convenzione: file *_right = sinistra fisica (calib order RL).
Uso: depth_ncc_patch_001.py sera [--frames 40,50,60,70,80] [--out img.jpg]
"""
import sys, os, json, argparse
import numpy as np, cv2
import depth_seg_001 as D

PH, NCC_MIN, BACK_PX, DMAX = 11, 0.75, 1.5, 700   # raggio patch 11 -> 23x23
SESSION = "session_20261111_182602"
BOXES = {  # box (x0,y0,x1,y1) letti dall'immagine di ieri sera (rettificata sinistra)
    "pannello attrezzi": (20, 20, 500, 230), "muro tra pannello e porta": (520, 60, 640, 250),
    "porta": (700, 40, 1000, 330), "strumento nero sopra alimentatore": (740, 300, 1010, 350),
    "alimentatore (fronte)": (740, 350, 930, 530), "straccio bianco": (860, 420, 1100, 700)}


def picco_vicino(z, frac_min=0.25, bin_log=0.04):
    """REGOLA FISSATA 2026-11-12 PRIMA dei video (capo): istogramma di Z in scala log (bin 4%), lisciato [1,1,1]; popolazioni =
    tratti separati da una valle (valle < 50% del picco piu' basso fra i due vicini); si prende la PRIMA popolazione (la piu' vicina)
    con >= 25% dei punti; picco = mediana dei punti entro +-5% dal bin di picco. Ritorna (Z_picco, frazione_popolazione, n_popolazioni)."""
    z = np.asarray(z, float); z = z[z > 0]
    if len(z) == 0:
        return None, 0.0, 0
    lz = np.log(z); e = lz.min() - 1e-9 + bin_log * np.arange(int(np.ceil((lz.max() - lz.min()) / bin_log)) + 2)
    h = np.histogram(lz, bins=e)[0].astype(float)
    hs = np.convolve(h, [1, 1, 1], "same") if len(h) >= 3 else h
    pk = [i for i in range(len(hs)) if hs[i] > 0 and (i == 0 or hs[i] >= hs[i - 1]) and (i == len(hs) - 1 or hs[i] > hs[i + 1])]
    pops = []                                     # (lo, hi, picco)
    for i in pk:
        if pops:
            lo_pk = min(hs[pops[-1][2]], hs[i]); valley = hs[pops[-1][2]:i + 1].min()
            if valley >= 0.5 * lo_pk:             # niente valle vera: stessa popolazione (tengo il picco piu' alto)
                if hs[i] > hs[pops[-1][2]]:
                    pops[-1] = (pops[-1][0], i, i)
                else:
                    pops[-1] = (pops[-1][0], i, pops[-1][2])
                continue
            vi = pops[-1][2] + int(np.argmin(hs[pops[-1][2]:i + 1]))
            pops[-1] = (pops[-1][0], vi, pops[-1][2]); pops.append((vi + 1, len(hs) - 1, i))
        else:
            pops.append((0, len(hs) - 1, i))
    for lo, hi, p in pops:
        fr = h[lo:hi + 1].sum() / h.sum()
        if fr >= frac_min:
            c = 0.5 * (e[p] + e[p + 1])
            keep = z[np.abs(lz - c) < 0.05]
            zp = float(np.median(keep if len(keep) else z)); zm = float(np.median(z))
            # CORREZIONE v2 (2026-11-12, critico f6051: picco = specchio del furgone a 6.97 m su auto vera a 15 m): se ci sono piu'
            # popolazioni e il picco e' < 0.6 x mediana, il picco e' un occlusore sottile davanti -> uso la mediana.
            # Fissata PRIMA di rigirare; verificata su straccio (0.41/0.54=0.76 >= 0.6, resta picco) e f6051.
            if len(pops) > 1 and zp < 0.6 * zm:
                return zm, float(fr), len(pops)
            return zp, float(fr), len(pops)
    return float(np.median(z)), 1.0, len(pops)


def best_match(tmpl, strip, x_off):
    """strip: fascia della riga; ritorna (posizione x del centro, ncc) col massimo NCC."""
    r = cv2.matchTemplate(strip, tmpl, cv2.TM_CCOEFF_NORMED)[0]
    j = int(np.nanargmax(r))
    return j + x_off + PH, float(r[j])


def patch_depth(L, R, box, step=6, f=1379.89, B=0.19656):
    x0, y0, x1, y1 = box
    out = []
    for y in range(max(y0, PH), min(y1, 800 - PH - 1), step):
        for x in range(max(x0, PH), min(x1, 1280 - PH - 1), step):
            t = L[y - PH:y + PH + 1, x - PH:x + PH + 1]
            if t.std() < 3:
                continue
            xa = max(0, x - DMAX - PH)                 # destra: d>=0 => xr<=x
            strip = R[y - PH:y + PH + 1, xa:x + PH + 1]
            if strip.shape[1] < t.shape[1]:
                continue
            xr, n1 = best_match(t, strip, xa)
            if n1 < NCC_MIN:
                continue
            tr = R[y - PH:y + PH + 1, xr - PH:xr + PH + 1]
            xb = xr
            stripL = L[y - PH:y + PH + 1, xb - PH:min(1280, xb + DMAX + PH + 1)]
            xl, n2 = best_match(tr, stripL, xb - PH)
            d = x - xr
            if d < 4 or abs(xl - x) > BACK_PX or n2 < NCC_MIN:
                continue
            out.append(f * B / d)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--frames", default="40,50,60,70,80")
    ap.add_argument("--out", default=None); a = ap.parse_args()
    rc = D.Rect(); fr = [int(v) for v in a.frames.split(",")]
    gl = D.gray_frames(os.path.join(D.LOGS, SESSION + "_right.h264")); gr = D.gray_frames(os.path.join(D.LOGS, SESSION + "_left.h264"))
    Z = {k: [] for k in BOXES}; img = None
    for i, (Lr, Rr) in enumerate(zip(gl, gr)):
        if i > max(fr): break
        if i not in fr: continue
        L, R = rc(Lr, Rr)
        if img is None: img = L.copy()
        for k, b in BOXES.items():
            Z[k] += patch_depth(L, R, b, f=rc.f, B=rc.r['baseline_m'])
    res = {}
    for k, z in Z.items():
        z = np.array(z)
        pv = picco_vicino(z) if len(z) else (None, 0, 0)
        res[k] = dict(n=len(z), Z=float(np.median(z)) if len(z) else None, Z_picco=pv[0], frac_picco=pv[1], n_pop=pv[2],
                      q25=float(np.percentile(z, 25)) if len(z) else None, q75=float(np.percentile(z, 75)) if len(z) else None)
        print(f"{k:36s} n={res[k]['n']:5d} mediana={res[k]['Z']:.3f} picco_vicino={res[k]['Z_picco']:.3f} (pop {res[k]['frac_picco']:.2f}, {res[k]['n_pop']} pop) IQR={res[k]['q25']:.2f}-{res[k]['q75']:.2f}")
    if a.out and img is not None:
        c = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        for k, b in BOXES.items():
            cv2.rectangle(c, b[:2], b[2:], (0, 0, 255), 2)
            if res[k]["Z"]: cv2.putText(c, f"{k}: {res[k]['Z_picco']:.2f} m (med {res[k]['Z']:.2f})", (b[0] + 4, b[1] + 16), 0, 0.6, (0, 255, 255), 2)
        cv2.imwrite(a.out, c)


if __name__ == "__main__":
    main()
