"""Fuoco in diretta di UNA camera (A di default, senza proxy della B): larghezza bordi 10-90% in px, piu' basso = piu' nitido.
Si gira piano la ghiera guardando il numero; si tiene il minimo. Uso: python3 logger02/fuoco_live.py [A|B] [secondi] [host]"""
import sys, time, urllib.request
import numpy as np, cv2

# 24/11 (Daniele: "che non capiti piu'"): lo streaming lungo fa cadere la A, e la B passa dal proxy della A (peggio).
# Questo strumento resta solo per la A e solo con --so-cosa-faccio; per il fuoco usa larghezza_bordi.py su UNA foto.
if '--so-cosa-faccio' not in sys.argv:
    sys.exit("BLOCCATO: niente streaming lungo su logger02 (fa cadere la connessione). Usa: python3 logger02/larghezza_bordi.py --live A")
if 'B' in sys.argv[1:2] or ('nitidezza' in __file__):
    sys.exit("BLOCCATO: niente streaming della B attraverso la A")
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from larghezza_bordi import larghezze

CAM = sys.argv[1] if len(sys.argv) > 1 else 'A'
SEC = float(sys.argv[2]) if len(sys.argv) > 2 else 300
HOST = sys.argv[3] if len(sys.argv) > 3 else '192.168.1.122'
url = f'http://{HOST}:81/stream' if CAM == 'A' else f'http://{HOST}:82/b/stream'
best, t0, buf = 99.0, time.time(), b''
print(f'FUOCO camera {CAM}: numero piu BASSO = piu NITIDO (a fuoco ~2,0-2,5). Gira piano, fermati al minimo.\n')
def mostra(im, m):
    v = cv2.cvtColor(cv2.resize(im, (960, 600)), cv2.COLOR_GRAY2BGR)
    col = (0, 200, 0) if m <= best + 0.13 else (0, 0, 255)
    cv2.rectangle(v, (0, 0), (960, 120), (0, 0, 0), -1)
    cv2.putText(v, f'{CAM}  {m:4.2f} px', (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 3, col, 6)
    cv2.putText(v, f'migliore {best:4.2f}', (620, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    cv2.imshow('fuoco ' + CAM + ' (basso = nitido)', v)
    return cv2.waitKey(1) == 27


esc = False
while time.time() - t0 < SEC and not esc:
    try:                                     # il logger puo' cadere: si riconnette da solo
        with urllib.request.urlopen(url, timeout=8) as r:
            while time.time() - t0 < SEC and not esc:
                buf += r.read(65536)
                j = buf.rfind(b'\xff\xd9'); i = buf.rfind(b'\xff\xd8', 0, j) if j > 0 else -1
                if i < 0:
                    continue
                im = cv2.imdecode(np.frombuffer(buf[i:j + 2], np.uint8), cv2.IMREAD_GRAYSCALE); buf = b''
                if im is None:
                    continue
                w = larghezze(im, n_max=1200)
                if len(w) < 100:
                    print('   pochi bordi (mano davanti?)', flush=True); continue
                m = float(np.median(w[:, 2])); best = min(best, m)
                print(f'{time.time() - t0:5.0f}s   {m:4.2f} px   migliore finora {best:4.2f}', flush=True)
                esc = mostra(im, m)
    except Exception as e:
        print('   logger non raggiungibile, riprovo...', type(e).__name__, flush=True)
        buf = b''
        time.sleep(2)
