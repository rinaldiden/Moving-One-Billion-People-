"""Validazione dy (scarto verticale L-R in pixel) su un TRATTO DIVERSO dal fit (>870 s: stanza/porta, mai usato per il fit) con la calibrazione data.
SIFT L-R sui fotogrammi rettificati, mutual NN + rapporto, gate loose |dy|<6 (non filtra l'errore da misurare) e d>1.
Statistiche per zona 3x3 (mediana |dy|, p95) e separando i fotogrammi con la bici in rotazione (|giro|>15 dps = in movimento)."""
import os,sys,json,pickle,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from rect import *
def zone(a,W_=None,H_=None):
    W_,H_=W_ or size()[0],H_ or size()[1]
    return np.clip((a[:,1]/H_*3).astype(int),0,2)*3+np.clip((a[:,0]/W_*3).astype(int),0,2)
def run(calib,lo,hi,step,tag):
    S=load(calib);P=pairs();T=np.array([p[0][0]/1e6 for p in P]);X=imu();ti=X[:,0]/1e6
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();ks=[k for k in range(len(P)) if lo<=T[k]<hi][::step]
    rows=[]
    for k in ks:
        ra,rb=rectpair(S,P,k);m=np.zeros_like(ra);m[8:-8,8:-8]=255
        ka,da=sift.detectAndCompute(ra,m);kb,db=sift.detectAndCompute(rb,m)
        if da is None or db is None or len(ka)<20 or len(kb)<20: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
        i0=np.searchsorted(ti,T[k]-0.05);i1=np.searchsorted(ti,T[k]+0.05);w=float(np.abs(X[i0:i1,4:7]-[-1,0.85,-0.94]).max()) if i1>i0 else 0.0
        for q in ab:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                a=ka[q[0].queryIdx].pt;b=kb[q[0].trainIdx].pt
                if abs(a[1]-b[1])<6 and a[0]-b[0]>1: rows.append((T[k],a[0],a[1],a[0]-b[0],b[1]-a[1],w))
    return np.array(rows)
def report(r,name):
    a=np.abs(r[:,4]);z=zone(r[:,1:3]);print(name,'n',len(r),'frames',len(np.unique(r[:,0])),'dy med %.2f p95 %.2f (segno medio %.2f)'%(np.median(a),np.percentile(a,95),np.median(r[:,4])))
    zs=[]
    for i in range(9):
        m=z==i;zs.append((int(m.sum()),round(float(np.median(a[m])),2) if m.sum()>=15 else None,round(float(np.percentile(a[m],95)),2) if m.sum()>=15 else None))
    print('   zone (n,med,p95):',zs);return zs
if __name__=='__main__':
    calib=sys.argv[1] if len(sys.argv)>1 else CALIB
    lo,hi,step=float(sys.argv[2]),float(sys.argv[3]),int(sys.argv[4])
    r=run(calib,lo,hi,step,'x');np.save(os.path.join(W,'dy_%d_%d.npy'%(lo,hi)),r)
    zs=report(r,'TRATTO %d-%d'%(lo,hi))
    mov=r[r[:,5]>15];
    if len(mov)>50: report(mov,'  solo con rotazione >15 dps (in moto)')
