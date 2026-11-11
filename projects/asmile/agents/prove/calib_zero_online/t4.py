import numpy as np, pickle, cv2, sys
from core import *
T=pickle.load(open('triples.pkl','rb'))
def flowZ(p,tr,scale=1.0):
    fL,k1,k2=p[3],p[4],p[9]
    K=np.array([[fL,0,W/2],[0,fL,H/2],[0,0,1.]]);D=np.array([k1,k2,0,0,0])
    ni=cv2.undistortPoints(tr['pi'].reshape(-1,1,2),K,D).reshape(-1,2);nj=cv2.undistortPoints(tr['pj'].reshape(-1,1,2),K,D).reshape(-1,2)
    E,inl=cv2.findEssentialMat(ni,nj,np.eye(3),cv2.RANSAC,0.999,1.0/fL)
    if E is None or E.shape!=(3,3): return None
    _,Rr,t,inl2=cv2.recoverPose(E,ni,nj,np.eye(3),mask=inl.copy())
    t=t.ravel()
    P1=np.hstack([np.eye(3),np.zeros((3,1))]);P2=np.hstack([Rr,t.reshape(3,1)*tr['dl']*scale])
    X=cv2.triangulatePoints(P1,P2,ni.T,nj.T);X=(X[:3]/X[3]).T
    ok=(inl2.ravel()>0)&(X[:,2]>0)
    return X[:,2],ok,t
def run(p_cam,label,scale=1.0,p_st=REF):
    rows=[]
    for tr in T:
        r=flowZ(p_cam,tr,scale)
        if r is None: continue
        Zf,ok,t=r
        u1,u2=proj(p_st,tr['pi'],tr['pr']);d=u1[:,0]-u2[:,0];dy=u1[:,1]-u2[:,1]
        Zs=p_st[3]*B/np.where(d>0.3,d,np.nan)
        good=ok&np.isfinite(Zs)&(abs(dy)<1.5)&(abs(t[2])>0.8)
        for zf,zs,x,dd in zip(Zf[good],Zs[good],tr['pi'][good,0],d[good]): rows.append((zf,zs,x,dd))
    R=np.array(rows);print(label,'n punti',len(R))
    return R
if __name__=='__main__':
    R=run(REF,'camera=REF')
    print('Zstereo(ref) bin | n | mediana Zflow/Zstereo | MAD% ')
    for lo,hi in((1.5,3),(3,5),(5,8),(8,12),(12,20),(20,40)):
        m=(R[:,1]>=lo)&(R[:,1]<hi);rr=R[m,0]/R[m,1]
        print(f'{lo:4}-{hi:4} n={m.sum():5d} med={np.median(rr):.3f} MAD={100*np.median(abs(rr-np.median(rr))):.1f}% ')
    pickle.dump(R,open('R_flow.pkl','wb'))
