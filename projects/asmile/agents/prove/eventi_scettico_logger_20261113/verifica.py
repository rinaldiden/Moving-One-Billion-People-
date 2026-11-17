import glob,os,datetime as dt,numpy as np,cv2,pandas as pd,sys
cv2.setNumThreads(2)
L="asmile-loggers/asmile-logger/"
def ep(s): return dt.datetime.fromisoformat(s).timestamp()
RIDES={"1050":("2026-11-09T10:50:10","2026-11-09T10:55:15"),"1109":("2026-11-09T11:09:05","2026-11-09T11:14:40")}
out=[]
for k,(a,b) in RIDES.items():
    a,b=ep(a),ep(b)
    cl=sorted((os.path.getmtime(f),f) for f in glob.glob(L+"clip_20261109_*.h264"))
    for mt,f in cl:
        if mt<a-1 or mt>b+40: continue
        cap=cv2.VideoCapture(f); fr=[]
        while True:
            ok,im=cap.read()
            if not ok:break
            g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY) if im.ndim==3 else im
            fr.append(cv2.resize(g[:,:1280][300:780],(320,120)))
        n=len(fr)
        for i in range(1,n):
            fl=cv2.calcOpticalFlowFarneback(fr[i-1],fr[i],None,0.5,2,15,2,5,1.1,0)
            mag=np.hypot(fl[...,0],fl[...,1])
            out.append((mt-(n-1-i)/15.0,k,float(np.median(mag[40:,:])),float(np.mean(np.abs(fr[i].astype(float)-fr[i-1])))))
    print(k,len(out),flush=True)
pd.DataFrame(out,columns=["wall","ride","flow","diff"]).to_csv(os.path.dirname(__file__)+"/flusso.csv",index=False)
