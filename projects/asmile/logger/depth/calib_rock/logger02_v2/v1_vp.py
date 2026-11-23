"""Strada 2: focale dai punti di fuga (Manhattan). Pezzi rettilinei (sul fotogramma A, lente candidata) -> rette nel piano normalizzato.
Per ogni fotogramma: RANSAC sequenziale di 2 punti di fuga (soglia 1.0 gradi, >=5 rette ciascuno); se le direzioni sono ortogonali
(v1/q).(v2/q) + 1 = 0  =>  q^2 = -(v1.v2)   con q = f_vera / f_K (f_K = 1123.5 px). Scorporo: mediana sui fotogrammi, bootstrap, per scena."""
import os,sys,json,pickle,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from l2_plumb import undist_np,c,piece_rms,params
Kc=c['K_left'];KK=[Kc[0][0],Kc[1][1],Kc[0][2],Kc[1][2]];dist=c['dist_left']
L=pickle.load(open(os.path.join(os.environ.get('L02W','.'),'lines.pkl'),'rb'));L=[l for l in L if l[1]=='A']
frames={}
for t,_,p in L: frames.setdefault(t,[]).append(p.astype(np.float64))
def fit_line(p):
    x,y=undist_np(p[:,0],p[:,1],KK,dist)
    if np.max(np.hypot(x,y))>0.7: return None
    m=np.array([x.mean(),y.mean()]);u,s,vt=np.linalg.svd(np.c_[x-m[0],y-m[1]],full_matrices=False)
    ln=s[0]/np.sqrt(len(x))
    if s[1]/s[0]>0.03 or ln*np.sqrt(12)<0.09: return None   # abbastanza dritta (rettilineita') e lunga (>0.07 in unita' normalizzate ~ 80 px)
    d=vt[0];n=np.array([-d[1],d[0]]);return dict(m=m,d=d,n=n,c=-n@m,len=float(ln*np.sqrt(12)))
def ang_resid(lines,v):
    # angolo fra direzione della retta e direzione dal punto medio al VP
    M=np.array([l['m'] for l in lines]);D=np.array([l['d'] for l in lines])
    w=v[None,:]-M;w/=np.linalg.norm(w,axis=1)[:,None];return np.abs(w[:,0]*D[:,1]-w[:,1]*D[:,0])
def vp_from(lines):
    N=np.array([np.r_[l['n'],l['c']] for l in lines]);w=np.array([l['len'] for l in lines]);u,s,vt=np.linalg.svd(N*w[:,None],full_matrices=False);v=vt[-1]
    return v[:2]/v[2] if abs(v[2])>1e-9 else None
def ransac(lines,rng,thr=np.sin(np.radians(1.0)),it=400):
    best=None
    for _ in range(it):
        i,j=rng.choice(len(lines),2,replace=False);v=np.cross(np.r_[lines[i]['n'],lines[i]['c']],np.r_[lines[j]['n'],lines[j]['c']])
        if abs(v[2])<1e-6: continue
        v=v[:2]/v[2]
        if np.linalg.norm(v)>400: continue
        inl=ang_resid(lines,v)<thr;sc=sum(l['len'] for l,k in zip(lines,inl) if k)
        if best is None or sc>best[0]: best=(sc,inl)
    if best is None or best[1].sum()<5: return None
    v=vp_from([l for l,k in zip(lines,best[1]) if k]);inl=ang_resid(lines,v)<thr if v is not None else None
    return (v,inl) if v is not None and inl.sum()>=5 else None
if __name__=='__main__':
    rng=np.random.default_rng(0);res=[]
    for t,pcs in sorted(frames.items()):
        lines=[fit_line(p) for p in pcs];lines=[l for l in lines if l is not None]
        if len(lines)<12: continue
        r1=ransac(lines,rng)
        if r1 is None: continue
        v1,in1=r1;rest=[l for l,k in zip(lines,in1) if not k]
        if len(rest)<8: continue
        r2=ransac(rest,rng)
        if r2 is None: continue
        v2,in2=r2;dot=v1@v2
        res.append(dict(t=t,v1=v1.tolist(),v2=v2.tolist(),n1=int(in1.sum()),n2=int(in2.sum()),dot=float(dot)))
    print('fotogrammi con 2 VP',len(res))
    good=[r for r in res if r['dot']<-0.3 and min(r['n1'],r['n2'])>=6]
    print('con prodotto negativo e >=6 rette per VP:',len(good))
    q=np.array([np.sqrt(-r['dot']) for r in good]);tt=np.array([r['t'] for r in good])
    print('q=f_vera/f_K: mediana %.3f  p25-p75 %.3f-%.3f'%(np.median(q),*np.percentile(q,[25,75])))
    for lo,hi in((150,450),(450,700),(700,880)):
        m=(tt>=lo)&(tt<hi);print('  scena',lo,hi,'n',m.sum(),'q med %.3f'%np.median(q[m]) if m.sum() else '')
    bs=[np.median(rng.choice(q,len(q))) for _ in range(500)];print('bootstrap mediana q: %.3f +- %.3f'%(np.mean(bs),np.std(bs)))
    print('f_rett equivalente = %.0f px (nominale candidato 1236)'%(1236.26*np.median(q)))
    json.dump(dict(n=len(good),q_med=float(np.median(q)),q_boot_sd=float(np.std(bs)),q_all=q.tolist(),t=tt.tolist()),open(os.path.join(os.environ.get('L02W','.'),'vp.json'),'w'))
