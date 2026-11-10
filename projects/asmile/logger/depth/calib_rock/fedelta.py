#!/usr/bin/env python3
"""
fedelta.py - prova di FEDELTA' del gemello contro una sessione REALE di #001.

Idea: per ogni coppia reale (tabellone ChArUco visto da entrambe le camere) si stima la posa del tabellone
(solvePnP con la calib di #001), si RENDE la stessa posa col gemello (istanza senza errori = la calib stessa),
si rilevano i corner con lo STESSO detector e si confrontano corner veri vs resi, id per id, per zona 3x3.
Si confrontano anche nitidezza (varianza del laplaciano), rumore e tasso di rilevamento.
Metriche: scarto grezzo (include l'errore della posa) e scarto dopo allineamento per vista (similarita' 4 dof,
toglie l'errore di posa e lascia la differenza di lente/forma).
Stato: sulla sessione reale NON VERIFICATO (nessuna coppia ChArUco reale di #001 sul Mac: la sessione
'vicino_153251' usa una scacchiera 7x10 a mano, non ChArUco). Pronta per la ripresa ChArUco: vedi README.
Il self-test sintetico prova solo il CODICE (e che la metrica sia sensibile), non la fedelta' al reale.
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import twin, render, autocal  # noqa: E402,E401
import calib_charuco_dual as ccd  # noqa: E402

W, H = twin.W, twin.H


def sharpness(img):
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def noise_estimate(img):
    """sigma di rumore (stima robusta su alte frequenze)."""
    d = img.astype(np.float32) - cv2.GaussianBlur(img.astype(np.float32), (0, 0), 1.5)
    return float(1.4826 * np.median(np.abs(d - np.median(d))))


def similarity_align(a, b):
    M, _ = cv2.estimateAffinePartial2D(a.astype(np.float32), b.astype(np.float32), method=cv2.LMEDS)
    if M is None:
        return b
    return (a @ M[:, :2].T) + M[:, 2]


def compare(real_pairs, calib_path, board_name, seed=0, unit="asmile-001"):
    """real_pairs: lista di (imgL_phys_left, imgR_phys_right) grayscale uint8 (gia' in ordine pipeline: L = sinistra fisica)."""
    inst, nom = twin.make_instance(calib_path, seed, 0.0, lens_var=False, unit=unit)
    board = render.make_board(board_name)
    det = autocal.make_detector(board)
    rng = np.random.default_rng(seed)
    rows = []
    d = {1: [[] for _ in range(9)], 2: [[] for _ in range(9)]}
    da = {1: [[] for _ in range(9)], 2: [[] for _ in range(9)]}
    det_real = det_twin = 0
    sh_r, sh_t, nz_r, nz_t = [], [], [], []
    for imgs in real_pairs:
        va = [autocal._detect(det, board, im) for im in imgs]
        det_real += sum(v is not None for v in va)
        if va[0] is None:
            continue
        ok, rv, tv = cv2.solvePnP(va[0]["obj"], va[0]["img"], nom.K1, nom.d1, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue
        pl = render.board_plane(board_name, rv.ravel(), tv.ravel())
        for ci, (im, v) in enumerate(zip(imgs, va), 1):
            ren = render.render(inst, ci, [pl], rng)
            vt = autocal._detect(det, board, ren)
            det_twin += vt is not None
            sh_r.append(sharpness(im)); sh_t.append(sharpness(ren))
            nz_r.append(noise_estimate(im)); nz_t.append(noise_estimate(ren))
            if v is None or vt is None:
                continue
            com, ia, ib = np.intersect1d(v["ids"], vt["ids"], return_indices=True)
            if len(com) < 8:
                continue
            pr, pt = v["img"][ia], vt["img"][ib]
            pal = similarity_align(pt, pr)
            zr = ccd.zone_of(pr)
            for k in range(len(com)):
                d[ci][zr[k]].append(float(np.linalg.norm(pr[k] - pt[k])))
                da[ci][zr[k]].append(float(np.linalg.norm(pr[k] - pal[k])))
    stat = lambda L: [None if not x else dict(p50=float(np.median(x)), p95=float(np.percentile(x, 95)), n=len(x)) for x in L]
    return dict(n_coppie=len(real_pairs), rilevate_reali=det_real, rilevate_gemello=int(det_twin),
                scarto_grezzo_px={f"cam{c}": stat(d[c]) for c in (1, 2)},
                scarto_allineato_px={f"cam{c}": stat(da[c]) for c in (1, 2)},
                nitidezza=dict(reale=float(np.median(sh_r)) if sh_r else None, gemello=float(np.median(sh_t)) if sh_t else None),
                rumore_sigma=dict(reale=float(np.median(nz_r)) if nz_r else None, gemello=float(np.median(nz_t)) if nz_t else None))


def selftest(calib_path, n=14):
    """Prova SOLO del codice: 'reale' = istanza con lenti variate (scala 1) resa dal gemello stesso."""
    rng = np.random.default_rng(5)
    board = "A2_11x8_50mm"
    out = {}
    for name, sc, lv in (("identico_a_se_stesso", 0.0, False), ("lente_variata_scala1", 1.0, True)):
        real, _ = twin.make_instance(calib_path, 11, sc, lens_var=lv)
        poses = autocal.sample_poses_zoned(np.random.default_rng(3), n, board)
        pairs = []
        for rv, tv in poses:
            pl = render.board_plane(board, rv, tv)
            pairs.append((render.render(real, 1, [pl], rng), render.render(real, 2, [pl], rng)))
        r = compare(pairs, calib_path, board)
        med = lambda k: float(np.median([z["p50"] for c in r[k].values() for z in c if z] or [np.nan]))
        out[name] = dict(mediana_scarto_grezzo_px=med("scarto_grezzo_px"), mediana_scarto_allineato_px=med("scarto_allineato_px"),
                         rilevate=r["rilevate_reali"], rilevate_gemello=r["rilevate_gemello"])
    a_, b_ = out["identico_a_se_stesso"], out["lente_variata_scala1"]
    # il grezzo (include errore di posa e di lente) deve distinguere un set identico da uno con lenti variate;
    # l'allineato (similarita' per vista) assorbe di proposito pose e scala: informativo
    ok = (np.isfinite(a_["mediana_scarto_grezzo_px"]) and a_["mediana_scarto_grezzo_px"] < 1.5
          and b_["mediana_scarto_grezzo_px"] > 3 * a_["mediana_scarto_grezzo_px"])
    out["selftest"] = "VERDE (codice ok, metrica sensibile)" if ok else "ROSSO (metrica non distingue o non funziona)"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calib", default=os.path.join(os.path.dirname(HERE), "calib_asmile-001.json"))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--left", help="cartella o glob delle immagini della camera SINISTRA FISICA (png/pgm)")
    ap.add_argument("--right", help="idem DESTRA fisica (stesso ordine alfabetico)")
    ap.add_argument("--board", default="A2_11x8_50mm")
    a = ap.parse_args()
    if a.selftest:
        r = selftest(a.calib)
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["selftest"].startswith("VERDE") else 1)
    if not (a.left and a.right):
        sys.exit("serve --selftest oppure --left/--right con coppie ChArUco reali di #001")
    L = sorted(glob.glob(os.path.join(a.left, "*")) if os.path.isdir(a.left) else glob.glob(a.left))
    R = sorted(glob.glob(os.path.join(a.right, "*")) if os.path.isdir(a.right) else glob.glob(a.right))
    pairs = [(cv2.imread(x, 0), cv2.imread(y, 0)) for x, y in zip(L, R)]
    print(json.dumps(compare(pairs, a.calib, a.board), indent=1))


if __name__ == "__main__":
    main()
