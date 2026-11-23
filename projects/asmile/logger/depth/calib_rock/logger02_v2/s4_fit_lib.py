"""Regressione targhe (stessa logica di s4_fit.py ma come funzione)."""
import numpy as np
def good(R,angmax=8,tm=0.80):
    return [r for r in R if r['tm']>=tm and abs(r['ang'])<angmax and abs(r['wL']-r['wR'])<0.03*r['wL'] and abs(r['dL']-r['dR'])<0.04*r['dL']+1.0 and r['ntext']>=7 and abs(r['dy'])<4]
def regress(G):
    w=np.array([0.5*(r['wL']+r['wR']) for r in G]);d=np.array([0.5*(r['dL']+r['dR']) for r in G]);m=np.ones(len(w),bool)
    for _ in range(5):
        A=np.c_[w[m],-np.ones(m.sum())];sol=np.linalg.lstsq(A,d[m],rcond=None)[0];res=d-(sol[0]*w-sol[1]);s=1.4826*np.median(abs(res[m]));m=abs(res)<3*max(s,0.2)
    rng=np.random.default_rng(0);idx=np.where(m)[0];bs=[]
    for _ in range(300):
        i=rng.choice(idx,len(idx));bs.append(np.linalg.lstsq(np.c_[w[i],-np.ones(len(i))],d[i],rcond=None)[0]*np.array([520,1]))
    bs=np.array(bs)
    if m.sum()<12 or w[m].max()/w[m].min()<1.5: return None
    return dict(B_mm=float(sol[0]*520),B_boot_sd=float(bs[:,0].std()),d0_intercetta=float(sol[1]),n_viste=int(m.sum()),w_range=[float(w[m].min()),float(w[m].max())],B_sist_mm=3.5)
