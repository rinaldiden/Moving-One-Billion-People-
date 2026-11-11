import sys,pickle,json,subprocess
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth')
import numpy as np,cv2
from stereo_common import Calib
cal=Calib.load(sys.argv[1]); tag=sys.argv[2]; SESS=sys.argv[3]; SEG=[tuple(x) for x in json.load(open(sys.argv[4]))]; STEP=int(sys.argv[5]) if len(sys.argv)>5 else 6
r=cal.rectify(); fx=r['focal_px']; B=r['baseline_m']; cx=float(r['P1'][0,2]); cy=float(r['P1'][1,2])
base='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/asmile-001/'+SESS+'/'
KEEP=None
NLAST=int(json.load(open(sys.argv[4]+'.last')))
def frames(f):
    p=subprocess.Popen(['ffmpeg','-v','quiet','-i',base+f,'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
    while True:
        b=p.stdout.read(1280*800)
        if len(b)<1280*800: break
        yield np.frombuffer(b,np.uint8).reshape(800,1280).copy()
# (f0,f1,etichetta,D nominale m, lateralita' nominale m, +dx), video_right = fisicamente SINISTRA
allf=[x for s in SEG for x in range(s[0],s[1])]
def keep(f):
    d={};last=[]
    for i,x in enumerate(frames(f)):
        if i in allset: d[i]=x
        last.append(x) if i>=NLAST else None
        if len(last)>40: last.pop(0)
    return d,last
allset=set(allf)
FL,lastL=keep('video_right.h264'); FR,_=keep('video_left.h264')
print(len(FL),len(FR),len(lastL))
bg=np.median(np.array(lastL[-30:-5]),axis=0).astype(np.uint8)
sgbm=cv2.StereoSGBM_create(minDisparity=0,numDisparities=320,blockSize=7,P1=8*49,P2=32*49,uniquenessRatio=8,speckleWindowSize=80,speckleRange=2,disp12MaxDiff=1,mode=cv2.STEREO_SGBM_MODE_HH)
res=[]
for sg in SEG:
    for i in range(sg[0],sg[1],STEP):
        gl,gr=FL[i],FR[i]
        sc=np.median(bg)/max(np.median(gl),1); gn=np.clip(gl.astype(np.float32)*sc,0,255).astype(np.uint8)
        d=cv2.GaussianBlur(cv2.absdiff(gn,bg),(5,5),0)
        mk=(d>22).astype(np.uint8); mk=cv2.morphologyEx(mk,cv2.MORPH_OPEN,np.ones((3,3),np.uint8)); mk=cv2.dilate(mk,np.ones((9,9),np.uint8))
        mk=cv2.remap(mk,r['m1x'],r['m1y'],cv2.INTER_NEAREST)
        n,lab,st,cen=cv2.connectedComponentsWithStats(mk)
        q=[j for j in range(1,n) if st[j,4]>300]
        if not q: continue
        j=max(q,key=lambda j:st[j,4]); x,y,w,h=st[j,:4]
        rl=cv2.remap(gl,r['m1x'],r['m1y'],cv2.INTER_LINEAR); rr=cv2.remap(gr,r['m2x'],r['m2y'],cv2.INTER_LINEAR)
        x0=int(x+0.25*w);x1=int(x+0.75*w);y0=int(y+0.25*h);y1=int(y+0.65*h)
        disp=sgbm.compute(rl,rr).astype(np.float32)/16
        v=disp[y0:y1,x0:x1]; v=v[v>1]
        # secondo metodo indipendente: NCC su strisce del ritaglio (cerca lo spostamento a sx nell'immagine destra)
        dn=[]
        for yy in range(y0,y1-24,16):
            t=rl[yy:yy+24,x0:x1]
            if t.std()<3: continue
            xs=max(0,x0-260)
            sr=rr[yy:yy+24,xs:x1+4]
            res_=cv2.matchTemplate(sr,t,cv2.TM_CCOEFF_NORMED)
            _,mv,_,ml=cv2.minMaxLoc(res_)
            if mv>0.6:
                dd=x0-(xs+ml[0])
                # raffinamento parabolico
                if 0<ml[0]<res_.shape[1]-1:
                    a_,b_,c_=res_[0,ml[0]-1],res_[0,ml[0]],res_[0,ml[0]+1]; dd-=0.5*(a_-c_)/(a_-2*b_+c_+1e-9)
                dn.append(dd)
        Zn=fx*B/float(np.median(dn)) if len(dn)>=3 else None
        if len(v)>30 or Zn:
            if len(v)<=30: v=np.array([np.median(dn)]*31)
            dm=float(np.median(v)); Z=fx*B/dm; uc=(x0+x1)/2; vc=(y0+y1)/2
            res.append(dict(Zn=Zn,nn=len(dn),seg=sg[2],D=sg[3],lat=sg[4],frame=i,disp=dm,n=int(len(v)),Z=Z,X=(uc-cx)*Z/fx-B/2,Y=(vc-cy)*Z/fx,bbox=[int(x),int(y),int(w),int(h)]))
pickle.dump(res,open(f'/tmp/cv2/soste_{tag}.pkl','wb'))
import collections
by=collections.defaultdict(list)
for q in res: by[q['seg']].append(q)
for k,v in by.items():
    Z=np.array([q['Z'] for q in v]);X=np.array([q['X'] for q in v]);Zn=[q['Zn'] for q in v if q['Zn']]
    print(k,'NCC Z med',np.median(Zn) if Zn else None,len(Zn))
    print(k,len(v),'Z med %.3f p10 %.3f p90 %.3f X %.2f D %s err %s'%(np.median(Z),np.percentile(Z,10),np.percentile(Z,90),np.median(X),v[0]['D'],('%.1f%%'%(100*(np.median(Z)/v[0]['D']-1))) if v[0]['D'] else '-'))
