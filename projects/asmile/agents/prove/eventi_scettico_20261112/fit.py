import pandas as pd, numpy as np
df=pd.read_csv('agents/prove/eventi_scettico_20261112/ev.csv')
S='asmile-loggers/asmile-001/_sensors/sensors/sensors_%s.csv'
g={}
for s in df.s.unique():
    d=pd.read_csv(S%s,low_memory=False,usecols=['t_ms','gps_speed_ms','imu_az_g','imu_ax_g','imu_ay_g']);g[s]=d
r=[]
for _,e in df.iterrows():
    d=g[e.s];w=d[(d.t_ms/1000>=e.t)&(d.t_ms/1000<=e.t+e.dur)]
    gp=w.gps_speed_ms.dropna()
    r.append((gp.mean()*3.6 if len(gp) else np.nan, w[['imu_ax_g','imu_ay_g','imu_az_g']].std().mean()))
df['gps_kmh']=[x[0] for x in r];df['imu_std']=[x[1] for x in r]
print(df[['s','t','v0','gps_kmh','imu_std']].round(2).to_string())
stop=df[df.v1<2]
print(len(stop),'stop tot')
pure=stop[(stop.bomax<1)&(stop.lim<0.2)]
con=stop[~stop.index.isin(pure.index)]
print('PURI',len(pure),'CONTAM',len(con))
def fit(x,lab):
    v=x.v0/3.6;b=np.polyfit(v,x.sp,1);res=x.sp-np.polyval(b,v)
    print(lab,'n',len(x),'sp=%.2f*v+%.2f'%tuple(b),'p75res %.2f'%np.percentile(res,75))
    return b,np.percentile(res,75)
for x,l in [(stop,'tutti'),(pure,'puri')]: 
    b,o=fit(x,l)
    for k in [3,5,8,10,12,15]:
        v=k/3.6;print('  ',k,'frena_entro=%.2f'%(np.polyval(b,v)+o+v*.5+.5),end=';')
    print()
print(pure[['t','v0','sp','am']].round(2).to_string())
print('max v0 puri',pure.v0.max(),'; decel mediane puri',pure.am.median())
# segnaposto
for k in [3,5,8,10,12,15]:
    v=k/3.6;print(k,'segn %.2f'%(v*.5+v*v/3+.5),end='; ')
