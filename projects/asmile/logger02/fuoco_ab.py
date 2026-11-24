"""Fuoco di una camera rispetto all'altra SULLO STESSO CONTENUTO (indipendente dalla scena), per i logger stereo.
Un fotogramma da A (:81/stream) e uno da B (:82/b/stream, UNA lettura breve: lo streaming lungo dalla B via proxy della A
la fa cadere), SIFT fra le due, gradiente normalizzato al contrasto su pezzetti 31x31 attorno a ogni corrispondenza.
Stampa A/B (1.00 = uguale; <0.9 A piu' morbida) totale, vicino/medio/lontano (dalla disparita') e per zona 3x3.
Uso: python3 logger02/fuoco_ab.py [host]   (24/11: A da 0.75 a 1.01 dopo la messa a fuoco)"""
import sys, time
import numpy as np, cv2
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/logger/depth/calib_rock/logger02_v2')
import foto_metro as F

H = 15


def energia(im, x, y):
    p = im[y - H:y + H + 1, x - H:x + H + 1].astype(np.float32)
    if p.shape != (2 * H + 1, 2 * H + 1) or p.std() <= 8:
        return None
    gx, gy = cv2.Sobel(p, cv2.CV_32F, 1, 0), cv2.Sobel(p, cv2.CV_32F, 0, 1)
    return float(np.sqrt((gx * gx + gy * gy).mean()) / p.std())


def main(host='192.168.1.122'):
    a = F.grab(f'http://{host}:81/stream', 1.5); time.sleep(0.5)
    b = F.grab(f'http://{host}:82/b/stream', 1.0)
    s = cv2.SIFT_create(4000)
    k1, d1 = s.detectAndCompute(a, None); k2, d2 = s.detectAndCompute(b, None)
    m = [x for x, y in cv2.BFMatcher().knnMatch(d1, d2, k=2) if x.distance < 0.75 * y.distance]
    r = []
    for x in m:
        (xa, ya), (xb, yb) = k1[x.queryIdx].pt, k2[x.trainIdx].pt
        ea, eb = energia(a, int(xa), int(ya)), energia(b, int(xb), int(yb))
        if ea and eb:
            r.append((xa, ya, xa - xb, ea / eb))
    r = np.array(r)
    h, w = a.shape
    print('punti confrontati', len(r), '| A/B mediana %.2f' % np.median(r[:, 3]))
    d = r[:, 2]; p33, p66 = np.percentile(d, [33, 66])
    for nome, msk in (('vicino', d > p66), ('medio', (d >= p33) & (d <= p66)), ('lontano', d < p33)):
        print(' %-8s %.2f (n %d)' % (nome, np.median(r[msk, 3]), msk.sum()))
    for j, yn in enumerate(('alto', 'centro', 'basso')):
        cel = []
        for i, xn in enumerate(('sx', 'centro', 'dx')):
            msk = (r[:, 0] // (w / 3) == i) & (r[:, 1] // (h / 3) == j)
            cel.append('%s %s(%d)' % (xn, '%.2f' % np.median(r[msk, 3]) if msk.sum() > 4 else ' -- ', msk.sum()))
        print(' %-6s ' % yn + '  '.join(cel))


if __name__ == '__main__':
    main(*sys.argv[1:])
