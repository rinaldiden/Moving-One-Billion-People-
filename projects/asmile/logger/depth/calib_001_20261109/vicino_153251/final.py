import sys,cv2,numpy as np,pickle,json,os
sys.argv=['x','/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json','/dev/null']
exec(open('meas3.py').read().split("res=[]")[0])
M={m['run'][0]:m for m in pickle.load(open('meas3_ref.pkl','rb'))}
# (nominale, posizione, run start, centro di riferimento della stessa passata)
S=[(1,'centro',25,None),
(2,'dx',243,348),(2,'centro',348,None),(2,'dx',2064,2152),(2,'centro',1818,None),(2,'centro',2152,None),(2,'sx',2197,2152),
(3,'sx',523,639),(3,'centro',639,None),
(4,'dx',852,990),(4,'centro',990,None),(4,'sx',1096,990),
(5,'sx',1187,1319),(5,'centro',1319,None),(5,'dx',1425,1319)]
IMG='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/agents/rapporti/img/'
os.makedirs(IMG,exist_ok=True);rows=[];tiles=[]
for nom,pos,a,ref in S:
    m=M[a];Z=m['Z'];err=100*(Z-nom)/nom
    row=dict(nominale_m=nom,pos=pos,frame=m['frame'],run=list(m['run']),n=m['n'],d_px=round(m['d'],2),sd_px=round(m['sd'],2),Z_stereo_m=round(Z,3),err_pct=round(err,1),dy_px=round(m['dy'],2),x_rett=int(m['cx']),zncc=round(m['zncc'],2))
    if ref:
        mc=M[ref];Zs=mc['Z']*mc['sq_ref']/m['sq_ref'];row['Z_da_scala_m']=round(Zs,3);row['stereo_vs_scala_pct']=round(100*(Z-Zs)/Zs,1)
    rows.append(row)
    i=m['frame'];L=rl(i);R=rr(i);x0,y0,w,h=int(m['x0b']),int(m['y0b']),int(m['w']),int(m['h']);dd=int(round(m['d']))
    cx,cy=x0+w//2,y0+h//2;hw=max(150,w);hh=max(190,h)
    def crop(I,cx,cy):
        c=np.zeros((2*hh,2*hw),np.uint8);xs=cx-hw;ys=cy-hh
        sx0=max(0,xs);sy0=max(0,ys);sx1=min(CW,cx+hw);sy1=min(CH,cy+hh)
        c[sy0-ys:sy1-ys,sx0-xs:sx1-xs]=I[sy0:sy1,sx0:sx1];return cv2.resize(c,(300,380))
    A=crop(L,cx,cy);Bc=crop(R,cx-dd,cy)
    for X in (A,Bc):cv2.line(X,(0,190),(300,190),255,1)
    cv2.rectangle(A,(int(150-w/2*300/(2*hw)),int(190-h/2*380/(2*hh))),(int(150+w/2*300/(2*hw)),int(190+h/2*380/(2*hh))),255,1)
    t=np.hstack([A,Bc]);cv2.putText(t,'%gm %s f%d Z=%.2f e=%+.1f%%'%(nom,pos,i,Z,err),(5,20),0,0.55,255,2)
    cv2.imwrite(IMG+'calib001_vicino_%gm_%s_f%d.png'%(nom,pos,i),t);tiles.append(t)
while len(tiles)%3:tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(IMG+'calib001_vicino_panoramica.png',np.vstack([np.hstack(tiles[k:k+3]) for k in range(0,len(tiles),3)]))
pickle.dump(rows,open('rows.pkl','wb'))
for r_ in rows:print(r_)
