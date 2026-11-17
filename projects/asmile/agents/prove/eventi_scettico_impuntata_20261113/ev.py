import numpy as np, pandas as pd, sys
C=0.3374
def load(p):
    d=pd.read_csv(p,usecols=['t_ms','imu_ax_g','imu_ay_g','imu_az_g','imu_gx_dps','imu_gy_dps','imu_gz_dps','enc_wheel_cum','wall'])
    d=d.dropna(subset=['imu_gx_dps']).reset_index(drop=True)
    t=(d.t_ms.values-d.t_ms.values[0])/1000.
    # resample uniform 50Hz
    return d,t
def feats(p,C=C):
    d,t=load(p)
    dt=0.02
    gx=d.imu_gx_dps.values; ay=d.imu_ay_g.values
    # speed from encoder cum (monotonic-ish), smooth 0.5 s
    cum=d.enc_wheel_cum.values.astype(float)
    # robust: incremental using windows of 0.5s
    n=len(d); v=np.zeros(n)
    k=25
    v[k:]=(cum[k:]-cum[:-k])*C/ (t[k:]-t[:-k])  # counts?? assume counts per rev unknown
    return d,t,v
