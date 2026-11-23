"""Strade 2 e 3 - passo 1: pezzi di bordo lunghi e quasi rettilinei dai fotogrammi A e B (grezzi, con distorsione).
Canny -> contorni -> spezzati con RDP (tolleranza 5 px) -> pezzi >= 90 px. Salva lines_{A,B}.pkl: lista (t, side, pts Nx2 float32 coordinate grezze)."""
import os,sys,pickle,collections,numpy as np,cv2
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from common import *
def pieces(img,minlen=90,eps=5.0):
    g=cv2.GaussianBlur(img,(0,0),1.2);e=cv2.Canny(g,30,90)
    e[:12]=0;e[-12:]=0;e[:,:12]=0;e[:,-12:]=0
    cs,_=cv2.findContours(e,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE);out=[]
    for c in cs:
        c=c[:,0,:]
        if len(c)<minlen: continue
        # un contorno chiuso percorre il bordo due volte: tengo meta' (dedup grossolano)
        n=len(c)//2 if np.linalg.norm(c[0]-c[-1])<3 else len(c)
        c=c[:max(n,2)].astype(np.float32)
        ap=cv2.approxPolyDP(c.reshape(-1,1,2),eps,False)[:,0,:]
        # indici dei vertici nel contorno
        idx=[int(np.argmin(np.sum((c-v)**2,1))) for v in ap];idx=sorted(set(idx))
        for a,b in zip(idx[:-1],idx[1:]):
            if b-a>=minlen: out.append(c[a:b+1:2])
    return out
def work(args):
    clipname,lst=args;V=clip(clipname);P=pairs();res=[]
    for k,t,side in lst:
        a,b,_=P[k];src=a if side=='A' else b
        im=clip(src[1])[src[2]]
        if im.mean()<25: continue
        for p in pieces(im): res.append((t,side,p))
    return res
if __name__=='__main__':
    P=pairs();T=np.array([p[0][0]/1e6 for p in P]);jobs=collections.OrderedDict()
    ts=list(np.arange(150,450,6))+list(np.arange(500,580,6))+list(np.arange(630,700,6))+list(np.arange(690,872,4))
    for t in ts:
        k=int(np.argmin(abs(T-t)))
        for side in 'AB': jobs.setdefault(P[k][0 if side=='A' else 1][1],[]).append((k,float(T[k]),side))
    with Pool(8) as p: out=p.map(work,list(jobs.items()))
    out=[x for o in out for x in o];print(len(out),'pezzi',sum(len(x[2]) for x in out),'punti')
    pickle.dump(out,open(os.path.join(W,'lines.pkl'),'wb'))
