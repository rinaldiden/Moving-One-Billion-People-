"""Nitidezza in diretta di A e B di logger02 (varianza del Laplaciano al centro), per mettere a fuoco una camera.
Uso: python3 logger02/nitidezza_live.py [secondi] [host]  -> una riga ogni ~0,5 s: A, B e rapporto A/B."""
import sys, time, threading, urllib.request
import numpy as np, cv2

BOUND = b'--123456789000000000000987654321'
SEC = float(sys.argv[1]) if len(sys.argv) > 1 else 20
HOST = sys.argv[2] if len(sys.argv) > 2 else '192.168.1.122'
ultimo = {}


def leggi(nome, url):
    buf = b''
    with urllib.request.urlopen(url, timeout=8) as r:
        t0 = time.time()
        while time.time() - t0 < SEC + 2:
            buf += r.read(32768)
            while True:
                i = buf.find(b'\xff\xd8'); j = buf.find(b'\xff\xd9', i + 2)
                if i < 0 or j < 0:
                    break
                im = cv2.imdecode(np.frombuffer(buf[i:j + 2], np.uint8), cv2.IMREAD_GRAYSCALE)
                buf = buf[j + 2:]
                if im is not None:
                    h, w = im.shape
                    c = im[h // 4:3 * h // 4, w // 4:3 * w // 4]
                    ultimo[nome] = cv2.Laplacian(c, cv2.CV_64F).var()


for n, u in (('A', f'http://{HOST}:81/stream'), ('B', f'http://{HOST}:82/b/stream')):
    threading.Thread(target=leggi, args=(n, u), daemon=True).start()
t0 = time.time()
while time.time() - t0 < SEC:
    time.sleep(0.5)
    a, b = ultimo.get('A'), ultimo.get('B')
    if a and b:
        print(f'{time.time() - t0:5.1f}s  A {a:6.0f}  B {b:6.0f}  A/B {a / b:4.2f}', flush=True)
