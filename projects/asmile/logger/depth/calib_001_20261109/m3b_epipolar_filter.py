#!/usr/bin/env python3
"""m3b: tiene i frame con |dy_raw + 118.5| < 0.8 px (vincolo epipolare: scarta gli alias del pattern a scacchi). Uso: m3b IN.pkl (sovrascrive con la maschera 'ok')"""
import sys, pickle, numpy as np
M = pickle.load(open(sys.argv[1], 'rb'))
for m in M:
    m['ok'] = np.abs((m['b1'][:, 1] - m['b2'][:, 1]) + 118.5) < 0.8
pickle.dump(M, open(sys.argv[1], 'wb'))
