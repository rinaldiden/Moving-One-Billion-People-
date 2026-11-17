import sys, os, subprocess, numpy as np, cv2, math
sys.path.insert(0,'training/depth'); sys.path.insert(0,'pi/autonomous')
import ego_001 as E, corridoio_replay_001 as R
from corridoio import Corridoio
OUT='agents/prove/occhio_corridoio_7df61925/fr'; os.makedirs(OUT,exist_ok=True)
t,cum,g,st=R.carica(); s=cum*2.1219e-5
c=Corridoio("asmile-001",calib=R.CAL_0911); v=R.vcausale(t,s)
KK=np.zeros(len(t)); OZ=np.zeros(len(t))
for i in range(len(t)):
    c.update(t[i],st[i],v[i],g[i]); KK[i]=c.k; OZ[i]=c.orizzonte
fr=np.loadtxt('asmile-loggers/asmile-001/session_20261109_094146/frames_left.csv',delimiter=',',skiprows=1,usecols=(0,1)); ft=fr[:,1]
e=E.Ego("session_20261109_094146"); vf=np.interp(ft,e.t,e.v_s)
rng=np.random.default_rng(20261113)
cand=np.where((vf>2.0)&(ft>ft[0]+20000)&(np.arange(len(ft))<len(ft)-120))[0]
cand=cand[::5]
stf=np.interp(ft[cand],e.t,e.steer_s)
big=cand[np.argsort(-np.abs(stf))[:60]]; pick=list(rng.choice(big,10,replace=False))
rest=[x for x in cand if x not in set(big)]; pick+=list(rng.choice(rest,10,replace=False))
# decimazione: evita vicini
pick=sorted(set(pick)); print(len(pick),pick)
want=set(pick); F=1379.9; cx,cy=640,400; pitch=math.radians(7.4); h=0.825
imgs={}
pr=subprocess.Popen(['ffmpeg','-v','quiet','-r','15','-i','asmile-loggers/asmile-001/session_20261109_094146_left.h264','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
k=0; mx=max(want)
while k<=mx:
    buf=b''
    while len(buf)<1280*800:
        d=pr.stdout.read(1280*800-len(buf))
        if not d: break
        buf+=d
    if len(buf)<1280*800: break
    if k in want: imgs[k]=np.frombuffer(buf,np.uint8).reshape(800,1280).copy()
    k+=1
pr.kill()
def proj(X,Z):
    zc=Z*math.cos(pitch)+h*math.sin(pitch); yc=h*math.cos(pitch)-Z*math.sin(pitch)
    return F*X/zc+cx, F*yc/zc+cy, (zc>0.3)&(yc>0)
K3=np.array([[F,0,cx],[0,F,cy],[0,0,1.]])
tiles=[]
for k in pick:
    row=int(np.searchsorted(t,ft[k]/1000)); c.k=KK[row]; c.orizzonte=OZ[row]; c.psi0=0; c.x0=0; c._cache=None
    im=cv2.cvtColor(imgs[k],cv2.COLOR_GRAY2BGR)
    poly=c.poligono_immagine(K3,pitch)
    ov=im.copy()
    if len(poly): cv2.fillPoly(ov,[poly.astype(np.int32)],(0,200,0)); im=cv2.addWeighted(ov,0.35,im,0.65,0); cv2.polylines(im,[poly.astype(np.int32)],True,(0,255,0),2)
    # percorso reale: centro bici nei prossimi metri (odometria ruota + imbardata vista dal gz bias-corretto)
    j=row; tt=t[j:j+4000]; sv=s[j:j+4000]-s[j]; yaw=np.cumsum(np.radians(-(g[j:j+4000]-1.75))*np.gradient(tt))
    px=np.cumsum(np.gradient(sv)*np.sin(yaw)); pz=np.cumsum(np.gradient(sv)*np.cos(yaw))
    for Zt in (2,3,4,6,8,10,13):
        if pz[-1]<Zt: break
        x=np.interp(Zt,pz,px); u,vv,ok=proj(x,Zt)
        if ok and 0<u<1280 and 0<vv<800: cv2.circle(im,(int(u),int(vv)),7,(0,0,255),-1); cv2.putText(im,f"{Zt}",(int(u)+8,int(vv)),0,0.6,(0,0,255),2)
    cv2.putText(im,f"f{k} v{vf[k]:.1f} k{KK[row]:+.3f} sterzo{np.interp(ft[k],e.t,e.steer_s):+.0f}",(10,30),0,0.8,(0,255,255),2)
    cv2.imwrite(f'{OUT}/f{k}.jpg',im); tiles.append(cv2.resize(im,(640,400)))
for n in range(0,len(tiles),4):
    grp=tiles[n:n+4]
    while len(grp)<4: grp.append(np.zeros_like(tiles[0]))
    cv2.imwrite(f'{OUT}/sheet{n//4}.jpg',np.vstack([np.hstack(grp[:2]),np.hstack(grp[2:])]))
