#!/usr/bin/env python3
"""m4: match SIFT L<->R su frame IN MOVIMENTO (spinta 093909 + giro 094146), mai usati nel fit. Uso: m4 MP4DIR OUT.pkl"""
import sys, cv2, numpy as np, pickle
d, out = sys.argv[1], sys.argv[2]
sift = cv2.SIFT_create(4000); bf = cv2.BFMatcher(); res = {}
for sid, n in (('093909', 40), ('094146', 80)):
    cL = cv2.VideoCapture(f'{d}/s{sid}_right.mp4'); cR = cv2.VideoCapture(f'{d}/s{sid}_left.mp4')   # L = fisica sinistra (file *_right)
    N = int(min(cL.get(7), cR.get(7))); P1 = []; P2 = []
    for i in np.linspace(5, N - 5, n).astype(int):
        cL.set(1, int(i)); cR.set(1, int(i)); a, fa = cL.read(); b, fb = cR.read()
        if not (a and b): continue
        L = cv2.cvtColor(fa, cv2.COLOR_BGR2GRAY); R = cv2.cvtColor(fb, cv2.COLOR_BGR2GRAY)
        k1, d1 = sift.detectAndCompute(L, None); k2, d2 = sift.detectAndCompute(R, None)
        m = [x for x, y in bf.knnMatch(d1, d2, k=2) if x.distance < 0.7 * y.distance]
        if len(m) < 20: continue
        p1 = np.float32([k1[x.queryIdx].pt for x in m]); p2 = np.float32([k2[x.trainIdx].pt for x in m])
        _, inl = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.999)
        if inl is None: continue
        i = inl.ravel() > 0; P1.append(p1[i]); P2.append(p2[i])
    res[sid] = (np.vstack(P1), np.vstack(P2)); print(sid, len(res[sid][0]), 'match')
pickle.dump(res, open(out, 'wb'))
