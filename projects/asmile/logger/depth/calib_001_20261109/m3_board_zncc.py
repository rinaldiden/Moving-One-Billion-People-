import sys,cv2,numpy as np,pickle
SP=sys.argv[1]
M=pickle.load(open(f'{SP}/meas2.pkl','rb')); C=pickle.load(open(f'{SP}/corners.pkl','rb'))
cL=cv2.VideoCapture(f'{SP}/mp4/s093216_right.mp4'); cR=cv2.VideoCapture(f'{SP}/mp4/s093216_left.mp4')
def rd(t):
    cL.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15))); cR.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15)))
    a,fa=cL.read(); b,fb=cR.read()
    return cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY),cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
# template: scacchiera a Z=2 (sq medio 16.5px), frame con corners
i,a,b=[c for c in C if c[1] is not None and c[2] is not None and 20<c[0]/15<28][3]
L,_=rd(i/15); sq=np.median(np.linalg.norm(np.diff(a.reshape(9,6,2),axis=1),axis=2))
x0,y0=(a.min(0)-sq*0.9).astype(int); x1,y1=(a.max(0)+sq*0.9).astype(int)
TPL=L[y0:y1,x0:x1]; SQ0=sq; print('tpl',TPL.shape,'sq',sq)
SQZ=lambda Z: SQ0*2.0/Z
for k,mm in enumerate(M):
    Z=mm['Z']; s=SQZ(Z)/SQ0
    tp=cv2.resize(TPL,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
    L0,_=rd(mm['t'][4]); X0,X1,Y0,Y1=mm['roi']; ex=60
    X0=max(0,X0-ex);X1=min(1280,X1+ex);Y1=min(800,Y1+int(0.6*(Y1-Y0)))
    res=cv2.matchTemplate(L0[Y0:Y1,X0:X1],tp,cv2.TM_CCOEFF_NORMED); _,mx,_,(lx,ly)=cv2.minMaxLoc(res)
    bx0,by0=X0+lx,Y0+ly; bx1,by1=bx0+tp.shape[1],by0+tp.shape[0]
    # restringi al nucleo (scacchiera interna) per evitare bordi/sfondo
    mg=int(0.12*tp.shape[1]); my=int(0.1*tp.shape[0]); bx0+=mg;bx1-=mg;by0+=my;by1-=my
    P1=[];P2=[];ZN=[]
    for t in mm['t']:
        L,R=rd(t); tpl=L[by0:by1,bx0:bx1]
        sy0=max(0,by0+118-25); sy1=min(800,by1+118+25); sx0=max(0,bx0-420); sx1=min(1280,bx1+30)
        r=cv2.matchTemplate(R[sy0:sy1,sx0:sx1],tpl,cv2.TM_CCOEFF_NORMED); _,m2,_,(lx,ly)=cv2.minMaxLoc(r); dx=dy=0.
        if 0<lx<r.shape[1]-1:
            u,v,w=r[ly,lx-1],r[ly,lx],r[ly,lx+1]; dx=0.5*(u-w)/(u-2*v+w)
        if 0<ly<r.shape[0]-1:
            u,v,w=r[ly-1,lx],r[ly,lx],r[ly+1,lx]; dy=0.5*(u-w)/(u-2*v+w)
        P1.append(((bx0+bx1)/2,(by0+by1)/2)); P2.append((sx0+lx+dx+(bx1-bx0)/2,sy0+ly+dy+(by1-by0)/2)); ZN.append(m2)
    P1=np.array(P1);P2=np.array(P2);ZN=np.array(ZN); d=P1[:,0]-P2[:,0]
    print(f'stop {k} Z={Z} match={mx:.2f} win=({bx0},{by0},{bx1},{by1}) zncc={np.median(ZN):.2f} d={np.median(d):.2f} sd={d.std():.2f} dy={np.median(P1[:,1]-P2[:,1]):.2f}')
    mm['b_roi']=(bx0,bx1,by0,by1); mm['b1']=P1; mm['b2']=P2; mm['bz']=ZN; mm['bmatch']=mx
pickle.dump(M,open(f'{SP}/meas3.pkl','wb'))
