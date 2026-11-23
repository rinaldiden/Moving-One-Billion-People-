"""Strada 4: baseline dalle targhe in AUTOMATICO. Rileva rettangoli-targa (rapporto 520:110 ~ 4.7) con morfologia sui bordi verticali del testo
nel fotogramma sinistro rettificato, verifica la presenza di testo (alternanza chiaro/scuro) e il match sinistra-destra; i bordi sinistro/destro
sono presi SUB-PIXEL dal profilo di gradiente (mediana su righe) sia in L che in R. Poi larghezza 3D (con X,Z dalle disparita' dei 2 bordi, B=1)
-> B = 520 mm / larghezza3D(B=1). La focale si elimina (ne serve solo un valore approssimato per la piccola componente in Z).
Regressione lineare d = (B/520)*w - d0: pendenza = B, intercetta = -d0 (anche d0 senza focale)."""
import os,sys,json,pickle,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from rect import *
PW=520.0
def candidates(g):
    gx=np.abs(cv2.Sobel(g,cv2.CV_32F,1,0,ksize=3));gx=cv2.GaussianBlur(gx,(0,0),1.0)
    th=gx>max(25,np.percentile(gx,88))
    m=th.astype(np.uint8)*255
    out=[]
    for kw,kh in ((31,5),(21,3),(13,3)):
        mm=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(kw,kh)))
        mm=cv2.morphologyEx(mm,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(9,3)))
        n,lab,st,_=cv2.connectedComponentsWithStats(mm)
        for i in range(1,n):
            x,y,w,h,a=st[i]
            if w<60 or w>520 or h<12 or h>140: continue
            r=w/h
            if 3.6<r<6.2 and a>0.35*w*h: out.append((x,y,w,h))
    return out
def prof_grad(img,y0,y1,x0,x1):
    x0=max(int(x0),3);x1=min(int(x1),img.shape[1]-4)
    prof=np.median(img[y0:y1,x0-2:x1+3].astype(np.float32),axis=0)
    p=cv2.GaussianBlur(prof.reshape(1,-1),(0,0),0.9).ravel();return x0,prof,np.gradient(p)[2:-2]
def subpix(g,j,sign):
    if j<=0 or j>=len(g)-1: return float(j)
    a,b,c=sign*g[j-1],sign*g[j],sign*g[j+1];den=a-2*b+c
    return j+(0.5*(a-c)/den if den!=0 else 0.0)
def valley(prof,i0,i1):
    p=cv2.GaussianBlur(prof.astype(np.float32).reshape(1,-1),(0,0),0.8).ravel();seg=p[i0:i1]
    if len(seg)<5: return None
    j=int(np.argmin(seg))+i0
    if j<=1 or j>=len(p)-2: return None
    a,b,c=p[j-1],p[j],p[j+1];den=a-2*b+c;sub=j+(0.5*(a-c)/den if den>0 else 0.0)
    ctx=min(np.max(p[max(j-12,0):j]),np.max(p[j+1:j+13]))
    return float(sub),float(ctx-p[j])
def plate_edges(img,y0,y1,x,w):
    """bordo della targa = fondo (valle) scuro della cornice nera ai due lati, sub-pixel, su profilo mediano della banda centrale.
    (Il portatarga e la bordatura nera della targa sono scuri; la banda blu sx e' grigia: la valle piu' esterna e' il bordo targa +-2-3 mm)."""
    xa=int(x-0.12*w);xb=int(x+1.12*w)
    if xa<4 or xb>img.shape[1]-5: return None
    prof=np.median(img[y0:y1,xa:xb].astype(np.float32),axis=0)
    L=valley(prof,int(0.04*w),int(0.24*w));Rr=valley(prof,int(1.00*w),int(1.20*w)-0)
    if L is None or Rr is None: return None
    return float(xa+L[0]),float(xa+Rr[0]),float(min(L[1],Rr[1]))
def text_ok(img,y0,y1,xl,xr):
    seg=np.median(img[y0:y1,int(xl)+int(0.1*(xr-xl)):int(xr)-int(0.1*(xr-xl))].astype(np.float32),axis=0)
    if len(seg)<30: return 0
    g=np.diff(cv2.GaussianBlur(seg.reshape(1,-1),(0,0),1.0).ravel());thr=0.12*(np.percentile(seg,95)-np.percentile(seg,5))
    big=np.abs(g)>thr;sg=np.sign(g)[big]
    return int(np.sum(sg[1:]!=sg[:-1]))
def measure_plate(ra,rb,box,f):
    x,y,w,h=box
    tpl=ra[y:y+h,x:x+w];xs0=max(x-int(0.9*w)-60,0);roi=rb[max(y-4,0):y+h+4,xs0:x+w+10]
    if roi.shape[0]<tpl.shape[0] or roi.shape[1]<tpl.shape[1]: return None
    r=cv2.matchTemplate(roi,tpl,cv2.TM_CCOEFF_NORMED);_,mv,_,ml=cv2.minMaxLoc(r)
    if mv<0.7: return None
    dc=x-(xs0+ml[0]);dy=(max(y-4,0)+ml[1])-y
    if dc<4 or abs(dy)>6: return None
    by0=y+int(0.3*h);by1=y+int(0.7*h)
    eL=plate_edges(ra,by0,by1,x,w);eR=plate_edges(rb,by0+dy,by1+dy,x-dc,w)
    if eL is None or eR is None: return None
    nt=text_ok(ra,by0,by1,eL[0],eL[1])
    return dict(box=box,ncc=float(mv),xl=eL[0],xr=eL[1],xl_R=eR[0],xr_R=eR[1],wL=eL[1]-eL[0],wR=eR[1]-eR[0],dL=eL[0]-eR[0],dR=eL[1]-eR[1],contr=min(eL[2],eR[2]),ntext=nt,dy=float(dy),yc=float(y+h/2))
def width3d(m,S):
    f,cx=S['f'],S['cx'];dl,dr=m['dL'],m['dR']
    if dl<=2 or dr<=2: return None
    dX=((m['xr']-cx)/dr-(m['xl']-cx)/dl);dZ=f*(1/dr-1/dl)
    return float(np.hypot(dX,dZ)),float(np.degrees(np.arctan2(dZ,dX)))   # larghezza con B=1 ; angolo targa vs piano immagine
if __name__=='__main__':
    S=load();P=pairs();T=np.array([p[0][0]/1e6 for p in P])
    lo,hi=float(sys.argv[1]),float(sys.argv[2]);step=int(sys.argv[3]);dbg=len(sys.argv)>4
    rows=[]
    ks=[k for k in range(len(P)) if lo<=T[k]<hi][::step]
    for k in ks:
        ra,rb=rectpair(S,P,k)
        for bx in candidates(ra):
            m=measure_plate(ra,rb,bx,S['f'])
            if m is None: continue
            w3=width3d(m,S)
            if w3 is None: continue
            m.update(k=int(k),t=float(T[k]),w3=w3[0],ang=w3[1]);rows.append(m)
    print('righe',len(rows))
    pickle.dump(rows,open(os.path.join(W,'plates_raw_%d_%d.pkl'%(lo,hi)),'wb'))
