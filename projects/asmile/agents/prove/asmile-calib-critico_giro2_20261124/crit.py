import glob,csv,json,sys,subprocess,numpy as np,cv2
D='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02'
def rows(side,tag,col):
    o=[]
    for f in sorted(glob.glob(f'{D}/clip_20261124_{tag}_{side}_*_frames.csv')):
        for i,r in enumerate(csv.DictReader(open(f))): o.append((int(r[col]),f.replace('_frames.csv','.h264'),i))
    return o
A=rows('A','162459','t_us');B=sorted(rows('B','162506','t_a_us'))
tb=np.array([r[0] for r in B]);ta=np.array([r[0] for r in A])
print('B t_a monotona:',(np.diff(tb)>0).all(),'A t_us==t_a_us?')
j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1);dt=(tb[jj]-ta)
ok=(abs(dt)<=100)&(ta>=130e6)
print('pairs ok',ok.sum(),'dt med/p95/max us',np.median(abs(dt[ok])),np.percentile(abs(dt[ok]),95),abs(dt[ok]).max(),'dup B usate',len(jj[ok])-len(set(jj[ok])))
# A-frame spacing: B nearest sempre dentro 1/2 periodo? periodo medio
print('periodo A us',np.median(np.diff(ta)))
c=json.load(open('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v5_20261124.json'))
K1=np.array(c['K_left']);K2=np.array(c['K_right']);d=np.array(c['dist_left']);R=np.array(c['R']);T=np.array(c['T']).reshape(3,1)
r=cv2.stereoRectify(K1,d,K2,np.array(c['dist_right']),(1280,800),R,T,flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
m1=cv2.initUndistortRectifyMap(K1,d,r[0],r[2],(1280,800),cv2.CV_32FC1);m2=cv2.initUndistortRectifyMap(K2,np.array(c['dist_right']),r[1],r[2],(1280,800),cv2.CV_32FC1)
def dec(clip,idx):
    e='+'.join(f'eq(n\\,{i})' for i in idx);p=subprocess.run(['ffmpeg','-v','error','-i',clip,'-vf',f"select='{e}'",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    v=np.frombuffer(p.stdout,np.uint8);return v.reshape(-1,800,1280)
sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher()
def run(tag,lo,hi,n,off):
    idx=[i for i in np.where(ok&(ta>=lo*1e6)&(ta<hi*1e6))[0] if i%12==off];idx=idx[::max(1,len(idx)//n)][:n]
    rr=[]
    for i in idx:
        a=dec(A[i][1],[A[i][2]]);b=dec(B[jj[i]][1],[B[jj[i]][2]])
        if len(a)!=1 or len(b)!=1: continue
        ra=cv2.remap(a[0],*m1,cv2.INTER_LINEAR);rb=cv2.remap(b[0],*m2,cv2.INTER_LINEAR);mk=np.zeros_like(ra);mk[8:-8,8:-8]=255
        ka,da=sift.detectAndCompute(ra,mk);kb,db=sift.detectAndCompute(rb,mk)
        if da is None or db is None or len(ka)<20 or len(kb)<20: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
        for q in ab:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                p=ka[q[0].queryIdx].pt;s=kb[q[0].trainIdx].pt
                if abs(p[1]-s[1])<40 and p[0]-s[0]>1: rr.append((p[0],p[1],s[1]-p[1],p[0]-s[0]))
    rr=np.array(rr);ad=abs(rr[:,2])
    zz=np.clip((rr[:,1]/800*3).astype(int),0,2)*3+np.clip((rr[:,0]/1280*3).astype(int),0,2)
    print(tag,'pairs',len(idx),'n',len(rr),'med %.2f p95 %.2f segno %.2f'%(np.median(ad),np.percentile(ad,95),np.median(rr[:,2])))
    print('  zone med',[round(float(np.median(ad[zz==k])),2) if (zz==k).sum()>=15 else None for k in range(9)],'segno',[round(float(np.median(rr[zz==k,2])),2) if (zz==k).sum()>=15 else None for k in range(9)])
    for lo_,hi_ in((1,15),(15,40),(40,400)):
        s=(rr[:,3]>=lo_)&(rr[:,3]<hi_);print('  disp',lo_,hi_,s.sum(),'med|dy| %.2f segno %.2f'%(np.median(ad[s]),np.median(rr[s,2])) if s.sum()>10 else '')
for tag,lo,hi,n,off in [('ferma1_off3',330,360,25,3),('ferma2_off3',720,830,25,3),('moto_off3_130-330',130,330,40,3),('moto_off9_390-715',390,715,40,9)]: run(tag,lo,hi,n,off)
