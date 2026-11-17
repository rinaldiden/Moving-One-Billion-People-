import cv2,numpy as np,sys,json
F=1379.888;B=0.19656
def ncc_roi(sess,fr,roi,step=5,P=10,dmax=300):
    L=cv2.imread(f'{sess}_{fr}_L.png',0);R=cv2.imread(f'{sess}_{fr}_R.png',0)
    L=cv2.GaussianBlur(L,(3,3),0);R=cv2.GaussianBlur(R,(3,3),0)
    x0,y0,x1,y1=roi;ds=[]
    for y in range(y0+P,y1-P,step):
        for x in range(x0+P,x1-P,step):
            t=L[y-P:y+P+1,x-P:x+P+1]
            if t.std()<8: continue
            xs=max(0,x-dmax-P)
            best=None
            for dy in(-1,0,1):
                if y+dy-P<0 or y+dy+P+1>800: continue
                s=R[y+dy-P:y+dy+P+1,xs:x+P+1-2]  # d>=2
                if s.shape[1]<t.shape[1]: continue
                r=cv2.matchTemplate(s,t,cv2.TM_CCOEFF_NORMED)[0]
                i=int(np.argmax(r))
                if best is None or r[i]>best[0]: best=(r[i],i+xs+P,r,i,xs,dy)
            if best is None or best[0]<0.8: continue
            c,xr,r,i,xs,dy=best
            # unicita: secondo picco lontano
            rr=r.copy();rr[max(0,i-4):i+5]=-1
            if rr.max()>c-0.05: continue
            d=x-xr
            if i>0 and i<len(r)-1:
                a,b,cc=r[i-1],r[i],r[i+1];den=a-2*b+cc
                if den!=0:d-=0.5*(a-cc)/den*-1*-1
            if d<3:continue
            ds.append(d)
    return np.array(ds)
def summarize(ds):
    if len(ds)<8:return None
    Z=F*B/ds
    lz=np.log(Z);h,e=np.histogram(lz,bins=np.arange(lz.min()-.04,lz.max()+.08,.04))
    hs=np.convolve(h,[1,2,1],'same')
    # prima popolazione con >=25% punti
    thr=max(3,.25*len(Z));pk=None
    for i in range(len(hs)):
        if hs[i]>=hs[max(0,i-1)] and hs[i]>=hs[min(len(hs)-1,i+1)] and hs[i]>=.25*hs.max() and h[max(0,i-1):i+2].sum()>=thr:
            pk=i;break
    zc=np.exp((e[pk]+e[pk+1])/2);near=Z[np.abs(Z/zc-1)<.06]
    mode=np.exp((e[np.argmax(hs)]+e[np.argmax(hs)+1])/2);modeZ=np.median(Z[np.abs(Z/mode-1)<.06])
    return dict(n=len(Z),med=float(np.median(Z)),near=float(np.median(near)),mode=float(modeZ),p10=float(np.percentile(Z,10)),p90=float(np.percentile(Z,90)))
if __name__=='__main__':
    sess,fr=sys.argv[1],int(sys.argv[2]);roi=list(map(int,sys.argv[3:7]))
    print(summarize(ncc_roi(sess,fr,roi)))
