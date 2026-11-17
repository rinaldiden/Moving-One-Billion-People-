import sys,cv2,numpy as np,pickle
M=pickle.load(open('meas3.pkl','rb'))
cL=cv2.VideoCapture('mp4/s093216_right.mp4');cR=cv2.VideoCapture('mp4/s093216_left.mp4')
def rd(t):
    cL.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15)));cR.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15)))
    a,fa=cL.read();b,fb=cR.read();return cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY),cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
def det(I,x0,x1,y0,y1):
    x0=max(0,int(x0));y0=max(0,int(y0));x1=min(1280,int(x1));y1=min(800,int(y1))
    for up in (2,3,4):
        cr=cv2.resize(I[y0:y1,x0:x1],None,fx=up,fy=up,interpolation=cv2.INTER_CUBIC)
        for pat in ((6,9),(9,6)):
            ok,c=cv2.findChessboardCornersSB(cr,pat,cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
            if ok:return pat,c.reshape(-1,2)/up+[x0,y0]
out={}
for k,m in enumerate(M):
    bx0,bx1,by0,by1=m['b_roi'];w=bx1-bx0;h=by1-by0;fr=[]
    d=float(np.median(m['b1'][:,0]-m['b2'][:,0]))
    for t in m['t']:
        L,R=rd(t);c1=np.median(m['b1'],0);A=det(L,c1[0]-.9*w,c1[0]+.9*w,c1[1]-.9*h,c1[1]+.9*h)
        if A is None:continue
        c2=np.median(m['b2'],0);Bc=det(R,c2[0]-.9*w,c2[0]+.9*w,c2[1]-.9*h,c2[1]+.9*h)
        if Bc is None or Bc[0]!=A[0]:continue
        a=A[1];best=None
        for bb in (Bc[1],Bc[1][::-1]):
            dd=a[:,1]-bb[:,1];s=np.median(abs(dd-np.median(dd)))
            if best is None or s<best[0]:best=(s,bb)
        if best[0]>6:continue
        fr.append(dict(i=int(round(t*15)),pat=A[0],b1=a,b2=best[1]))
    print(m['Z'],len(fr),'/',len(m['t']),flush=True);out[k]=fr
pickle.dump(out,open('boards_am.pkl','wb'))
