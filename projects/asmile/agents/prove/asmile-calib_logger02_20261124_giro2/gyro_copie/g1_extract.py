"""Strada 1 (giroscopio) - passo 1: coppie di fotogrammi A (sinistra) vicine nel tempo, scelte dove l'IMU dice che la camera ruota
(1.5-20 gradi in 0.1-0.3 s), match SIFT L0-L1 puliti con F-RANSAC. Salva g1_matches.pkl (piccolo)."""
import os,sys,pickle,collections,numpy as np,cv2
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from common import *
BIAS=np.array([-1.04,0.48,-0.94])
def integ(X,t0,t1,bias=BIAS):
    """rotazione IMU (matrice) fra t0 e t1: prodotto di exp(w dt), w=giro-bias (dps)"""
    t=X[:,0]/1e6;i0=np.searchsorted(t,t0);i1=np.searchsorted(t,t1)
    R=np.eye(3)
    for i in range(i0,i1):
        w=np.radians(X[i,4:7]-bias);dt=(min(t[i+1],t1)-max(t[i],t0)) if i+1<len(t) else 0.02
        R=R@cv2.Rodrigues(w*max(dt,0))[0]
    return R
def candidates(DKs=(2,4)):
    P=pairs();T=np.array([p[0][0]/1e6 for p in P]);X=imu();out=[]
    for DK in DKs:
        for k in range(0,len(P)-DK,DK):
            t0,t1=T[k],T[k+DK]
            if not(0.09<t1-t0<0.32): continue
            if not(130<=t0<330 or 390<=t1<715): continue
            if P[k][0][1]!=P[k+DK][0][1]: continue   # stesso clip A (decodifica una volta)
            R=integ(X,t0,t1);ang=np.degrees(np.linalg.norm(cv2.Rodrigues(R)[0]))
            if 1.5<ang<20: out.append((k,k+DK,t0,t1,ang))
    return out
def work(args):
    clipname,lst=args
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher(cv2.NORM_L2);P=pairs();res=[]
    V=clip(clipname)
    for (k0,k1,t0,t1,ang) in lst:
        ims=[V[P[k][0][2]].copy() for k in (k0,k1)]
        m=np.zeros_like(ims[0]);m[10:-10,10:-10]=255
        F=[sift.detectAndCompute(im,m) for im in ims]
        if any(f[1] is None or len(f[0])<30 for f in F): continue
        ab=bf.knnMatch(F[0][1],F[1][1],k=2);ba=bf.knnMatch(F[1][1],F[0][1],k=1);a=[];b=[]
        for mm in ab:
            if len(mm)==2 and mm[0].distance<0.8*mm[1].distance and ba[mm[0].trainIdx][0].trainIdx==mm[0].queryIdx:
                a.append(F[0][0][mm[0].queryIdx].pt);b.append(F[1][0][mm[0].trainIdx].pt)
        if len(a)<30: continue
        a=np.array(a);b=np.array(b)
        try: Fm,inl=cv2.findFundamentalMat(a,b,cv2.USAC_MAGSAC,2.0,0.999,5000)
        except cv2.error: continue
        if Fm is None: continue
        inl=inl.ravel().astype(bool)
        if inl.sum()<30: continue
        res.append(dict(k0=k0,k1=k1,t0=t0,t1=t1,ang=ang,a=a[inl],b=b[inl]))
    return res
if __name__=='__main__':
    c=candidates();print('candidati',len(c),flush=True)
    P=pairs();rng=np.random.default_rng(0)
    # al massimo ~25 coppie per intervallo di 20 s, per bilanciare le scene
    c.sort(key=lambda r:r[2]);keep=[];bins=collections.defaultdict(list)
    for r in c: bins[int(r[2]//20)].append(r)
    for b,l in bins.items():
        idx=rng.permutation(len(l))[:25];keep+= [l[i] for i in idx]
    print('tenuti',len(keep))
    g=collections.OrderedDict()
    for r in keep: g.setdefault(P[r[0]][0][1],[]).append(r)
    with Pool(2) as p: out=p.map(work,list(g.items()))
    out=[x for o in out for x in o];out.sort(key=lambda r:r['k0'])
    print('coppie buone',len(out),'punti',sum(len(o['a']) for o in out))
    pickle.dump(out,open(os.path.join(W,'g1_matches.pkl'),'wb'))
