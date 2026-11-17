import pandas as pd, numpy as np, json
from scipy.signal import savgol_filter
S='asmile-loggers/asmile-001/_sensors/sensors/sensors_%s.csv'
circ=0.3477
out=[]
for s in ['20261108_160150','20261109_085334']:
    d=pd.read_csv(S%s,low_memory=False)
    print(s,len(d),'lim_zone',d.lim_zone.value_counts(dropna=False).to_dict())
    for c in ['brake_cmd_deg','brake_out_deg','brake_target_deg']:
        x=pd.to_numeric(d[c],errors='coerce');print(c,x.notna().sum(),x.max())
    d=d[d.enc_wheel_cum.notna()].reset_index(drop=True)
    # independent: dt from t_ms, resample 50Hz via diff
    t=d.t_ms.values/1000.;cum=d.enc_wheel_cum.values*circ/16384
    tt=np.arange(t[0],t[-1],0.02);cu=np.interp(tt,t,cum)
    v=savgol_filter(cu,25,2,deriv=1,delta=.02);a=savgol_filter(cu,75,2,deriv=2,delta=.02)
    ay=np.interp(tt,t,d.imu_ay_g.values*9.81)
    bo=np.interp(tt,t,pd.to_numeric(d.brake_out_deg,errors='coerce').fillna(0).values)
    bc=np.interp(tt,t,pd.to_numeric(d.brake_cmd_deg,errors='coerce').fillna(0).values)
    lz=d.lim_zone.fillna('').values; lzt=np.interp(tt,t,np.arange(len(t))).astype(int); lzz=lz[lzt]
    mov=np.abs(v)>0.3
    # decel events
    i=0;n=len(tt)
    ev=[]
    while i<n:
        if a[i]<-0.3:
            j=i
            while j<n-1 and a[j+1]<-0.1:j+=1
            k=i
            while k>0 and a[k-1]<-0.1:k-=1
            dur=tt[j]-tt[k]
            v0=v[k]*3.6;v1=v[j]*3.6
            if dur>=1 and v[k]-v[j]>=.5 and v[k]>.7:
                ev.append(dict(s=s,t=tt[k],v0=v0,v1=v1,dur=dur,am=(v[k]-v[j])/dur,sp=v[k:j+1].clip(0).sum()*.02,
                  bomax=bo[max(0,k-50):j+1].max(),bcmax=bc[max(0,k-50):j+1].max(),
                  lim=np.mean(np.isin(lzz[k:j+1],['OVER','RELEASE','HYST'])),ayimu=-ay[k:j+1].mean()))
            i=j+1
        else:i+=1
    out+=ev
df=pd.DataFrame(out);pd.set_option('display.width',250)
print(df.round(2).to_string())
df.to_csv('agents/prove/eventi_scettico_20261112/ev.csv',index=False)
