# misure: ROI bersaglio per sosta, SIFT sfondo, disparita' grezza ZNCC e angoli scacchiera
import sys,cv2,numpy as np,pickle
SP=sys.argv[1]
STOPS=[(1,7),(15,31),(45,57),(62,74),(80,93),(98,106),(111,126),(131,142),(148,158),(166,178),(187,202)]
Z=[1,2,3,4,5,6,7,8,10,12,15]
cL=cv2.VideoCapture(f'{SP}/mp4/s093216_right.mp4'); cR=cv2.VideoCapture(f'{SP}/mp4/s093216_left.mp4')   # L=fisica sinistra
def rd(t):
    cL.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15))); cR.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*15)))
    a,fa=cL.read(); b,fb=cR.read()
    return cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY),cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
bgL,_=rd(258)
sift=cv2.SIFT_create(4000); bf=cv2.BFMatcher()
out=[]
for k,(s,e) in enumerate(STOPS):
    ts=np.linspace(s+1,e-1,10)
    # ROI dal blob di differenza col fondo (mediana di 5 frame)
    L0,_=rd((s+e)/2)
    m=(cv2.absdiff(cv2.GaussianBlur(L0,(5,5),0),cv2.GaussianBlur(bgL,(5,5),0))>28).astype(np.uint8)
    m[:, :400]=0; m[:,880:]=0
    m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((3,3),np.uint8)); m=cv2.dilate(m,np.ones((9,9),np.uint8))
    n,l,st,_=cv2.connectedComponentsWithStats(m)
    if n<2: print('no blob',k); out.append(None); continue
    j=1+np.argmax(st[1:,4]); x,y,w,h,_a=st[j]
    # torso: terzo superiore del blob (scacchiera/torso), ristretto
    rx0,rx1=int(x+0.2*w),int(x+0.8*w); ry0,ry1=int(y+0.05*h),int(y+0.55*h)
    dL=[];P1=[];P2=[];ZN=[]
    sP1=[];sP2=[]
    for t in ts:
        L,R=rd(t)
        tpl=L[ry0:ry1,rx0:rx1]
        sy0=max(0,ry0+118-35); sy1=min(800,ry1+118+35); sx0=max(0,rx0-420); sx1=min(1280,rx1+30)
        res=cv2.matchTemplate(R[sy0:sy1,sx0:sx1],tpl,cv2.TM_CCOEFF_NORMED)
        _,mx,_,(lx,ly)=cv2.minMaxLoc(res)
        dx=dy=0.
        if 0<lx<res.shape[1]-1:
            a,b,c=res[ly,lx-1],res[ly,lx],res[ly,lx+1]; dx=0.5*(a-c)/(a-2*b+c)
        if 0<ly<res.shape[0]-1:
            a,b,c=res[ly-1,lx],res[ly,lx],res[ly+1,lx]; dy=0.5*(a-c)/(a-2*b+c)
        pr=(sx0+lx+dx+(rx1-rx0)/2, sy0+ly+dy+(ry1-ry0)/2); pl=((rx0+rx1)/2,(ry0+ry1)/2)
        if mx>0.5: P1.append(pl); P2.append(pr); ZN.append(mx)
        k1_,d1=sift.detectAndCompute(L,None); k2_,d2=sift.detectAndCompute(R,None)
        mm=[p for p,q in bf.knnMatch(d1,d2,k=2) if p.distance<0.7*q.distance]
        p1=np.float32([k1_[q.queryIdx].pt for q in mm]); p2=np.float32([k2_[q.trainIdx].pt for q in mm])
        _,inl=cv2.findFundamentalMat(p1,p2,cv2.FM_RANSAC,2.0,0.999)
        if inl is not None:
            i=inl.ravel()>0; sP1.append(p1[i]); sP2.append(p2[i])
    P1=np.array(P1);P2=np.array(P2)
    rec=dict(Z=Z[k],roi=(rx0,rx1,ry0,ry1),t=ts,tp1=P1,tp2=P2,zncc=np.array(ZN),s1=np.vstack(sP1),s2=np.vstack(sP2))
    dd=P1[:,0]-P2[:,0]
    print(f'stop {k} Z={Z[k]} roi={rx0,rx1,ry0,ry1} n={len(P1)} zncc={np.median(ZN):.2f} raw d={np.median(dd):.2f} sd={dd.std():.2f} dy={np.median(P1[:,1]-P2[:,1]):.1f} sift={len(rec["s1"])}',flush=True)
    out.append(rec)
pickle.dump(out,open(f'{SP}/meas.pkl','wb'))
