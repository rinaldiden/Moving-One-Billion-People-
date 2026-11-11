import numpy as np, pandas as pd, cv2, pickle, sys
from core import *
A='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/asmile-001/'
fr=pd.read_csv(A+'session_20261109_094146/frames_right.csv'); cum=np.load('cum.npy')
g=pd.read_csv(A+'_sensors/sensors/sensors_20261109_085334.csv',usecols=['t_ms','gps_speed_ms']).dropna()
tt=fr.t_ms.values; gs=np.interp(tt,g.t_ms,g.gps_speed_ms); dist_gps=np.sum(gs[:-1]*np.diff(tt)/1000)
s_gps=dist_gps/(cum[-1]-cum[0]); print('GPS dist',dist_gps,'m/tick',s_gps)
# scelta coppie
sp=np.gradient(cum,tt/1000.)*s_gps   # m/s
pairs=[]
i=40
while i<len(tt)-60:
    if sp[i]>2.0:
        j=i+1
        while j<len(tt)-1 and (cum[j]-cum[i])*s_gps<1.0: j+=1
        if (j-i)<=30: pairs.append((i,j,(cum[j]-cum[i])*s_gps))
        i+=45
    else: i+=10
print('pairs',len(pairs)); need=set();[need.update([a,b]) for a,b,_ in pairs]
cL=cv2.VideoCapture(A+'session_20261109_094146_right.h264');cR=cv2.VideoCapture(A+'session_20261109_094146_left.h264')
fL={};fR={};k=0;pi={a for a,_,_ in pairs}
while True:
    a=cL.grab();b=cR.grab()
    if not(a and b):break
    if k in need:
        fL[k]=cv2.cvtColor(cL.retrieve()[1],cv2.COLOR_BGR2GRAY)
        if k in pi: fR[k]=cv2.cvtColor(cR.retrieve()[1],cv2.COLOR_BGR2GRAY)
    k+=1
sift=cv2.SIFT_create(3000);bf=cv2.BFMatcher()
def feat(im): return sift.detectAndCompute(im,None)
def mt(k1,d1,k2,d2):
    m=[x for x,y in bf.knnMatch(d1,d2,k=2) if x.distance<0.75*y.distance]
    return {x.queryIdx:x.trainIdx for x in m}
out=[]
for (i,j,dl) in pairs:
    if i not in fL or j not in fL or i not in fR: continue
    ki,di=feat(fL[i]);kj,dj=feat(fL[j]);kr,dr=feat(fR[i])
    if di is None or dj is None or dr is None: continue
    mj=mt(ki,di,kj,dj);mr=mt(ki,di,kr,dr)
    idx=[q for q in mj if q in mr]
    if len(idx)<40: continue
    pi_=np.float64([ki[q].pt for q in idx]);pj=np.float64([kj[mj[q]].pt for q in idx]);pr=np.float64([kr[mr[q]].pt for q in idx])
    out.append(dict(i=i,j=j,dl=dl,pi=pi_,pj=pj,pr=pr))
print('usable pairs',len(out));pickle.dump(out,open('triples.pkl','wb'))
pickle.dump(dict(s_gps=s_gps),open('sgps.pkl','wb'))
