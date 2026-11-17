import sys,cv2,numpy as np,pickle
from seg2 import load
calib=sys.argv[1] if len(sys.argv)>1 else '/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json'
outp=sys.argv[2] if len(sys.argv)>2 else 'meas2_cur.pkl'
c,r=load(calib);f=r['focal_px'];B=0.2
FL=np.load('full_left.npy',mmap_mode='r');FR=np.load('full_right.npy',mmap_mode='r')
runs=pickle.load(open('runs.pkl','rb'))
OX,OY,CW,CH=300,200,1900,1200
def mk(K,Dd,R,P):
    P=P.copy();P[0,2]+=OX;P[1,2]+=OY
    return cv2.initUndistortRectifyMap(K,Dd,R,P,(CW,CH),cv2.CV_32FC1)
M1=mk(c.K1,c.d1,r['R1'],r['P1']);M2=mk(c.K2,c.d2,r['R2'],r['P2'])
rl=lambda i:cv2.remap(np.array(FR[i]),M1[0],M1[1],cv2.INTER_LINEAR)
rr=lambda i:cv2.remap(np.array(FL[i]),M2[0],M2[1],cv2.INTER_LINEAR)
BG=np.median(np.array([rl(i) for i in range(0,2596,40)]),axis=0).astype(np.float32)
C0=pickle.load(open('corners_raw.pkl','rb'))
# template dalla rect del frame 36 (Z~1.04)
cc0=build=None
from seg2 import build
rows=dict(build(c,r,{36:C0[36]}))
ua=rows[36]['ua'];x0,y0=(ua.min(0)+[OX,OY]).astype(int);x1,y1=(ua.max(0)+[OX,OY]).astype(int)
TPL=rl(36)[y0:y1,x0:x1];sq0=rows[36]['d']; SQ=np.median(np.linalg.norm(np.diff(ua.reshape(9,6,2),axis=1),axis=2))
print('tpl',TPL.shape,'sq',SQ)
def sub(v):
    u,m,w=v;den=(u-2*m+w);return 0.0 if abs(den)<1e-9 else 0.5*(u-w)/den
res=[]
for (a,b) in runs:
    mid=(a+b)//2;L=rl(mid)
    fg=cv2.dilate((np.abs(L.astype(np.float32)-BG)>25).astype(np.uint8),np.ones((15,15),np.uint8))
    best=None
    for s in np.geomspace(0.12,1.15,60):
        tp=cv2.resize(TPL,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
        if min(tp.shape)<10 or tp.shape[0]>=CH or tp.shape[1]>=CW:continue
        rs=cv2.matchTemplate(L,tp,cv2.TM_CCOEFF_NORMED)
        H,W=rs.shape;ys,xs=np.mgrid[0:H,0:W];ctrm=fg[(ys+tp.shape[0]//2),(xs+tp.shape[1]//2)]
        rs=np.where(ctrm>0,rs,-1);_,mx,_,(lx,ly)=cv2.minMaxLoc(rs)
        if best is None or mx>best[0]:best=(mx,s,lx,ly,tp.shape)
    mx,s,lx,ly,sh=best
    if mx<0.4:print(a,b,'no board mx=%.2f'%mx);continue
    x0b,y0b=lx,ly;h,w=sh;D=[];DY=[];ZN=[]
    for i in np.linspace(a+int(.15*(b-a)),b-int(.15*(b-a)),min(12,b-a)).astype(int):
        L=rl(i);R=rr(i);tp=L[y0b:y0b+h,x0b:x0b+w]
        sy0=max(0,y0b-14);sy1=min(CH,y0b+h+14);sx0=max(0,x0b-340);sx1=min(CW,x0b+w+20)
        if sx1-sx0<=w or sy1-sy0<=h:continue
        rs_=cv2.matchTemplate(R[sy0:sy1,sx0:sx1],tp,cv2.TM_CCOEFF_NORMED);_,m2,_,(px,py)=cv2.minMaxLoc(rs_)
        if m2<0.6:continue
        dx=sub((rs_[py,px-1],rs_[py,px],rs_[py,px+1])) if 0<px<rs_.shape[1]-1 else 0
        dy=sub((rs_[py-1,px],rs_[py,px],rs_[py+1,px])) if 0<py<rs_.shape[0]-1 else 0
        D.append(x0b-(sx0+px+dx));DY.append(y0b-(sy0+py+dy));ZN.append(m2)
    if len(D)<3:print(a,b,'stereo fail (board mx=%.2f at x=%d)'%(mx,x0b));continue
    d=float(np.median(D))
    rec=dict(run=(a,b),n=len(D),d=d,sd=float(np.std(D)),Z=f*B/d,dy=float(np.median(DY)),zncc=float(np.median(ZN)),cx=x0b+w/2-OX,cy=y0b+h/2-OY,x0b=x0b,y0b=y0b,w=w,h=h,scale=float(s),sqpx=SQ*s,frame=mid)
    res.append(rec);print(a,b,'n=%d d=%.2f sd=%.2f Z=%.3f dy=%.2f zncc=%.2f mx=%.2f ctr=(%d,%d) sq=%.1f'%(len(D),d,rec['sd'],rec['Z'],rec['dy'],rec['zncc'],mx,rec['cx'],rec['cy'],rec['sqpx']))
pickle.dump(res,open(outp,'wb'))
