import sys, json, numpy as np, cv2
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
z = np.load("logger/depth/calib_asmile-001.CANDIDATO.maps.npz")
sift = cv2.SIFT_create(3000)
bf = cv2.BFMatcher()
rows = []
for s in ["session_20261111_082437", "session_20261111_083054", "session_20261111_083632"]:
    base = "asmile-loggers/asmile-001/" + s + "/"
    gl = C.gray_frames(base + "video_right.h264", 1280, 800)   # fisicamente sinistra
    gr = C.gray_frames(base + "video_left.h264", 1280, 800)
    for i, (a, b) in enumerate(zip(gl, gr)):
        if i % 45: continue
        A = cv2.remap(a, z["m1x"], z["m1y"], cv2.INTER_LINEAR); B = cv2.remap(b, z["m2x"], z["m2y"], cv2.INTER_LINEAR)
        ka, da = sift.detectAndCompute(A, None); kb, db = sift.detectAndCompute(B, None)
        if da is None or db is None: continue
        for m, n in bf.knnMatch(da, db, k=2):
            if m.distance < 0.7 * n.distance:
                pa, pb = ka[m.queryIdx].pt, kb[m.trainIdx].pt
                rows.append((pa[0], pa[1], pa[0] - pb[0], pb[1] - pa[1], i))
r = np.array(rows); print("match totali", len(r))
dy = r[:, 3]; dx = r[:, 2]
print("dy mediana grezza %.3f, |dy|<1: %.1f%%, |dy|<3: %.1f%%" % (np.median(dy), 100*np.mean(abs(dy)<1), 100*np.mean(abs(dy)<3)))
k = (abs(dy) < 3) & (dx > 0.5) & (dx < 300)
r = r[k]; print("tenuti", len(r))
zx = np.minimum((r[:,0] // (1280/3)).astype(int), 2); zy = np.minimum((r[:,1] // (800/3)).astype(int), 2)
names = ["alto-sx","alto-c","alto-dx","mezzo-sx","centro","mezzo-dx","basso-sx","basso-c","basso-dx"]
for zi in range(9):
    m = (zy*3+zx) == zi
    if m.sum() < 20: print(names[zi], "n", int(m.sum()), "INSUFF"); continue
    d = r[m, 3]; 
    print("%-9s n %5d  dy med %+.3f  |dy-med| p50 %.3f p95 %.3f  |dy| p95 %.3f" % (names[zi], m.sum(), np.median(d), np.median(abs(d-np.median(d))), np.percentile(abs(d-np.median(d)),95), np.percentile(abs(d),95)))
# dy medio in funzione di x e y
for nm, col, edges in (("x", 0, [0,200,400,640,880,1080,1280]), ("y", 1, [0,150,300,450,600,800])):
    print("dy mediano per fascia", nm, [(edges[j], int(((r[:,col]>=edges[j])&(r[:,col]<edges[j+1])).sum()), round(float(np.median(r[(r[:,col]>=edges[j])&(r[:,col]<edges[j+1]),3])),3)) for j in range(len(edges)-1)])
