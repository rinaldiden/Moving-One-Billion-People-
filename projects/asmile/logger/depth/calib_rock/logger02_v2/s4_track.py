"""Strada 4 (inseguitore): nei fotogrammi con la targa dell'auto, il rettangolo e' trovato per template multi-scala (seme = il fotogramma piu' nitido,
scelto dal rilevatore automatico), poi i bordi (valli scure sub-pixel) sono misurati in L e R da s4_plates.measure_plate. Regressione d = (B/520)*w - d0."""
import os,sys,pickle,numpy as np,cv2,json
sys.path.insert(0,os.path.dirname(__file__))
from s4_plates import *
def run(S,P,T,lo,hi,seed_k,seed_box,step=1,wfrac=(0.995,)):
    ra0,_=rectpair(S,P,seed_k);x,y,w,h=seed_box;tpl=ra0[y:y+h,x:x+w].astype(np.float32);rows=[]
    ks=[k for k in range(len(P)) if lo<=T[k]<hi][::step];prev=None
    for k in ks:
        ra,rb=rectpair(S,P,k);best=(-1,None)
        sc=np.geomspace(0.15,1.5,60)
        small=cv2.resize(ra,None,fx=0.5,fy=0.5,interpolation=cv2.INTER_AREA).astype(np.float32)
        for s in sc:
            t=cv2.resize(tpl,None,fx=s*0.5,fy=s*0.5,interpolation=cv2.INTER_AREA)
            if t.shape[0]<8 or t.shape[1]<24 or t.shape[0]>=small.shape[0] or t.shape[1]>=small.shape[1]: continue
            r=cv2.matchTemplate(small,t,cv2.TM_CCOEFF_NORMED);_,mv,_,ml=cv2.minMaxLoc(r)
            if mv>best[0]: best=(mv,(s,ml))
        if best[1] is None or best[0]<0.80: prev=None;continue
        s,ml=best[1];prev=s
        bx=(int(ml[0]*2),int(ml[1]*2),int(w*s),int(h*s))
        m=measure_plate(ra,rb,bx,S['f'])
        if m is None: continue
        w3=width3d(m,S)
        if w3 is None: continue
        m.update(k=int(k),t=float(T[k]),w3=w3[0],ang=w3[1],tm=float(best[0]),scale=float(s));rows.append(m)
    return rows
if __name__=='__main__':
    S=load();P=pairs();T=np.array([p[0][0]/1e6 for p in P])
    seed_k=11716;rows=run(S,P,T,float(sys.argv[1]),float(sys.argv[2]),seed_k,(381,408,388,85))
    pickle.dump(rows,open(os.path.join(W,'plate_track.pkl'),'wb'));print(len(rows))
