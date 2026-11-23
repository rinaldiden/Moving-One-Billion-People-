"""Interasse 150 vs 200 mm, passo 1 (logger02 giro2): finestre di N fotogrammi consecutivi -> rettifica (calib v3) -> SGBM 200 mm
(LR-consistency) -> tracce LK di punti -> serie di disparita' per traccia. Salva npz nella cartella di lavoro (NON su git).
uso: python3 interasse_prep.py <giro_dir> <calib.json> <lavoro> [n_finestre=14] [N=9]   (max 2 processi)"""
import os,sys,glob,csv,collections,subprocess,numpy as np,cv2
from multiprocessing import Pool
def rows(side,D):
    out=[]
    for f in sorted(glob.glob(f'{D}/{side}/clip_*_{side}_*_frames.csv')):
        clip=f.replace('_frames.csv','.h264');sess=os.path.basename(f).split('_')[2]+'_'+os.path.basename(f).split('_')[3]
        for i,r in enumerate(csv.DictReader(open(f))): out.append((int(r['t_us' if side=='A' else 't_a_us']),clip,i,sess))
    return out
def windows(D,nwin,N,tmin=390,tmax=1040):
    A=[r for r in rows('A',D) if r[3].endswith('134617_A')];B=[r for r in rows('B',D) if r[3].startswith('134615')]
    tb=np.array([r[0] for r in B]);cand=[]
    for i in range(len(A)-N):
        t=A[i][0]/1e6
        if t<tmin or t>tmax:continue
        seg=A[i:i+N]
        if len({s[1] for s in seg})!=1 or any(seg[k+1][2]-seg[k][2]!=1 for k in range(N-1)):continue
        ta=np.array([s[0] for s in seg]);j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1)
        if np.abs(tb[jj]-ta).max()>10000:continue
        bs=[B[k] for k in jj]
        if len({b[1] for b in bs})!=1:continue
        cand.append((t,seg[0][1],[s[2] for s in seg],bs[0][1],[b[2] for b in bs]))
    if isinstance(nwin,list):
        ts=np.array([c[0] for c in cand]);return [cand[int(np.argmin(abs(ts-x)))] for x in nwin]
    sel=np.linspace(0,len(cand)-1,nwin).astype(int);return [cand[k] for k in sel]
def decode(clip,idx):
    expr='+'.join(f'eq(n\\,{i})' for i in idx)
    p=subprocess.run(['ffmpeg','-v','error','-i',clip,'-vf',f"select='{expr}'",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    W,H=1280,720;v=np.frombuffer(p.stdout,np.uint8);n=len(v)//(W*H);assert n==len(idx);return v.reshape(n,H,W)
def rectmaps(calib):
    import json;c=json.load(open(calib));K1=np.array(c['K_left']);K2=np.array(c['K_right']);d1=np.array(c['dist_left']);d2=np.array(c['dist_right'])
    r=cv2.stereoRectify(K1,d1,K2,d2,tuple(c['size']),np.array(c['R']),np.array(c['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    m1=cv2.initUndistortRectifyMap(K1,d1,r[0],r[2],tuple(c['size']),cv2.CV_32FC1);m2=cv2.initUndistortRectifyMap(K2,d2,r[1],r[2],tuple(c['size']),cv2.CV_32FC1)
    return m1,m2,float(r[2][0,0]),float(np.linalg.norm(np.array(c['T']))),float(c.get('d0_px',0))
MIND=-16;ND=288
def sgbm():
    return cv2.StereoSGBM_create(minDisparity=MIND,numDisparities=ND,blockSize=9,P1=8*3*81,P2=32*3*81,disp12MaxDiff=1,uniquenessRatio=5,speckleWindowSize=200,speckleRange=2,preFilterCap=63,mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
def disp_lr(L,R,sg,thr=1.0):
    dl=sg.compute(L,R).astype(np.float32)/16
    dr=sg.compute(np.ascontiguousarray(R[:,::-1]),np.ascontiguousarray(L[:,::-1])).astype(np.float32)[:,::-1]/16
    h,w=dl.shape;xs=np.arange(w)[None,:].repeat(h,0);xr=np.clip(np.round(xs-dl).astype(int),0,w-1)
    back=np.take_along_axis(dr,xr,1)
    ok=(dl>MIND+0.5)&(dl<MIND+ND-2)&(np.abs(dl-back)<=thr)
    return dl,ok
def work(a):
    k,(t,ca,ia,cb,ib),calib,out=a;m1,m2,f,B,d0=rectmaps(calib)
    A=decode(ca,ia);Bm=decode(cb,ib);sg=sgbm();Ls=[];Ds=[];Os=[]
    for x,y in zip(A,Bm):
        L=cv2.remap(x,*m1,cv2.INTER_LINEAR);R=cv2.remap(y,*m2,cv2.INTER_LINEAR);dl,ok=disp_lr(L,R,sg);Ls.append(L);Ds.append(dl.astype(np.float16));Os.append(ok)
    # tracce LK sul primo fotogramma, avanti e check indietro
    L0=Ls[0];valid=cv2.erode(Os[0].astype(np.uint8),np.ones((5,5)))>0;valid[:20]=0;valid[-20:]=0;valid[:,:20]=0;valid[:,-20:]=0
    p0=cv2.goodFeaturesToTrack(L0,1500,0.01,8,mask=valid.astype(np.uint8)*255);tr=[p0.reshape(-1,2)];alive=np.ones(len(p0),bool);cur=p0
    for n in range(1,len(Ls)):
        p1,s,_=cv2.calcOpticalFlowPyrLK(Ls[n-1],Ls[n],cur,None,winSize=(21,21),maxLevel=3)
        pb,sb,_=cv2.calcOpticalFlowPyrLK(Ls[n],Ls[n-1],p1,None,winSize=(21,21),maxLevel=3)
        alive&=(s[:,0]==1)&(sb[:,0]==1)&(np.linalg.norm(pb-cur,axis=2)[:,0]<0.5);tr.append(p1.reshape(-1,2));cur=p1
    tr=np.stack(tr,1);H,W=L0.shape
    dd=np.full((len(p0),len(Ls)),np.nan,np.float32)
    for n in range(len(Ls)):
        for q in range(len(p0)):
            if not alive[q]:continue
            x,y=np.round(tr[q,n]).astype(int)
            if x<2 or y<2 or x>=W-2 or y>=H-2:alive[q]=False;continue
            o=Os[n][y-1:y+2,x-1:x+2];d=Ds[n][y-1:y+2,x-1:x+2].astype(np.float32)
            if o.sum()>=5:dd[q,n]=np.median(d[o])
    np.savez_compressed(f'{out}/win{k:02d}.npz',t=t,L0=L0,D=np.stack(Ds),OK=np.stack(Os),tr=tr,dd=dd,alive=alive,f=f,B=B,d0=d0,ia=ia)
    return k,t,int(alive.sum())
if __name__=='__main__':
    D,calib,out=map(os.path.abspath,sys.argv[1:4]);nw=[float(x) for x in sys.argv[4].split(',')] if len(sys.argv)>4 else 14;N=int(sys.argv[5]) if len(sys.argv)>5 else 9
    os.makedirs(out,exist_ok=True);W=windows(D,nw,N);print(len(W),'finestre',[round(w[0]) for w in W],flush=True)
    with Pool(2) as p:
        for r in p.imap_unordered(work,[(k,w,calib,out) for k,w in enumerate(W)]):print(r,flush=True)
