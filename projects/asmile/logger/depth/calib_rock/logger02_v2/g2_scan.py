"""Strada 1 - passo 2: focale dal giroscopio. Per ogni coppia: R_rel(camera) da IMU (+bias dei fermi) con R_imu->cam v5; la traslazione e'
ricavata in forma chiusa (t perpendicolare a (R x0)xx1). Costo = Sampson in pixel (trimmed). Scansione del fattore sf sulla focale
(x_norm/sf dopo la correzione della lente). Il giroscopio da' la scala: sf ~ 1/scala_giro  (limite = tolleranza di sensibilita' MPU6050)."""
import os,sys,json,pickle,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from g1_extract import integ,BIAS
c=json.load(open(CALIB));K=np.array(c['K_left']);dist=np.array(c['dist_left']);F0=c['focal_rect_px']
Rc0=np.array(json.load(open(IMUJ))['R_imu_to_cam_raw_A'])
M=pickle.load(open(os.path.join(W,'g1_matches.pkl'),'rb'));X=imu()
def undist(p): return cv2.undistortPointsIter(p.reshape(-1,1,2).astype(np.float64),K,dist,None,None,(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,40,1e-10)).reshape(-1,2)
for m in M:
    m['xa']=undist(m['a']);m['xb']=undist(m['b']);m['r']=np.hypot(*(m['a']-[K[0,2],K[1,2]]).T)
def sampson_t(x0,x1,R,sf,rmax=None,rm=None):
    a=np.c_[x0/sf,np.ones(len(x0))];b=np.c_[x1/sf,np.ones(len(x1))]
    Ra=a@R.T;C=np.cross(Ra,b)
    w=np.ones(len(a))
    for _ in range(4):
        t=np.linalg.svd(C*w[:,None],full_matrices=False)[2][-1]
        e=C@t   # = x1.(t x Rx0)
        # Sampson
        tx=np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]]);E=tx@R
        Ex0=a@E.T;Etx1=b@E;den=np.sqrt(Ex0[:,0]**2+Ex0[:,1]**2+Etx1[:,0]**2+Etx1[:,1]**2)
        s=np.sum(b*Ex0,1)/den
        w=1/np.sqrt(1+(s*F0/1.5)**2)
    return np.abs(s)*F0
def pair_cost(m,sf,Rc,rot_sign=1,dt=0.0,rmax=None,bias=BIAS):
    key=(round(dt,4),tuple(np.round(bias,3)))
    cache=m.setdefault('_c',{})
    if key not in cache: cache[key]=integ(X,m['t0']+dt,m['t1']+dt,bias)
    Rg=cache[key]
    if rot_sign<0: Rg=Rg.T
    Rrel=Rc@Rg.T@Rc.T
    mk=np.ones(len(m['xa']),bool) if rmax is None else (m['r']<rmax)
    if mk.sum()<30: return None
    s=sampson_t(m['xa'][mk],m['xb'][mk],Rrel,sf)
    return float(np.mean(np.minimum(s,4.0)**2))   # troncato a 4 px
def total(sf,Ms,**kw):
    v=[pair_cost(m,sf,**kw) for m in Ms];v=[x for x in v if x is not None];return float(np.mean(v)),len(v)
if __name__=='__main__':
    Rc=Rc0
    print('coppie',len(M),'rotazione mediana gyro deg',np.median([m['ang'] for m in M]))
    sfs=[0.80,0.85,0.9,0.95,1.0,1.05,1.1,1.15,1.2,1.3]
    for sg in (1,-1):
        print('segno',sg,[round(total(s,M,Rc=Rc,rot_sign=sg)[0],3) for s in sfs])
