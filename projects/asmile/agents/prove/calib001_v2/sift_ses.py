import sys, json, numpy as np, cv2
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
from stereo_common import Calib
z = Calib.load(sys.argv[1]).rectify()
sift = cv2.SIFT_create(3000)
bf = cv2.BFMatcher()
rows = []
for SI,s in enumerate(["session_20261111_082437","session_20261111_083632","session_20261111_101400","session_20261111_102053"]):
    base = "asmile-loggers/asmile-001/" + s + "/"
    gl = C.gray_frames(base + "video_right.h264", 1280, 800)   # fisicamente sinistra
    gr = C.gray_frames(base + "video_left.h264", 1280, 800)
    for i, (a, b) in enumerate(zip(gl, gr)):
        if i % 60: continue
        A = cv2.remap(a, z["m1x"], z["m1y"], cv2.INTER_LINEAR); B = cv2.remap(b, z["m2x"], z["m2y"], cv2.INTER_LINEAR)
        ka, da = sift.detectAndCompute(A, None); kb, db = sift.detectAndCompute(B, None)
        if da is None or db is None: continue
        for m, n in bf.knnMatch(da, db, k=2):
            if m.distance < 0.7 * n.distance:
                pa, pb = ka[m.queryIdx].pt, kb[m.trainIdx].pt
                rows.append((pa[0], pa[1], pa[0] - pb[0], pb[1] - pa[1], SI))
r = np.array(rows); print("match totali", len(r))

dy=r[:,3]; dx=r[:,2]; k=(abs(dy)<3)&(dx>0.5)&(dx<300); r=r[k]
for si in range(4):
    m=r[:,4]==si
    if m.sum()<100: continue
    q=r[m]
    for nm,lo,hi in (("alto y<250",0,250),("mezzo",250,550),("basso y>550",550,800)):
        mm=(q[:,1]>=lo)&(q[:,1]<hi)&(q[:,0]>400)&(q[:,0]<880)
        print("sess",si,nm,int(mm.sum()),"dy med %+.3f"%np.median(q[mm,3]))
    # gradient: fit dy = a + b*y
    b=np.polyfit(q[:,1],q[:,3],1); print("sess",si,"dy vs y slope %.5f px/px (=> %.2f px su 800)"%(b[0],b[0]*800))
