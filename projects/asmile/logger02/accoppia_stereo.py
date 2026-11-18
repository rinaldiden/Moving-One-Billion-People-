#!/usr/bin/env python3
"""
accoppia_stereo.py — logger HW3 (A+B): dai video delle due schede a UN video stereo affiancato (SBS 2560x720),
coppia per coppia, pronto per la calibrazione (logger/depth/calib_charuco.py --video ... --size 1280x720 --no-flip).

Ogni scheda registra i suoi pezzi da 60 s: clip_<sess>_<A|B>_NNNNN.h264 + _frames.csv (frame, t_us, t_a_us, bytes).
Il numero di fotogramma è comune alle due schede e t_a_us è l'ora della A per entrambe: una coppia è buona se il
numero è uguale E |t_a(B) - t_a(A)| è sotto --max-us (18/11: ~20% delle coppie aveva il numero sfasato di secondi).

Scarica SEMPRE ognuna dalla sua scheda (A dal suo IP, B dal suo): passare dalla A per i file della B la fa crashare.

Uso:
  python3 logger02/accoppia_stereo.py                       # ultimi 2 pezzi completi di A e B → SBS
  python3 logger02/accoppia_stereo.py --pezzi 3 --out calib_logger02.mp4
  python3 logger02/accoppia_stereo.py --solo-locale DIR     # file già scaricati in DIR
Uscita: <out>.mp4 (SBS: sinistra = A, destra = B) + <out>_coppie.csv (frame, t_a_us A, differenza B-A in µs).
"""
import argparse, csv, glob, json, os, re, subprocess, sys, urllib.request
import numpy as np

W, H = 1280, 720


def get(url, dest=None, timeout=300):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = r.read()
    if dest:
        open(dest, "wb").write(data)
    return data


from datetime import datetime, timedelta


def ora_pezzo(nome):
    """clip_<YYYYmmdd_HHMMSS>_<A|B>_<NNNNN>.h264 -> (inizio, fine) in ora vera; None se la sessione è bootNNNN"""
    m = re.match(r"clip_(\d{8}_\d{6})_[AB]_(\d{5})\.h264$", nome)
    if not m:
        return None
    t0 = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S") + timedelta(seconds=60 * int(m.group(2)))
    return t0, t0 + timedelta(seconds=60)


def scarica(host, lettera, pezzi, cartella, finestra=None):
    """Pezzi completi (h264 + frames.csv) di una scheda.
    A: gli ultimi `pezzi` della sessione più recente. B: i pezzi che cadono nella finestra di ora vera della A.
    (18/11: i numeri di fotogramma e t_a ripartono quando una scheda si riavvia: mai mischiare sessioni diverse.)"""
    files = json.loads(get(f"http://{host}/api/files", timeout=15))
    nomi = {f["nome"]: f["byte"] for f in files}
    clip = [n for n, b in nomi.items() if n.startswith("clip_") and f"_{lettera}_" in n and n.endswith(".h264")
            and b > 100000 and nomi.get(n[:-5] + "_frames.csv", 0) > 0 and ora_pezzo(n)]
    if finestra is None:
        sess = max(n.split("_")[1] + "_" + n.split("_")[2] for n in clip)
        scelti = sorted(n for n in clip if sess in n)[-pezzi:]
    else:
        a0, a1 = finestra
        scelti = sorted(n for n in clip if ora_pezzo(n)[1] > a0 - timedelta(seconds=30) and ora_pezzo(n)[0] < a1 + timedelta(seconds=30))
    if not scelti:
        sys.exit(f"{lettera}: nessun pezzo completo su {host}")
    for n in scelti:
        for f in (n, n[:-5] + "_frames.csv"):
            d = os.path.join(cartella, f)
            if not os.path.exists(d) or os.path.getsize(d) != nomi[f]:
                print(f"  {lettera} ← {f} ({nomi[f] / 1e6:.1f} MB)")
                get(f"http://{host}/dl?f={f}", d)
    return [os.path.join(cartella, n) for n in scelti]


