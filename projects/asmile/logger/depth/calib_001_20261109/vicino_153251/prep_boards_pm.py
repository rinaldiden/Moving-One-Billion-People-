import sys,cv2,numpy as np,pickle
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth')
from stereo_common import Calib
c=Calib.load('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json');r=c.rectify()
OX,OY=300,200
def raw(u,K,D,R,P):
    u=np.asarray(u,float)-[OX,OY]   # rect full-grid -> P coords
    n=(np.linalg.inv(P[:3,:3])@np.hstack([u,np.ones((len(u),1))]).T).T
    ray=n@R   # R.T @ n  (row form)
    return cv2.projectPoints(ray.reshape(-1,1,3),np.zeros(3),np.zeros(3),K,D)[0].reshape(-1,2)
S={25:(1,'C'),243:(2,'dx'),348:(2,'C'),2064:(2,'dx'),1818:(2,'C'),2152:(2,'C'),2197:(2,'sx'),523:(3,'sx'),639:(3,'C'),852:(4,'dx'),990:(4,'C'),1425:(5,'dx'),1319:(5,'C')}
FIT={25,348,639,1319,243,523,852}
CR=pickle.load(open('corn_rect.pkl','rb'))
out=[]
for run,L in CR:
    if run[0] not in S:continue
    nom,pos=S[run[0]];fr=[]
    for i,A,B in L:
        if A[0]!=B[0]:continue
        a=A[1];best=None
        for bb in (B[1],B[1][::-1]):
            dy=a[:,1]-bb[:,1];s=np.median(abs(dy))
            if best is None or s<best[0]:best=(s,bb)
        if best[0]>10:continue
        ra=raw(a,c.K1,c.d1,r['R1'],r['P1']);rb=raw(best[1],c.K2,c.d2,r['R2'],r['P2'])
        fr.append(dict(i=i,pat=A[0],b1=ra,b2=rb))
    print(run,nom,pos,len(fr),'FIT' if run[0] in FIT else 'HOLD')
    out.append(dict(run=run,nom=nom,pos=pos,fit=run[0] in FIT,frames=fr))
pickle.dump(out,open('../boards_pm.pkl','wb'))
