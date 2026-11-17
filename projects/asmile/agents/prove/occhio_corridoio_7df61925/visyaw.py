# asmile-occhio: imbardata VISIVA indipendente (essential matrix LK) su 094146 cam left, finestre v>2
import sys, csv, numpy as np, cv2
sys.path.insert(0,'training/depth'); import ego_001 as E
cv2.setNumThreads(2)
e=E.Ego("session_20261109_094146"); 
fr=np.loadtxt('asmile-loggers/asmile-001/session_20261109_094146/frames_left.csv',delimiter=',',skiprows=1,usecols=(0,1))
ft=fr[:,1]; v=np.interp(ft,e.t,e.v_s)
# finestre: blocchi consecutivi con v>2 lunghi >=30s, prendo i primi 5 distinti separati
ok=v>2.0; blocks=[]; i=0
while i<len(ok):
    if ok[i]:
        j=i
        while j<len(ok) and ok[j]: j+=1
        if (ft[j-1]-ft[i])>30000: blocks.append((i,j))
        i=j
    else: i+=1
print(len(blocks),[(b[0],b[1]) for b in blocks][:10])
sel=[]; last=-9999
for b in blocks:
    sel.append((b[0],min(b[1],b[0]+1500)))
sel=sel[:6]; print(sel)
cap=cv2.VideoCapture('asmile-loggers/asmile-001/session_20261109_094146_left.h264')
K=np.array([[656,0,320],[0,656,200],[0,0,1.]])
out=[]
prev=None; idx=0
for (a,b) in sel:
    cap.set(cv2.CAP_PROP_POS_FRAMES,a); 
    prev=None
    for k in range(a,b):
        ret,im=cap.read()
        if not ret: break
        g=cv2.cvtColor(cv2.resize(im,(640,400)),cv2.COLOR_BGR2GRAY)
        if prev is not None:
            p0=cv2.goodFeaturesToTrack(prev,600,0.01,8)
            yaw=np.nan
            if p0 is not None and len(p0)>50:
                p1,st,_=cv2.calcOpticalFlowPyrLK(prev,g,p0,None,winSize=(21,21),maxLevel=3)
                m=st.ravel()==1; q0=p0[m].reshape(-1,2); q1=p1[m].reshape(-1,2)
                if len(q0)>50:
                    Em,mk=cv2.findEssentialMat(q0,q1,K,cv2.RANSAC,0.999,1.0)
                    if Em is not None and Em.shape==(3,3):
                        n,R,t,_=cv2.recoverPose(Em,q0,q1,K,mask=mk)
                        rv,_=cv2.Rodrigues(R); yaw=float(rv[1,0]); 
                        out.append((ft[k],yaw,int(mk.sum()),float(np.degrees(np.linalg.norm(rv)))))
        prev=g
    print('blocco',a,b,len(out),flush=True)
np.save('agents/prove/occhio_corridoio_7df61925/visyaw.npy',np.array(out))
