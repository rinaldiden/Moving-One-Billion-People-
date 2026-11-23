"""Rettifica con un JSON di calibrazione (default: candidato v1). Restituisce mappe e P1."""
import os,sys,json,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from common import *
def load(path=CALIB,B=None):
    c=json.load(open(path));K1=np.array(c['K_left']);K2=np.array(c['K_right']);d1=np.array(c['dist_left']);d2=np.array(c['dist_right'])
    R=np.array(c['R']);T=np.array(c['T']).reshape(3,1)
    if B is not None: T=T/np.linalg.norm(T)*B
    r=cv2.stereoRectify(K1,d1,K2,d2,(1280,720),R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    m1=cv2.initUndistortRectifyMap(K1,d1,r[0],r[2],(1280,720),cv2.CV_32FC1);m2=cv2.initUndistortRectifyMap(K2,d2,r[1],r[2],(1280,720),cv2.CV_32FC1)
    return dict(c=c,K1=K1,K2=K2,d1=d1,d2=d2,R1=r[0],R2=r[1],P1=r[2],P2=r[3],m1=m1,m2=m2,f=r[2][0,0],cx=r[2][0,2],cy=r[2][1,2],B=float(np.linalg.norm(T)))
def rectpair(S,P,k):
    a,b,_=P[k];ia=clip(a[1])[a[2]].copy();ib=clip(b[1])[b[2]].copy()
    return cv2.remap(ia,*S['m1'],cv2.INTER_LINEAR),cv2.remap(ib,*S['m2'],cv2.INTER_LINEAR)
