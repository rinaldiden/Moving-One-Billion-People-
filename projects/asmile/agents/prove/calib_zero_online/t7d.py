import numpy as np, pickle, sys
from scipy.optimize import least_squares
from t4 import flowZ
from core import *
P1,P2=load();Zr,dyr,dr=depth(REF,P1,P2)
rng=np.random.default_rng(int(sys.argv[1]) if len(sys.argv)>1 else 0)
sel=np.isfinite(Zr)&(Zr>2)&(Zr<8);cen=sel&(abs(P1[:,0]-640)<250);edg=sel&((P1[:,0]<250)|(P1[:,0]>1030))
tr=pickle.load(open('triples.pkl','rb'))
sub=rng.choice(len(P1),20000,replace=False)
FREE=[0,2,3,6,4,7]
SIG=np.array([0.5,0.5,0.02*1150,0.02*1150,0.03,0.03])   # prior = tolleranze di montaggio assunte (1 sigma)
PW=float(sys.argv[6]) if len(sys.argv)>6 else 1.0
def resid(q,p0,S1,S2):
    p=p0.copy();p[FREE]=q;u1,u2=proj(p,S1,S2);z=(u1[:,1]-u2[:,1])/0.5
    r=np.sign(z)*np.sqrt(2*(np.sqrt(1+z*z)-1))
    pri=(q-NOM)/SIG*PW*np.sqrt(len(S1))/20.0
    return np.concatenate([r,pri])
def f_d0(p,pairs):
    per=[]
    for t in pairs:
        r=flowZ(p,t)
        if r is None: continue
        Zf,ok,tt=r;u1,u2=proj(p,t['pi'],t['pr']);d=u1[:,0]-u2[:,0];dy=u1[:,1]-u2[:,1]
        g=ok&(abs(dy)<1.5)&(abs(tt[2])>0.8)&(Zf>1)&(Zf<100)
        per.append(np.c_[Zf[g],d[g]])
    R=np.vstack(per);d0=0.0
    # init d0,f da regressione per bin su 1/Zf
    m=(R[:,0]>2.5)&(R[:,0]<40);iz=1/R[m,0];dd=R[m,1];q=np.quantile(iz,np.linspace(0,1,13))
    xs=[];ys=[]
    for a,b in zip(q[:-1],q[1:]):
        s_=(iz>=a)&(iz<=b);xs.append(np.median(iz[s_]));ys.append(np.median(dd[s_]))
    A=np.vstack([xs,np.ones(len(xs))]).T;sl,d0=np.linalg.lstsq(A,ys,rcond=None)[0]
    for _ in range(6):
        dp=R[:,1]-d0;m=(dp>12)&(dp<45)
        if m.sum()<20: return np.nan,d0
        f=np.median(dp[m]*R[m,0])/B
        m2=(dp>6)&(dp<45);d0=d0+np.median(dp[m2]-f*B/R[m2,0])
    return f,d0
def ev(p,f=None,d0=0.0):
    Z,dy,d=depth(p,P1,P2)
    if f is not None: Z=f*B/np.where(d-d0>0.05,d-d0,np.nan)
    e=100*(Z/Zr-1)
    return [np.nanmedian(abs(e[cen])),np.nanpercentile(abs(e[cen]),90),np.nanmedian(abs(e[edg])),np.nanpercentile(abs(e[edg]),90),np.median(abs(dy[sub])),np.percentile(abs(dy[sub]),95)]
def pert(sa,sf,sk,spp):
    p=REF.copy();p[0:3]+=rng.normal(0,sa,3);p[3]*=1+rng.normal(0,sf);p[6]*=1+rng.normal(0,sf);p[4]+=rng.normal(0,sk);p[7]+=rng.normal(0,sk)
    p[5]+=rng.normal(0,spp);p[8]+=rng.normal(0,spp);return p
cfg=dict(sa=float(sys.argv[2]),sf=float(sys.argv[3]),sk=float(sys.argv[4]),spp=float(sys.argv[5]))
print('cfg',cfg)
rows=[]
for k in range(6):
    p0=pert(**cfg);e0=ev(p0)
    NOM=p0[FREE].copy()
    r=least_squares(resid,p0[FREE],args=(p0,P1[sub],P2[sub]),loss='linear',x_scale=[1,1,100,100,.1,.1],max_nfev=60)
    p1=p0.copy();p1[FREE]=r.x;e1=ev(p1)
    print('   err S1 (rec-ref): rx %+.2f rz %+.2f fL %+.0f fR %+.0f k1L %+.3f k1R %+.3f dcy %+.1f | start err: rx %+.2f rz %+.2f fL %+.0f fR %+.0f k1L %+.3f k1R %+.3f dcy %+.1f'%tuple([p1[i]-REF[i] for i in (0,2,3,6,4,7,5)]+[p0[i]-REF[i] for i in (0,2,3,6,4,7,5)]))
    f,d0=f_d0(p1,tr);e2=ev(p1,f,d0)
    rows.append(e0+e1+e2);print(k,'start cen/edge med%%: %.1f/%.1f | dopo S1(dy): %.1f/%.1f dy %.2f/%.2f | +f,d0 (f=%.0f d0=%+.2f): cen %.2f(p90 %.1f) edge %.2f(p90 %.1f) dy %.2f/%.2f'%(e0[0],e0[2],e1[0],e1[2],e1[4],e1[5],f,d0,e2[0],e2[1],e2[2],e2[3],e2[4],e2[5]),flush=True)
R=np.array(rows);print('MEDIA su draw: start cen %.1f edge %.1f dy %.2f/%.2f | S1 cen %.1f edge %.1f dy %.2f/%.2f| S1+flow cen %.2f p90 %.2f edge %.2f p90 %.2f dy %.2f/%.2f'%(tuple(np.median(R[:,[0,2,4,5]],0))+tuple(np.median(R[:,[6,8,10,11]],0))+tuple(np.median(R[:,[12,13,14,15,16,17]],0))))
