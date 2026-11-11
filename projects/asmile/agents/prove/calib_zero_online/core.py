import numpy as np, cv2, pickle, json
W,H,B=1280,800,0.2
REF=np.array(json.load(open('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_001_20261109/fit_final_params.json'))['params'])
REF[10:]=0
def rect(p):
    rx,ry,rz,fL,k1L,dcx,fR,k1R,dcy,k2=p[:10]
    K1=np.array([[fL,0,W/2],[0,fL,H/2],[0,0,1.]]);K2=np.array([[fR,0,W/2+dcx],[0,fR,H/2+dcy],[0,0,1.]])
    D1=np.array([k1L,k2,0,0,0]);D2=np.array([k1R,k2,0,0,0])
    R=cv2.Rodrigues(np.radians([rx,ry,rz]))[0];T=np.array([[-B],[0],[0.]])
    R1,R2,P1,P2,*_=cv2.stereoRectify(K1,D1,K2,D2,(W,H),R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    return K1,K2,D1,D2,R1,R2
def proj(p,p1,p2):
    K1,K2,D1,D2,R1,R2=rect(p);f=p[3]
    def one(pt,Rr,Kc,Dc):
        n=cv2.undistortPoints(pt.reshape(-1,1,2).astype(np.float64),Kc,Dc).reshape(-1,2)
        v=np.hstack([n,np.ones((len(n),1))])@Rr.T
        return f*v[:,:2]/v[:,2:3]
    return one(p1,R1,K1,D1),one(p2,R2,K2,D2)
def load():
    m=pickle.load(open('m.pkl','rb'));P1,P2=m['094146']
    return P1.astype(np.float64),P2.astype(np.float64)
def depth(p,P1,P2):
    u1,u2=proj(p,P1,P2);d=u1[:,0]-u2[:,0];return p[3]*B/np.where(d>0.05,d,np.nan),u1[:,1]-u2[:,1],d
