#!/usr/bin/env python3
# Stampa (a cadenza limitata) quando sterzo/ruota cambiano -> conferma quale si muove.
import time
last_s = last_w = None
last_print = 0.0
while True:
    try:
        s = int(open("/tmp/encoder_steer").read())
        w = int(open("/tmp/encoder_wheel").read())
    except Exception:
        time.sleep(0.2)
        continue
    now = time.time()
    moved = (last_s is None) or abs(s - last_s) >= 10 or abs(w - last_w) >= 10
    if moved and now - last_print > 1.0:
        ds = 0 if last_s is None else s - last_s
        dw = 0 if last_w is None else w - last_w
        print("steer=%d wheel=%d  (Dsterzo=%+d Druota=%+d)" % (s, w, ds, dw), flush=True)
        last_s, last_w, last_print = s, w, now
    time.sleep(0.05)
