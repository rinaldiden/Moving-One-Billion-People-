"""Foto da logger02 fermo + distanze stimate su 6-8 punti, da far misurare a Daniele col metro.

Uso: python3 foto_metro.py <calib.json> <cartella_uscita> [--host 192.168.1.122] [--a a.jpg --b b.jpg]
Prende un fotogramma da A (:81/stream) e da B (:82/b/stream), rettifica con la calib, SGBM con controllo
sinistra-destra, sceglie punti ben definiti sparsi per distanza e zona, e scrive:
  foto_metro.jpg (punti numerati + distanza), punti.json (pixel, disparita', Z, distanza diretta).
Distanza diretta = dal punto a META' fra le due lenti (quella che si misura col metro); Z = lungo l'asse ottico.
Convenzione calib: d_misurata = f*B/Z + d0_px  ->  Z = f*B/(d - d0).
"""
import argparse, json, os, time, urllib.request
import numpy as np, cv2

BOUND = b'--123456789000000000000987654321'


def grab(url, secondi=3.0):
    """Ultimo JPEG completo dello stream MJPEG letto per qualche secondo (l'esposizione si assesta)."""
    buf, t0 = b'', time.time()
    with urllib.request.urlopen(url, timeout=8) as r:
        while time.time() - t0 < secondi:
            ch = r.read(65536)
            if not ch:
                break
            buf += ch
    jpgs = []
    for part in buf.split(BOUND):
        i, j = part.find(b'\xff\xd8'), part.rfind(b'\xff\xd9')
        if i >= 0 and j > i:
            jpgs.append(part[i:j + 2])
    if not jpgs:
        raise RuntimeError(f'nessun JPEG da {url}')
    return cv2.imdecode(np.frombuffer(jpgs[-1], np.uint8), cv2.IMREAD_GRAYSCALE)


