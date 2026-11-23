"""d0 dalle colline lontane, per POSIZIONE nell'immagine (colonne/righe) e per fotogramma. Scrive far_d0.json in $L02W.
Argomenti opzionali: coppie 't0:t1:ymax' dei tratti con collina (default: quelli del giro 23/11)."""
import os,sys,json
sys.path.insert(0,os.path.dirname(__file__))
from s5_far import *
def main(segs=((757,764.5,150),(835,839,130),(845,848,130),(700,712,120))):
    S=load();P=pairs();T=np.array([p[0][0]/1e6 for p in P]);allr=[]
    for lo,hi,ym in segs:
        r=far_disp(S,P,T,np.arange(lo,hi,0.2),ym)
        if len(r): allr.append(r)
    r=np.concatenate(allr);sel=r[(r[:,3]>-6)&(r[:,3]<0.5)]
    out=dict(n_tot=int(len(r)),n_picco=int(len(sel)),d0_med=float(np.median(sel[:,3])),d0_mean=float(sel[:,3].mean()),sd=float(sel[:,3].std()))
    for nm,col,bins in (('x',1,[(0,400),(400,800),(800,1280)]),('y',2,[(0,60),(60,110),(110,200)])):
        out['per_'+nm]={f'{a}-{b}':[int(((sel[:,col]>=a)&(sel[:,col]<b)).sum()),float(np.median(sel[(sel[:,col]>=a)&(sel[:,col]<b),3]))] for a,b in bins if ((sel[:,col]>=a)&(sel[:,col]<b)).sum()>=15}
    ts=np.unique(sel[:,0]);pm=[np.median(sel[sel[:,0]==t,3]) for t in ts if (sel[:,0]==t).sum()>=8]
    out['per_fotogramma']=dict(n=len(pm),med=float(np.median(pm)),p10=float(np.percentile(pm,10)),p90=float(np.percentile(pm,90)))
    json.dump(out,open(os.path.join(W,'far_d0.json'),'w'),indent=1);print(json.dumps(out,indent=1));return out
if __name__=='__main__': main()
