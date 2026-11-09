import sys,cv2,numpy as np,pickle
SP=sys.argv[1]
M=pickle.load(open(f'{SP}/meas.pkl','rb'))
cL=cv2.VideoCapture(f'{SP}/mp4/s093216_right.mp4'); cR=cv2.VideoCapture(f'{SP}/mp4/s093216_left.mp4')
def rd(t):
    cL.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15))); cR.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15)))
    a,fa=cL.read(); b,fb=cR.read()
    return cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY),cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
out=[]
for k,mm in enumerate(M):
    Z=mm['Z']; sq=34.0/Z
    ww,wh=int(5*sq)+2,int(8*sq)+2
    L0,_=rd(mm['t'][4]); x0,x1,y0,y1=mm['roi']
    # finestra a massima varianza locale entro roi allargata
    ex=int(0.3*(x1-x0))+4
    X0,X1,Y0,Y1=max(0,x0-ex),min(1280,x1+ex),max(0,y0),min(800,y1+int(0.4*(y1-y0))+10)
    g=L0[Y0:Y1,X0:X1].astype(np.float32)
    m=cv2.blur(g,(ww,wh)); m2=cv2.blur(g*g,(ww,wh)); v=m2-m*m
    # centri validi
    v[:wh//2,:]=0; v[-wh//2:,:]=0; v[:,:ww//2]=0; v[:,-ww//2:]=0
    cy,cx=np.unravel_index(np.argmax(v),v.shape); cx+=X0; cy+=Y0
    bx0,bx1,by0,by1=cx-ww//2,cx+ww//2,cy-wh//2,cy+wh//2
    P1=[];P2=[];ZN=[]
    for t in mm['t']:
        L,R=rd(t); tpl=L[by0:by1,bx0:bx1]
        sy0=max(0,by0+118-30); sy1=min(800,by1+118+30); sx0=max(0,bx0-420); sx1=min(1280,bx1+30)
        res=cv2.matchTemplate(R[sy0:sy1,sx0:sx1],tpl,cv2.TM_CCOEFF_NORMED)
        _,mx,_,(lx,ly)=cv2.minMaxLoc(res); dx=dy=0.
        if 0<lx<res.shape[1]-1:
            a,b,c=res[ly,lx-1],res[ly,lx],res[ly,lx+1]; dx=0.5*(a-c)/(a-2*b+c)
        if 0<ly<res.shape[0]-1:
            a,b,c=res[ly-1,lx],res[ly,lx],res[ly+1,lx]; dy=0.5*(a-c)/(a-2*b+c)
        P1.append(((bx0+bx1)/2,(by0+by1)/2)); P2.append((sx0+lx+dx+(bx1-bx0)/2,sy0+ly+dy+(by1-by0)/2)); ZN.append(mx)
    P1=np.array(P1);P2=np.array(P2);ZN=np.array(ZN)
    d=P1[:,0]-P2[:,0]
    print(f'stop {k} Z={Z} board win=({bx0},{by0},{bx1},{by1}) zncc={np.median(ZN):.2f} d={np.median(d):.2f} sd={d.std():.2f} dy={np.median(P1[:,1]-P2[:,1]):.2f}')
    mm['b_roi']=(bx0,bx1,by0,by1); mm['b1']=P1; mm['b2']=P2; mm['bz']=ZN
pickle.dump(M,open(f'{SP}/meas2.pkl','wb'))
