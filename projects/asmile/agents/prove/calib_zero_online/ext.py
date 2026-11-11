import cv2, numpy as np, pickle
d='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/asmile-001/'
res={}
sift=cv2.SIFT_create(3000); bf=cv2.BFMatcher()
for sid in ('094146','093909'):
    cL=cv2.VideoCapture(d+f'session_20261109_{sid}_right.h264'); cR=cv2.VideoCapture(d+f'session_20261109_{sid}_left.h264')
    P1=[];P2=[];i=0;nf=0
    while True:
        a=cL.grab(); b=cR.grab()
        if not(a and b): break
        i+=1
        if i%25: continue
        _,fa=cL.retrieve(); _,fb=cR.retrieve()
        L=cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY); R=cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
        k1,d1=sift.detectAndCompute(L,None); k2,d2=sift.detectAndCompute(R,None)
        if d1 is None or d2 is None: continue
        m=[x for x,y in bf.knnMatch(d1,d2,k=2) if x.distance<0.7*y.distance]
        if len(m)<20: continue
        p1=np.float32([k1[x.queryIdx].pt for x in m]); p2=np.float32([k2[x.trainIdx].pt for x in m])
        _,inl=cv2.findFundamentalMat(p1,p2,cv2.FM_RANSAC,2.0,0.999)
        if inl is None: continue
        k=inl.ravel()>0; P1.append(p1[k]);P2.append(p2[k]);nf+=1
    print(sid,i,nf,sum(len(x) for x in P1),flush=True)
    res[sid]=(np.vstack(P1),np.vstack(P2))
pickle.dump(res,open('m.pkl','wb'))