def leggi(h264s):
    """frame -> (file, indice nel file, t_a_us), solo dai pezzi scelti"""
    m = {}
    for h264 in h264s:
        for i, r in enumerate(csv.DictReader(open(h264[:-5] + "_frames.csv"))):
            m[int(r["frame"])] = (h264, i, int(r["t_a_us"]))
    return m


def fotogrammi(h264):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", h264, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    n = len(p.stdout) // (W * H)
    return np.frombuffer(p.stdout[:n * W * H], np.uint8).reshape(n, H, W)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--a", default="192.168.1.122", help="IP della scheda A")
    ap.add_argument("--b", default="192.168.1.124", help="IP della scheda B (diretto, non /b)")
    ap.add_argument("--pezzi", type=int, default=2, help="ultimi N pezzi completi da 60 s")
    ap.add_argument("--max-us", type=float, default=1000, help="scarto massimo A-B per tenere la coppia")
    ap.add_argument("--dir", default=os.path.expanduser("~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02_stereo"))
    ap.add_argument("--solo-locale", metavar="DIR", help="non scaricare: usa i file in DIR")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cart = a.solo_locale or a.dir
    os.makedirs(cart, exist_ok=True)
    if a.solo_locale:
        ha = sorted(glob.glob(os.path.join(cart, "clip_*_A_*.h264"))); hb = sorted(glob.glob(os.path.join(cart, "clip_*_B_*.h264")))
    else:
        ha = scarica(a.a, "A", a.pezzi, cart)
        oa = [ora_pezzo(os.path.basename(h)) for h in ha]
        hb = scarica(a.b, "B", 0, cart, finestra=(min(x[0] for x in oa), max(x[1] for x in oa)))
    fa, fb = leggi(ha), leggi(hb)
    comuni = sorted(set(fa) & set(fb))
    buone = [f for f in comuni if abs(fb[f][2] - fa[f][2]) <= a.max_us]
    d = np.array([fb[f][2] - fa[f][2] for f in buone], float)
    print(f"fotogrammi A {len(fa)}, B {len(fb)}, stesso numero {len(comuni)}, coppie buone (<{a.max_us:.0f} µs) {len(buone)}")
    if not buone:
        sys.exit("nessuna coppia buona")
    ad = np.abs(d)
    print(f"sincronia coppie buone: mediana {np.median(ad):.0f} µs, 95% < {np.percentile(ad, 95):.0f} µs, max {ad.max():.0f} µs")

    out = a.out or os.path.join(cart, "stereo_logger02.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{2 * W}x{H}",
                            "-r", "16.67", "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", out],
                           stdin=subprocess.PIPE)
    cache = {}
    def fr(m, f):
        h264, i, _ = m[f]
        if h264 not in cache:
            if len(cache) > 4:
                cache.pop(next(iter(cache)))
            cache[h264] = fotogrammi(h264)
        v = cache[h264]
        return v[i] if i < len(v) else None
    righe, scritte = [], 0
    for f in buone:
        l, r = fr(fa, f), fr(fb, f)
        if l is None or r is None:
            continue
        enc.stdin.write(np.hstack([l, r]).tobytes())
        righe.append((f, fa[f][2], fb[f][2] - fa[f][2]))
        scritte += 1
    enc.stdin.close(); enc.wait()
    with open(out.rsplit(".", 1)[0] + "_coppie.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["frame", "t_a_us", "b_meno_a_us"]); w.writerows(righe)
    print(f"→ {out} ({scritte} coppie SBS {2 * W}x{H}, sinistra=A destra=B)")
    print(f"calibrazione: python3 logger/depth/calib_charuco.py --video {out} --size {W}x{H} --no-flip --out calib_logger02.json")


if __name__ == "__main__":
    main()
