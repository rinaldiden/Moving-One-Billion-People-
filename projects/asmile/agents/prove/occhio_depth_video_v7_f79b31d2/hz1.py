import sys, numpy as np, pandas as pd
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth')
from ego_001 import Ego, x_arc, path_xz
import video_fluido_001 as V
sess='session_20261109_094146'
ego=Ego(sess)
o=pd.read_csv('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth/out_20261112_v5/session_20261109_094146_f/objects.csv')
t0=V.D.read_t(sess,'right')[0]
o['ts']=(o.t_ms-t0)/1000
psi=np.concatenate([[0],np.cumsum(np.radians(0.5*(ego.yaw_s[1:]+ego.yaw_s[:-1]))*np.diff(ego.t)/1000)])
vv=ego.v_s
pn=np.concatenate([[0],np.cumsum(np.cos(psi[:-1])*0.5*(vv[1:]+vv[:-1])*np.diff(ego.t)/1000)])
pe=np.concatenate([[0],np.cumsum(np.sin(psi[:-1])*0.5*(vv[1:]+vv[:-1])*np.diff(ego.t)/1000)])
sarc=ego.s-ego.s[0]
I=lambda a,x:np.interp(x,ego.t,a)
rows=[]
for fr,g in o.groupby('frame'):
    t=g.t_ms.iloc[0]; s0=I(sarc,t); k=float(ego.at(t,'k')); pz,px=path_xz(k); ps,e0,n0=I(psi,t),I(pe,t),I(pn,t)
    for _,r in g.iterrows():
        Z=r.Z_picco
        if Z>25: continue
        X=r.X
        wx=(e0+Z*np.sin(ps)+X*np.cos(ps), n0+Z*np.cos(ps)-X*np.sin(ps))
        m=(ego.t>=t)&(sarc<=s0+Z+2)
        if m.sum()<2: continue
        dm=np.hypot(pe[m]-wx[0],pn[m]-wx[1]).min()
        b=1.5+0.03*Z
        a6=abs(X-np.interp(Z,pz,px))<=b
        st6=abs(X)<=b
        b7=b+0.1*Z
        c7=abs(X-np.interp(Z,pz,px))<=b7 or abs(X)<=b7 or abs(X-float(x_arc(k,Z)))<=b7
        rows.append(dict(frame=fr,ts=r.ts,src=r.src,classe=r.classe,Z=Z,X=X,dm=dm,decl=str(r.declassato)=='True',sosp=bool(r.sospetto),v6=a6,v6s=a6 or st6,v7=c7,k=k,v=r.v_ms,box=r.box))
d=pd.DataFrame(rows); d.to_pickle('hz1.pkl'); print(len(d))
