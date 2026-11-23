"""Strada 1 - passo 3: stima congiunta sf (focale), correzione di R_imu->cam (3 gradi di liberta'), offset temporale IMU-video,
scale per asse del giro (stessa per tutti i punti). Controlli: sottoinsiemi per scena/blocchi alterni, bootstrap per coppie."""
import os,sys
sys.path.insert(0,os.path.dirname(__file__))
from g2_scan import *
from scipy.optimize import least_squares,minimize_scalar
def Rc_of(w): return cv2.Rodrigues(np.asarray(w).reshape(3,1))[0]@Rc0
def scan(Ms,Rc,**kw):
    sfs=np.linspace(0.9,1.25,15);v=np.array([total(s,Ms,Rc=Rc,**kw)[0] for s in sfs]);i=int(np.argmin(v))
    if 0<i<len(sfs)-1:
        a,b,c=v[i-1],v[i],v[i+1];sf=sfs[i]+0.5*(a-c)/(a-2*b+c)*(sfs[1]-sfs[0])
    else: sf=sfs[i]
    return sf,v
def joint(Ms,x0=(1.05,0,0,0),dt=0.0,rmax=None,bias=BIAS):
    def f(x):
        Rc=Rc_of(x[1:4]);v=[pair_cost(m,x[0],Rc,dt=dt,rmax=rmax,bias=bias) for m in Ms];return np.array([np.sqrt(q) for q in v if q is not None])
    s=least_squares(f,x0,x_scale=[0.03,0.01,0.01,0.01],diff_step=1e-3,max_nfev=25);return s.x,float(np.mean(s.fun**2))
if __name__=='__main__':
    T=np.array([m['t0'] for m in M])
    print('--- Rc fisso (v5): sf per scena/intervallo')
    for lo,hi in((0,450),(450,700),(700,880),(880,1420),(150,880),(0,1420)):
        Ms=[m for m in M if lo<=m['t0']<hi]
        if len(Ms)<15: print(lo,hi,'pochi',len(Ms));continue
        sf,v=scan(Ms,Rc0);print(lo,hi,len(Ms),'sf %.3f  cost min %.3f (a sf=1: %.3f)'%(sf,v.min(),total(1.0,Ms,Rc=Rc0)[0]))
    print('--- offset temporale (tutti, Rc fisso)')
    for dt in (-0.04,-0.02,-0.01,0,0.01,0.02,0.04):
        sf,v=scan(M,Rc0,dt=dt);print('dt',dt,'sf %.3f cost %.3f'%(sf,v.min()))
    print('--- raggio max (centro) Rc fisso')
    for rm in (300,450,600,2000):
        sf,v=scan(M,Rc0,rmax=rm);print('rmax',rm,'sf %.3f cost %.3f'%(sf,v.min()))
    print('--- congiunto sf+Rc (blocchi alterni di 15 coppie: train/test)')
    idx=np.arange(len(M));blk=(idx//15)%2;tr=[M[i] for i in idx if blk[i]==0];te=[M[i] for i in idx if blk[i]==1]
    x,c=joint(tr);print('train x',x.round(4),'cost %.3f'%c)
    Rt=Rc_of(x[1:4]);print('  TEST: sf %.3f cost con x train %.3f | con sf=1,Rc0 %.3f | solo sf (Rc0) %.3f'%(x[0],total(x[0],te,Rc=Rt)[0],total(1.0,te,Rc=Rc0)[0],total(scan(te,Rc0)[0],te,Rc=Rc0)[0]))
    x2,c2=joint(te);print('test-fit x',x2.round(4),'cost %.3f'%c2)
    xa,ca=joint(M);print('ALL x',xa.round(4),'cost %.3f'%ca,'(rotazione corr deg',np.degrees(np.linalg.norm(xa[1:4])).round(2),')')
    pickle.dump(dict(xa=xa),open(os.path.join(W,'g3_all.pkl'),'wb'))
    rng=np.random.default_rng(3);bs=[]
    for _ in range(30):
        ii=rng.integers(0,len(M),len(M));x,_=joint([M[i] for i in ii],x0=xa);bs.append(x[0])
    print('bootstrap sf: media %.3f sd %.3f p5-p95 %.3f-%.3f'%(np.mean(bs),np.std(bs),*np.percentile(bs,[5,95])))
