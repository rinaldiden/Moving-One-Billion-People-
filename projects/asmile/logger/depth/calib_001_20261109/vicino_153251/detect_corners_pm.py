import sys,cv2,numpy as np,pickle
sys.argv=['x','/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json','/dev/null']
exec(open('meas3.py').read().split("res=[]")[0])
M=pickle.load(open('meas3_ref.pkl','rb'))
def det(I,cx,cy,w,h,up0):
  for up in ((3,2,4) if up0>1 else (2,)):
    r_=det1(I,cx,cy,w,h,up)
    if r_ is not None: return r_
  return None
def det1(I,cx,cy,w,h,up):
    mx=int(0.35*w);my=int(0.35*h)
    x0=max(0,int(cx-w/2-mx));x1=min(CW,int(cx+w/2+mx));y0=max(0,int(cy-h/2-my));y1=min(CH,int(cy+h/2+my))
    cr=cv2.resize(I[y0:y1,x0:x1],None,fx=up,fy=up,interpolation=cv2.INTER_CUBIC)
    for pat in ((6,9),(9,6)):
        for fl in (cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY, cv2.CALIB_CB_ACCURACY|cv2.CALIB_CB_NORMALIZE_IMAGE):
            ok,c_=cv2.findChessboardCornersSB(cr,pat,fl)
            if ok: return pat,c_.reshape(-1,2)/up+[x0,y0]
    return None
out=[]
for m in M:
    a,b=m['run'];fr=np.linspace(a+int(.15*(b-a)),b-int(.15*(b-a)),min(12,b-a)).astype(int)
    got=0;L=[]
    for i in fr:
        l=rl(i);r_=rr(i);cx=m['x0b']+m['w']/2;cy=m['y0b']+m['h']/2
        A=det(l,cx,cy,m['w'],m['h'],3 if m['w']<250 else 2)
        if A is None: continue
        B_=det(r_,cx-m['d'],cy-m['dy'],m['w'],m['h'],3 if m['w']<250 else 2)
        if B_ is None: continue
        L.append((i,A,B_))
    print(m['run'],'w=%d'%m['w'],'detected',len(L),'/',len(fr),flush=True)
    out.append((m['run'],L))
pickle.dump(out,open('corn_rect.pkl','wb'))
