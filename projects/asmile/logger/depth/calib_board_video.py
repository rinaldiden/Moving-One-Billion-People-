"""
calib_board_video.py — focale e depth dalla SCACCHIERA a distanze misurate col metro (2026-11-08).

Per UNA unità alla volta (mai mescolare: #001 ≠ logger ≠ asmile2).
La scacchiera è sempre ripresa di fronte: da viste frontali focale e distanza NON si separano
(calibrateCamera diverge), quindi la scala la danno il METRO e il lato del quadretto:
  focale      f = Z_metro · lato_px / lato_mm           (per ogni sosta, camera sinistra)
  disparità   d = x_sinistra − x_destra della scacchiera (template matching nella fascia ±dy)
  modello     d = f·B / Z + d0   → fit (f·B, d0) sulle soste, errore % per sosta vs metro
Le soste si trovano da sole: tratti dove la dimensione del quadretto resta ferma ≥ 5 s.

Uso (logger, side-by-side 2560x800):
  ~/.asmile_depth_venv/bin/python logger/depth/calib_board_video.py --unit asmile-logger \
     --video 'asmile-loggers/asmile-logger/calib_20261108_160535/clip_*_0006[2-4].h264' --sbs 2560x800 \
     --square-mm 29.2 --pattern 6x4 --baseline-mm 200 --distances 1,2,3 --out logger/depth/calib_asmile-logger.json
"""
import argparse
import glob
import json
import subprocess

import cv2
import numpy as np


def frames(path, w, h, step):
    p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-framerate", "15", "-i", path, "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h:
            break
        if i % step == 0:
            yield i, np.frombuffer(b, np.uint8).reshape(h, w)
        i += 1


def square_px(c, pat):
    g = c.reshape(pat[1], pat[0], 2)
    return float(np.median(np.concatenate([np.linalg.norm(np.diff(g, axis=1), axis=2).ravel(),
                                           np.linalg.norm(np.diff(g, axis=0), axis=2).ravel()])))


