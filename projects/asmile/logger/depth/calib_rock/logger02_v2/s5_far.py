"""Controllo d0 / convergenza senza metro: punti LONTANISSIMI (colline della Valtellina, km) hanno disparita' vera ~ 0: la disparita' misurata
in rettificato su quei punti = d0 residuo (indipendente da targhe, rigidita', focale). Match SIFT L-R sulle zone alte con collina visibile."""
import os,sys,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from rect import *
def far_disp(S,P,T,ts,ymax,xr=(0,1280),B_ref=None):
    sift=cv2.SIFT_create(nfeatures=1500,contrastThreshold=0.01);bf=cv2.BFMatcher();out=[]
    for t in ts:
        k=int(np.argmin(abs(T-t)));ra,rb=rectpair(S,P,k);m=np.zeros_like(ra);m[8:ymax,xr[0]:xr[1]]=255
        ka,da=sift.detectAndCompute(ra,m);kb,db=sift.detectAndCompute(rb,m)
        if da is None or db is None or len(ka)<10 or len(kb)<10: continue
        mt=bf.knnMatch(da,db,k=2);bk=bf.knnMatch(db,da,k=1)
        for q in mt:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and bk[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                a=ka[q[0].queryIdx].pt;b=kb[q[0].trainIdx].pt
                if abs(a[1]-b[1])<1.0: out.append((t,a[0],a[1],a[0]-b[0]))
    return np.array(out)
if __name__=='__main__':
    S=load();P=pairs();T=np.array([p[0][0]/1e6 for p in P])
    for name,ts,ymax in (('collina 757-764',np.arange(757,764.5,0.25),140),('collina 835-838',np.arange(835,839,0.25),120),('collina 845-847',np.arange(845,848,0.25),120)):
        r=far_disp(S,P,T,ts,ymax)
        if len(r)==0: print(name,'nessun punto');continue
        d=r[:,3];print(name,'n',len(d),'frames',len(np.unique(r[:,0])),'disp: p10 %.2f med %.2f p90 %.2f'%tuple(np.percentile(d,[10,50,90])))
        h,e=np.histogram(d,bins=np.arange(-8,14,1.0));print('   ',list(zip(e[:-1].astype(int),h)))
