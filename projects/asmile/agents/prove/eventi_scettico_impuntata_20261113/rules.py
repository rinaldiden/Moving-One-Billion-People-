import numpy as np,pandas as pd
from scipy.signal import savgol_filter
B='asmile-loggers/asmile-001/_sensors/sensors/'
def load(name,C):
    d=pd.read_csv(B+f'sensors_{name}.csv',usecols=['t_ms','wall','imu_ay_g','imu_gx_dps','enc_wheel_cum','brake_out_deg'],low_memory=False)
    d=d.dropna(subset=['imu_gx_dps','enc_wheel_cum']).reset_index(drop=True)
    d['brake_out_deg']=pd.to_numeric(d.brake_out_deg,errors='coerce')
    t=(d.t_ms.values)/1000.
    cum=d.enc_wheel_cum.values.astype(float)*C/16384
    v=savgol_filter(cum,25,2,deriv=1,delta=.02); a=savgol_filter(cum,25,2,deriv=2,delta=.02)
    still=np.abs(pd.Series(v).rolling(100,center=True,min_periods=1).max().values)<0.05
    ay0=np.median(d.imu_ay_g.values[still]); gx0=np.median(d.imu_gx_dps.values[still])
    # causal: EMA tau .14s for decel, d03 over 15 samples
    ay=(d.imu_ay_g.values-ay0)*9.81
    al=0.25; dec=np.zeros(len(ay)); 
    for i in range(1,len(ay)): dec[i]=dec[i-1]+al*(ay[i]-dec[i-1])
    g=d.imu_gx_dps.values-gx0
    cs=np.cumsum(g)*.02; d03=np.r_[np.zeros(15),cs[15:]-cs[:-15]]
    return dict(d=d,t=t,v=v,a=a,dec=dec,d03=d03,g=g,ay0=ay0,gx0=gx0,cs=cs,ayraw=ay)
def episodes(mask,t,gap=1.0):
    idx=np.where(mask)[0]; out=[]
    for i in idx:
        if not out or t[i]-t[out[-1][1]]>gap: out.append([i,i])
        else: out[-1][1]=i
    return out
