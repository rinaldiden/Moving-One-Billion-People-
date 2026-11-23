"""Strada 4 - passo finale: da plate_track.pkl, regressione robusta d = (B/520)*w3D - d0 sulle viste buone. Stampa B, d0, dispersione e per-intervallo di scala."""
import os,sys,pickle,json,numpy as np
sys.path.insert(0,os.path.dirname(__file__))
from common import *
R=pickle.load(open(os.path.join(W,'plate_track.pkl'),'rb'))
def good(R,angmax=8,tm=0.80):
    return [r for r in R if r['tm']>=tm and abs(r['ang'])<angmax and abs(r['wL']-r['wR'])<0.03*r['wL'] and abs(r['dL']-r['dR'])<0.04*r['dL']+1.0 and r['ntext']>=7 and abs(r['dy'])<4]
G=good(R);print('viste totali',len(R),'buone',len(G))
w=np.array([0.5*(r['wL']+r['wR']) for r in G]);d=np.array([0.5*(r['dL']+r['dR']) for r in G])
def reg(w,d,iters=5):
    m=np.ones(len(w),bool)
    for _ in range(iters):
        A=np.c_[w[m],-np.ones(m.sum())];sol=np.linalg.lstsq(A,d[m],rcond=None)[0];res=d-(sol[0]*w-sol[1]);s=1.4826*np.median(abs(res[m]));m=abs(res)<3*max(s,0.2)
    return sol,res,m
sol,res,m=reg(w,d)
B1=sol[0]*520;print('pendenza -> B = %.1f mm, d0 = %.2f px (d = a*w - d0), viste usate %d, sd residuo %.2f px'%(B1,sol[1],m.sum(),res[m].std()))
# con d0=0 imposto (B_eff per vista)
Bv=520*d/w;print('d0=0: B per vista mediana %.1f sd %.1f'%(np.median(Bv[m]),Bv[m].std()))
# bootstrap sulle viste
rng=np.random.default_rng(0);bs=[]
idx=np.where(m)[0]
for _ in range(500):
    i=rng.choice(idx,len(idx));A=np.c_[w[i],-np.ones(len(i))];s=np.linalg.lstsq(A,d[i],rcond=None)[0];bs.append(s*np.array([520,1]))
bs=np.array(bs);print('bootstrap: B %.1f +-%.1f (p5-p95 %.1f-%.1f) ; d0 %.2f +-%.2f'%(bs[:,0].mean(),bs[:,0].std(),*np.percentile(bs[:,0],[5,95]),bs[:,1].mean(),bs[:,1].std()))
# per classi di scala
for lo,hi in((100,200),(200,300),(300,420)):
    k=m&(w>=lo)&(w<hi)
    if k.sum()>3: print('w %d-%d n=%d  B(d0=0) med %.1f sd %.1f'%(lo,hi,k.sum(),np.median(Bv[k]),Bv[k].std()))
# solo meta' alternate (prima/seconda meta' del tempo) = indipendenza minima
ts=np.array([r['t'] for r in G]);o=np.argsort(ts);half=np.zeros(len(G),bool);half[o[::2]]=True
for h in (half,~half):
    k=m&h;A=np.c_[w[k],-np.ones(k.sum())];s=np.linalg.lstsq(A,d[k],rcond=None)[0];print('meta n=%d B %.1f d0 %.2f'%(k.sum(),s[0]*520,s[1]))
out=dict(B_mm_regressione=float(B1),d0_px=float(sol[1]),n_viste=int(m.sum()),B_boot_sd=float(bs[:,0].std()),B_d0zero_med=float(np.median(Bv[m])),B_d0zero_sd=float(Bv[m].std()),w_range=[float(w[m].min()),float(w[m].max())])
json.dump(out,open(os.path.join(W,'plate_fit.json'),'w'));print(out)
