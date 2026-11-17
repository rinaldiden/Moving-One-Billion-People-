import sys, os, pickle, math, numpy as np, cv2
sys.path.insert(0,'.'); sys.path.insert(0,'../../pi/autonomous')
import depth_seg_001 as D
from corridoio import Corridoio
import corridoio_replay_001 as R
a=pickle.load(open('out_20261112_v12/tracks_20261109_094146.pkl','rb')); b=pickle.load(open('../../agents/prove/occhio_corridoio_7df61925/new/tracks_20261109_094146.pkl','rb'))
fr=a['frames']; want=[2066,2068,2467,2473,2483,2486,2495,2500,2506,2069]
rc=D.Rect(); cy=rc.cy; F=rc.f; cx=rc.cx; K=np.array([[F,0,cx],[0,F,cy],[0,0,1.]]); pitch=math.radians(7.4)
OUT='../../agents/prove/occhio_corridoio_7df61925/frena'; os.makedirs(OUT,exist_ok=True)
c=Corridoio("asmile-001",calib=R.CAL_0911)
imgs={}
for i,L in enumerate(D.gray_frames(os.path.join(D.LOGS,"session_20261109_094146_right.h264"))):
    if i in want: imgs[i]=L.copy()
    if i>max(want): break
tiles=[]
for f in want:
    n=fr.index(f); k=b['cs'][n]['k']; v=b['cs'][n]['v']
    c.k=k; c._cache=None; c.psi0=0; c.x0=0; c.v_f=max(v,1.39); c.orizzonte=c.muso+c.sog.a(max(v,1.39))['rallenta_entro_m']
    L=cv2.remap(imgs[f],rc.r["m1x"],rc.r["m1y"],cv2.INTER_LINEAR); im=cv2.cvtColor(L,cv2.COLOR_GRAY2BGR)
    poly=c.poligono_immagine(K,pitch,h_cam=0.825)
    if len(poly): cv2.polylines(im,[poly.astype(np.int32)],True,(0,255,0),3)
    # vecchio corridoio: |X|<=1.5+0.03Z
    for sg in (-1,1):
        pts=[]
        for Z in np.geomspace(1.5,10,20):
            X=sg*(1.5+0.03*Z); zc=Z*math.cos(pitch)+0.825*math.sin(pitch); yc=0.825*math.cos(pitch)-Z*math.sin(pitch); pts.append((int(F*X/zc+cx),int(F*yc/zc+cy)))
        cv2.polylines(im,[np.array(pts,np.int32)],False,(0,0,255),2)
    for r in a['per'][n]:
        if r['id'] in set(v_ for v_ in a['cs'][n]['first'].values() if v_ is not None):
            x0,y0,x1,y1=r['box']; cv2.rectangle(im,(x0,y0),(x1,y1),(255,200,0),3); cv2.putText(im,f"id{r['id']} {r['fam']} Z{r['Z']:.1f} X{r['X']:+.2f}",(max(x0,5),max(y0+30,30)),0,1.0,(255,200,0),2)
    cv2.putText(im,f"f{f} v{v:.1f} verde=nuovo rosso=v12",(10,40),0,1.0,(0,255,255),2)
    cv2.imwrite(f'{OUT}/f{f}.jpg',im); tiles.append(cv2.resize(im,(640,400)))
for s in range(0,len(tiles),4):
    g=tiles[s:s+4]
    while len(g)<4: g.append(np.zeros_like(tiles[0]))
    cv2.imwrite(f'{OUT}/sheet{s//4}.jpg',np.vstack([np.hstack(g[:2]),np.hstack(g[2:])]))