def calib(path, h):
    c = json.load(open(path))
    K1, K2 = np.array(c['K_left'], float), np.array(c['K_right'], float)
    W, H = c['size']
    if h != H:
        if (H, h) != (720, 800):
            raise RuntimeError(f'calib a {H} righe, foto a {h}: conversione non nota')
        K1[1, 2] += 40; K2[1, 2] += 40  # il modo 720 e' il crop dalla riga 40 del modo 800
    d1, d2 = np.array(c['dist_left']), np.array(c['dist_right'])
    R, T = np.array(c['R']), np.array(c['T']).reshape(3, 1)
    r = cv2.stereoRectify(K1, d1, K2, d2, (W, h), R, T, flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    m1 = cv2.initUndistortRectifyMap(K1, d1, r[0], r[2], (W, h), cv2.CV_32FC1)
    m2 = cv2.initUndistortRectifyMap(K2, d2, r[1], r[2], (W, h), cv2.CV_32FC1)
    return dict(c=c, m1=m1, m2=m2, f=r[2][0, 0], cx=r[2][0, 2], cy=r[2][1, 2],
                B=float(np.linalg.norm(T)), d0=float(c.get('d0_px', 0.0)))


def disparita(L, R):
    kw = dict(minDisparity=0, numDisparities=256, blockSize=7, P1=8 * 49, P2=32 * 49,
              uniquenessRatio=10, speckleWindowSize=100, speckleRange=2, mode=cv2.STEREO_SGBM_MODE_HH)
    sl = cv2.StereoSGBM_create(**kw)
    dl = sl.compute(L, R).astype(np.float32) / 16
    # disparita' vista dalla destra: stesse immagini specchiate e scambiate (senza ximgproc)
    dr = cv2.flip(sl.compute(cv2.flip(R, 1), cv2.flip(L, 1)), 1).astype(np.float32) / 16
    # controllo sinistra-destra: il punto deve tornare a se stesso entro 1 px
    h, w = dl.shape
    xs = np.arange(w)[None, :].repeat(h, 0)
    xr = np.clip((xs - dl).round().astype(int), 0, w - 1)
    back = np.take_along_axis(dr, xr, 1)
    dl[(np.abs(back - dl) > 1) | (dr[np.arange(h)[:, None], xr] <= 0)] = -1
    dl[dl <= 0] = np.nan
    return dl


def scegli(L, d, S, n=8):
    """Angoli forti con disparita' stabile nel 7x7; uno per fascia di distanza e zona, al massimo n."""
    pts = cv2.goodFeaturesToTrack(L, 600, 0.02, 25, blockSize=7)
    cand = []
    for x, y in (pts.reshape(-1, 2) if pts is not None else []):
        x, y = int(x), int(y)
        w = d[max(0, y - 3):y + 4, max(0, x - 3):x + 4]
        if np.isnan(w).mean() > 0.2:
            continue
        dm = float(np.nanmedian(w))
        if np.nanstd(w) > 0.5 or dm - S['d0'] <= 1:
            continue
        # niente riflessi (saturato vicino) e intorno 15x15 coerente: un oggetto, non un bordo fra due piani
        if L[max(0, y - 7):y + 8, max(0, x - 7):x + 8].max() >= 235:
            continue
        w15 = d[max(0, y - 7):y + 8, max(0, x - 7):x + 8]
        if np.isnan(w15).mean() > 0.4 or abs(float(np.nanmedian(w15)) - dm) > 1:
            continue
        Z = S['f'] * S['B'] / (dm - S['d0'])
        X, Y = (x - S['cx']) * Z / S['f'], (y - S['cy']) * Z / S['f']
        cand.append(dict(x=x, y=y, d_px=round(dm, 2), Z_m=round(Z, 2),
                         dist_diretta_m=round(float(np.sqrt(X * X + Y * Y + Z * Z)), 2),
                         lato_m=round(X, 2), alto_m=round(-Y, 2), sd_px=round(float(np.nanstd(w)), 2)))
    fasce = [(0.5, 1.5), (1.5, 2.5), (2.5, 4), (4, 6), (6, 9), (9, 15)]
    h, w = L.shape
    scelti = []
    for lo, hi in fasce:
        in_f = sorted([c for c in cand if lo <= c['dist_diretta_m'] < hi], key=lambda c: c['sd_px'])
        for c in in_f:
            if all(abs(c['x'] - s['x']) > w / 6 or abs(c['y'] - s['y']) > h / 6 for s in scelti):
                scelti.append(c)
                if sum(lo <= s['dist_diretta_m'] < hi for s in scelti) >= 2:
                    break
    scelti = sorted(scelti, key=lambda c: c['dist_diretta_m'])[:n]
    for i, c in enumerate(scelti, 1):
        c['n'] = i
    return scelti


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('calib'); ap.add_argument('out')
    ap.add_argument('--host', default='192.168.1.122')
    ap.add_argument('--a'); ap.add_argument('--b')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    A = cv2.imread(a.a, 0) if a.a else grab(f'http://{a.host}:81/stream')
    B = cv2.imread(a.b, 0) if a.b else grab(f'http://{a.host}:82/b/stream')
    cv2.imwrite(os.path.join(a.out, 'A.jpg'), A); cv2.imwrite(os.path.join(a.out, 'B.jpg'), B)
    S = calib(a.calib, A.shape[0])
    L = cv2.remap(A, *S['m1'], cv2.INTER_LINEAR); R = cv2.remap(B, *S['m2'], cv2.INTER_LINEAR)
    d = disparita(L, R)
    P = scegli(L, d, S)
    img = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
    for p in P:
        cv2.circle(img, (p['x'], p['y']), 9, (0, 0, 255), 2)
        t = f"{p['n']}: {p['dist_diretta_m']:.2f} m"
        cv2.putText(img, t, (p['x'] + 12, p['y'] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(img, t, (p['x'] + 12, p['y'] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.imwrite(os.path.join(a.out, 'foto_metro.jpg'), img)
    json.dump(dict(calib=os.path.basename(a.calib), f_px=S['f'], B_m=S['B'], d0_px=S['d0'],
                   righe=int(A.shape[0]), quando=time.strftime('%Y-%m-%d %H:%M:%S'),
                   nota='distanza diretta = dal punto di mezzo fra le due lenti', punti=P),
              open(os.path.join(a.out, 'punti.json'), 'w'), indent=1)
    for p in P:
        print(f"{p['n']}: {p['dist_diretta_m']:.2f} m (Z {p['Z_m']:.2f}, lato {p['lato_m']:+.2f}, alto {p['alto_m']:+.2f}) px {p['x']},{p['y']}")


if __name__ == '__main__':
    main()
