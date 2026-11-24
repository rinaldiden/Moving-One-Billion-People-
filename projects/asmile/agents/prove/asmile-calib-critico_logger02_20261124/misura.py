import sys,json,numpy as np,cv2
D=sys.argv[1];sys.path.insert(0,D);import os;os.chdir(D)
from sync import pairs;from extract import decode
cc=json.load(open(sys.argv[2]))
K1=np.array(cc['K_left']);K2=np.array(cc['K_right']);d1=np.array(cc['dist_left']);d2=np.array(cc['dist_right'])
r=cv2.stereoRectify(K1,d1,K2,d2,tuple(cc['size']),np.array(cc['R']),np.array(cc['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
m1=cv2.initUndistortRectifyMap(K1,d1,r[0],r[2],(1280,800),cv2.CV_32FC1);m2=cv2.initUndistortRectifyMap(K2,d2,r[1],r[2],(1280,800),cv2.CV_32FC1)
P=[q for q in pairs('143247','143252') if abs(q['dt'])<=1]
sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher()
for lo,hi,n in((90,120,12),(130,330,25),(330,520,25),(520,870,25)):
    S=[q for q in P if lo<=q['t']<hi];S=S[::max(1,len(S)//n)][:n];rr=[]
    for q in S:
        ia=decode(q['a'][0],[q['a'][1]])[q['a'][1]];ib=decode(q['b'][0],[q['b'][1]])[q['b'][1]]
        ra=cv2.remap(ia,*m1,cv2.INTER_LINEAR);rb=cv2.remap(ib,*m2,cv2.INTER_LINEAR);mk=np.zeros_like(ra);mk[8:-8,8:-8]=255
        ka,da=sift.detectAndCompute(ra,mk);kb,db=sift.detectAndCompute(rb,mk)
        if da is None or db is None or len(ka)<20 or len(kb)<20: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
        for z in ab:
            if len(z)==2 and z[0].distance<.75*z[1].distance and ba[z[0].trainIdx][0].trainIdx==z[0].queryIdx:
                a=ka[z[0].queryIdx].pt;b=kb[z[0].trainIdx].pt
                if abs(a[1]-b[1])<25 and a[0]-b[0]>1: rr.append((a[0],a[1],b[1]-a[1]))
    rr=np.array(rr);ad=abs(rr[:,2]);zr=np.clip((rr[:,1]/800*3).astype(int),0,2)
    print(lo,hi,'n',len(rr),'med %.2f p95 %.2f segno %.2f'%(np.median(ad),np.percentile(ad,95),np.median(rr[:,2])),'righe alto/centro/basso segno',[round(float(np.median(rr[zr==i,2])),2) for i in range(3)],flush=True)
