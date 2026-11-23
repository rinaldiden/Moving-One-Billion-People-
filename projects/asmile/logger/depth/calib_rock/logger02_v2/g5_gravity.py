"""Strada 1 - passo 5: scala del giroscopio dall'ACCELEROMETRO (indipendente dalla camera). Fra due finestre quasi-ferme la direzione della gravita'
(accelerometro, indipendente dalla scala) cambia di un angolo noto; il giro integrato la deve riprodurre. Si stimano le scale per asse IMU
(s_x,s_y,s_z) dei soli assi con inclinazione (y,z: x e' verticale a bici dritta). Cosi' si separa scala-giro da focale nella Strada 1."""
import os,sys,numpy as np,cv2
from scipy.optimize import least_squares
sys.path.insert(0,os.path.dirname(__file__))
from common import *
BIAS=np.array([-1.0,0.85,-0.94])
X=imu();t=X[:,0]/1e6;acc=X[:,1:4];gy=X[:,4:7]
# finestre statiche da 0.6 s
w=30;wins=[]
for i in range(0,len(X)-w,10):
    a=acc[i:i+w];g=gy[i:i+w]-BIAS
    if a.std(0).max()<0.012 and np.abs(g).max()<1.5 and abs(np.linalg.norm(a.mean(0))-1.027)<0.03: wins.append((i,i+w,a.mean(0)))
print('finestre statiche',len(wins))
eps=[]
for wi in wins:
    if eps and wi[0]-eps[-1][-1][0]<=12: eps[-1].append(wi)
    else: eps.append([wi])
eps=[(e[0][0],e[-1][1],np.mean([x[2] for x in e],0)) for e in eps if len(e)>=2]
print('episodi statici',len(eps))
pairs_=[]
for a_,b_ in zip(eps[:-1],eps[1:]):
    gap=t[b_[0]]-t[a_[1]]
    if 0.3<gap<12.0:
        u0=a_[2]/np.linalg.norm(a_[2]);u1=b_[2]/np.linalg.norm(b_[2]);ang=np.degrees(np.arccos(np.clip(u0@u1,-1,1)))
        if ang>1.2: pairs_.append(((a_[0],a_[1],a_[2]),(b_[0],b_[1],b_[2]),ang))
print('transizioni con cambio di gravita >1.2 gradi',len(pairs_),'angoli',np.round([p[2] for p in pairs_],1)[:30])
def rot(i0,i1,s):
    R=np.eye(3)
    for i in range(i0,i1):
        dt=(t[i+1]-t[i]);R=R@cv2.Rodrigues(np.radians((gy[i]-BIAS)*s)*dt)[0]
    return R
def resid(s):
    out=[]
    for a,b,ang in pairs_:
        R=rot(a[1],b[0],s);u0=a[2]/np.linalg.norm(a[2]);u1=b[2]/np.linalg.norm(b[2]);pred=R.T@u0
        out.append(np.degrees(np.arccos(np.clip(pred@u1,-1,1))))
    return np.array(out)
if len(pairs_)>=2:
    print('errore predetto-misurato con scala 1: med %.2f deg (su angoli med %.1f)'%(np.median(resid(np.ones(3))),np.median([p[2] for p in pairs_])))
    def f(s): return resid(np.r_[1.0,s]) # s_x non osservabile: fisso 1
    r=least_squares(f,[1,1],diff_step=1e-3,x_scale=0.02,loss='soft_l1',f_scale=1.0);print('scale giro IMU y,z (gravita):',r.x.round(3),'err med',np.median(f(r.x)).round(2))
    rng=np.random.default_rng(0);bs=[]
    base=pairs_
    for _ in range(25):
        idx=rng.integers(0,len(base),len(base));pairs_[:]=[base[i] for i in idx]
        bs.append(least_squares(f,[1,1],diff_step=1e-3,x_scale=0.02,loss='soft_l1',f_scale=1.0).x)
    pairs_[:]=base;print('bootstrap sd',np.std(bs,0).round(3),'media',np.mean(bs,0).round(3))
