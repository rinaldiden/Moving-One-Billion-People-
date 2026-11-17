import cv2,numpy as np,pandas as pd,subprocess,sys
B='asmile-loggers/asmile-001/'
S=pd.read_csv(B+'_sensors/sensors/sensors_20261113_145727.csv',usecols=['t_ms','imu_gx_dps','imu_gz_dps'],low_memory=False)
tt=S.t_ms.values/1000.; gx=S.imu_gx_dps.values; gz=S.imu_gz_dps.values
for sess in ['20261113_150337','20261113_151400']:
    fr=pd.read_csv(f'{B}session_{sess}/frames_left.csv')
    W,H=320,200
    cap=cv2.VideoCapture(f'{B}session_{sess}_left.h264')
    prev=None;dy=[];dx=[];n=0
    win=cv2.createHanningWindow((W,H//2),cv2.CV_32F)
    while True:
        ok,fr_=cap.read()
        if not ok:break
        im=cv2.resize(cv2.cvtColor(fr_,cv2.COLOR_BGR2GRAY),(W,H)).astype(np.float32)[:H//2]
        if prev is not None:
            (sx,sy),_=cv2.phaseCorrelate(prev,im,win); dx.append(sx);dy.append(sy)
        else: dx.append(0);dy.append(0)
        prev=im;n+=1
    m=min(n,len(fr)); t=fr.t_ms.values[:m]/1000.
    dy=np.array(dy[:m]);dx=np.array(dx[:m])
    # interp imu to frame times, average gx over the frame interval
    cg=np.cumsum(gx)*0.02; cz=np.cumsum(gz)*0.02
    Gx=np.interp(t,tt,cg);Gz=np.interp(t,tt,cz)
    ddg=np.r_[0,np.diff(Gx)]; ddz=np.r_[0,np.diff(Gz)]
    def corr(a,b,lag):
        if lag>0:a,b=a[lag:],b[:-lag]
        elif lag<0:a,b=a[:lag],b[-lag:]
        return np.corrcoef(a,b)[0,1]
    # remove slow trend / bias in both via 1s highpass
    hp=lambda x: x-pd.Series(x).rolling(15,center=True,min_periods=1).mean().values
    for nm,a,b in [('dy~gx',dy,ddg),('dx~gz',dx,ddz)]:
        a=hp(a);b=hp(b)
        print(sess,nm,{l:round(corr(a,b,l),2) for l in (-3,-2,-1,0,1,2,3)},'frames',n,len(fr))
    np.save(f'agents/prove/eventi_scettico_impuntata_20261113/dy_{sess}.npy',np.c_[t,dy,dx,ddg])
