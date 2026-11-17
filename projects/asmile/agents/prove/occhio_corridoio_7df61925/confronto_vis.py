import sys, numpy as np, json
sys.path.insert(0,'training/depth'); sys.path.insert(0,'pi/autonomous')
import ego_001 as E
from corridoio import Corridoio
import corridoio_replay_001 as R
import sys
FSC=float(sys.argv[1]) if len(sys.argv)>1 else 1.0   # scala sul flusso visivo (f effettiva incerta)
d=np.load('agents/prove/occhio_corridoio_7df61925/visyaw2.npy'); ft=d[:,0]; yaw=-d[:,1]/656.0*FSC; sg=1.0   # rad/frame, + destra
e=E.Ego("session_20261109_094146"); t=e.t
# carica sensori grezzi per il causale
t_,cum,g,st=R.carica(); s_=cum*2.1219e-5
K,v,c,_=R.run_corr({},t_,cum,g,st)   # parametri di default config (tarato)
# per ogni sensore sample cadente in frame continuo
# heading visivo integrato su griglia frame (tratti continui = gap<0.15s)
brk=np.where(np.diff(ft)>150)[0]+1; segs=np.split(np.arange(len(ft)),brk)
zs=(3.,5.,10.)
res={n:{z:[] for z in zs} for n in ('corr','sterzo055','sterzo0646','sterzo047','sterzo075','dritto','sterzo075')}
kk={}
stdeg=(st-6606)*0.02197
for r_ in (0.47,0.55,0.646,0.75): kk[r_]=np.tan(np.radians(r_*stdeg))/1.15
vcs=R.vcausale(t_,s_)
# k imu causale semplice: gz filtrato 0.1 s
for sgm in segs:
    if len(sgm)<60: continue
    tt=ft[sgm]/1000; psi=np.cumsum(sg*yaw[sgm])  # rad, + destra (segno gia' orientato)
    sv=np.interp(tt*1000,t_*1000,s_)   # m
    for i in range(0,len(sgm)-1,8):
        t0=tt[i]; 
        if np.interp(t0*1000,t_*1000,v)<1.5: continue
        # percorso reale
        j=np.searchsorted(sv,sv[i]+13.0)
        if j>=len(sgm): break
        p=psi[i:j]-psi[i]; ds=np.diff(sv[i:j+0],prepend=sv[i]); 
        px=np.cumsum(ds*np.sin(p)); pz=np.cumsum(ds*np.cos(p))
        idx=int(np.searchsorted(t_,t0))
        def pred(k0,L=2.5):
            sgrid=np.arange(0,16,0.25)+0.125; ps=np.cumsum(k0*np.exp(-sgrid/L))*0.25
            return np.concatenate([[0],np.cumsum(np.cos(ps))*0.25]),np.concatenate([[0],np.cumsum(np.sin(ps))*0.25])
        for n,k0,L in (('corr',K[idx],2.5),('sterzo055',kk[0.55][idx],2.5),('sterzo0646',kk[0.646][idx],2.5),('sterzo047',kk[0.47][idx],2.5),('sterzo075',kk[0.75][idx],2.5),('dritto',0.0,2.5)):
            zp,xp=pred(k0,L)
            for z in zs:
                if pz[-1]<z: continue
                res[n][z].append(abs(np.interp(z,zp,xp)-np.interp(z,pz,px)))
out={}
for n in res:
    out[n]={z:(round(float(np.median(v_)),3),round(float(np.percentile(v_,90)),3),len(v_)) for z,v_ in res[n].items()}
    print(n,out[n])
json.dump(out,open('agents/prove/occhio_corridoio_7df61925/errore_vs_verita_visiva.json','w'),indent=1)
