"""Altezza camera dal piano strada (SGBM, RANSAC fascia bassa) con focale f e d0 dati: Z=f*B/(d-d0), X,Y=(u-cx,v-cy)*B/(d-d0)."""
import os,sys,json
sys.path.insert(0,os.path.dirname(__file__))
from rect import *
def run(calib,f_true,d0,B,ts):
    S=load(calib);P=pairs();T=np.array([p[0][0]/1e6 for p in P]);rng=np.random.default_rng(11)
    sg=cv2.StereoSGBM_create(minDisparity=0,numDisparities=192,blockSize=7,P1=8*49,P2=32*49,uniquenessRatio=8,speckleWindowSize=100,speckleRange=2,disp12MaxDiff=1,mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    res=[]
    for t in ts:
        k=int(np.argmin(abs(T-t)));ra,rb=rectpair(S,P,k);disp=sg.compute(ra,rb).astype(np.float32)/16.0
        yy,xx=np.mgrid[size()[1]-250:size()[1]-10:3,150:1130:3];d=disp[yy,xx];ok=d>3;dd=d[ok]-d0
        Z=f_true*B/dd;P3=np.c_[(xx[ok]-S['cx'])*B/dd,(yy[ok]-S['cy'])*B/dd,Z];P3=P3[(Z>1.2)&(Z<10)]
        if len(P3)<300: continue
        best=None;bn=0
        for _ in range(400):
            i=rng.choice(len(P3),3,replace=False);n=np.cross(P3[i[1]]-P3[i[0]],P3[i[2]]-P3[i[0]]);nr=np.linalg.norm(n)
            if nr<1e-9: continue
            n/=nr
            if n[1]<0: n=-n
            if n[1]<0.95: continue
            h=n@P3[i[0]]
            if not 0.3<h<1.8: continue
            inl=abs(P3@n-h)<0.02+0.006*P3[:,2]
            if inl.sum()>bn: best,bn=inl,inl.sum()
        if best is None or bn<0.35*len(P3): continue
        v=np.linalg.svd(np.c_[P3[best],-np.ones(best.sum())],full_matrices=False)[2][-1];nn=v[:3]/np.linalg.norm(v[:3]);hh=v[3]/np.linalg.norm(v[:3])
        if nn[1]<0: nn,hh=-nn,-hh
        res.append(dict(t=float(t),h=float(hh),pitch_up=float(-np.degrees(np.arcsin(nn[2]))),roll=float(np.degrees(np.arcsin(nn[0]))),inl=float(bn/len(P3))))
    h=np.array([r['h'] for r in res]);return res,h
if __name__=='__main__':
    f_true=float(sys.argv[2]);d0=float(sys.argv[3]);B=float(sys.argv[4])
    ts=list(np.arange(472,575,5))+list(np.arange(660,870,5))
    res,h=run(sys.argv[1],f_true,d0,B,ts)
    pi=np.array([r['pitch_up'] for r in res]);ro=np.array([r['roll'] for r in res])
    out=dict(n=len(res),h_med=float(np.median(h)),h_iqr=[float(x) for x in np.percentile(h,[25,75])],h_p10_p90=[float(x) for x in np.percentile(h,[10,90])],pitch_up_med=float(np.median(pi)),roll_med=float(np.median(ro)))
    print(out);json.dump(dict(summary=out,frames=res),open(os.path.join(W,'height_v2.json'),'w'))