def disparity(L, R, c, max_d=400, band=20):
    """Ritaglio della scacchiera a sinistra, cercato a destra sulla stessa fascia (±band per il dy)."""
    x0, y0 = c.min(0).astype(int) - 6
    x1, y1 = c.max(0).astype(int) + 6
    x0, y0 = max(x0, 0), max(y0, 0)
    tpl = L[y0:y1, x0:x1]
    sx0 = max(0, x0 - max_d)
    sy0, sy1 = max(0, y0 - band), min(R.shape[0], y1 + band)
    srch = R[sy0:sy1, sx0:x1 + 4]
    if srch.shape[0] < tpl.shape[0] or srch.shape[1] < tpl.shape[1]:
        return None, None
    res = cv2.matchTemplate(srch, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    # sub-pixel (parabola) in x
    lx, ly = loc
    dx = 0.0
    if 0 < lx < res.shape[1] - 1:
        a, b, cc = res[ly, lx - 1], res[ly, lx], res[ly, lx + 1]
        den = a - 2 * b + cc
        dx = 0.5 * (a - cc) / den if den != 0 else 0.0
    xr = sx0 + lx + dx
    return x0 - xr, (sy0 + ly) - y0 if mx > 0.6 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--video", help="glob segmenti side-by-side (logger)")
    ap.add_argument("--left", help="video camera sinistra (unità con 2 camere separate)")
    ap.add_argument("--right", help="video camera destra (se manca: solo focale, niente depth)")
    ap.add_argument("--sbs", default="2560x800")
    ap.add_argument("--size", default="1280x800", help="per --left/--right")
    ap.add_argument("--square-mm", type=float, required=True)
    ap.add_argument("--pattern", default="6x4")
    ap.add_argument("--baseline-mm", type=float, required=True)
    ap.add_argument("--distances", required=True, help="distanze delle soste in ordine, metri: 1,2,3")
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--min-stop-s", type=float, default=5, help="durata minima di una sosta (secondi)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pat = tuple(int(v) for v in a.pattern.split("x"))
    dist = [float(v) for v in a.distances.split(",")]

    samples = []                                   # (tag, lato_px, disparità, dy)
    if a.video:
        W, H = (int(v) for v in a.sbs.split("x"))
        for seg in sorted(glob.glob(a.video)):
            for i, g in frames(seg, W, H, a.step):
                L, R = g[:, :W // 2], g[:, W // 2:]
                ok, c = cv2.findChessboardCornersSB(L, pat, cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE)
                if ok:
                    c = c.reshape(-1, 2)
                    d, dy = disparity(L, R, c)
                    samples.append((f"{seg.split('_')[-1][:5]}:{i}", square_px(c, pat), d, dy))
    else:
        w, h = (int(v) for v in a.size.split("x"))
        gl = frames(a.left, w, h, a.step)
        gr = frames(a.right, w, h, a.step) if a.right else None
        for i, L in gl:
            R = next(gr)[1] if gr else None
            ok, c = cv2.findChessboardCornersSB(L, pat, cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE)
            if ok:
                c = c.reshape(-1, 2)
                d, dy = disparity(L, R, c) if R is not None else (None, None)
                samples.append((f"f{i}", square_px(c, pat), d, dy))
    print(f"{a.unit}: scacchiera trovata in {len(samples)} frame")

    # Soste. Mentre si cammina la scacchiera passa per tutte le dimensioni, quindi niente raggruppamento
    # "a occhio": si ancora la PRIMA distanza (la più vicina) al tratto fermo più lungo col quadretto più
    # grande, poi per ogni altra distanza si prendono i frame col lato atteso  lato_1 · Z_1 / Z  (±6%).
    runs, cur = [], [samples[0]]
    for s in samples[1:]:
        if abs(s[1] - np.median([x[1] for x in cur])) < 0.04 * s[1]:
            cur.append(s)
        else:
            runs.append(cur); cur = [s]
    runs.append(cur)
    min_n = max(3, int(a.min_stop_s * 15 / a.step))
    runs = [r for r in runs if len(r) >= min_n]
    anchor = max(runs, key=lambda r: np.median([x[1] for x in r]))
    lato1 = float(np.median([x[1] for x in anchor]))
    soste = [anchor] + [[x for x in samples if abs(x[1] - lato1 * dist[0] / z) < 0.06 * lato1 * dist[0] / z]
                        for z in dist[1:]]
    for z, s in zip(dist, soste):
        if len(s) < min_n:
            print(f"!! {z} m: solo {len(s)} frame con il lato atteso ({lato1 * dist[0] / z:.1f} px)")
    rows = []
    for s, z in zip(soste, dist):
        if not s:
            continue
        sq = float(np.median([x[1] for x in s]))
        ds = [x[2] for x in s if x[2] is not None]
        dys = [x[3] for x in s if x[3] is not None]
        rows.append(dict(z_metro_m=z, inizio=s[0][0], frame=len(s), lato_px=round(sq, 2),
                         f_px=round(z * sq / (a.square_mm / 1000), 1),
                         disp_px=round(float(np.median(ds)), 2) if ds else None,
                         dy_px=round(float(np.median(dys)), 1) if dys else None))
    f_med = float(np.median([r["f_px"] for r in rows]))
    print(f"focale dal metro: {[r['f_px'] for r in rows]} → mediana {f_med:.1f} px")

    fit = None
    st = [r for r in rows if r["disp_px"] is not None]
    if len(st) >= 2:
        A = np.array([[1 / r["z_metro_m"], 1] for r in st]); y = np.array([r["disp_px"] for r in st])
        (fB, d0), *_ = np.linalg.lstsq(A, y, rcond=None)
        fit = dict(fB_px_m=round(float(fB), 2), d0_px=round(float(d0), 2),
                   f_from_baseline_px=round(float(fB) / (a.baseline_mm / 1000), 1))
        print(f"fit disparità: f·B = {fB:.2f} px·m, d0 = {d0:+.2f} px → con B {a.baseline_mm:.0f} mm f = {fit['f_from_baseline_px']} px")
        for r in st:
            z_fit = fB / (r["disp_px"] - d0)
            z_raw = f_med * a.baseline_mm / 1000 / r["disp_px"]
            r["z_stereo_fit_m"] = round(float(z_fit), 3)
            r["err_fit_pct"] = round(100 * (z_fit - r["z_metro_m"]) / r["z_metro_m"], 2)
            r["z_stereo_semplice_m"] = round(float(z_raw), 3)
            r["err_semplice_pct"] = round(100 * (z_raw - r["z_metro_m"]) / r["z_metro_m"], 2)
    print("metro | frame | lato px | f px | disparità | dy | Z stereo (fit) | err | Z f·B/d senza d0 | err")
    for r in rows:
        print(f"{r['z_metro_m']:4.1f} m | {r['frame']:3d} | {r['lato_px']:6.2f} | {r['f_px']:6.1f} | "
              f"{r['disp_px']} | {r['dy_px']} | {r.get('z_stereo_fit_m')} | {r.get('err_fit_pct')}% | "
              f"{r.get('z_stereo_semplice_m')} | {r.get('err_semplice_pct')}%")
    json.dump(dict(unit=a.unit, method="scacchiera + metro (calib_board_video.py)", square_mm=a.square_mm,
                   baseline_mm=a.baseline_mm, f_px=round(f_med, 1), fit=fit, soste=rows,
                   valid_for=f"SOLO {a.unit} — mai usarla per un'altra unità"), open(a.out, "w"), indent=1)
    print("scritto", a.out)


if __name__ == "__main__":
    main()
