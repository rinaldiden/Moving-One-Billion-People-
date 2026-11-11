import numpy as np
from t4 import *
per=[]
for tr in T:
    r=flowZ(REF,tr)
    if r is None: continue
    Zf,ok,t=r;u1,u2=proj(REF,tr['pi'],tr['pr']);d=u1[:,0]-u2[:,0];dy=u1[:,1]-u2[:,1];Zs=REF[3]*B/np.where(d>0.3,d,np.nan)
    g=ok&np.isfinite(Zs)&(abs(dy)<1.5)&(abs(t[2])>0.8)
    per.append(np.c_[Zf[g],Zs[g],tr['pi'][g,0],d[g]])
def fest(R,d0=0.0,lo=4,hi=15):
    m=(R[:,0]>lo)&(R[:,0]<hi);return np.median((R[m,3]-d0)*R[m,0])/B
rng=np.random.default_rng(2)
allR=np.vstack(per);print('f(ratio, d0=0)',fest(allR),'ref',REF[3])
for n in (115,60,30,15,8):
    v=[fest(np.vstack([per[i] for i in rng.choice(len(per),n)])) for _ in range(150)]
    print(n,'coppie  f med',round(np.median(v)),'sd %.1f%%'%(100*np.std(v)/REF[3]),' (bias %.1f%%)'%(100*(np.median(v)/REF[3]-1)))
# d0 da fit a intercetta con f vincolata dal rapporto: d = fB/Zf + c  -> c = median(d - fB/Zf)
for n in (115,30):
    v=[]
    for _ in range(150):
        R=np.vstack([per[i] for i in rng.choice(len(per),n)]);m=(R[:,0]>3)&(R[:,0]<15)
        f=fest(R);v.append(np.median(R[m,3]-f*B/R[m,0]))
    print('d0 via mediana residui',n,'coppie: med %.2f sd %.2f px'%(np.median(v),np.std(v)))
print('--- selezione per disparita (pulita) ---')
def fest2(R,lo=12,hi=45):
    m=(R[:,3]>lo)&(R[:,3]<hi)&(R[:,0]>1)&(R[:,0]<100);return np.median(R[m,3]*R[m,0])/B
for lo,hi in((8,20),(12,45),(20,60),(30,80)):
    print('d',lo,hi,'f=',round(fest2(allR,lo,hi)),'bias %.1f%%'%(100*(fest2(allR,lo,hi)/REF[3]-1)))
for n in (115,60,30,15):
    v=[fest2(np.vstack([per[i] for i in rng.choice(len(per),n)]),12,45) for _ in range(150)]
    print(n,'coppie f med',round(np.median(v)),'sd %.1f%% bias %.1f%%'%(100*np.std(v)/REF[3],100*(np.median(v)/REF[3]-1)))
# d0 con selezione per disparita
def d0est(R,f):
    m=(R[:,3]>6)&(R[:,3]<45)&(R[:,0]>1)&(R[:,0]<100);return np.median(R[m,3]-f*B/R[m,0])
f=fest2(allR);print('d0',d0est(allR,f))
