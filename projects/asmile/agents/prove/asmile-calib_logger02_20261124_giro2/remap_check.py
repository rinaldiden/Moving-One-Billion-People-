"""Verifica indipendente: cv2.remap + SIFT nuovo su coppie NON usate nel fit (k%12==6). dispari con R(pari), pari con R(dispari), ferme con R finale, e v4 come confronto."""
import os,sys,json,pickle,numpy as np,cv2
from fitlib import *
from extract import decode
W=sys.argv[1];pr=pickle.load(open(W+'/par.pkl','rb'));M=Base();P=pickle.load(open(W+'/pairs.pkl','rb'))
def calib(p,mode='RC'):
    K1,K2,d,R,T=M.build(p,mode);c=dict(M.c);c.update(K_left=K1.tolist(),K_right=K2.tolist(),dist_left=d.tolist(),dist_right=d.tolist(),R=R.tolist(),T=T.tolist());return c
def maps(c):
    K1=np.array(c['K_left']);K2=np.array(c['K_right']);d1=np.array(c['dist_left']);d2=np.array(c['dist_right']);r=cv2.stereoRectify(K1,d1,K2,d2,(1280,800),np.array(c['R']),np.array(c['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    return cv2.initUndistortRectifyMap(K1,d1,r[0],r[2],(1280,800),cv2.CV_32FC1),cv2.initUndistortRectifyMap(K2,d2,r[1],r[2],(1280,800),cv2.CV_32FC1)
def sel(f,n):
    c=[(k,p) for k,p in enumerate(P) if k%12==6 and f(p[0][0]/1e6)];return [p for _,p in c[::max(1,len(c)//n)][:n]]
odd=lambda t:(130<=t<330 or 390<=t<715) and int(t//60)%2==1;even=lambda t:(130<=t<330 or 390<=t<715) and int(t//60)%2==0;fer=lambda t:330<=t<360 or 720<=t<830
sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();out={}
def run(tag,pairs,cals):
    imgs=[(decode(a[1],[a[2]])[a[2]],decode(b[1],[b[2]])[b[2]]) for a,b,_ in pairs];mp={k:maps(c) for k,c in cals.items()}
    for k,(m1,m2) in mp.items():
        rr=[]
        for ia,ib in imgs:
            ra=cv2.remap(ia,*m1,cv2.INTER_LINEAR);rb=cv2.remap(ib,*m2,cv2.INTER_LINEAR);mk=np.zeros_like(ra);mk[8:-8,8:-8]=255
            ka,da=sift.detectAndCompute(ra,mk);kb,db=sift.detectAndCompute(rb,mk)
            if da is None or db is None or len(ka)<20 or len(kb)<20: continue
            ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
            for q in ab:
                if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                    a=ka[q[0].queryIdx].pt;b=kb[q[0].trainIdx].pt
                    if abs(a[1]-b[1])<40 and a[0]-b[0]>1: rr.append((a[0],a[1],b[1]-a[1]))
        rr=np.array(rr);ad=abs(rr[:,2]);zz=np.clip((rr[:,1]/800*3).astype(int),0,2)*3+np.clip((rr[:,0]/1280*3).astype(int),0,2)
        out[tag+'|'+k]=dict(coppie=len(imgs),n=len(rr),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),segno=float(np.median(rr[:,2])),zone=[[int((zz==i).sum()),round(float(np.median(ad[zz==i])),2) if (zz==i).sum()>=15 else None] for i in range(9)])
        print(tag,k,out[tag+'|'+k]['coppie'],out[tag+'|'+k]['n'],'med %.2f p95 %.2f segno %.2f'%(out[tag+'|'+k]['med'],out[tag+'|'+k]['p95'],out[tag+'|'+k]['segno']),out[tag+'|'+k]['zone'],flush=True)
v4=json.load(open(V4))
run('dispari',sel(odd,60),{'R_pari':calib(pr['pari']),'v4':v4});run('pari',sel(even,60),{'R_dispari':calib(pr['dispari']),'v4':v4});run('ferme',sel(fer,30),{'R_finale':calib(pr['par']),'v4':v4})
json.dump(out,open(W+'/../remap_v5.json','w'),indent=1)
