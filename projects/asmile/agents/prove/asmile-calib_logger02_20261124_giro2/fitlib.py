"""Libreria fit v5 (giro2). Modello base = v4 (800). Parametri: R(3) T(2) centri(4) k1,k2(2)."""
import os,json,numpy as np,cv2
from scipy.optimize import least_squares
V4=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v4_20261124.json')
W_,H_=1280,800
def undist(p,K,d,it=30):
    fx,fy,cx,cy=K[0,0],K[1,1],K[0,2],K[1,2];k1,k2,p1,p2,k3=d;xd=(p[:,0]-cx)/fx;yd=(p[:,1]-cy)/fy;x=xd.copy();y=yd.copy()
    for _ in range(it):
        r2=x*x+y*y;rad=1+k1*r2+k2*r2**2+k3*r2**3;x=(xd-(2*p1*x*y+p2*(r2+2*x*x)))/rad;y=(yd-(p1*(r2+2*y*y)+2*p2*x*y))/rad
    return np.c_[x,y]
Rm=lambda w:cv2.Rodrigues(np.asarray(w,float).reshape(3,1))[0]
skew=lambda t:np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])
class Base:
    def __init__(s,c=None):
        c=c or json.load(open(V4));s.c=c;s.K1=np.array(c['K_left']);s.K2=np.array(c['K_right']);s.d=np.array(c['dist_left']);s.R0=np.array(c['R']);s.T0=np.array(c['T']).reshape(3);s.B=np.linalg.norm(s.T0)
    def build(s,p,mode):
        p=np.r_[p,np.zeros(11-len(p))];K1=s.K1.copy();K2=s.K2.copy();R=Rm(p[:3])@s.R0
        u=s.T0/abs(s.T0[0]);u[1]+=p[3];u[2]+=p[4];T=u/np.linalg.norm(u)*s.B
        K1[0,2]+=p[5];K1[1,2]+=p[6];K2[0,2]+=p[7];K2[1,2]+=p[8];d=s.d.copy();d[0]+=p[9];d[1]+=p[10];return K1,K2,d,R,T
NP={'RC':9,'RCL':11}
FREE={'RC':[0,2,3,4,8],'RCL':[0,2,3,4,8,9,10]}  # Ry, cx1, cx2, cy1 FISSI (non identificabili da epipolare: sposterebbero d0)
def sampson(K1,K2,d,R,T,a,b):
    x1=undist(a,K1,d);x2=undist(b,K2,d);E=skew(T/np.linalg.norm(T))@R;X1=np.c_[x1,np.ones(len(x1))];X2=np.c_[x2,np.ones(len(x2))];Ex=X1@E.T;Etx=X2@E
    return np.sum(X2*Ex,1)/np.sqrt(Ex[:,0]**2+Ex[:,1]**2+Etx[:,0]**2+Etx[:,1]**2)*K1[0,0]
XS=lambda mode:[0.005]*5+[5.0]*4+([0.02]*2 if mode=='RCL' else [])
def fit(M,A,B,mode,x0=None,only=None):
    """only: lista indici liberi (es. [0] per solo Rx) con gli altri a x0"""
    n=NP[mode];x0=np.zeros(n) if x0 is None else np.array(x0,float);free=FREE[mode] if only is None else only
    def res(q):
        p=x0.copy();p[free]=q;K1,K2,d,R,T=M.build(p,mode);return sampson(K1,K2,d,R,T,A,B)
    r=least_squares(res,x0[free],loss='soft_l1',f_scale=1.0,x_scale=np.array(XS(mode))[free],max_nfev=80);p=x0.copy();p[free]=r.x;return p
def rect_pts(M,p,mode,a,b):
    K1,K2,d,R,T=M.build(p,mode);r=cv2.stereoRectify(K1,d,K2,d,(W_,H_),R,T.reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    def f(q,K,Rr):
        x=undist(q,K,d);v=np.c_[x,np.ones(len(x))]@Rr.T;P=r[2];return np.c_[P[0,0]*v[:,0]/v[:,2]+P[0,2],P[1,1]*v[:,1]/v[:,2]+P[1,2]]
    return f(a,K1,r[0]),f(b,K2,r[1]),r
def zone(a): return np.clip((a[:,1]/H_*3).astype(int),0,2)*3+np.clip((a[:,0]/W_*3).astype(int),0,2)
def stats(M,p,mode,a,b):
    qa,qb,_=rect_pts(M,p,mode,a,b);dy=qa[:,1]-qb[:,1];dx=qa[:,0]-qb[:,0];ok=(dx>1)&(abs(dy)<40);dy=dy[ok];z=zone(a[ok]);ad=abs(dy)
    zs=[[int((z==i).sum()),round(float(np.median(ad[z==i])),2) if (z==i).sum()>=15 else None,round(float(np.percentile(ad[z==i],95)),2) if (z==i).sum()>=15 else None] for i in range(9)]
    return dict(n=int(ok.sum()),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),segno=float(np.median(dy)),zone=zs)
