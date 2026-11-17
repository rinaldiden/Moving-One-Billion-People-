# imbardata visiva: flusso LK, modello u = a + b*(x-cx) (a = rotazione, b = espansione da avanzamento), regressione robusta. Indipendente dal giroscopio.
import sys, numpy as np, cv2
sys.path.insert(0,'training/depth'); import ego_001 as E
e=E.Ego("session_20261109_094146")
fr=np.loadtxt('asmile-loggers/asmile-001/session_20261109_094146/frames_left.csv',delimiter=',',skiprows=1,usecols=(0,1)); ft=fr[:,1]
v=np.interp(ft,e.t,e.v_s); ok=v>2.0; blocks=[]; i=0
while i<len(ok):
    if ok[i]:
        j=i
        while j<len(ok) and ok[j]: j+=1
        if (ft[j-1]-ft[i])>30000: blocks.append((i,min(j,i+1500)))
        i=j
    else: i+=1
import subprocess
pr=subprocess.Popen(['ffmpeg','-v','quiet','-r','15','-i','asmile-loggers/asmile-001/session_20261109_094146_left.h264','-vf','scale=640:400,format=gray','-f','rawvideo','-'],stdout=subprocess.PIPE,bufsize=640*400*4)
f=656.0; cx=320.0
need=np.zeros(len(ft),bool)
for a,b in blocks: need[a:b]=True
def frames():
    k=0
    while True:
        buf=b''
        while len(buf)<640*400:
            c=pr.stdout.read(640*400-len(buf))
            if not c: return
            buf+=c
        yield k,np.frombuffer(buf,np.uint8).reshape(400,640); k+=1
print('frames csv',len(ft),flush=True)
out=[]; prev=None; pk=-5
for k,g in frames():
    if k>=len(ft): break
    if not need[k]: prev=None; continue
    if prev is not None and pk==k-1:
        p0=cv2.goodFeaturesToTrack(prev,500,0.01,8)
        if p0 is not None and len(p0)>40:
            p1,st,_=cv2.calcOpticalFlowPyrLK(prev,g,p0,None,winSize=(21,21),maxLevel=3)
            m=st.ravel()==1; q0=p0[m].reshape(-1,2); q1=p1[m].reshape(-1,2)
            if len(q0)>40:
                u=q1[:,0]-q0[:,0]; x=q0[:,0]-cx; best=None; rng=np.random.default_rng(0)
                for _ in range(80):
                    ii=rng.choice(len(u),2,replace=False)
                    if abs(x[ii[0]]-x[ii[1]])<40: continue
                    bb=(u[ii[0]]-u[ii[1]])/(x[ii[0]]-x[ii[1]]); aa=u[ii[0]]-bb*x[ii[0]]
                    inl=np.abs(u-(aa+bb*x))<0.7
                    if best is None or inl.sum()>best[0]: best=(inl.sum(),inl)
                if best is not None and best[0]>25:
                    inl=best[1]; A=np.vstack([np.ones(inl.sum()),x[inl]]).T; aa,bb=np.linalg.lstsq(A,u[inl],rcond=None)[0]
                    out.append((ft[k],aa,bb,int(inl.sum())))
    prev=g.copy(); pk=k
np.save('agents/prove/occhio_corridoio_7df61925/visyaw2.npy',np.array(out))
